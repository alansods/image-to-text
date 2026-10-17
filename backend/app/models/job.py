"""Estado de uma conversão, guardado no Redis enquanto ela existe (no máximo 1 hora)."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Tudo da conversão é apagado no máximo 1 hora após o envio (spec job-processing).
JOB_TTL = timedelta(hours=1)


class JobState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


ACTIVE_STATES = frozenset({JobState.QUEUED, JobState.PROCESSING})


class JobStage(StrEnum):
    """Etapa real da conversão, mostrada na tela de progresso (spec job-processing)."""

    QUEUED = "queued"
    PREPARING = "preparing"  # endireitar e limpar a imagem
    LAYOUT = "layout"  # achar títulos, parágrafos, tabelas e figuras
    READING = "reading"  # as duas leituras e a reconciliação
    FINISHING = "finishing"  # montar o documento


class Job(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )

    id: str
    source_file: str
    created_at: datetime
    state: JobState = JobState.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    stage: JobStage = JobStage.QUEUED
    # Página em andamento (a partir de 1) e total; 0 enquanto o arquivo não foi aberto.
    page: int = Field(default=0, ge=0)
    pages: int = Field(default=0, ge=0)
    # Código do motivo da falha; o texto mostrado ao usuário fica no frontend (PT/EN).
    error: str | None = None

    @model_validator(mode="after")
    def _failed_has_reason(self) -> Self:
        if self.state is JobState.FAILED and self.error is None:
            raise ValueError("conversão com falha precisa de error")
        return self

    def with_progress(self, progress: int) -> Self:
        """Novo estado com o percentual atualizado, sem nunca diminuir."""
        return self.model_copy(update={"progress": max(self.progress, progress)})

    def is_active(self) -> bool:
        return self.state in ACTIVE_STATES

    def is_expired(self, now: datetime) -> bool:
        return now >= self.created_at + JOB_TTL
