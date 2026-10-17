"""Pipeline usado pelo worker: carrega, pré-processa, detecta o layout e lê o texto.
Completude e tabelas entram na task 7."""

from pathlib import Path

from app.config import get_settings
from app.models.job import JobStage
from app.pipeline.base import PageInput, ProcessedPage, Report
from app.pipeline.layout import analyze_layout
from app.pipeline.preprocess import load_pages, preprocess
from app.pipeline.recognize import Readers, recognize_page


def default_readers() -> Readers:
    from app.pipeline.ocr_doctr import DoctrReader
    from app.pipeline.ocr_paddle import PaddleReader

    arbiter = None
    if get_settings().arbiter_enabled:
        from app.pipeline.arbiter import VlArbiter

        arbiter = VlArbiter()
    return Readers(primary=PaddleReader(), secondary=DoctrReader(), arbiter=arbiter)


class DocumentPipeline:
    def __init__(self, readers: Readers | None = None) -> None:
        self._readers = readers

    @property
    def readers(self) -> Readers:
        if self._readers is None:
            self._readers = default_readers()
        return self._readers

    def load_pages(self, source: Path) -> list[PageInput]:
        return load_pages(source)

    def process_page(self, page: PageInput, id_prefix: str, report: Report) -> ProcessedPage:
        report(0.0, JobStage.PREPARING)
        pre = preprocess(page)
        report(0.1, JobStage.LAYOUT)
        layout = None if pre.blank else analyze_layout(pre.aligned, pre.normalized)
        report(0.3, JobStage.READING)
        result = recognize_page(pre, layout, page, id_prefix, self.readers)
        report(1.0, JobStage.READING)
        return result
