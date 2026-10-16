"""PDF via LibreOffice (spec document-export). Pulado onde o LibreOffice não está instalado
(roda na imagem Docker do backend)."""

from pathlib import Path

import pypdfium2 as pdfium
import pytest

from app.export.pdf_export import export_pair, soffice
from tests.export_samples import sample_document

pytestmark = pytest.mark.skipif(soffice() is None, reason="LibreOffice não instalado")


def test_pdf_has_same_pages_sheets_and_searchable_text(tmp_path: Path) -> None:
    document = sample_document(tmp_path)

    docx_path, pdf_path = export_pair(document, tmp_path, tmp_path / "exports")

    assert docx_path.is_file()
    pdf = pdfium.PdfDocument(str(pdf_path))
    assert len(pdf) == 4
    sizes = [tuple(round(v) for v in pdf[i].get_size()) for i in range(4)]
    assert sizes == [(595, 842), (595, 842), (595, 842), (842, 595)]
    first = pdf[0].get_textpage().get_text_range()
    assert "CONTRATANTE" in first and "SILVA" in first
    assert pdf[1].get_textpage().get_text_range().strip() == ""  # página em branco
