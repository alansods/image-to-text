"""Tamanho relativo dos blocos medido no documento inteiro (spec layout-detection, D16)."""

import pytest

from app.models.document import BBox, Block, BlockType, Document, Page, PageSize, Word, WordStatus
from app.pipeline.sizes import normalize_sizes

A4 = PageSize(w_pt=595, h_pt=842)


def block(block_id: str, order: int, word_height: float, rel: float, kind: BlockType) -> Block:
    words = [
        Word(
            id=f"{block_id}w{i}",
            text="palavra",
            bbox=BBox(x=100 + i * 200, y=100 * order, w=150, h=word_height),
            confidence=0.99,
            status=WordStatus.ACCEPTED,
        )
        for i in range(4)
    ]
    return Block(
        id=block_id, type=kind, bbox=BBox(x=100, y=100 * order, w=900, h=word_height),
        order=order, rel_size=rel, words=words, confidence=0.99,
    )  # fmt: skip


def test_cover_title_is_measured_against_the_body_of_the_whole_document() -> None:
    # Capa: só o título, que na página parecia "1,21" do texto da própria página.
    cover = Page(index=0, width=2480, height=3508, page_size=A4, image_ref="pages/0.png",
                 blocks=[block("t", 0, 110, 1.21, BlockType.HEADING)])  # fmt: skip
    paragraphs = [block(f"p{i}", i, 46, 1.0, BlockType.PARAGRAPH) for i in range(5)]
    body = Page(index=1, width=2480, height=3508, page_size=A4, image_ref="pages/1.png",
                blocks=paragraphs)  # fmt: skip
    document = Document(id="d", source_file="a.pdf", pages=[cover, body])

    result = normalize_sizes(document)

    assert result.pages[0].blocks[0].rel_size == 2.39
    assert {b.rel_size for b in result.pages[1].blocks} == {1.0}


def test_document_without_paragraphs_keeps_sizes() -> None:
    page = Page(index=0, width=2480, height=3508, page_size=A4, image_ref="pages/0.png",
                blocks=[block("t", 0, 110, 1.5, BlockType.HEADING)])  # fmt: skip
    document = Document(id="d", source_file="a.png", pages=[page])

    assert normalize_sizes(document).pages[0].blocks[0].rel_size == 1.5


def test_small_variations_around_the_body_are_the_body_size() -> None:
    # Altura de palavra varia ±10% entre parágrafos do mesmo corpo (acentos, maiúsculas).
    blocks = [
        block(f"p{i}", i, h, 1.0, BlockType.PARAGRAPH) for i, h in enumerate([46, 49, 51, 43, 46])
    ]
    page = Page(index=0, width=2480, height=3508, page_size=A4, image_ref="pages/0.png",
                blocks=blocks)  # fmt: skip
    result = normalize_sizes(Document(id="d", source_file="a.pdf", pages=[page]))

    assert {b.rel_size for b in result.pages[0].blocks} == {1.0}


# ------------------------------------------------------------------ tamanho em pontos (D18)

import io  # noqa: E402

import numpy as np  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
from reportlab.pdfbase.pdfmetrics import stringWidth  # noqa: E402
from reportlab.pdfgen.canvas import Canvas  # noqa: E402

from app.pipeline.sizes import estimate_font_pt  # noqa: E402

SCALE = 300 / 72


def rendered(text: str, font: str, size: float, underline: bool = False):  # type: ignore[no-untyped-def]
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(595, 60))
    canvas.setFont(font, size)
    canvas.drawString(20, 25, text)
    words = []
    x = 20.0
    for token in text.split():
        w = stringWidth(token, font, size)
        top = 60 - (25 + size * 0.95)
        words.append(
            Word(
                id=f"w{len(words)}", text=token,
                bbox=BBox(x=x * SCALE, y=top * SCALE, w=w * SCALE, h=size * 1.3 * SCALE),
                confidence=0.99, status=WordStatus.ACCEPTED,
            )
        )  # fmt: skip
        x += w + stringWidth(" ", font, size)
    if underline:
        canvas.setLineWidth(1)
        canvas.line(20, 22, x, 22)
    canvas.save()
    rgb = pdfium.PdfDocument(buffer.getvalue())[0].render(scale=SCALE).to_numpy()
    return np.ascontiguousarray(rgb[:, :, :3].mean(axis=2).astype(np.uint8)), words


def test_font_size_is_measured_in_points_whatever_the_letters() -> None:
    for text, font, size in [
        ("agência pagamento quaisquer", "Helvetica", 11),
        ("CLÁUSULA QUARTA OBRIGAÇÕES", "Helvetica-Bold", 11),
        ("o meu amor e o vosso", "Times-Roman", 11),
        ("RELATÓRIO ANUAL 2026", "Times-Bold", 16),
    ]:
        image, words = rendered(text, font, size)
        assert estimate_font_pt(words, image, 72 / 300) == pytest.approx(size, rel=0.12), text


def test_underline_does_not_inflate_the_size() -> None:
    image, words = rendered("CLÁUSULA TERCEIRA VIGÊNCIA", "Helvetica-Bold", 11, underline=True)
    assert estimate_font_pt(words, image, 72 / 300) == pytest.approx(11, rel=0.12)


def test_blocks_carry_their_size_in_points_snapped_to_the_body() -> None:
    def sized(block_id: str, order: int, pt: float, kind: BlockType) -> Block:
        b = block(block_id, order, 46, 1.0, kind)
        return b.model_copy(update={"font_pt": pt})

    blocks = [
        sized("t", 0, 16.2, BlockType.HEADING),
        sized("a", 1, 11.3, BlockType.PARAGRAPH),
        sized("b", 2, 11.9, BlockType.PARAGRAPH),
        sized("c", 3, 10.8, BlockType.PARAGRAPH),
    ]
    page = Page(
        index=0, width=2480, height=3508, page_size=A4, image_ref="pages/0.png", blocks=blocks
    )
    result = normalize_sizes(Document(id="d", source_file="a.pdf", pages=[page]))

    title, *body = result.pages[0].blocks
    assert {b.rel_size for b in body} == {1.0}
    assert {b.font_pt for b in body} == {11.3}
    assert title.rel_size == pytest.approx(16.2 / 11.3, abs=0.01)
    assert title.font_pt == 16.2


def test_implausibly_small_measure_is_discarded() -> None:
    image, words = rendered("5", "Helvetica", 11)
    tiny = [
        w.model_copy(update={"bbox": BBox(x=w.bbox.x, y=w.bbox.y, w=w.bbox.w, h=4)}) for w in words
    ]
    assert estimate_font_pt(tiny, image, 72 / 300) is None
