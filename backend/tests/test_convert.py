"""Conversão de um arquivo inteiro, sem fila (usada pelo teste de precisão)."""

from pathlib import Path

from app.pipeline.convert import convert_file
from tests.conftest import pdf_bytes


def test_converts_every_page_of_a_file(tmp_path: Path) -> None:
    source = tmp_path / "contrato.pdf"
    source.write_bytes(pdf_bytes(pages=2))

    document = convert_file(source)

    assert document.source_file == "contrato.pdf"
    assert [p.index for p in document.pages] == [0, 1]
    assert [w.text for w in document.words_in_reading_order()] == ["Página", "1", "Página", "2"]
