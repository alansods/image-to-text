"""Traço decidido pela forma (spec reading-reconciliation). Imagens sintéticas: letras como
blocos de tinta com 30 px de altura, traços e sublinhado desenhados com medidas conhecidas."""

import numpy as np
import pytest

from app.models.document import BBox
from app.pipeline.dashes import dash_shape, is_dash_reading

CAP = 30
BASELINE = 100


def line(dash_length: float | None, underline: bool = False) -> tuple[np.ndarray, BBox]:
    """Linha "ABCD [traço] EFGH": quatro letras, o traço (comprimento em alturas das
    maiúsculas) e mais quatro letras. Devolve a imagem e a caixa que o leitor daria ao traço."""
    gray = np.full((160, 700), 255, dtype=np.uint8)
    x = 20
    for _ in range(4):
        gray[BASELINE - CAP : BASELINE, x : x + 20] = 0
        x += 26
    box = BBox(x=x + 10, y=BASELINE - CAP, w=60, h=CAP)
    if dash_length is not None:
        length = round(dash_length * CAP)
        top = BASELINE - round(CAP * 0.45)
        gray[top : top + 5, x + 12 : x + 12 + length] = 0
        box = BBox(x=x + 10, y=top - 4, w=length + 4, h=13)
    x += 80
    for _ in range(4):
        gray[BASELINE - CAP : BASELINE, x : x + 20] = 0
        x += 26
    if underline:
        gray[BASELINE + 6 : BASELINE + 9, 15 : x + 5] = 0
    return gray, box


@pytest.mark.parametrize(
    ("length", "expected"),
    [(0.40, "-"), (0.45, "-"), (0.75, "–"), (1.0, "–"), (1.48, "—")],  # noqa: RUF001
)
def test_the_symbol_comes_from_the_stroke_length(length: float, expected: str) -> None:
    gray, box = line(length)
    found = dash_shape(gray, box)
    assert found is not None
    assert found[0] == expected


def test_the_underline_does_not_change_the_measure() -> None:
    gray, box = line(0.75, underline=True)
    found = dash_shape(gray, box)
    assert found is not None
    assert found[0] == "–"  # noqa: RUF001


def test_only_the_underline_means_no_stroke() -> None:
    gray, _ = line(None, underline=True)
    under = BBox(x=136, y=BASELINE + 2, w=40, h=10)
    assert dash_shape(gray, under) == ("", None)


def test_without_letters_around_there_is_nothing_to_compare() -> None:
    gray = np.full((100, 200), 255, dtype=np.uint8)
    gray[50:55, 60:90] = 0
    assert dash_shape(gray, BBox(x=55, y=45, w=40, h=15)) is None


@pytest.mark.parametrize(
    ("texts", "expected"),
    [
        (["-", "-"], True),
        (["-", "_"], True),
        (["-", "--"], True),
        (["|}~°£", ""], True),
        (["–"], True),  # noqa: RUF001
        (["mão-de-obra", "mão-de-obra"], False),
        (["12345-6", "12345-6"], False),
        (["______", "______"], False),  # linha de preencher: conteúdo
        (["_", ""], False),  # pedaço de sublinhado: regra própria
        (["•", "•"], False),
        (["", ""], False),
    ],
)
def test_which_readings_are_dashes(texts: list[str], expected: bool) -> None:
    assert is_dash_reading(texts) is expected
