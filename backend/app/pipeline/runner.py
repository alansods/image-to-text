"""Pipeline usado pelo worker. Hoje: carrega e pré-processa as páginas (task 4); o reconhecimento
(layout, leitura dupla, reconciliação, completude e tabelas) entra nas tasks 5 a 7."""

from collections.abc import Callable
from pathlib import Path

from app.pipeline.base import PageInput, PipelineUnavailableError, ProcessedPage
from app.pipeline.preprocess import load_pages, preprocess


class DocumentPipeline:
    def load_pages(self, source: Path) -> list[PageInput]:
        return load_pages(source)

    def process_page(
        self, page: PageInput, id_prefix: str, report: Callable[[float], None]
    ) -> ProcessedPage:
        preprocess(page)
        report(0.2)
        raise PipelineUnavailableError("reconhecimento de texto ainda não implementado")
