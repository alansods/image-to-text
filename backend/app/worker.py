"""Worker Celery: executa as conversões fora da requisição HTTP."""

from celery import Celery

from app.config import get_settings

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
)


@celery_app.task(name="ping")
def ping() -> str:
    """Verificação simples de que o worker está de pé."""
    return "pong"
