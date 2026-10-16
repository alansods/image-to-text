"""Os dois leitores (spec text-recognition, design D6). Usa os modelos de verdade."""

import io
from functools import cache

import numpy as np
import pypdfium2 as pdfium
import pytest
from reportlab.pdfgen.canvas import Canvas

from app.models.document import BBox, ReadingSource
from app.pipeline.ocr_doctr import CONFIDENCE_SCALE, DoctrReader
from app.pipeline.ocr_paddle import PaddleReader, split_words
from app.pipeline.reading import Gray, Reader

PHRASE = "Ação de cobrança nº 123 — R$ 1.500,00"


@cache
def rendered_line() -> Gray:
    """Uma linha impressa em Times 14 pt, renderizada a 300 DPI, com margem branca."""
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(400, 40))
    canvas.setFont("Times-Roman", 14)
    canvas.drawString(20, 15, PHRASE)
    canvas.save()
    page = pdfium.PdfDocument(buffer.getvalue())[0]
    rgb = page.render(scale=300 / 72).to_numpy()
    return np.ascontiguousarray(rgb.mean(axis=2).astype(np.uint8))


def rendered_small(text: str = "Página 1") -> Gray:
    """Um bloco pequeno de uma linha (Helvetica 12 pt a 300 DPI), como um rodapé."""
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(52, 17))
    canvas.setFont("Helvetica", 12)
    canvas.drawString(2, 4, text)
    canvas.save()
    rgb = pdfium.PdfDocument(buffer.getvalue())[0].render(scale=300 / 72).to_numpy()
    return np.ascontiguousarray(rgb.mean(axis=2).astype(np.uint8))


@cache
def paddle_reader() -> PaddleReader:
    return PaddleReader()


@cache
def doctr_reader() -> DoctrReader:
    return DoctrReader()


class TestSplitWords:
    def test_word_boxes_come_from_the_character_regions(self) -> None:
        tokens = ["A", "çã", "o", " ", "de"]
        regions = [
            ((10, 5), (20, 5), (20, 30), (10, 30)),
            ((20, 5), (40, 5), (40, 30), (20, 30)),
            ((40, 5), (50, 5), (50, 30), (40, 30)),
            ((50, 5), (60, 5), (60, 30), (50, 30)),
            ((60, 5), (80, 5), (80, 30), (60, 30)),
        ]
        words = split_words("Ação de", 0.9, tokens, regions, (10, 0, 80, 30), (100, 200))

        assert [(w.text, w.bbox) for w in words] == [
            ("Ação", BBox(x=110, y=205, w=40, h=25)),
            ("de", BBox(x=160, y=205, w=20, h=25)),
        ]
        assert {w.confidence for w in words} == {0.9}
        assert {w.source for w in words} == {ReadingSource.PADDLE}

    def test_fragment_spanning_two_words_is_split_by_character(self) -> None:
        # O PaddleOCR agrupa acentuadas vizinhas: "pagará à" vira os fragmentos "pagar" e "á à".
        tokens = ["pagar", "á à"]
        regions = [((0, 0), (50, 0), (50, 10), (0, 10)), ((50, 0), (80, 0), (80, 10), (50, 10))]
        words = split_words("pagará à", 0.9, tokens, regions, (0, 0, 80, 10), (0, 0))

        assert [(w.text, w.bbox.x, w.bbox.x + w.bbox.w) for w in words] == [
            ("pagará", 0, 60),
            ("à", 70, 80),
        ]

    def test_falls_back_to_splitting_the_line_by_characters(self) -> None:
        words = split_words(
            "ab cd", 0.8, ["?"], [((0, 0), (1, 0), (1, 1), (0, 1))], (0, 0, 50, 10), (0, 0)
        )

        assert [(w.text, w.bbox.x, w.bbox.w) for w in words] == [("ab", 0, 20), ("cd", 30, 20)]


@pytest.mark.parametrize("make_reader", [paddle_reader, doctr_reader], ids=["paddle", "doctr"])
def test_reads_accented_portuguese_with_boxes_on_the_page(make_reader) -> None:  # type: ignore[no-untyped-def]
    reader: Reader = make_reader()
    image = rendered_line()
    words = reader.read_block(image, (1000, 2000))
    texts = [w.text for w in words]

    for expected in ["Ação", "cobrança", "123", "R$", "1.500,00"]:
        assert expected in texts
    assert all(0 <= w.confidence <= 1 for w in words)
    assert all(w.source is reader.source for w in words)
    lefts = [w.bbox.x for w in words]
    assert lefts == sorted(lefts)
    first = words[0].bbox
    assert 1000 <= first.x < 1000 + image.shape[1] / 4
    assert 2000 <= first.y < 2000 + image.shape[0]


@pytest.mark.parametrize("make_reader", [paddle_reader, doctr_reader], ids=["paddle", "doctr"])
def test_reads_small_single_line_blocks(make_reader) -> None:  # type: ignore[no-untyped-def]
    reader: Reader = make_reader()
    image = rendered_small()
    words = reader.read_block(image, (300, 400))

    assert [w.text for w in words] == ["Página", "1"]
    for w in words:
        assert w.bbox.x >= 300 and w.bbox.x + w.bbox.w <= 300 + image.shape[1] + 1
        assert w.bbox.y >= 400 and w.bbox.y + w.bbox.h <= 400 + image.shape[0] + 1


@pytest.mark.parametrize("make_reader", [paddle_reader, doctr_reader], ids=["paddle", "doctr"])
def test_snippet_reading_without_detection(make_reader) -> None:  # type: ignore[no-untyped-def]
    reader: Reader = make_reader()
    [word] = [w for w in reader.read_block(rendered_line(), (0, 0)) if w.text == "cobrança"]
    b = word.bbox
    crop = rendered_line()[int(b.y) - 4 : int(b.y + b.h) + 4, int(b.x) - 4 : int(b.x + b.w) + 4]

    text, confidence = reader.read_snippet(crop)

    assert text == "cobrança"
    assert 0.5 < confidence <= 1


def test_doctr_confidence_is_calibrated_below_paddle() -> None:
    # Medido no conjunto sintético: o docTR dá 1,0 até a leituras erradas (D7).
    words = doctr_reader().read_block(rendered_line(), (0, 0))
    assert max(w.confidence for w in words) <= CONFIDENCE_SCALE
    assert doctr_reader().read_snippet(rendered_small())[1] <= CONFIDENCE_SCALE


def test_doctr_exposes_its_vocabulary() -> None:
    vocab = doctr_reader().vocab
    assert "ã" in vocab
    assert "ª" not in vocab
