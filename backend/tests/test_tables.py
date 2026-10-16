"""Tabelas (spec table-extraction, design D15)."""

from functools import cache

import pytest

from app.models.document import BBox, Block, BlockType, PageSize, ReadingSource, WordStatus
from app.pipeline.base import PageInput
from app.pipeline.preprocess import load_pages
from app.pipeline.reading import ReadWord
from app.pipeline.runner import DocumentPipeline
from app.pipeline.tables import CellBox, assign_words, grid_from_boxes, trustworthy
from tests.fixtures.tables import borderless_table, merged_header_table
from tests.test_layout import FIXTURES

A4 = PageSize(w_pt=595, h_pt=842)


class TestGrid:
    def test_merged_cells_get_spans_from_the_aligned_edges(self) -> None:
        # Cabeçalho: "Mês" ocupa 2 linhas, "Período" 2 colunas (caixas como o detector devolve).
        boxes = [
            (8, 9, 467, 169),
            (467, 9, 1217, 89),
            (1218, 9, 1593, 169),
            (467, 89, 843, 170),
            (843, 89, 1218, 170),
            (8, 169, 468, 249),
            (467, 169, 843, 249),
            (843, 169, 1218, 249),
            (1217, 169, 1592, 249),
        ]

        cells = grid_from_boxes(boxes, (100, 200))

        assert [(c.row, c.col, c.row_span, c.col_span) for c in cells] == [
            (0, 0, 2, 1),
            (0, 1, 1, 2),
            (0, 3, 2, 1),
            (1, 1, 1, 1),
            (1, 2, 1, 1),
            (2, 0, 1, 1),
            (2, 1, 1, 1),
            (2, 2, 1, 1),
            (2, 3, 1, 1),
        ]
        assert cells[0].bbox == BBox(x=108, y=209, w=459, h=160)
        assert trustworthy(cells)


class TestTrust:
    def test_full_grid_is_trustworthy(self) -> None:
        cells = [
            CellBox(r, c, 1, 1, BBox(x=c * 10, y=r * 10, w=10, h=10))
            for r in range(2)
            for c in range(2)
        ]
        assert trustworthy(cells)

    def test_holes_overlaps_and_single_cells_are_not(self) -> None:
        full = [
            CellBox(r, c, 1, 1, BBox(x=c * 10, y=r * 10, w=10, h=10))
            for r in range(2)
            for c in range(2)
        ]
        assert not trustworthy(full[:3])  # buraco
        assert not trustworthy(
            [*full, CellBox(0, 0, 1, 2, BBox(x=0, y=0, w=20, h=10))]
        )  # sobreposta
        assert not trustworthy([CellBox(0, 0, 1, 1, BBox(x=0, y=0, w=10, h=10))])  # 1 célula


def word(text: str, x: float, y: float) -> ReadWord:
    return ReadWord(text, BBox(x=x, y=y, w=8, h=8), 0.97, ReadingSource.PADDLE)


def test_words_go_to_the_cell_that_contains_their_center() -> None:
    cells = [CellBox(0, c, 1, 1, BBox(x=c * 100, y=0, w=100, h=20)) for c in range(2)]
    from app.pipeline.reconcile import reconcile_block

    words = reconcile_block(
        [word("Caneta", 5, 5), word("azul", 40, 5), word("12", 150, 5)],
        [word("Caneta", 5, 5), word("azul", 40, 5), word("12", 150, 5)],
        frozenset(),
        "t",
    )
    assigned = assign_words(cells, words)

    assert assigned is not None
    assert [[w.text for w in c.words] for c in assigned] == [["Caneta", "azul"], ["12"]]


def test_word_outside_every_cell_makes_the_table_untrustworthy() -> None:
    cells = [CellBox(0, 0, 1, 1, BBox(x=0, y=0, w=100, h=20))]
    from app.pipeline.reconcile import reconcile_block

    words = reconcile_block([word("solta", 300, 300)], [word("solta", 300, 300)], frozenset(), "t")
    assert assign_words(cells, words) is None


# ------------------------------------------------------------------ com os modelos de verdade


@cache
def pipeline() -> DocumentPipeline:
    return DocumentPipeline()


def tables_of(page: PageInput) -> list[Block]:
    result = pipeline().process_page(page, "p0-", lambda _f: None)
    return [b for b in result.page.blocks if b.type is BlockType.TABLE]


def text_of(block: Block, row: int, col: int) -> str:
    [cell] = [c for c in block.cells if (c.row, c.col) == (row, col)]
    return " ".join(w.text for w in cell.words)


def test_receipt_table_with_merged_total() -> None:
    page = load_pages(FIXTURES / "recibo_tabela" / "input.pdf")[0]
    [table] = tables_of(page)

    assert len(table.cells) == 18
    assert text_of(table, 0, 1) == "Descrição"
    assert text_of(table, 3, 1) == "Mídia de entrega"
    [total] = [c for c in table.cells if c.row == 4 and c.col == 0]
    assert (total.col_span, " ".join(w.text for w in total.words)) == (3, "Total")
    assert text_of(table, 4, 3) == "1.234,56"
    assert all(w.status is not WordStatus.UNCERTAIN for c in table.cells for w in c.words)


def test_merged_header_and_empty_cell() -> None:
    [table] = tables_of(PageInput(0, merged_header_table(), A4))

    spans = {(c.row, c.col): (c.row_span, c.col_span) for c in table.cells}
    assert spans[(0, 0)] == (2, 1)  # "Mês"
    assert spans[(0, 1)] == (1, 2)  # "Período"
    assert spans[(0, 3)] == (2, 1)  # "Saldo"
    assert text_of(table, 1, 2) == "Saídas"
    assert text_of(table, 4, 2) == ""  # Março sem saídas: célula vazia, nada se desloca
    assert text_of(table, 4, 3) == "1.500,00"


def test_borderless_table_by_alignment() -> None:
    [table] = tables_of(PageInput(0, borderless_table(), A4))

    assert len(table.cells) == 12
    assert text_of(table, 1, 0) == "Caneta azul"
    assert text_of(table, 3, 2) == "32,00"


def test_unstructurable_table_stays_as_image(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.pipeline.recognize as recognize

    monkeypatch.setattr(recognize, "table_structure", lambda image, origin: [])
    result = pipeline().process_page(
        load_pages(FIXTURES / "recibo_tabela" / "input.pdf")[0], "p0-", lambda _f: None
    )

    assert not [b for b in result.page.blocks if b.type is BlockType.TABLE]
    assert sum(b.type is BlockType.FIGURE for b in result.page.blocks) == 2  # tabela + carimbo
