"""Negrito e itálico por palavra, medidos na imagem (spec text-recognition, design D8).

Nenhum leitor informa ênfase. Negrito: largura das hastes das letras comparada à
mediana da página, já descontado o tamanho relativo da letra do bloco. Itálico: inclinação
que mais "endireita" as letras.
"""

import math
from statistics import median

import cv2
import numpy as np

from app.models.document import ILLEGIBLE, BBox, Block, Word
from app.pipeline.reading import Gray

# Hastes ao menos 1,26 vez mais largas que as típicas da página (descontado o tamanho) = negrito.
# Medido no conjunto de teste: normal até 1,22; negrito a partir de 1,30 (negrito+itálico).
BOLD_RATIO = 1.26
# Inclinação de ao menos 8° para a direita = itálico.
ITALIC_DEGREES = 8.0
MAX_SLANT = 20
# Trechos de tinta mínimos para a medida de espessura valer.
MIN_RUNS = 10
# Palavras curtas ("a", "de") têm pouca tinta para medir: seguem as vizinhas.
MIN_MEASURE_CHARS = 3


def _ink(crop: Gray) -> np.ndarray:
    """Máscara da tinta (True onde há letra)."""
    if crop.size == 0 or int(crop.max()) - int(crop.min()) < 40:
        return np.zeros(crop.shape, dtype=bool)
    _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return np.asarray(binary > 0)


def stroke_width(crop: Gray) -> float | None:
    """Largura típica das hastes em pixels; `None` se não há tinta suficiente.

    Mede os trechos contínuos de tinta em cada linha de pixels (a largura das hastes
    verticais, que é o que o negrito engrossa) e tira a média do miolo da distribuição.
    """
    ink = _ink(crop).astype(np.int8)
    edges = np.diff(np.pad(ink, ((0, 0), (1, 1))), axis=1)
    starts, ends = np.nonzero(edges == 1), np.nonzero(edges == -1)
    runs = (ends[1] - starts[1]).astype(np.float64)
    if runs.size < MIN_RUNS:
        return None
    low, high = np.percentile(runs, [25, 75])
    middle = runs[(runs >= low) & (runs <= high)]
    return float(middle.mean())


def slant(crop: Gray) -> float:
    """Inclinação das letras em graus (positivo = para a direita, como no itálico)."""
    ink = _ink(crop).astype(np.uint8)
    if not ink.any():
        return 0.0
    height, width = ink.shape
    pad = math.ceil(height * math.tan(math.radians(MAX_SLANT)))
    best_angle, best_score = 0.0, -1.0
    for angle in range(-MAX_SLANT, MAX_SLANT + 1):
        shear = math.tan(math.radians(angle))
        # Desloca cada linha para a esquerda proporcionalmente à altura acima da base.
        matrix = np.array([[1, shear, pad - shear * height], [0, 1, 0]], dtype=np.float32)
        sheared = cv2.warpAffine(ink, matrix, (width + 2 * pad, height), flags=cv2.INTER_NEAREST)
        columns = sheared.sum(axis=0).astype(np.float64)
        score = float((columns**2).sum())
        if score > best_score:
            best_angle, best_score = float(angle), score
    return best_angle


def _crop(image: Gray, box: BBox) -> Gray:
    h, w = image.shape[:2]
    top, left = max(0, int(box.y)), max(0, int(box.x))
    return image[top : min(h, math.ceil(box.y + box.h)), left : min(w, math.ceil(box.x + box.w))]


def _follow_neighbors(words: list[Word], measured: list[bool]) -> list[bool]:
    """Palavra curta entre duas vizinhas medidas segue as duas se elas concordam; na borda do
    bloco (vizinha de um lado só) vale a medida dela mesma."""
    reliable = [len(w.text) >= MIN_MEASURE_CHARS for w in words]
    result = list(measured)
    for i, word in enumerate(words):
        if reliable[i] or word.text == ILLEGIBLE:
            continue
        before = next((measured[j] for j in range(i - 1, -1, -1) if reliable[j]), None)
        after = next((measured[j] for j in range(i + 1, len(words)) if reliable[j]), None)
        if before is not None and before == after:
            result[i] = before
    return result


def mark_emphasis(blocks: list[Block], image: Gray) -> list[Block]:
    """Preenche `bold` e `italic` das palavras dos blocos de texto da página."""
    widths: dict[str, float] = {}
    for block in blocks:
        for word in block.words:
            if word.text != ILLEGIBLE:
                measured = stroke_width(_crop(image, word.bbox))
                if measured is not None:
                    widths[word.id] = measured / block.rel_size
    if not widths:
        return blocks
    typical = median(widths.values())

    result = []
    for block in blocks:
        if not block.words:
            result.append(block)
            continue
        italic = _follow_neighbors(
            block.words,
            [
                w.text != ILLEGIBLE and slant(_crop(image, w.bbox)) >= ITALIC_DEGREES
                for w in block.words
            ],
        )
        bold = _follow_neighbors(
            block.words, [widths.get(w.id, 0.0) >= BOLD_RATIO * typical for w in block.words]
        )
        words = [
            word.model_copy(update={"bold": bold[i], "italic": italic[i]})
            for i, word in enumerate(block.words)
        ]
        result.append(block.model_copy(update={"words": words}))
    return result
