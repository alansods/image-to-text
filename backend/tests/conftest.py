"""Fábricas de arquivos de teste compartilhadas."""

import io
from pathlib import Path

import pytest
from PIL import Image
from reportlab.pdfgen.canvas import Canvas


def png_bytes(width: int = 40, height: int = 30) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, "PNG")
    return buffer.getvalue()


def image_bytes(fmt: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, fmt)
    return buffer.getvalue()


def pdf_bytes(pages: int = 1, password: str | None = None) -> bytes:
    buffer = io.BytesIO()
    canvas = Canvas(buffer, encrypt=password) if password else Canvas(buffer)
    for index in range(pages):
        canvas.drawString(72, 720, f"Página {index + 1}")
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


@pytest.fixture
def write_file(tmp_path: Path):  # type: ignore[no-untyped-def]
    def write(name: str, content: bytes) -> Path:
        path = tmp_path / name
        path.write_bytes(content)
        return path

    return write
