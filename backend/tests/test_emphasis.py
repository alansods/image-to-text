"""Negrito e itálico por palavra (spec text-recognition, design D8). Texto renderizado."""

import io

import numpy as np
import pypdfium2 as pdfium
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from app.models.document import ILLEGIBLE, BBox, Block, BlockType, Word, WordStatus
from app.pipeline.emphasis import mark_emphasis, slant, stroke_width
from app.pipeline.reading import Gray

SCALE = 400 / 72  # ~400 DPI: letra com ~32 px, como na página pré-processada
REGULAR, BOLD, ITALIC = "Times-Roman", "Times-Bold", "Times-Italic"

Line = list[tuple[str, str]]  # (palavra, fonte)


def render(lines: list[tuple[Line, float]]) -> tuple[Gray, list[list[BBox]]]:
    """Desenha linhas (palavras, tamanho em pt); devolve a imagem e a caixa de cada palavra."""
    width, height = 560.0, 40.0 + sum(size * 2.2 for _, size in lines)
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(width, height))
    boxes: list[list[BBox]] = []
    y = height - 20
    for words, size in lines:
        y -= size * 1.6
        x = 20.0
        line_boxes = []
        for text, font in words:
            canvas.setFont(font, size)
            canvas.drawString(x, y, text)
            w = stringWidth(text, font, size)
            top = height - (y + size * 0.95)
            line_boxes.append(BBox(x=x * SCALE, y=top * SCALE, w=w * SCALE, h=size * 1.25 * SCALE))
            x += w + stringWidth(" ", font, size)
        boxes.append(line_boxes)
    canvas.save()
    rgb = pdfium.PdfDocument(buffer.getvalue())[0].render(scale=SCALE).to_numpy()
    return np.ascontiguousarray(rgb.mean(axis=2).astype(np.uint8)), boxes


def crop(image: Gray, box: BBox) -> Gray:
    return image[int(box.y) : int(box.y + box.h), int(box.x) : int(box.x + box.w)]


def block(block_id: str, order: int, texts: list[str], boxes: list[BBox], rel: float) -> Block:
    words = [
        Word(id=f"{block_id}w{i}", text=t, bbox=b, confidence=0.99, status=WordStatus.ACCEPTED)
        for i, (t, b) in enumerate(zip(texts, boxes, strict=True))
    ]
    x1 = min(b.x for b in boxes)
    y1 = min(b.y for b in boxes)
    x2 = max(b.x + b.w for b in boxes)
    y2 = max(b.y + b.h for b in boxes)
    return Block(
        id=block_id,
        type=BlockType.PARAGRAPH,
        bbox=BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1),
        order=order,
        rel_size=rel,
        words=words,
        confidence=0.99,
    )


def styled(text: str, special: set[str], font: str) -> Line:
    return [(w, font if w in special else REGULAR) for w in text.split()]


BODY = "O contratante declara que leu e aceita todas as cláusulas deste contrato"


class TestMeasures:
    def test_bold_strokes_are_thicker(self) -> None:
        image, [[regular, bold]] = render([([("CONTRATANTE", REGULAR), ("CONTRATANTE", BOLD)], 11)])
        thin, thick = stroke_width(crop(image, regular)), stroke_width(crop(image, bold))
        assert thin is not None and thick is not None
        assert thick >= 1.35 * thin

    def test_italic_leans_right_and_regular_stands_up(self) -> None:
        image, [[regular, italic]] = render(
            [([("contratada", REGULAR), ("contratada", ITALIC)], 11)]
        )
        assert abs(slant(crop(image, regular))) < 4
        assert slant(crop(image, italic)) >= 8

    def test_blank_crop_has_no_stroke(self) -> None:
        assert stroke_width(np.full((30, 60), 255, dtype=np.uint8)) is None


def test_only_the_bold_word_is_marked_bold() -> None:
    line = styled(BODY, {"contratante"}, BOLD)
    image, [boxes] = render([(line, 11)])
    [result] = mark_emphasis([block("b0", 0, [w for w, _ in line], boxes, 1.0)], image)

    assert [w.text for w in result.words if w.bold] == ["contratante"]
    assert not any(w.italic for w in result.words)


def test_italic_phrase_is_marked_italic() -> None:
    text = "as partes concordam conforme dispõe a lei vigente sobre o tema"
    line = styled(text, {"conforme", "dispõe", "a", "lei", "vigente"}, ITALIC)
    image, [boxes] = render([(line, 11)])
    [result] = mark_emphasis([block("b0", 0, [w for w, _ in line], boxes, 1.0)], image)

    assert [w.text for w in result.words if w.italic] == [
        "conforme",
        "dispõe",
        "a",
        "lei",
        "vigente",
    ]
    assert not any(w.bold for w in result.words)


def test_large_titles_are_compared_by_their_size() -> None:
    bold_title = [(w, BOLD) for w in ["CONTRATO", "DE", "SERVIÇOS"]]
    plain_title = [(w, REGULAR) for w in ["Anexo", "Primeiro"]]
    body = styled(BODY, set(), BOLD)
    image, [b1, b2, b3] = render([(bold_title, 18), (plain_title, 18), (body, 11)])
    blocks = [
        block("t", 0, [w for w, _ in bold_title], b1, 18 / 11),
        block("s", 1, [w for w, _ in plain_title], b2, 18 / 11),
        block("p", 2, [w for w, _ in body], b3, 1.0),
    ]
    title, subtitle, paragraph = mark_emphasis(blocks, image)

    assert all(w.bold for w in title.words)
    assert not any(w.bold for w in subtitle.words)
    assert not any(w.bold for w in paragraph.words)


def test_illegible_words_are_left_plain() -> None:
    line = styled(BODY, set(), BOLD)
    image, [boxes] = render([(line, 11)])
    paragraph = block("b0", 0, [w for w, _ in line], boxes, 1.0)
    illegible = paragraph.words[0].model_copy(
        update={
            "text": ILLEGIBLE,
            "status": WordStatus.UNCERTAIN,
            "bbox": BBox(x=0, y=0, w=50, h=30),
        }
    )
    paragraph = paragraph.model_copy(update={"words": [illegible, *paragraph.words[1:]]})

    [result] = mark_emphasis([paragraph], image)
    assert not result.words[0].bold and not result.words[0].italic
