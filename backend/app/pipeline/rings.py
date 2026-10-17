"""Grau, ordinal ou letra "o" decididos pela forma (spec reading-reconciliation, design D21).

Os leitores confundem o "o" com o "°": no contrato real, o artigo "o" virou "°" e o outro
leitor não leu nada. A diferença está na altura: a letra fica apoiada na linha de base, e o
grau (ou o "º") fica suspenso no alto da linha. Medimos o fundo da mancha redonda acima da
linha de base, em alturas de maiúscula, com as mesmas medidas da linha usadas nos traços.
"""

from typing import Literal

from app.models.document import BBox
from app.pipeline.dashes import line_ink
from app.pipeline.reading import Gray

Height = Literal["base", "raised"]

RAISED_CHARS = frozenset("°º")
BASE_CHARS = frozenset("oO0")
# Fundo da mancha acima da linha de base: até isto é letra; disto para cima, sinal no alto.
BASE_MAX = 0.15
RAISED_MIN = 0.35
# O sinal no alto é pequeno: no máximo isto da altura das maiúsculas.
RAISED_SIZE = 0.6


def round_slots(first: str, second: str) -> tuple[str, list[int]] | None:
    """Texto base e posições onde as leituras só divergem entre "°"/"º" e "o"/"O"/"0".

    Também vale um sinal redondo sozinho que só um leitor viu. `None`: não há o que medir.
    """
    if not first or not second:
        seen = (first or second).strip()
        if len(seen) == 1 and seen in RAISED_CHARS | BASE_CHARS:
            return seen, [0]
        return None
    if len(first) != len(second):
        return None
    slots = []
    for index, (a, b) in enumerate(zip(first, second, strict=True)):
        if a == b:
            continue
        if {a, b} & RAISED_CHARS and {a, b} <= RAISED_CHARS | BASE_CHARS and a != b:
            slots.append(index)
        else:
            return None
    return (first, slots) if slots else None


def ring_height(gray: Gray, box: BBox) -> Height | None:
    """Onde está a marca redonda da caixa: na linha de base ou no alto da linha.

    `None`: sem letras em volta para comparar, ou a medida fica entre as duas faixas.
    """
    line = line_ink(gray, box)
    if line is None:
        return None
    left, right = box.x - line.x0, box.x + box.w - line.x0
    top, bottom = box.y - line.y0, box.y + box.h - line.y0
    # A marca é a maior mancha dentro da caixa: pingos e acentos das linhas vizinhas não contam.
    inside = [
        s
        for s in line.stats
        if left <= s[0] + s[2] / 2 <= right and top <= s[1] + s[3] / 2 <= bottom and s[4] >= 4
    ]
    if not inside:
        return None
    _, y, _, h, _ = max(inside, key=lambda s: int(s[4]))
    baseline = line.baseline(y + h / 2)
    if baseline is None:
        return None
    lift = (baseline - (y + h)) / line.cap
    if lift >= RAISED_MIN and h <= RAISED_SIZE * line.cap:
        return "raised"
    return "base" if lift <= BASE_MAX else None
