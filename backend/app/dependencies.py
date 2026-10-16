"""Dependências injetadas nas rotas (substituídas nos testes por versões falsas)."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from redis import Redis

from app.config import Settings, get_settings
from app.job_store import JobStore


class JobQueue:
    """Fila de conversões. A implementação real usa o Celery."""

    def enqueue(self, job_id: str) -> str:
        from app.worker import convert_job

        return str(convert_job.delay(job_id).id)

    def cancel(self, task_id: str) -> None:
        from app.worker import celery_app

        # Interrompe até uma página demorada (spec: parar em até 10 segundos).
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")


@lru_cache
def _redis(url: str) -> Redis:
    return Redis.from_url(url)


def get_job_store(settings: Annotated[Settings, Depends(get_settings)]) -> JobStore:
    return JobStore(_redis(settings.redis_url))


def get_queue() -> JobQueue:
    return JobQueue()


def client_ip(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> str:
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"
