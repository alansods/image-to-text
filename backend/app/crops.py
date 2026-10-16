"""Recorte de uma palavra com contexto, mostrado no quadro de conferência ("Na imagem:")."""

import io

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from app.models.document import BBox

# Contexto: algumas letras dos dois lados e uma folga acima e abaixo da linha.
_SIDE_CONTEXT = 3.0
_VERTICAL_CONTEXT = 0.6


def word_crop(page: NDArray[np.uint8], bbox: BBox) -> NDArray[np.uint8]:
    height, width = page.shape[:2]
    side = bbox.h * _SIDE_CONTEXT
    vertical = bbox.h * _VERTICAL_CONTEXT
    left = max(0, int(bbox.x - side))
    right = min(width, int(bbox.x + bbox.w + side))
    top = max(0, int(bbox.y - vertical))
    bottom = min(height, int(bbox.y + bbox.h + vertical))
    return page[top:bottom, left:right]


def png_bytes(image: NDArray[np.uint8]) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, "PNG")
    return buffer.getvalue()
