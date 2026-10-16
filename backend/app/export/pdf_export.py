"""PDF a partir do Word gerado, pelo LibreOffice em modo sem tela (design D10).

Word e PDF ficam idênticos. A paginação é conferida aqui: se o PDF tiver mais páginas que o
original (alguma página transbordou), as fontes são reduzidas em 5% e tudo é gerado de novo.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pypdfium2 as pdfium

from app.export.docx_export import build_docx
from app.models.document import Document

FONT_STEP = 0.95
MAX_TRIES = 6
TIMEOUT_SECONDS = 120


class ExportError(RuntimeError):
    """Não foi possível gerar o arquivo (LibreOffice ausente, falhou ou estourou o tempo)."""


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def docx_to_pdf(source: Path, out_dir: Path) -> Path:
    binary = soffice()
    if binary is None:
        raise ExportError("LibreOffice não instalado")
    with tempfile.TemporaryDirectory() as profile:
        # Perfil próprio por chamada: duas conversões simultâneas não disputam o mesmo perfil.
        command = [
            binary,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(source),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=TIMEOUT_SECONDS)
        except (subprocess.SubprocessError, OSError) as error:
            raise ExportError("falha ao converter para PDF") from error
    pdf = out_dir / f"{source.stem}.pdf"
    if not pdf.is_file():
        raise ExportError("o LibreOffice não gerou o PDF")
    return pdf


def page_count(pdf: Path) -> int:
    document = pdfium.PdfDocument(str(pdf))
    try:
        return len(document)
    finally:
        document.close()


def export_pair(document: Document, assets: Path, out_dir: Path) -> tuple[Path, Path]:
    """Gera `document.docx` e `document.pdf` com a mesma paginação do original."""
    out_dir.mkdir(parents=True, exist_ok=True)
    docx_path = out_dir / "document.docx"
    scale = 1.0
    for _ in range(MAX_TRIES):
        build_docx(document, assets, docx_path, scale)
        pdf_path = docx_to_pdf(docx_path, out_dir)
        if page_count(pdf_path) <= len(document.pages):
            return docx_path, pdf_path
        scale *= FONT_STEP
    return docx_path, pdf_path
