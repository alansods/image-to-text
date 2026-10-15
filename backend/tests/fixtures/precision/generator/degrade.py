"""Rasterização do PDF desenhado e degradações que simulam scanner e câmera de celular."""

from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
from numpy.typing import NDArray
from PIL import Image

Gray = NDArray[np.uint8]


def render(pdf_path: Path, dpi: int = 300) -> list[Gray]:
    pdf = pdfium.PdfDocument(str(pdf_path))
    pages = [np.asarray(page.render(scale=dpi / 72).to_pil().convert("L")) for page in pdf]
    pdf.close()
    return pages


def scan(page: Gray, rng: np.random.Generator, *, tilt_deg: float = 0.4) -> Gray:
    """Scanner de mesa: leve inclinação, papel não tão branco e ruído de sensor."""
    h, w = page.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), tilt_deg, 1.0)
    tilted = cv2.warpAffine(page, matrix, (w, h), borderValue=255)
    paper = tilted.astype(np.float32) * 0.96 + 4
    noise = rng.normal(0, 4, size=paper.shape)
    return np.clip(paper + noise, 0, 255).astype(np.uint8)


def photo(page: Gray, rng: np.random.Generator) -> NDArray[np.uint8]:
    """Foto de celular: folha sobre a mesa, em perspectiva, inclinada, com sombra e ruído."""
    h, w = page.shape
    canvas_w, canvas_h = int(w * 1.25), int(h * 1.18)
    desk = np.zeros((canvas_h, canvas_w, 3), np.float32)
    desk[:] = (92, 120, 150)  # madeira (BGR)
    desk += rng.normal(0, 10, size=desk.shape)

    def jitter(spread: float) -> float:
        return float(rng.uniform(-spread, spread))

    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    dst = np.array(
        [
            [canvas_w * 0.12 + jitter(30), canvas_h * 0.06 + jitter(30)],
            [canvas_w * 0.86 + jitter(30), canvas_h * 0.09 + jitter(30)],
            [canvas_w * 0.90 + jitter(30), canvas_h * 0.95 + jitter(30)],
            [canvas_w * 0.08 + jitter(30), canvas_h * 0.92 + jitter(30)],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(src, dst)
    sheet = cv2.cvtColor(page, cv2.COLOR_GRAY2BGR).astype(np.float32)
    warped = cv2.warpPerspective(sheet, matrix, (canvas_w, canvas_h), borderValue=(0, 0, 0))
    mask = cv2.warpPerspective(
        np.ones((h, w), np.float32), matrix, (canvas_w, canvas_h), borderValue=0
    )[..., None]
    image = desk * (1 - mask) + warped * mask * np.array([0.93, 0.96, 1.0], dtype=np.float32)

    rotation = cv2.getRotationMatrix2D((canvas_w / 2, canvas_h / 2), 7.0, 1.0)
    image = cv2.warpAffine(image, rotation, (canvas_w, canvas_h), borderValue=(70, 90, 110))

    shadow = np.linspace(0.62, 1.0, canvas_w, dtype=np.float32)[None, :, None]
    image = image * shadow + rng.normal(0, 5, size=image.shape)
    image = cv2.GaussianBlur(np.clip(image, 0, 255).astype(np.uint8), (3, 3), 0.8)
    return np.asarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), dtype=np.uint8)


def save_scanned_pdf(pages: list[Gray], path: Path, dpi: int = 300) -> None:
    """PDF escaneado: cada página é só uma imagem (sem texto), como sai de um scanner."""
    images = [Image.fromarray(p) for p in pages]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=dpi)


def save_jpeg(image: NDArray[np.uint8], path: Path, quality: int = 82) -> None:
    Image.fromarray(image).save(path, "JPEG", quality=quality, optimize=True)


def save_png(image: NDArray[np.uint8], path: Path) -> None:
    Image.fromarray(image).save(path, "PNG", optimize=True)


def pdf_page_sizes(path: Path) -> list[tuple[float, float]]:
    pdf = pdfium.PdfDocument(str(path))
    sizes = [(round(p.get_width(), 2), round(p.get_height(), 2)) for p in pdf]
    pdf.close()
    return sizes
