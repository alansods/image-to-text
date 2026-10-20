"""Montagem da página lida: blocos, leitura dupla, reconciliação e listas. Leitores falsos."""

import numpy as np

from app.models.document import (
    ILLEGIBLE,
    Alignment,
    BBox,
    BlockType,
    PageSize,
    QualityIssue,
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

    def read_block(
        self, image: Gray, origin: tuple[float, float], sensitive: bool = False
    ) -> list[ReadWord]:
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


def test_page_records_quality_issues() -> None:
    layout = PageLayout([block(BlockType.PARAGRAPH, 0, 100, 100)], columns=1)
    rs = readers([("Sllva", 110, 110, 0.80)], [("Silva", 110, 110, 0.82)])
    result = recognize_page(preprocessed(), layout, page_input(), "p2-", rs)

    assert QualityIssue.UNCERTAIN_READING in result.page.quality_issues


def test_blank_page_has_no_quality_issues() -> None:
    result = recognize_page(preprocessed(blank=True), None, page_input(), "p2-", readers([], []))

    assert result.page.quality_issues == []


class ShyPrimary(FakeReader):
    """Leitor principal que só enxerga o bloco no modo sensível (escaneamento difícil)."""

    def __init__(self, words: list[tuple[str, float, float, float]]) -> None:
        super().__init__(ReadingSource.PADDLE, words)
        self.calls: list[bool] = []

    def read_block(
        self, image: Gray, origin: tuple[float, float], sensitive: bool = False
    ) -> list[ReadWord]:
        self.calls.append(sensitive)
        return super().read_block(image, origin) if sensitive else []


def test_primary_rereads_the_block_sensitively_when_it_sees_much_less_than_the_secondary() -> None:
    words = [("Todos", 110, 110, 0.97), ("os", 200, 110, 0.97), ("encargos", 260, 110, 0.97)]
    primary = ShyPrimary(words)
    rs = Readers(primary=primary, secondary=FakeReader(ReadingSource.DOCTR, words, vocab="abc"))
    layout = PageLayout([block(BlockType.PARAGRAPH, 0, 100, 100)], columns=1)

    result = recognize_page(preprocessed(), layout, page_input(), "p2-", rs)

    assert primary.calls == [False, True]
    paragraph = result.page.blocks[0]
    assert [(w.text, w.status) for w in paragraph.words] == [
        ("Todos", WordStatus.ACCEPTED),
        ("os", WordStatus.ACCEPTED),
        ("encargos", WordStatus.ACCEPTED),
    ]


def test_text_inside_a_signature_image_is_not_repeated_and_touching_text_is_erased_from_it() -> (
    None
):
    # Assinatura (figura) sobre "EMPRESA EXEMPLO" (inteiro dentro) e encostando na data.
    aligned = np.zeros((1000, 800, 3), dtype=np.uint8)  # tinta em tudo: dá para ver o apagado
    normalized = np.full((1000, 800), 255, dtype=np.uint8)
    pre = Preprocessed(aligned, normalized, False, 0, 0.0, 1.0, False)
    layout = PageLayout(
        [
            block(BlockType.PARAGRAPH, 0, 50, 100, w=300, h=40),  # data: metade dentro
            block(BlockType.FIGURE, 1, 200, 110, w=400, h=300),  # assinatura
            block(BlockType.PARAGRAPH, 2, 300, 350, w=150, h=40),  # nome, todo dentro
        ],
        columns=1,
    )
    words = [("15", 60, 105, 0.97), ("março", 260, 105, 0.97), ("EMPRESA", 310, 355, 0.97)]
    result = recognize_page(pre, layout, page_input(), "p2-", readers(words, words))

    kinds = [(b.id, b.type) for b in result.page.blocks]
    assert ("p2-b2", BlockType.PARAGRAPH) not in kinds
    assert ("p2-b0", BlockType.PARAGRAPH) in kinds
    crop = result.crops["p2-b1"]
    assert (crop[0:30, 0:150] == 255).all()  # pedaço da data apagado da imagem
    assert (crop[100:200, 100:200] == 0).all()  # o resto da assinatura intacto
    assert (result.aligned == 0).all()  # a página original não é alterada


def test_orphan_region_does_not_reread_text_already_read(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Contorno do papel ligou tudo numa região órfã do tamanho da página.
    import app.pipeline.recognize as recognize

    monkeypatch.setattr(recognize, "orphan_regions", lambda *_: [BBox(x=0, y=0, w=800, h=1000)])
    monkeypatch.setattr(recognize, "stray_strokes", lambda *_: [])
    layout = PageLayout([block(BlockType.PARAGRAPH, 0, 100, 100)], columns=1)
    words = [("contrato", 110, 110, 0.97), ("nota", 110, 700, 0.97)]

    result = recognize_page(preprocessed(), layout, page_input(), "p2-", readers(words, words))

    texts = [w.text for b in result.page.blocks for w in b.words]
    assert texts.count("contrato") == 1
    assert "nota" in texts


def test_stray_stroke_becomes_a_figure_without_words(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.pipeline.recognize as recognize

    edge = BBox(x=780, y=50, w=6, h=900)
    monkeypatch.setattr(recognize, "orphan_regions", lambda *_: [])
    monkeypatch.setattr(recognize, "stray_strokes", lambda *_: [edge])
    layout = PageLayout([block(BlockType.PARAGRAPH, 0, 100, 100)], columns=1)
    words = [("contrato", 110, 110, 0.97), ("borda", 781, 100, 0.5)]

    result = recognize_page(preprocessed(), layout, page_input(), "p2-", readers(words, words))

    [figure] = [b for b in result.page.blocks if b.bbox == edge]
    assert figure.type is BlockType.FIGURE
    assert figure.words == []
    assert figure.id in result.crops
    assert "borda" not in [w.text for b in result.page.blocks for w in b.words]
