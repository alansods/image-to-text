"""Estado das conversões no Redis. As chaves expiram sozinhas (nada sobrevive a 2 horas)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from redis import Redis

from app.models.job import JOB_TTL, Job, JobStage, JobState

# A chave vive o dobro do prazo, para que, depois de 1 hora, a conversão ainda responda "expirada"
# em vez de "não encontrada". Os arquivos em disco somem em até 1 hora (limpeza periódica).
_KEY_TTL = int(JOB_TTL.total_seconds() * 2)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _text(raw: bytes | str) -> str:
    return raw.decode() if isinstance(raw, bytes) else raw


class JobStore:
    def __init__(self, redis: Redis, now: Callable[[], datetime] = utc_now) -> None:
        self.redis = redis
        self.now = now

    @staticmethod
    def _key(job_id: str) -> str:
        return f"job:{job_id}"

    @staticmethod
    def _ip_key(ip: str) -> str:
        return f"ip:{ip}"

    def create(self, job: Job, client_ip: str) -> None:
        pipe = self.redis.pipeline()
        pipe.set(self._key(job.id), job.model_dump_json(), ex=_KEY_TTL)
        pipe.sadd(self._ip_key(client_ip), job.id)
        pipe.expire(self._ip_key(client_ip), _KEY_TTL)
        pipe.execute()

    def _load(self, job_id: str) -> Job | None:
        raw = self.redis.get(self._key(job_id))
        return Job.model_validate_json(raw) if raw else None

    def get(self, job_id: str) -> Job | None:
        job = self._load(job_id)
        if job is not None and job.is_expired(self.now()):
            return job.model_copy(update={"state": JobState.EXPIRED})
        return job

    def save(self, job: Job) -> None:
        self.redis.set(self._key(job.id), job.model_dump_json(), ex=_KEY_TTL, keepttl=False)

    def update(self, job_id: str, **changes: Any) -> Job | None:
        job = self._load(job_id)
        if job is None:
            return None
        updated = Job.model_validate(job.model_dump() | changes)
        self.save(updated)
        return updated

    def set_progress(
        self,
        job_id: str,
        progress: int,
        stage: JobStage | None = None,
        page: int | None = None,
        pages: int | None = None,
    ) -> None:
        job = self._load(job_id)
        if job is None or job.state is not JobState.PROCESSING:
            return
        job = job.with_progress(progress)
        step = {"stage": stage, "page": page, "pages": pages}
        self.save(job.model_copy(update={k: v for k, v in step.items() if v is not None}))

    def set_task_id(self, job_id: str, task_id: str) -> None:
        self.redis.set(f"{self._key(job_id)}:task", task_id, ex=_KEY_TTL)

    def task_id(self, job_id: str) -> str | None:
        raw = self.redis.get(f"{self._key(job_id)}:task")
        return _text(raw) if raw else None

    def active_count(self, client_ip: str) -> int:
        count = 0
        for raw_id in self.redis.smembers(self._ip_key(client_ip)):
            job = self.get(_text(raw_id))
            if job is not None and job.is_active():
                count += 1
            else:
                self.redis.srem(self._ip_key(client_ip), raw_id)
        return count
