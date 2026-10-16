"""Execução de uma conversão página a página: progresso, falhas e cancelamento."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import fakeredis
import numpy as np
import pytest

from app.job_store import JobStore
from app.models.document import (
    ILLEGIBLE,
    BBox,
    Block,
    BlockType,
    Document,
    Page,
    PageSize,
    Word,
    WordStatus,
)
from app.models.job import Job, JobState
from app.orchestrator import run_job
from app.pipeline.base import PageInput, PipelineUnavailableError, ProcessedPage
from app.storage import JobFiles

T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
A4 = PageSize(w_pt=595.28, h_pt=841.89)


def page_input(index: int) -> PageInput:
    return PageInput(index=index, image=np.full((140, 100), 255, np.uint8), page_size=A4)


def processed(page_input: PageInput, id_prefix: str) -> ProcessedPage:
    word = Word(
        id=f"{id_prefix}w0",
        text=f"página{page_input.index}",
        bbox=BBox(x=10, y=10, w=40, h=10),
        confidence=0.99,
        status=WordStatus.ACCEPTED,
    )
    logo = Block(
        id=f"{id_prefix}b1",
        type=BlockType.FIGURE,
        bbox=BBox(x=0, y=100, w=30, h=30),
        order=1,
        image_ref=f"crops/{id_prefix}b1.png",
        confidence=1,
    )
    text = Block(
        id=f"{id_prefix}b0",
        type=BlockType.PARAGRAPH,
        bbox=BBox(x=0, y=0, w=100, h=50),
        order=0,
        words=[word],
        confidence=0.99,
    )
    page = Page(
        index=page_input.index,
        width=100,
        height=140,
        page_size=page_input.page_size,
        image_ref=f"pages/{page_input.index}.png",
        blocks=[text, logo],
    )
    return ProcessedPage(
        page=page,
        aligned=page_input.image,
        crops={logo.id: np.zeros((30, 30), np.uint8)},
    )


class FakePipeline:
    def __init__(
        self,
        pages: int = 3,
        fail_on: set[int] | None = None,
        on_page: Callable[[int], None] | None = None,
        load_error: Exception | None = None,
    ) -> None:
        self.pages = pages
        self.fail_on = fail_on or set()
        self.on_page = on_page
        self.load_error = load_error
        self.processed: list[int] = []

    def load_pages(self, source: Path) -> list[PageInput]:
        if self.load_error:
            raise self.load_error
        return [page_input(i) for i in range(self.pages)]

    def process_page(
        self, page: PageInput, id_prefix: str, report: Callable[[float], None]
    ) -> ProcessedPage:
        if self.on_page:
            self.on_page(page.index)
        report(0.5)
        if page.index in self.fail_on:
            raise RuntimeError("página corrompida")
        self.processed.append(page.index)
        return processed(page, id_prefix)


@pytest.fixture
def store() -> JobStore:
    return JobStore(fakeredis.FakeRedis(), now=lambda: T0)


@pytest.fixture
def files(tmp_path: Path) -> JobFiles:
    files = JobFiles(tmp_path, "j1")
    files.create(created_at=T0)
    files.source("pdf").write_bytes(b"%PDF-")
    return files


@pytest.fixture
def job(store: JobStore) -> Job:
    job = Job(id="j1", source_file="contrato.pdf", created_at=T0)
    store.create(job, client_ip="1.2.3.4")
    return job


def test_successful_job_writes_result_and_finishes_at_100(
    store: JobStore, files: JobFiles, job: Job
) -> None:
    run_job(job.id, store, files, FakePipeline(pages=3))

    final = store.get(job.id)
    assert final is not None and final.state is JobState.DONE and final.progress == 100
    document = Document.model_validate_json(files.result.read_text())
    assert [p.index for p in document.pages] == [0, 1, 2]
    assert document.source_file == "contrato.pdf"
    assert files.page_image(2).is_file()
    assert (files.dir / "crops" / "p1-b1.png").is_file()


def test_progress_grows_page_by_page_and_never_goes_down(
    store: JobStore, files: JobFiles, job: Job
) -> None:
    seen: list[int] = []

    def record(_index: int) -> None:
        current = store.get(job.id)
        assert current is not None
        seen.append(current.progress)

    run_job(job.id, store, files, FakePipeline(pages=5, on_page=record))

    assert seen == sorted(seen)
    assert seen[0] == 0 and 40 <= seen[2] <= 60


def test_failed_page_becomes_original_image_with_illegible_doubt(
    store: JobStore, files: JobFiles, job: Job
) -> None:
    run_job(job.id, store, files, FakePipeline(pages=4, fail_on={1}))

    document = Document.model_validate_json(files.result.read_text())
    assert len(document.pages) == 4
    failed = document.pages[1]
    assert [b.type for b in failed.blocks] == [BlockType.FIGURE, BlockType.PARAGRAPH]
    assert failed.blocks[0].image_ref == "pages/1.png"
    assert [w.text for w in failed.blocks[1].words] == [ILLEGIBLE]
    assert document.uncertain_count() == 1
    assert files.page_image(1).is_file()


def test_all_pages_failing_fails_the_job(store: JobStore, files: JobFiles, job: Job) -> None:
    run_job(job.id, store, files, FakePipeline(pages=2, fail_on={0, 1}))

    final = store.get(job.id)
    assert final is not None and final.state is JobState.FAILED and final.error == "unreadable"
    assert not files.result.exists()


def test_unreadable_source_fails_the_job(store: JobStore, files: JobFiles, job: Job) -> None:
    run_job(job.id, store, files, FakePipeline(load_error=ValueError("arquivo corrompido")))

    final = store.get(job.id)
    assert final is not None and final.state is JobState.FAILED and final.error == "unreadable"


def test_missing_pipeline_fails_with_its_own_reason(
    store: JobStore, files: JobFiles, job: Job
) -> None:
    run_job(job.id, store, files, FakePipeline(load_error=PipelineUnavailableError()))

    final = store.get(job.id)
    assert final is not None and final.error == "pipeline_unavailable"


def test_cancel_between_pages_stops_and_deletes_files(
    store: JobStore, files: JobFiles, job: Job
) -> None:
    def cancel_after_first(index: int) -> None:
        if index == 1:
            store.update(job.id, state=JobState.CANCELLED)

    pipeline = FakePipeline(pages=5, on_page=cancel_after_first)
    run_job(job.id, store, files, pipeline)

    assert pipeline.processed == [0, 1]  # a página em andamento termina; a seguinte não começa
    assert not files.exists()
    final = store.get(job.id)
    assert final is not None and final.state is JobState.CANCELLED


def test_job_that_is_not_queued_is_ignored(store: JobStore, files: JobFiles, job: Job) -> None:
    store.update(job.id, state=JobState.CANCELLED)
    pipeline = FakePipeline()

    run_job(job.id, store, files, pipeline)

    assert pipeline.processed == []


class UnavailableRecognition(FakePipeline):
    """Páginas carregam, mas o reconhecimento ainda não existe neste servidor."""

    def process_page(
        self, page: PageInput, id_prefix: str, report: Callable[[float], None]
    ) -> ProcessedPage:
        raise PipelineUnavailableError


def test_missing_recognition_fails_whole_job_not_page_by_page(
    store: JobStore, files: JobFiles, job: Job
) -> None:
    run_job(job.id, store, files, UnavailableRecognition(pages=3))

    final = store.get(job.id)
    assert final is not None and final.state is JobState.FAILED
    assert final.error == "pipeline_unavailable"
    assert not files.result.exists()


def test_worker_pipeline_loads_real_pages_but_recognition_is_pending(tmp_path: Path) -> None:
    from app.pipeline.runner import DocumentPipeline
    from tests.conftest import pdf_bytes

    source = tmp_path / "source.pdf"
    source.write_bytes(pdf_bytes(pages=2))
    pipeline = DocumentPipeline()

    pages = pipeline.load_pages(source)

    assert [p.index for p in pages] == [0, 1]
    with pytest.raises(PipelineUnavailableError):
        pipeline.process_page(pages[0], "p0-", lambda _f: None)
