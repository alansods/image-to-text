"""Worker Celery: configuração da fila (as tarefas de conversão entram nas tasks 3.x)."""

from app.config import get_settings
from app.worker import celery_app, ping


def test_worker_uses_configured_redis() -> None:
    settings = get_settings()

    assert celery_app.conf.broker_url == settings.redis_url
    assert celery_app.conf.result_backend == settings.redis_url


def test_worker_takes_one_job_at_a_time() -> None:
    # Conversões são pesadas: cada processo pega uma por vez e só confirma ao terminar.
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_acks_late is True


def test_ping_task_runs() -> None:
    assert ping.apply().get() == "pong"
