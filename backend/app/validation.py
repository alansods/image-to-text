"""Validação do arquivo enviado: formato pelo conteúdo, tamanho, páginas e senha (spec file-upload).

HEIC não chega aqui: o navegador converte para JPG antes do envio (design D11).
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image, UnidentifiedImageError

from app.errors import ErrorCode, UploadRejectedError

MAX_PAGES = 50
_CHUNK = 1024 * 1024


class SourceKind(StrEnum):
    IMAGE = "image"
    PDF = "pdf"


@dataclass(frozen=True)
class SourceInfo:
    kind: SourceKind
    extension: str
    pages: int


def _sniff(head: bytes) -> str | None:
    """Extensão pelo começo do arquivo (assinatura), ignorando nome e extensão enviados."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if b"%PDF-" in head[:1024]:
        return "pdf"
    return None


def save_limited(stream: BinaryIO, dest: Path, max_bytes: int) -> None:
    """Grava o envio em blocos, sem carregar tudo na memória, e para ao passar do limite."""
    written = 0
    try:
        with dest.open("wb") as out:
            while chunk := stream.read(_CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    raise UploadRejectedError(413, ErrorCode.FILE_TOO_LARGE)
                out.write(chunk)
    except UploadRejectedError:
        dest.unlink(missing_ok=True)
        raise


def _unsupported() -> UploadRejectedError:
    return UploadRejectedError(415, ErrorCode.UNSUPPORTED_FORMAT)


def _count_pdf_pages(path: Path) -> int:
    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as error:
        if getattr(error, "err_code", None) == pdfium_raw.FPDF_ERR_PASSWORD:
            raise UploadRejectedError(422, ErrorCode.PDF_PASSWORD) from error
        raise _unsupported() from error
    try:
        return len(pdf)
    finally:
        pdf.close()


def inspect_source(path: Path) -> SourceInfo:
    with path.open("rb") as file:
        extension = _sniff(file.read(1024))
    if extension is None:
        raise _unsupported()

    if extension == "pdf":
        pages = _count_pdf_pages(path)
        if pages == 0:
            raise _unsupported()
        if pages > MAX_PAGES:
            raise UploadRejectedError(422, ErrorCode.TOO_MANY_PAGES)
        return SourceInfo(kind=SourceKind.PDF, extension="pdf", pages=pages)

    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise _unsupported() from error
    return SourceInfo(kind=SourceKind.IMAGE, extension=extension, pages=1)
