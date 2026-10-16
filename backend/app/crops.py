"""Recorte de uma palavra com contexto, mostrado no quadro de conferência ("Na imagem:")."""

import io

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from app.models.document import BBox

# Contexto: algumas letras dos dois lados e uma folga acima e abaixo da linha.
_SIDE_CONTEXT = 3.0
_VERTICAL_CONTEXT = 0.6


# Contorno da palavra em dúvida, no âmbar da interface (#D49400).
_OUTLINE = (212, 148, 0)


def word_crop(page: NDArray[np.uint8], bbox: BBox) -> NDArray[np.uint8]:
    """Recorte colorido com a palavra contornada em âmbar e um pouco de contexto."""
    height, width = page.shape[:2]
    side = bbox.h * _SIDE_CONTEXT
    vertical = bbox.h * _VERTICAL_CONTEXT
    left = max(0, int(bbox.x - side))
    right = min(width, int(bbox.x + bbox.w + side))
    top = max(0, int(bbox.y - vertical))
    bottom = min(height, int(bbox.y + bbox.h + vertical))
    crop = page[top:bottom, left:right]
    rgb = np.stack([crop] * 3, axis=2) if crop.ndim == 2 else crop[:, :, :3].copy()
    pad = max(2, int(bbox.h * 0.15))
    thick = max(2, int(bbox.h * 0.06))
    x1 = max(0, int(bbox.x) - left - pad)
    y1 = max(0, int(bbox.y) - top - pad)
    x2 = min(rgb.shape[1], int(bbox.x + bbox.w) - left + pad)
    y2 = min(rgb.shape[0], int(bbox.y + bbox.h) - top + pad)
    rgb[y1 : y1 + thick, x1:x2] = _OUTLINE
    rgb[max(y1, y2 - thick) : y2, x1:x2] = _OUTLINE
    rgb[y1:y2, x1 : x1 + thick] = _OUTLINE
    rgb[y1:y2, max(x1, x2 - thick) : x2] = _OUTLINE
    return np.ascontiguousarray(rgb)


def png_bytes(image: NDArray[np.uint8]) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, "PNG")
    return buffer.getvalue()
