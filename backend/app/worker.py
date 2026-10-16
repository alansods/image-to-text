"""Worker Celery: executa as conversões fora da requisição HTTP e apaga o que passou de 1 hora."""

from pathlib import Path
from typing import Any

from celery import Celery
from celery.signals import worker_ready
from redis import Redis

from app.cleanup import cleanup_expired
from app.config import get_settings
from app.job_store import JobStore, utc_now
from app.orchestrator import run_job
from app.pipeline.base import Pipeline
from app.pipeline.runner import DocumentPipeline
from app.storage import JobFiles

_settings = get_settings()

celery_app = Celery(
    "image_to_text",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)
celery_app.conf.update(
    # Conversões são longas e pesadas: um job por vez por processo, confirmado só ao terminar,
    # para que um worker reiniciado no meio não perca o job.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_track_started=True,
    result_expires=3600,
    beat_schedule={
        "cleanup-expired-jobs": {"task": "cleanup_expired_jobs", "schedule": 300},
    },
)


def _context() -> tuple[JobStore, Path]:
    settings = get_settings()
    return JobStore(Redis.from_url(settings.redis_url)), Path(settings.data_dir)


def _pipeline() -> Pipeline:
    return DocumentPipeline()


@celery_app.task(name="ping")
def ping() -> str:
    """Verificação simples de que o worker está de pé."""
    return "pong"


@celery_app.task(name="convert_job")
def convert_job(job_id: str) -> None:
    store, root = _context()
    run_job(job_id, store, JobFiles(root, job_id), _pipeline())


@celery_app.task(name="cleanup_expired_jobs")
def cleanup_expired_jobs() -> list[str]:
    _, root = _context()
    return cleanup_expired(root, utc_now())


@worker_ready.connect
def _cleanup_on_start(**_kwargs: Any) -> None:
    cleanup_expired_jobs.delay()
