"""Grau, ordinal ou letra "o" decididos pela forma (spec reading-reconciliation). Imagens
sintéticas: letras como blocos de tinta com 30 px de altura e um anel desenhado na linha de
base (letra "o") ou no alto da linha (sinal de grau)."""

import cv2
import numpy as np
import pytest

from app.models.document import BBox
from app.pipeline.rings import ring_height, round_slots

CAP = 30
BASELINE = 100


def line(raised: bool) -> tuple[np.ndarray, BBox]:
    """Linha "ABCD [anel] EFGH". Devolve a imagem e a caixa que o leitor daria ao anel."""
    gray = np.full((160, 700), 255, dtype=np.uint8)
    x = 20
    for _ in range(4):
        gray[BASELINE - CAP : BASELINE, x : x + 20] = 0
        x += 26
    if raised:
        radius, center_y = 5, BASELINE - CAP + 6
    else:
        radius, center_y = 9, BASELINE - 10
    center_x = x + 14
    cv2.circle(gray, (center_x, center_y), radius, 0, 3)
    box = BBox(x=center_x - radius - 3, y=center_y - radius - 3, w=2 * radius + 6, h=2 * radius + 6)
    x += 36
    for _ in range(4):
        gray[BASELINE - CAP : BASELINE, x : x + 20] = 0
        x += 26
    return gray, box


def test_a_ring_on_the_baseline_is_a_letter() -> None:
    gray, box = line(raised=False)
    assert ring_height(gray, box) == "base"


def test_a_ring_high_on_the_line_is_a_degree_sign() -> None:
    gray, box = line(raised=True)
    assert ring_height(gray, box) == "raised"


def test_a_mark_on_the_line_above_does_not_count() -> None:
    gray, box = line(raised=False)
    left = int(box.x) + 6
    for x in range(20, 680, 26):  # linha de cima, logo acima, sem letra na coluna do "o"
        if not x - 20 <= left <= x + 25:
            gray[BASELINE - CAP - 45 : BASELINE - 45, x : x + 20] = 0
    # Pingo de "i" no alto da linha de cima, na mesma coluna do "o".
    gray[BASELINE - CAP - 45 : BASELINE - CAP - 40, left : left + 5] = 0
    gray[BASELINE - CAP - 36 : BASELINE - 45, left : left + 5] = 0
    assert ring_height(gray, box) == "base"


def test_without_letters_around_there_is_nothing_to_compare() -> None:
    gray = np.full((100, 200), 255, dtype=np.uint8)
    cv2.circle(gray, (80, 50), 8, 0, 3)
    assert ring_height(gray, BBox(x=68, y=38, w=24, h=24)) is None


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("°", "", ("°", [0])),
        ("", "o", ("o", [0])),
        ("25oC", "25°C", ("25oC", [2])),
        ("nº", "no", ("nº", [1])),
        ("o", "°", ("o", [0])),
        ("°", "°", None),  # concordam: nada a medir
        ("contrato", "contrat0", None),  # "0" e "o" têm a mesma altura
        ("abc", "abd", None),
        ("nº", "ng", None),
        ("°C", "", None),
    ],
)
def test_which_readings_differ_only_in_round_signs(
    first: str, second: str, expected: tuple[str, list[int]] | None
) -> None:
    assert round_slots(first, second) == expected
