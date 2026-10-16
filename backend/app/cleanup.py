"""Apaga arquivos de conversões com mais de 1 hora (spec job-processing: "Nada guardado")."""

import logging
from datetime import datetime
from pathlib import Path

from app.models.job import JOB_TTL
from app.storage import job_dirs

log = logging.getLogger(__name__)


def cleanup_expired(root: Path, now: datetime) -> list[str]:
    removed: list[str] = []
    for files in job_dirs(root):
        try:
            created_at = files.created_at()
        except (OSError, ValueError):
            created_at = None  # pasta incompleta (envio interrompido): sempre apagar
        if created_at is None or now - created_at >= JOB_TTL:
            files.delete()
            removed.append(files.dir.name)
    if removed:
        log.info("conversões apagadas por prazo: %d", len(removed))
    return sorted(removed)
