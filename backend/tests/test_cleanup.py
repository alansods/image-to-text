"""Descarte dos arquivos em até 1 hora e tarefas do worker (spec job-processing)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import fakeredis
import pytest

from app import worker
from app.cleanup import cleanup_expired
from app.job_store import JobStore
from app.models.job import Job, JobState
from app.storage import JobFiles

T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def make_files(root: Path, job_id: str, created_at: datetime) -> JobFiles:
    files = JobFiles(root, job_id)
    files.create(created_at=created_at)
    files.result.write_text("{}")
    return files


def test_deletes_jobs_older_than_one_hour_and_keeps_recent(tmp_path: Path) -> None:
    old = make_files(tmp_path, "antigo", T0 - timedelta(minutes=61))
    recent = make_files(tmp_path, "recente", T0 - timedelta(minutes=10))

    removed = cleanup_expired(tmp_path, now=T0)

    assert removed == ["antigo"]
    assert not old.exists() and recent.exists()


def test_removes_leftovers_without_creation_mark(tmp_path: Path) -> None:
    (tmp_path / "sem-marca").mkdir()

    assert cleanup_expired(tmp_path, now=T0) == ["sem-marca"]


def test_missing_data_dir_is_fine(tmp_path: Path) -> None:
    assert cleanup_expired(tmp_path / "nao-existe", now=T0) == []


def test_cleanup_runs_every_five_minutes() -> None:
    schedule = worker.celery_app.conf.beat_schedule["cleanup-expired-jobs"]

    assert schedule["task"] == "cleanup_expired_jobs"
    assert schedule["schedule"] == 300


def test_convert_job_task_runs_the_orchestrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JobStore(fakeredis.FakeRedis(), now=lambda: T0)
    store.create(Job(id="j1", source_file="a.png", created_at=T0), client_ip="1.2.3.4")
    make_files(tmp_path, "j1", T0).source("png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(worker, "_context", lambda: (store, tmp_path))

    worker.convert_job.apply(args=("j1",)).get()

    job = store.get("j1")
    # Sem o pipeline instalado (tasks 4 a 7), a conversão falha com motivo explícito.
    assert job is not None and job.state is JobState.FAILED and job.error == "pipeline_unavailable"
