"""Pipeline usado pelo worker. Hoje: carrega, pré-processa (task 4) e detecta o layout (task 5);
a leitura do texto (leitura dupla, reconciliação, completude e tabelas) entra nas tasks 6 e 7."""

from collections.abc import Callable
from pathlib import Path

from app.pipeline.base import PageInput, PipelineUnavailableError, ProcessedPage
from app.pipeline.layout import analyze_layout
from app.pipeline.preprocess import load_pages, preprocess


class DocumentPipeline:
    def load_pages(self, source: Path) -> list[PageInput]:
        return load_pages(source)

    def process_page(
        self, page: PageInput, id_prefix: str, report: Callable[[float], None]
    ) -> ProcessedPage:
        pre = preprocess(page)
        report(0.1)
        if not pre.blank:
            analyze_layout(pre.aligned, pre.normalized)
        report(0.2)
        raise PipelineUnavailableError("leitura do texto ainda não implementada (task 6)")
