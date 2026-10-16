"""Avaliação de qualidade da página (spec image-preprocessing, design D13).

A baixa qualidade não impede a conversão: só faz a tela avisar que o texto e a formatação
devem ser conferidos com atenção. As medidas são feitas dentro dos blocos de texto — a página
inteira mistura ilustrações e degradês que distorcem nitidez e contraste.
"""

from collections.abc import Sequence

import cv2
import numpy as np

from app.models.document import ILLEGIBLE, BBox, Block, BlockType, QualityIssue, WordStatus
from app.pipeline.preprocess import Preprocessed

TEXT_TYPES = frozenset(
    {BlockType.HEADING, BlockType.PARAGRAPH, BlockType.LIST, BlockType.HEADER, BlockType.FOOTER}
)
# Ampliação de 2 vezes ou mais: as letras do original tinham menos de ~16 px (ex.: print pequeno).
MIN_SCALE_FOR_LOW_RESOLUTION = 2.0
# Medido (D13): páginas nítidas de 0,35 a 0,69; desfocadas de 0,10 a 0,27.
MIN_SHARPNESS = 0.30
# Medido (D13): papel menos tinta nas páginas boas de 136 a 242; desbotadas de 35 a 50.
MIN_CONTRAST = 80.0
# Mais de 10% das palavras em dúvida ou ilegíveis (spec).
MAX_UNCERTAIN_SHARE = 0.10


def _text_mask(shape: tuple[int, ...], boxes: Sequence[BBox]) -> np.ndarray:
    mask = np.zeros(shape[:2], dtype=bool)
    for b in boxes:
        mask[int(b.y) : int(b.y + b.h), int(b.x) : int(b.x + b.w)] = True
    return mask


def image_issues(pre: Preprocessed, text_boxes: Sequence[BBox]) -> list[QualityIssue]:
    """Resolução, contraste e nitidez da imagem original alinhada, dentro dos blocos de texto."""
    issues = []
    if pre.scale >= MIN_SCALE_FOR_LOW_RESOLUTION:
        issues.append(QualityIssue.RESOLUTION)
    gray = pre.aligned if pre.aligned.ndim == 2 else cv2.cvtColor(pre.aligned, cv2.COLOR_RGB2GRAY)
    mask = _text_mask(gray.shape, text_boxes)
    if not mask.any():
        return issues
    values = gray[mask].reshape(-1, 1)
    threshold = cv2.threshold(values, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]
    flat = values.ravel()
    paper = float(np.median(flat[flat > threshold])) if (flat > threshold).any() else 255.0
    ink = float(np.median(flat[flat <= threshold])) if (flat <= threshold).any() else paper
    contrast = paper - ink
    if contrast < MIN_CONTRAST:
        issues.append(QualityIssue.CONTRAST)
    # Nitidez: |Laplaciano| forte na faixa em volta da tinta, relativo ao contraste.
    ink_mask = ((gray <= threshold) & mask).astype(np.uint8)
    band = (cv2.dilate(ink_mask, np.ones((5, 5), np.uint8)) > 0) & mask
    if band.any() and contrast > 0:
        laplacian = np.abs(cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F))
        sharpness = float(np.percentile(laplacian[band], 90)) / contrast
        if sharpness < MIN_SHARPNESS:
            issues.append(QualityIssue.BLUR)
    return issues


def reading_issues(blocks: Sequence[Block]) -> list[QualityIssue]:
    """Leitura incerta: muitas palavras da página ficaram em dúvida ou ilegíveis."""
    words = [w for b in blocks for w in b.all_words()]
    if not words:
        return []
    doubtful = sum(w.status is WordStatus.UNCERTAIN or w.text == ILLEGIBLE for w in words)
    return [QualityIssue.UNCERTAIN_READING] if doubtful / len(words) > MAX_UNCERTAIN_SHARE else []
