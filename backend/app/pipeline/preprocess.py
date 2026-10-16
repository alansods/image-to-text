"""Pré-processamento das páginas (spec image-preprocessing, design D4).

Funções puras: imagem in → imagem/dados out. Saem duas versões de cada página:
- `aligned`: o original apenas retificado e endireitado (colorido), base de recortes e imagens;
- `normalized`: cinza, limpa e contrastada, usada só para a leitura.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pypdfium2 as pdfium
from numpy.typing import NDArray
from PIL import Image as PILImage
from PIL import ImageOps

from app.models.document import PageSize
from app.pipeline.base import Image, PageInput

PDF_DPI = 300
A4 = PageSize(w_pt=595.28, h_pt=841.89)

# Texto com letras abaixo disso é ampliado (spec: "Print pequeno"). O alvo é um pouco acima de 30 px
# porque, ao ampliar, as bordas suavizadas das letras "encolhem" ~10% na binarização.
MIN_CHAR_HEIGHT = 20
TARGET_CHAR_HEIGHT = 32

# A folha precisa ocupar ao menos metade da foto para corrigirmos a perspectiva.
MIN_SHEET_AREA = 0.5

Gray = NDArray[np.uint8]


# ------------------------------------------------------------------ carregar (4.1)


def _pdf_pages(source: Path) -> list[PageInput]:
    pdf = pdfium.PdfDocument(str(source))
    try:
        pages = []
        for index, page in enumerate(pdf):
            image = np.asarray(page.render(scale=PDF_DPI / 72).to_pil().convert("RGB"))
            size = PageSize(w_pt=round(page.get_width(), 2), h_pt=round(page.get_height(), 2))
            pages.append(PageInput(index=index, image=image, page_size=size))
        return pages
    finally:
        pdf.close()


def _image_page(source: Path) -> PageInput:
    with PILImage.open(source) as raw:
        # Fotos de celular costumam vir "deitadas" com a rotação só anotada no EXIF.
        upright = ImageOps.exif_transpose(raw).convert("RGB")
    image = np.asarray(upright)
    h, w = image.shape[:2]
    size = A4 if h >= w else PageSize(w_pt=A4.h_pt, h_pt=A4.w_pt)
    return PageInput(index=0, image=image, page_size=size)


def load_pages(source: Path) -> list[PageInput]:
    if source.suffix.lower() == ".pdf":
        return _pdf_pages(source)
    return [_image_page(source)]


# ------------------------------------------------------------------ geometria (4.2, 4.3)


def _u8(array: object) -> Gray:
    return np.asarray(array, dtype=np.uint8)


def _to_gray(image: Image) -> Gray:
    return image if image.ndim == 2 else np.asarray(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY))


def _order_corners(points: NDArray[np.float32]) -> NDArray[np.float32]:
    """Cantos em ordem: superior-esquerdo, superior-direito, inferior-direito, inferior-esquerdo."""
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).ravel()
    return np.array(
        [
            points[np.argmin(sums)],
            points[np.argmin(diffs)],
            points[np.argmax(sums)],
            points[np.argmax(diffs)],
        ],
        dtype=np.float32,
    )


def correct_perspective(image: Image) -> Image | None:
    """Recorta e retifica a folha numa foto; None se não houver contorno de folha confiável."""
    gray = _to_gray(image)
    scale = 1000 / max(gray.shape)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(small, (7, 7), 0)
    # A folha é a região clara; a mesa e o fundo, as escuras.
    mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    sheet = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(sheet) / (small.shape[0] * small.shape[1])
    # Folha pequena demais ou já ocupando a imagem toda (scan): nada a corrigir.
    if area_ratio < MIN_SHEET_AREA or area_ratio > 0.97:
        return None
    perimeter = cv2.arcLength(sheet, closed=True)
    quad = None
    for factor in (0.01, 0.02, 0.03, 0.04, 0.05):
        approx = cv2.approxPolyDP(sheet, factor * perimeter, closed=True)
        if len(approx) == 4:
            quad = approx
            break
    if quad is None or not cv2.isContourConvex(quad):
        return None

    corners = _order_corners(quad.reshape(4, 2).astype(np.float32) / scale)
    top_left, top_right, bottom_right, bottom_left = corners
    width = int(
        max(np.linalg.norm(top_right - top_left), np.linalg.norm(bottom_right - bottom_left))
    )
    height = int(
        max(np.linalg.norm(bottom_left - top_left), np.linalg.norm(bottom_right - top_right))
    )
    target = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32
    )
    matrix = cv2.getPerspectiveTransform(corners, target)
    return np.asarray(
        cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_CUBIC),
        dtype=np.uint8,
    )


@lru_cache(maxsize=1)
def _orientation_model() -> Any:
    from paddleocr import DocImgOrientationClassification

    return DocImgOrientationClassification(model_name="PP-LCNet_x1_0_doc_ori")


def detect_orientation(image: Image) -> int:
    """Rotação da página em graus (0, 90, 180 ou 270), pelo classificador do PaddleOCR."""
    rgb = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    result = _orientation_model().predict(np.ascontiguousarray(rgb), batch_size=1)[0]
    return int(result["label_names"][0])


def fix_orientation(image: Image, rotation: int) -> Image:
    """Desfaz a rotação detectada (o classificador responde no sentido horário)."""
    return np.ascontiguousarray(np.rot90(image, rotation // 90))


def _projection_score(binary: Gray, angle: float) -> float:
    h, w = binary.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rotated = cv2.warpAffine(binary, matrix, (w, h), flags=cv2.INTER_NEAREST, borderValue=(0,))
    rows = rotated.sum(axis=1, dtype=np.float64)
    # Linhas de texto alinhadas deixam a projeção horizontal com picos e vales bem marcados.
    return float(np.var(rows))


def _best_angle(binary: Gray, center: float, span: float, step: float) -> float:
    angles = np.arange(center - span, center + span + step / 2, step)
    return float(max(angles, key=lambda a: _projection_score(binary, float(a))))


def deskew(image: Image, max_angle: float = 15) -> tuple[Image, float]:
    """Endireita a página; devolve a imagem e o ângulo corrigido (graus, anti-horário)."""
    gray = _to_gray(image)
    binary = _u8(cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1])
    coarse_scale = 800 / max(binary.shape)
    coarse = _u8(
        cv2.resize(binary, None, fx=coarse_scale, fy=coarse_scale, interpolation=cv2.INTER_AREA)
    )
    angle = _best_angle(coarse, 0.0, max_angle, 0.5)
    fine_scale = 1600 / max(binary.shape)
    fine = _u8(cv2.resize(binary, None, fx=fine_scale, fy=fine_scale, interpolation=cv2.INTER_AREA))
    angle = _best_angle(fine, angle, 0.6, 0.05)
    if abs(angle) < 0.05:
        return image, 0.0
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    straight = cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255)
    )
    return np.asarray(straight, dtype=np.uint8), angle


# ------------------------------------------------------------------ limpeza (4.4, 4.5)


def clean(gray: Gray) -> Gray:
    """Remove sombra, aumenta o contraste e reduz o ruído (só para leitura)."""
    scale = 0.25
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    # Fundo estimado: fecha (apaga) o texto escuro e suaviza bastante.
    background = cv2.morphologyEx(small, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    background = cv2.medianBlur(background, 21)
    background = cv2.resize(
        background, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR
    )
    flat = cv2.divide(gray, background, scale=255)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(flat)
    return np.asarray(cv2.fastNlMeansDenoising(contrasted, None, h=7), dtype=np.uint8)


def _ink(gray: Gray) -> Gray:
    # Limiar fixo: em página limpa o papel fica perto de 255; ruído de sensor não chega a 140.
    return np.asarray(cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)[1], dtype=np.uint8)


def _components(gray: Gray) -> NDArray[np.int32]:
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(_ink(gray), connectivity=8)
    return np.asarray(stats[1:count], dtype=np.int32)


def median_char_height(gray: Gray) -> float:
    """Altura típica das letras (px), pela mediana das manchas com cara de letra."""
    stats = _components(gray)
    heights = stats[:, cv2.CC_STAT_HEIGHT]
    widths = stats[:, cv2.CC_STAT_WIDTH]
    letter_like = (heights >= 4) & (heights <= gray.shape[0] / 10) & (widths <= heights * 3)
    if not letter_like.any():
        return 0.0
    return float(np.median(heights[letter_like]))


def is_blank(gray: Gray) -> bool:
    """Sem nenhuma mancha do tamanho de uma letra pequena: página em branco."""
    stats = _components(gray)
    return not bool((stats[:, cv2.CC_STAT_AREA] >= 12).any()) if len(stats) else True


def _upscale_factor(gray: Gray) -> float:
    height = median_char_height(gray)
    if 0 < height < MIN_CHAR_HEIGHT:
        return TARGET_CHAR_HEIGHT / height
    return 1.0


# ------------------------------------------------------------------ tudo junto


@dataclass(frozen=True)
class Preprocessed:
    aligned: Image
    normalized: Gray
    blank: bool
    rotation: int
    skew: float
    scale: float
    perspective_corrected: bool


def preprocess(page: PageInput) -> Preprocessed:
    image = page.image
    sheet = correct_perspective(image)
    if sheet is not None:
        image = sheet
    rotation = detect_orientation(image)
    image = fix_orientation(image, rotation)
    image, skew = deskew(image)

    normalized = clean(_to_gray(image))
    if is_blank(normalized):
        return Preprocessed(image, normalized, True, rotation, skew, 1.0, sheet is not None)

    factor = _upscale_factor(normalized)
    if factor > 1:
        size = (round(image.shape[1] * factor), round(image.shape[0] * factor))
        image = np.asarray(cv2.resize(image, size, interpolation=cv2.INTER_CUBIC), dtype=np.uint8)
        normalized = clean(_to_gray(image))
    return Preprocessed(image, normalized, False, rotation, skew, factor, sheet is not None)
