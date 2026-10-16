"""Árbitro com o modelo PaddleOCR-VL de verdade. Lento (~3 s por palavra em CPU) e com download
grande na primeira vez: roda só com `-m precision`, junto dos testes lentos."""

import pytest

from app.pipeline.arbiter import VlArbiter
from tests.test_ocr_readers import paddle_reader, rendered_line

pytestmark = pytest.mark.precision


def test_real_arbiter_picks_the_reading_that_matches_the_image() -> None:
    image = rendered_line()
    [word] = [w for w in paddle_reader().read_block(image, (0, 0)) if w.text == "cobrança"]
    b = word.bbox
    crop = image[int(b.y) - 6 : int(b.y + b.h) + 6, int(b.x) - 4 : int(b.x + b.w) + 4]

    assert VlArbiter().choose(crop, image, ["cobranca", "cobrança"]) == "cobrança"
