"""Montagem da página lida: blocos, leitura dupla, reconciliação e listas. Leitores falsos."""

import numpy as np

from app.models.document import (
    ILLEGIBLE,
    Alignment,
    BBox,
    BlockType,
    PageSize,
    ReadingSource,
    ResolvedBy,
    WordStatus,
)
from app.pipeline.base import PageInput
from app.pipeline.layout import LayoutBlock, PageLayout
from app.pipeline.preprocess import Preprocessed
from app.pipeline.reading import Gray, ReadWord
from app.pipeline.recognize import Readers, recognize_page

SIZE = PageSize(w_pt=595, h_pt=842)


class FakeReader:
    def __init__(
        self,
        source: ReadingSource,
        words: list[tuple[str, float, float, float]],
        snippet: str = "",
        vocab: str = "",
    ) -> None:
        self.source = source
        self.words = [ReadWord(t, BBox(x=x, y=y, w=60, h=20), c, source) for t, x, y, c in words]
        self.snippet = snippet
        self.snippet_shapes: list[tuple[int, ...]] = []
        self.vocab = vocab

    def read_block(self, image: Gray, origin: tuple[float, float]) -> list[ReadWord]:
        ox, oy = origin
        h, w = image.shape[:2]
        return [
            word for word in self.words if ox <= word.bbox.x < ox + w and oy <= word.bbox.y < oy + h
        ]

    def read_snippet(self, image: Gray) -> tuple[str, float]:
        self.snippet_shapes.append(image.shape)
        return self.snippet, 0.9


def preprocessed(blank: bool = False) -> Preprocessed:
    aligned = np.full((1000, 800, 3), 255, dtype=np.uint8)
    normalized = np.full((1000, 800), 255, dtype=np.uint8)
    return Preprocessed(aligned, normalized, blank, 0, 0.0, 1.0, False)


def block(
    kind: BlockType, order: int, x: float, y: float, w: float = 400, h: float = 60
) -> LayoutBlock:
    return LayoutBlock(
        type=kind,
        bbox=BBox(x=x, y=y, w=w, h=h),
        order=order,
        column=0,
        align=Alignment.JUSTIFY,
        rel_size=1.4,
        score=0.9,
        label="text",
    )


def page_input() -> PageInput:
    return PageInput(index=2, image=np.zeros((10, 10, 3), dtype=np.uint8), page_size=SIZE)


def readers(
    primary: list[tuple[str, float, float, float]],
    secondary: list[tuple[str, float, float, float]],
    snippet: str = "",
    vocab: str = "abcdefghijklmnopqrstuvwxyz",
) -> Readers:
    return Readers(
        primary=FakeReader(ReadingSource.PADDLE, primary, snippet),
        secondary=FakeReader(ReadingSource.DOCTR, secondary, snippet, vocab),
    )


def test_text_block_gets_reconciled_words_and_keeps_layout() -> None:
    layout = PageLayout([block(BlockType.HEADING, 0, 100, 100)], columns=1)
    result = recognize_page(
        preprocessed(),
        layout,
        page_input(),
        "p2-",
        readers([("contrato", 110, 110, 0.97)], [("contrato", 112, 111, 0.99)]),
    )
    page = result.page
    [heading] = page.blocks
    assert (page.index, page.width, page.height, page.page_size) == (2, 800, 1000, SIZE)
    assert page.image_ref == "pages/2.png"
    assert (heading.id, heading.type, heading.align, heading.rel_size) == (
        "p2-b0",
        BlockType.HEADING,
        Alignment.JUSTIFY,
        1.4,
    )
    assert [(w.id, w.text, w.status) for w in heading.words] == [
        ("p2-b0w0", "contrato", WordStatus.ACCEPTED)
    ]
    assert heading.confidence == 0.99


def test_figures_and_tables_keep_a_crop_of_the_original() -> None:
    layout = PageLayout(
        [block(BlockType.FIGURE, 0, 0, 0, 200, 100), block(BlockType.TABLE, 1, 0, 300, 400, 200)],
        columns=1,
    )
    result = recognize_page(preprocessed(), layout, page_input(), "p2-", readers([], []))

    assert [(b.type, b.image_ref) for b in result.page.blocks] == [
        (BlockType.FIGURE, "crops/p2-b0.png"),
        (BlockType.FIGURE, "crops/p2-b1.png"),
    ]
    assert result.crops["p2-b0"].shape == (100, 200, 3)
    assert result.crops["p2-b1"].shape == (200, 400, 3)


def test_text_block_nobody_could_read_becomes_illegible() -> None:
    layout = PageLayout([block(BlockType.PARAGRAPH, 0, 100, 100)], columns=1)
    result = recognize_page(preprocessed(), layout, page_input(), "p2-", readers([], []))

    [word] = result.page.blocks[0].words
    assert (word.text, word.status) == (ILLEGIBLE, WordStatus.UNCERTAIN)
    assert word.bbox == BBox(x=100, y=100, w=400, h=60)


def test_divergence_is_reread_enlarged() -> None:
    layout = PageLayout([block(BlockType.PARAGRAPH, 0, 100, 100)], columns=1)
    rs = readers([("Sllva", 110, 110, 0.85)], [("Silva", 110, 110, 0.86)], snippet="Silva")
    result = recognize_page(preprocessed(), layout, page_input(), "p2-", rs)

    [word] = result.page.blocks[0].words
    assert (word.text, word.resolved_by) == ("Silva", ResolvedBy.REREAD)
    assert isinstance(rs.primary, FakeReader)
    [shape] = rs.primary.snippet_shapes
    # Margem vertical folgada (acentos), lateral curta (não pegar a letra vizinha).
    assert shape[0] >= 2 * 20 * 1.4
    assert 2 * 60 <= shape[1] <= 2 * (60 + 2 * 20 * 0.1)


def test_characters_outside_doctr_vocabulary_are_blind() -> None:
    layout = PageLayout([block(BlockType.PARAGRAPH, 0, 100, 100)], columns=1)
    rs = readers([("1ª", 110, 110, 0.97)], [("13", 110, 110, 0.7)], vocab="0123456789")
    result = recognize_page(preprocessed(), layout, page_input(), "p2-", rs)

    [word] = result.page.blocks[0].words
    assert (word.text, word.status) == ("1ª", WordStatus.ACCEPTED)


def test_marked_paragraphs_become_a_list() -> None:
    layout = PageLayout(
        [block(BlockType.PARAGRAPH, 0, 100, 100), block(BlockType.PARAGRAPH, 1, 100, 200)],
        columns=1,
    )
    words = [
        ("a)", 110, 110, 0.97),
        ("um", 200, 110, 0.97),
        ("b)", 110, 210, 0.97),
        ("dois", 200, 210, 0.97),
    ]
    result = recognize_page(preprocessed(), layout, page_input(), "p2-", readers(words, words))

    [listing] = result.page.blocks
    assert listing.type is BlockType.LIST
    assert [w.text for w in listing.words] == ["a)", "um", "b)", "dois"]
    assert [i.word_start for i in listing.items] == [0, 2]


def test_blank_page_has_no_blocks() -> None:
    result = recognize_page(preprocessed(blank=True), None, page_input(), "p2-", readers([], []))

    assert result.page.blank
    assert result.page.blocks == []


def test_emphasis_is_measured_on_the_normalized_page(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.pipeline.recognize as recognize

    seen: list[tuple[list[str], tuple[int, ...]]] = []

    def fake_mark(blocks, image):  # type: ignore[no-untyped-def]
        seen.append(([b.id for b in blocks], image.shape))
        return [
            b.model_copy(update={"words": [w.model_copy(update={"bold": True}) for w in b.words]})
            for b in blocks
        ]

    monkeypatch.setattr(recognize, "mark_emphasis", fake_mark)
    layout = PageLayout([block(BlockType.PARAGRAPH, 0, 100, 100)], columns=1)
    rs = readers([("contrato", 110, 110, 0.97)], [("contrato", 110, 110, 0.97)])
    result = recognize_page(preprocessed(), layout, page_input(), "p2-", rs)

    assert seen == [(["p2-b0"], (1000, 800))]
    assert result.page.blocks[0].words[0].bold
