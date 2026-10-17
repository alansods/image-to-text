"""Estado das conversões no Redis e arquivos em disco (spec job-processing)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import fakeredis
import pytest

from app.job_store import JobStore
from app.models.job import Job, JobStage, JobState
from app.storage import JobFiles, new_job_id

T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(clock: Clock) -> JobStore:
    return JobStore(fakeredis.FakeRedis(), now=clock)


def new_job(job_id: str = "j1") -> Job:
    return Job(id=job_id, source_file="contrato.pdf", created_at=T0)


class TestJobIds:
    def test_ids_are_long_random_and_url_safe(self) -> None:
        ids = {new_job_id() for _ in range(100)}

        assert len(ids) == 100
        assert all(len(i) >= 20 and i.replace("-", "").replace("_", "").isalnum() for i in ids)


class TestJobStore:
    def test_create_and_get(self, store: JobStore) -> None:
        store.create(new_job(), client_ip="1.2.3.4")

        assert store.get("j1") == new_job()

    def test_unknown_job_is_none(self, store: JobStore) -> None:
        assert store.get("nao-existe") is None

    def test_progress_never_goes_down(self, store: JobStore) -> None:
        store.create(new_job(), client_ip="1.2.3.4")
        store.update("j1", state=JobState.PROCESSING)

        store.set_progress("j1", 60)
        store.set_progress("j1", 40)

        job = store.get("j1")
        assert job is not None and job.progress == 60

    def test_progress_carries_the_stage_and_page(self, store: JobStore) -> None:
        store.create(new_job(), client_ip="1.2.3.4")
        store.update("j1", state=JobState.PROCESSING)

        store.set_progress("j1", 30, JobStage.READING, page=2, pages=5)

        job = store.get("j1")
        assert job is not None
        assert (job.progress, job.stage, job.page, job.pages) == (30, JobStage.READING, 2, 5)

    def test_job_reads_as_expired_after_one_hour(self, store: JobStore, clock: Clock) -> None:
        store.create(new_job(), client_ip="1.2.3.4")
        clock.now = T0 + timedelta(hours=1)

        job = store.get("j1")

        assert job is not None and job.state is JobState.EXPIRED

    def test_remembers_task_id(self, store: JobStore) -> None:
        store.create(new_job(), client_ip="1.2.3.4")
        store.set_task_id("j1", "celery-123")

        assert store.task_id("j1") == "celery-123"

    def test_counts_only_active_jobs_per_ip(self, store: JobStore) -> None:
        for job_id in ["a", "b", "c"]:
            store.create(new_job(job_id), client_ip="1.2.3.4")
        store.create(new_job("outro"), client_ip="9.9.9.9")
        store.update("c", state=JobState.DONE, progress=100)

        assert store.active_count("1.2.3.4") == 2
        assert store.active_count("9.9.9.9") == 1
        assert store.active_count("5.5.5.5") == 0


class TestJobFiles:
    def test_creates_layout_and_deletes_everything(self, tmp_path: Path) -> None:
        files = JobFiles(tmp_path, "j1")
        files.create(created_at=T0)

        files.page_image(0).write_bytes(b"png")
        files.result.write_text("{}")

        assert files.created_at() == T0
        files.delete()
        assert not (tmp_path / "j1").exists()

    def test_delete_is_safe_when_missing(self, tmp_path: Path) -> None:
        JobFiles(tmp_path, "j1").delete()

    def test_rejects_ids_that_escape_the_data_dir(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            JobFiles(tmp_path, "../etc")
