"""Estado da conversão: estados, percentual que nunca diminui e expiração em 1 hora."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models.job import JOB_TTL, Job, JobStage, JobState

CREATED = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def make_job(**overrides: object) -> Job:
    data: dict[str, object] = {"id": "j1", "source_file": "contrato.pdf", "created_at": CREATED}
    data.update(overrides)
    return Job.model_validate(data)


def test_new_job_is_queued_at_zero_percent() -> None:
    job = make_job()

    assert job.state is JobState.QUEUED
    assert job.progress == 0
    assert (job.stage, job.page, job.pages) == (JobStage.QUEUED, 0, 0)


def test_progress_is_between_0_and_100() -> None:
    with pytest.raises(ValidationError):
        make_job(progress=101)


def test_progress_never_goes_down() -> None:
    job = make_job(state=JobState.PROCESSING, progress=60)

    assert job.with_progress(40).progress == 60
    assert job.with_progress(75).progress == 75


def test_ttl_is_one_hour() -> None:
    assert timedelta(hours=1) == JOB_TTL


def test_job_expires_one_hour_after_upload() -> None:
    job = make_job(state=JobState.DONE, progress=100)

    assert not job.is_expired(CREATED + timedelta(minutes=59))
    assert job.is_expired(CREATED + timedelta(hours=1))


def test_active_states() -> None:
    assert make_job().is_active()
    assert make_job(state=JobState.PROCESSING).is_active()
    assert not make_job(state=JobState.DONE, progress=100).is_active()
    assert not make_job(state=JobState.CANCELLED).is_active()


def test_failed_job_carries_a_reason() -> None:
    with pytest.raises(ValidationError, match="error"):
        make_job(state=JobState.FAILED)

    assert make_job(state=JobState.FAILED, error="unreadable").error == "unreadable"
