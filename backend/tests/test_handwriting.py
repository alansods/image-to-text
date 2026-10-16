"""Assinatura, rubrica e preenchimento à mão viram imagem (spec layout-detection)."""

import io

import numpy as np
import pypdfium2 as pdfium
from reportlab.pdfgen.canvas import Canvas

from app.models.document import Alignment, BBox, BlockType, ReadingSource, WordStatus
from app.pipeline.layout import LayoutBlock, PageLayout
from app.pipeline.preprocess import Preprocessed
from app.pipeline.reading import Gray, ReadWord
from app.pipeline.recognize import Readers, recognize_page
from tests.fixtures.precision.generator.drawings import signature
from tests.fixtures.precision.generator.layout import register_fonts
from tests.test_recognize import FakeReader, page_input

SCALE = 300 / 72
FULL_VOCAB = "".join(chr(i) for i in range(32, 0x250))
PAGE = (595, 300)


def render(draw) -> Gray:  # type: ignore[no-untyped-def]
    register_fonts()
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=PAGE)
    draw(canvas)
    canvas.save()
    rgb = pdfium.PdfDocument(buffer.getvalue())[0].render(scale=SCALE).to_numpy()
    return np.ascontiguousarray(rgb[:, :, :3].mean(axis=2).astype(np.uint8))


def region(x: float, y_top: float, w: float, h: float) -> BBox:
    return BBox(x=x * SCALE, y=y_top * SCALE, w=w * SCALE, h=h * SCALE)


class Garbled(FakeReader):
    """Leitor que, como na vida real, devolve lixo em cima de traço cursivo."""

    def __init__(self, source: ReadingSource, box: BBox, texts: list[str], vocab: str = "") -> None:
        super().__init__(source, [], "", vocab)
        step = box.w / len(texts)
        self.words = [
            ReadWord(t, BBox(x=box.x + i * step, y=box.y, w=step * 0.8, h=box.h * 0.6), 0.6, source)
            for i, t in enumerate(texts)
        ]

    def read_block(self, image, origin, sensitive=False):  # type: ignore[no-untyped-def]
        return list(self.words)


def recognize(image: Gray, box: BBox, first: list[str], second: list[str]):  # type: ignore[no-untyped-def]
    readers = Readers(
        primary=Garbled(ReadingSource.PADDLE, box, first),
        secondary=Garbled(ReadingSource.DOCTR, box, second, vocab=FULL_VOCAB),
    )
    layout = PageLayout(
        [
            LayoutBlock(
                type=BlockType.PARAGRAPH, bbox=box, order=0, column=0, align=Alignment.LEFT,
                rel_size=1.0, score=0.7, label="text",
            )
        ],
        columns=1,
    )  # fmt: skip
    rgb = np.ascontiguousarray(np.stack([image] * 3, axis=2))
    return recognize_page(
        Preprocessed(rgb, image, False, 0, 0.0, 1.0, False), layout, page_input(), "p0-", readers
    )


def test_signature_marked_as_text_becomes_an_image_without_doubts() -> None:
    image = render(lambda c: signature(c, 200, 120, 200, 70))
    box = region(190, 100, 220, 90)

    result = recognize(image, box, ["Ir!", "M", "/"], ["%&'(", "lv"])

    [block] = result.page.blocks
    assert block.type is BlockType.FIGURE
    assert block.words == []
    assert result.crops[block.id].size > 0


def test_handwritten_fill_in_becomes_an_image() -> None:
    def draw(c: Canvas) -> None:
        c.setFont("Helvetica", 11)  # o resto da página é impresso, como num formulário
        for i in range(6):
            c.drawString(
                40, 120 - i * 16, "Texto impresso do documento com letras de tamanho normal."
            )
        c.setFont("Caveat", 24)
        c.drawString(60, 200, "Mariana P. Lopes")
        c.drawString(60, 170, "000.123.456-78")

    image = render(draw)
    box = region(50, 80, 300, 70)

    result = recognize(
        image, box, ["Marlana", "P.L.", "Lopcs", "000-23.456-78"], ["lorohna", "£", "Q", "|"]
    )

    [filled] = [b for b in result.page.blocks if b.bbox == box]
    assert filled.type is BlockType.FIGURE
    assert filled.words == []


def test_printed_paragraph_full_of_doubts_stays_text() -> None:
    lines = [
        "Este parágrafo de exemplo foi impresso para testar a leitura de um texto",
        "comum, com palavras de tamanho normal e frases longas que ocupam quase",
        "toda a largura da linha, como em qualquer documento digitado e escaneado",
    ]

    def draw(c: Canvas) -> None:
        c.setFont("Helvetica", 11)
        for i, line in enumerate(lines):
            c.drawString(40, 250 - i * 16, line)

    image = render(draw)
    box = region(36, 38, 480, 52)
    words = " ".join(lines).split()

    result = recognize(image, box, words, [w + "x" for w in words])  # discordam em tudo

    [block] = result.page.blocks
    assert block.type is BlockType.PARAGRAPH
    assert sum(w.status is WordStatus.UNCERTAIN for w in block.words) > len(block.words) / 2
