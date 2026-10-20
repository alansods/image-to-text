"""Checagem de completude (spec completeness-check, design D9).

Nada visível pode ficar de fora: tinta fora de todos os blocos vira região órfã (lida de
novo); linha visível de um bloco sem nenhuma palavra lida é relida e, se continuar sem
leitura, vira "[ilegível]" em dúvida.
"""

from collections.abc import Sequence

import cv2
import numpy as np

from app.models.document import BBox
from app.pipeline.reading import Gray

# Margem em volta dos blocos já conhecidos (bordas e acentos não são órfãos).
BLOCK_MARGIN = 10
# Mancha menor que isto (em alturas de letra), nas duas direções, é poeira ou risco do scanner.
MIN_CONTENT = 0.6
# Manchas a menos de uma altura de letra uma da outra pertencem à mesma região.
GROUP_DISTANCE = 1.0
# Faixa de linha: manchas com altura de letra (0,5 a 2,5 alturas típicas).
LETTER_MIN, LETTER_MAX = 0.5, 2.5
# Borda do papel escaneado: manchas órfãs com ao menos isto de comprimento (em alturas de letra).
# Medido num contrato real: contorno da folha com 1 a 2% de tinta na caixa (ignorado) e bordas
# laterais 59 a 68 vezes mais compridas que largas (figura, sem leitura).
EDGE_MIN_LENGTH = 10
OUTLINE_MAX_FILL = 0.05
STROKE_MIN_RATIO = 20


def _ink(gray: Gray) -> Gray:
    return np.asarray(cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)[1], dtype=np.uint8)


def _orphan_ink(gray: Gray, blocks: Sequence[BBox], char_height: float) -> tuple[Gray, list[BBox]]:
    """Tinta fora de todos os blocos, sem poeira nem contorno do papel; e os traços soltos
    compridos (borda lateral, régua, dobra), separados do resto."""
    ink = _ink(gray)
    for b in blocks:
        top, left = max(0, int(b.y) - BLOCK_MARGIN), max(0, int(b.x) - BLOCK_MARGIN)
        ink[top : int(b.y + b.h) + BLOCK_MARGIN, left : int(b.x + b.w) + BLOCK_MARGIN] = 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    widths, heights = stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]
    longest = np.maximum(widths, heights)
    shortest = np.maximum(np.minimum(widths, heights), 1)
    edge = longest >= EDGE_MIN_LENGTH * char_height
    outline = edge & (stats[:, cv2.CC_STAT_AREA] < OUTLINE_MAX_FILL * widths * heights)
    stroke = edge & ~outline & (longest >= STROKE_MIN_RATIO * shortest)
    minimum = MIN_CONTENT * char_height
    keep = ((widths >= minimum) | (heights >= minimum)) & ~outline & ~stroke
    keep[0] = False
    strokes = [
        BBox(
            x=int(stats[i, cv2.CC_STAT_LEFT]),
            y=int(stats[i, cv2.CC_STAT_TOP]),
            w=int(widths[i]),
            h=int(heights[i]),
        )
        for i in range(1, count)
        if stroke[i]
    ]
    return np.where(keep[labels], 255, 0).astype(np.uint8), strokes


def orphan_regions(gray: Gray, blocks: Sequence[BBox], char_height: float) -> list[BBox]:
    """Regiões com tinta fora de todos os blocos, sem poeira nem borda do papel, agrupadas por
    proximidade."""
    if char_height <= 0:
        return []
    content, _strokes = _orphan_ink(gray, blocks, char_height)
    if not content.any():
        return []
    size = max(3, int(GROUP_DISTANCE * char_height))
    grouped = cv2.dilate(content, np.ones((size, size), np.uint8))
    count, labels, _stats, _ = cv2.connectedComponentsWithStats(grouped, connectivity=8)
    regions = []
    for index in range(1, count):
        ys, xs = np.nonzero((labels == index) & (content > 0))
        if len(xs) == 0:
            continue
        x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        regions.append(BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1))
    return sorted(regions, key=lambda r: (r.y, r.x))


def stray_strokes(gray: Gray, blocks: Sequence[BBox], char_height: float) -> list[BBox]:
    """Traços soltos compridos fora dos blocos (borda lateral do papel, régua, dobra): entram
    como figura, sem leitura."""
    if char_height <= 0:
        return []
    _content, strokes = _orphan_ink(gray, blocks, char_height)
    return sorted(strokes, key=lambda r: (r.y, r.x))


def _line_bands(gray: Gray, block: BBox, char_height: float) -> list[tuple[int, int]]:
    """Faixas horizontais (em y da página) ocupadas por manchas com altura de letra."""
    top, left = max(0, int(block.y)), max(0, int(block.x))
    crop = _ink(gray[top : int(block.y + block.h) + 1, left : int(block.x + block.w) + 1])
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(crop, connectivity=8)
    heights = stats[1:count, cv2.CC_STAT_HEIGHT]
    tops = stats[1:count, cv2.CC_STAT_TOP]
    letters = (heights >= LETTER_MIN * char_height) & (heights <= LETTER_MAX * char_height)
    rows = np.zeros(crop.shape[0] + 1, dtype=bool)
    for t, h in zip(tops[letters], heights[letters], strict=True):
        rows[t : t + h] = True
    edges = np.diff(np.concatenate(([0], rows.astype(np.int8), [0])))
    starts, ends = np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]
    return [(top + int(s), top + int(e)) for s, e in zip(starts, ends, strict=True)]


def missing_lines(gray: Gray, block: BBox, words: Sequence[BBox], char_height: float) -> list[BBox]:
    """Linhas visíveis do bloco em que nenhuma palavra lida tem o centro."""
    if char_height <= 0:
        return []
    centers = [w.y + w.h / 2 for w in words]
    missing = []
    for start, end in _line_bands(gray, block, char_height):
        if end - start < LETTER_MIN * char_height:
            continue
        if not any(start <= c <= end for c in centers):
            missing.append(BBox(x=block.x, y=start, w=block.w, h=end - start))
    return missing
