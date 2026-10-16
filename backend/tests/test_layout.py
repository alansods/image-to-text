"""Detecção de layout (spec layout-detection): tipos, ordem de leitura, colunas, alinhamento,
tamanho relativo, elementos não-texto e listas."""

from functools import cache
from pathlib import Path

import numpy as np
import pytest

from app.models.document import (
    Alignment,
    BBox,
    Block,
    BlockType,
    Word,
    WordStatus,
)
from app.pipeline.layout import (
    Candidate,
    PageLayout,
    analyze_layout,
    group_lists,
    map_label,
    merge_passes,
    reading_order,
)
from app.pipeline.preprocess import load_pages, preprocess
from tests.precision.truth import Truth

FIXTURES = Path(__file__).parent / "fixtures" / "precision"


def box(x: float, y: float, w: float, h: float) -> BBox:
    return BBox(x=x, y=y, w=w, h=h)


def cand(
    x: float, y: float, w: float, h: float, label: str = "text", score: float = 0.9
) -> Candidate:
    return Candidate(label=label, score=score, bbox=box(x, y, w, h))


# ------------------------------------------------------------------ geometria pura


class TestLabels:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("doc_title", BlockType.HEADING),
            ("paragraph_title", BlockType.HEADING),
            ("text", BlockType.PARAGRAPH),
            ("figure_title", BlockType.PARAGRAPH),
            ("abstract", BlockType.PARAGRAPH),
            ("table", BlockType.TABLE),
            ("image", BlockType.FIGURE),
            ("chart", BlockType.FIGURE),
            ("seal", BlockType.FIGURE),
            ("formula", BlockType.FORMULA),
            ("header", BlockType.HEADER),
            ("footer", BlockType.FOOTER),
            ("number", BlockType.FOOTER),
        ],
    )
    def test_model_labels_map_to_spec_types(self, label: str, expected: BlockType) -> None:
        assert map_label(label) is expected


class TestTwoPasses:
    def test_keeps_confident_boxes_and_fills_gaps_with_weaker_ones(self) -> None:
        strong = [cand(0, 0, 100, 50, "header", 0.77), cand(0, 100, 500, 300, "image", 0.98)]
        weak = [
            cand(0, 0, 60, 50, "header", 0.44),  # duplicata do cabeçalho: descartada
            cand(50, 500, 400, 40, "doc_title", 0.37),  # área vazia: aproveitada
            cand(80, 560, 300, 30, "text", 0.46),  # área vazia: aproveitada
            cand(50, 500, 400, 90, "text", 0.36),  # cobre as duas anteriores: descartada
        ]

        merged = merge_passes(strong + weak)

        assert sorted((c.label, c.score) for c in merged) == [
            ("doc_title", 0.37),
            ("header", 0.77),
            ("image", 0.98),
            ("text", 0.46),
        ]


class TestReadingOrder:
    def test_single_column_top_to_bottom(self) -> None:
        blocks = [cand(100, 300, 800, 50), cand(100, 100, 800, 50), cand(100, 200, 300, 50)]

        ordered, columns = reading_order(blocks)

        assert [c.bbox.y for c, _ in ordered] == [100, 200, 300]
        assert columns == 1

    def test_two_columns_left_column_first_even_with_aligned_gaps(self) -> None:
        title = cand(100, 50, 1000, 40)
        left = [cand(100, 120, 480, 200), cand(100, 350, 480, 200), cand(100, 600, 480, 100)]
        right = [cand(620, 120, 480, 150), cand(620, 290, 480, 260), cand(620, 600, 480, 120)]

        ordered, columns = reading_order([*right, title, *left])

        assert [c for c, _ in ordered] == [title, *left, *right]
        assert [col for _, col in ordered] == [0, 0, 0, 0, 1, 1, 1]
        assert columns == 2

    def test_header_first_and_footer_last(self) -> None:
        footer = cand(500, 1000, 30, 20, "number")
        header = cand(700, 10, 300, 20, "header")
        body = cand(100, 100, 800, 300)

        ordered, _ = reading_order([footer, body, header])

        assert [c for c, _ in ordered] == [header, body, footer]

    def test_side_by_side_signatures_are_not_page_columns(self) -> None:
        text = cand(100, 100, 1000, 300)
        signatures = [cand(150, 500, 300, 60, "image"), cand(700, 500, 300, 60, "image")]

        _, columns = reading_order([text, *signatures])

        assert columns == 1


def word(word_id: str, text: str, x: float = 0) -> Word:
    return Word(
        id=word_id, text=text, bbox=box(x, 0, 10, 10), confidence=0.9, status=WordStatus.ACCEPTED
    )


def paragraph(block_id: str, order: int, texts: list[str], x: float = 100) -> Block:
    return Block(
        id=block_id,
        type=BlockType.PARAGRAPH,
        bbox=box(x, order * 50, 400, 40),
        order=order,
        words=[word(f"{block_id}w{i}", t, x) for i, t in enumerate(texts)],
        confidence=0.9,
    )


class TestLists:
    def test_consecutive_marked_paragraphs_become_one_list_with_levels(self) -> None:
        blocks = [
            paragraph("p0", 0, ["As", "entregas:"]),
            paragraph("p1", 1, ["1.", "catálogo"]),
            paragraph("p2", 2, ["a)", "atas"], x=140),
            paragraph("p3", 3, ["b)", "mapas"], x=140),
            paragraph("p4", 4, ["2.", "oficina"]),
            paragraph("p5", 5, ["Fim."]),
        ]

        result = group_lists(blocks)

        assert [b.type for b in result] == [
            BlockType.PARAGRAPH,
            BlockType.LIST,
            BlockType.PARAGRAPH,
        ]
        lst = result[1]
        assert [w.text for w in lst.words] == [
            "1.",
            "catálogo",
            "a)",
            "atas",
            "b)",
            "mapas",
            "2.",
            "oficina",
        ]
        assert [(i.word_start, i.level) for i in lst.items] == [(0, 0), (2, 1), (4, 1), (6, 0)]
        assert [b.order for b in result] == [0, 1, 2]

    @pytest.mark.parametrize("marker", ["a)", "(b)", "1.", "10)", "•", "-", "–", "iv)"])  # noqa: RUF001
    def test_recognizes_common_markers(self, marker: str) -> None:
        blocks = [paragraph("p1", 0, [marker, "um"]), paragraph("p2", 1, [marker, "dois"])]

        assert group_lists(blocks)[0].type is BlockType.LIST

    def test_single_marked_paragraph_is_not_a_list(self) -> None:
        blocks = [paragraph("p1", 0, ["1.", "Introdução"]), paragraph("p2", 1, ["Texto."])]

        assert [b.type for b in group_lists(blocks)] == [BlockType.PARAGRAPH] * 2


# ------------------------------------------------------------------ integração com o modelo


@cache
def layout_of(case: str, page_index: int = 0) -> PageLayout:
    page = load_pages(next((FIXTURES / case).glob("input.*")))[page_index]
    pre = preprocess(page)
    return analyze_layout(pre.aligned, pre.normalized)


def truth(case: str) -> Truth:
    return Truth.model_validate_json((FIXTURES / case / "expected.json").read_text())


def texts_by_y(layout: PageLayout) -> list[BlockType]:
    return [b.type for b in sorted(layout.blocks, key=lambda b: b.bbox.y)]


class TestContract:
    def test_title_is_centered_and_larger(self) -> None:
        first = layout_of("contrato_impresso").blocks[0]

        assert first.type is BlockType.HEADING
        assert first.align is Alignment.CENTER
        assert first.rel_size > 1.2

    def test_paragraphs_are_justified_and_place_line_centered(self) -> None:
        blocks = layout_of("contrato_impresso").blocks
        paragraphs = [b for b in blocks if b.type is BlockType.PARAGRAPH]

        assert paragraphs[0].align is Alignment.JUSTIFY  # "Pelo presente instrumento..."
        place = next(b for b in paragraphs if b.bbox.w < 800 and b.bbox.y > 1700)
        assert place.align is Alignment.CENTER  # "São Paulo, 15 de outubro de 2026."

    def test_signature_is_a_figure(self) -> None:
        figures = [b for b in layout_of("contrato_impresso").blocks if b.type is BlockType.FIGURE]

        assert len(figures) == 1
        assert 1900 < figures[0].bbox.y < 2100  # a rubrica, entre a data e "CONTRATANTE"

    def test_reading_order_follows_the_page(self) -> None:
        blocks = layout_of("contrato_impresso").blocks

        assert [b.bbox.y for b in blocks] == sorted(b.bbox.y for b in blocks)
        assert [b.order for b in blocks] == list(range(len(blocks)))


class TestTwoColumnArticle:
    def test_has_two_columns_and_reads_left_column_first(self) -> None:
        layout = layout_of("artigo_duas_colunas")
        body = [b for b in layout.blocks if b.bbox.y > 470]

        assert layout.columns == 2
        columns = [b.column for b in body]
        assert columns == sorted(columns)
        assert set(columns) == {0, 1}

    def test_caption_comes_right_after_the_chart(self) -> None:
        blocks = layout_of("artigo_duas_colunas").blocks
        index = next(i for i, b in enumerate(blocks) if b.type is BlockType.FIGURE)

        caption = blocks[index + 1]
        assert caption.type is BlockType.PARAGRAPH
        assert caption.bbox.y > blocks[index].bbox.y


class TestOtherDocuments:
    def test_receipt_has_table_and_stamp(self) -> None:
        types = [b.type for b in layout_of("recibo_tabela").blocks]

        assert types.count(BlockType.TABLE) == 1
        assert types.count(BlockType.FIGURE) == 1

    def test_cover_keeps_logo_illustration_title_and_subtitle(self) -> None:
        blocks = layout_of("relatorio_tres_paginas", 0).blocks
        figures = [b for b in blocks if b.type is BlockType.FIGURE]
        texts = [b for b in blocks if b.type is not BlockType.FIGURE]

        assert len(figures) == 2  # logotipo e ilustração
        assert len(texts) >= 2  # título e subtítulo recuperados
        assert all(b.align is Alignment.CENTER for b in texts)

    def test_header_first_and_page_number_last(self) -> None:
        blocks = layout_of("relatorio_tres_paginas", 1).blocks

        assert blocks[0].type is BlockType.HEADER
        assert blocks[0].align is Alignment.RIGHT
        assert blocks[-1].type is BlockType.FOOTER

    @pytest.mark.parametrize(
        "case",
        [
            "contrato_impresso",
            "contrato_foto",
            "recibo_tabela",
            "artigo_duas_colunas",
            "relatorio_tres_paginas",
            "print_tela",
            "cabeca_para_baixo",
            "enfase_mista",
            "manuscrito",
        ],
    )
    def test_figure_count_matches_truth_on_every_non_blank_page(self, case: str) -> None:
        expected = truth(case)
        for page in expected.pages:
            if page.blank:
                continue
            found = [b for b in layout_of(case, page.index).blocks if b.type is BlockType.FIGURE]
            assert len(found) == expected.figure_counts()[page.index], (case, page.index)


def test_layout_coordinates_match_the_page_image() -> None:
    layout = layout_of("recibo_tabela")
    page = preprocess(load_pages(FIXTURES / "recibo_tabela" / "input.pdf")[0])

    h, w = page.normalized.shape
    assert all(b.bbox.x >= 0 and b.bbox.x + b.bbox.w <= w + 1 for b in layout.blocks)
    assert all(b.bbox.y >= 0 and b.bbox.y + b.bbox.h <= h + 1 for b in layout.blocks)
    assert isinstance(np.asarray(page.aligned), np.ndarray)
