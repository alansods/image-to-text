"""Checagem de completude (spec completeness-check, design D9)."""

import numpy as np

from app.models.document import ILLEGIBLE, Alignment, BBox, BlockType, ReadingSource, WordStatus
from app.pipeline.completeness import missing_lines, orphan_regions
from app.pipeline.layout import LayoutBlock, PageLayout
from app.pipeline.preprocess import Preprocessed
from app.pipeline.recognize import Readers, recognize_page
from tests.test_emphasis import REGULAR, render
from tests.test_recognize import FakeReader, page_input

LINES = [
    ("Primeira linha do parágrafo principal", 11),
    ("segunda linha que o leitor pulou aqui", 11),
    ("terceira linha que fecha o parágrafo", 11),
    ("Nota: valores sujeitos a reajuste anual.", 9),
]


def page() -> tuple[np.ndarray, list[list[BBox]]]:
    return render([([(w, REGULAR) for w in text.split()], size) for text, size in LINES])


def union(boxes: list[BBox]) -> BBox:
    x1, y1 = min(b.x for b in boxes), min(b.y for b in boxes)
    x2, y2 = max(b.x + b.w for b in boxes), max(b.y + b.h for b in boxes)
    return BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1)


def contains(outer: BBox, inner: BBox, slack: float = 6) -> bool:
    return (
        outer.x - slack <= inner.x
        and outer.y - slack <= inner.y
        and inner.x + inner.w <= outer.x + outer.w + slack
        and inner.y + inner.h <= outer.y + outer.h + slack
    )


class TestOrphans:
    def test_text_outside_every_block_is_found(self) -> None:
        image, boxes = page()
        paragraph = union([b for line in boxes[:3] for b in line])

        [orphan] = orphan_regions(image, [paragraph], 30)

        assert contains(union(boxes[3]), orphan)

    def test_specks_smaller_than_a_letter_are_ignored(self) -> None:
        image, boxes = page()
        everything = union([b for line in boxes for b in line])
        image = image.copy()
        image[20:22, 20:22] = 0  # poeira
        image[40:43, 2000:2003] = 0
        image[60:72, 1500:1505] = 0  # risco fino do scanner (5 por 12 px), menor que uma letra

        assert orphan_regions(image, [everything], 30) == []


class TestMissingLines:
    def test_visible_line_without_words_is_reported(self) -> None:
        image, boxes = page()
        paragraph = union([b for line in boxes[:3] for b in line])
        read = [b for line in (boxes[0], boxes[2]) for b in line]

        [line] = missing_lines(image, paragraph, read, 30)

        assert contains(union(boxes[1]), line)

    def test_complete_block_has_no_missing_lines(self) -> None:
        image, boxes = page()
        paragraph = union([b for line in boxes[:3] for b in line])

        assert missing_lines(image, paragraph, [b for line in boxes[:3] for b in line], 30) == []


# ------------------------------------------------------------------ na montagem da página


def words_of(boxes: list[list[BBox]], lines: list[int]) -> list[tuple[str, float, float, float]]:
    texts = [text.split() for text, _ in LINES]
    return [(texts[i][j], box.x, box.y, 0.97) for i in lines for j, box in enumerate(boxes[i])]


class SizedReader(FakeReader):
    """Leitor falso que devolve as palavras com as caixas reais."""

    def __init__(
        self, source: ReadingSource, words: list[tuple[str, BBox]], vocab: str = ""
    ) -> None:
        super().__init__(source, [], "", vocab)
        from app.pipeline.reading import ReadWord

        self.words = [ReadWord(t, b, 0.97, source) for t, b in words]

    def read_block(self, image, origin):  # type: ignore[no-untyped-def]
        ox, oy = origin
        h, w = image.shape[:2]
        return [
            word
            for word in self.words
            if ox <= word.bbox.x + word.bbox.w / 2 < ox + w
            and oy <= word.bbox.y + word.bbox.h / 2 < oy + h
        ]


def scenario(read_lines: list[int], layout_lines: list[int]):  # type: ignore[no-untyped-def]
    image, boxes = page()
    texts = [text.split() for text, _ in LINES]
    seen = [(texts[i][j], b) for i in read_lines for j, b in enumerate(boxes[i])]
    vocab = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,:áéíóúãõç"
    readers = Readers(
        primary=SizedReader(ReadingSource.PADDLE, seen),
        secondary=SizedReader(ReadingSource.DOCTR, seen, vocab),
    )
    region = union([b for i in layout_lines for b in boxes[i]])
    layout = PageLayout(
        [
            LayoutBlock(
                type=BlockType.PARAGRAPH,
                bbox=region,
                order=0,
                column=0,
                align=Alignment.LEFT,
                rel_size=1.0,
                score=0.9,
                label="text",
            )
        ],
        columns=1,
    )
    rgb = np.ascontiguousarray(np.stack([image] * 3, axis=2))
    pre = Preprocessed(rgb, image, False, 0, 0.0, 1.0, False)
    return recognize_page(pre, layout, page_input(), "p0-", readers), boxes


def test_forgotten_footnote_becomes_a_block_at_the_end() -> None:
    result, _ = scenario(read_lines=[0, 1, 2, 3], layout_lines=[0, 1, 2])

    blocks = result.page.blocks
    assert len(blocks) == 2
    assert [w.text for w in blocks[-1].words] == LINES[3][0].split()
    assert blocks[-1].type is BlockType.PARAGRAPH


def test_skipped_line_becomes_illegible_doubt_in_place() -> None:
    result, boxes = scenario(read_lines=[0, 2, 3], layout_lines=[0, 1, 2])

    paragraph = result.page.blocks[0]
    texts = [w.text for w in paragraph.words]
    first, third = LINES[0][0].split(), LINES[2][0].split()
    assert texts == [*first, ILLEGIBLE, *third]
    illegible = paragraph.words[len(first)]
    assert illegible.status is WordStatus.UNCERTAIN
    assert contains(union(boxes[1]), illegible.bbox)
