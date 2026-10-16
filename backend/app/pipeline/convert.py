"""Converte um arquivo inteiro de uma vez, sem fila nem disco (testes de precisão e scripts)."""

from pathlib import Path

from app.models.document import Document
from app.pipeline.runner import DocumentPipeline
from app.pipeline.sizes import normalize_sizes


def convert_file(source: Path, pipeline: DocumentPipeline | None = None) -> Document:
    pipeline = pipeline or DocumentPipeline()
    pages = [
        pipeline.process_page(page, f"p{page.index}-", lambda _fraction: None).page
        for page in pipeline.load_pages(source)
    ]
    return normalize_sizes(Document(id=source.stem, source_file=source.name, pages=pages))
