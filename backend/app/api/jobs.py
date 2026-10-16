"""Rotas /jobs: enviar, acompanhar, obter o resultado, recortes e cancelar/apagar."""

from pathlib import Path
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, Depends, File, Response, UploadFile
from PIL import Image

from app.config import Settings, get_settings
from app.crops import png_bytes, word_crop
from app.dependencies import JobQueue, client_ip, get_job_store, get_queue
from app.errors import ApiError, ErrorCode, UploadRejectedError
from app.job_store import JobStore
from app.models.document import Document
from app.models.job import Job, JobState
from app.storage import JobFiles, new_job_id
from app.validation import inspect_source, save_limited

router = APIRouter(prefix="/jobs", tags=["jobs"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[JobStore, Depends(get_job_store)]
QueueDep = Annotated[JobQueue, Depends(get_queue)]


def _display_name(filename: str | None) -> str:
    """Só o nome do arquivo, sem pastas (vem do navegador e pode trazer qualquer coisa)."""
    name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    return name[:120] or "arquivo"


def _files(settings: Settings, job_id: str) -> JobFiles:
    try:
        return JobFiles(Path(settings.data_dir), job_id)
    except ValueError as error:
        raise ApiError(404, ErrorCode.NOT_FOUND) from error


def _get_job(store: JobStore, job_id: str) -> Job:
    job = store.get(job_id)
    if job is None:
        raise ApiError(404, ErrorCode.NOT_FOUND)
    return job


@router.post("", status_code=201)
def create_job(
    file: Annotated[list[UploadFile], File()],
    settings: SettingsDep,
    store: StoreDep,
    queue: QueueDep,
    ip: Annotated[str, Depends(client_ip)],
) -> dict[str, Any]:
    if len(file) != 1:
        raise UploadRejectedError(400, ErrorCode.MULTIPLE_FILES)
    if store.active_count(ip) >= settings.max_active_jobs:
        raise ApiError(429, ErrorCode.TOO_MANY_ACTIVE_JOBS)

    upload = file[0]
    job = Job(id=new_job_id(), source_file=_display_name(upload.filename), created_at=store.now())
    files = JobFiles(Path(settings.data_dir), job.id)
    files.create(created_at=job.created_at)
    try:
        received = files.dir / "upload.tmp"
        save_limited(upload.file, received, settings.max_upload_bytes)
        info = inspect_source(received)
        received.rename(files.source(info.extension))
    except BaseException:
        files.delete()
        raise

    store.create(job, client_ip=ip)
    store.set_task_id(job.id, queue.enqueue(job.id))
    return job.model_dump(mode="json")


@router.get("/{job_id}")
def get_job(job_id: str, store: StoreDep) -> dict[str, Any]:
    return _get_job(store, job_id).model_dump(mode="json")


def _done_document(job_id: str, settings: Settings, store: JobStore) -> tuple[Document, JobFiles]:
    job = _get_job(store, job_id)
    if job.state is JobState.EXPIRED:
        raise ApiError(410, ErrorCode.EXPIRED)
    if job.state in {JobState.CANCELLED, JobState.FAILED}:
        raise ApiError(404, ErrorCode.NOT_FOUND)
    files = _files(settings, job_id)
    if job.state is not JobState.DONE or not files.result.is_file():
        raise ApiError(409, ErrorCode.NOT_READY)
    return Document.model_validate_json(files.result.read_text(encoding="utf-8")), files


@router.get("/{job_id}/result")
def get_result(job_id: str, settings: SettingsDep, store: StoreDep) -> dict[str, Any]:
    document, _ = _done_document(job_id, settings, store)
    return document.model_dump(mode="json")


@router.get("/{job_id}/crops/{word_id}")
def get_word_crop(job_id: str, word_id: str, settings: SettingsDep, store: StoreDep) -> Response:
    document, files = _done_document(job_id, settings, store)
    for page in document.pages:
        for block in page.blocks:
            for word in block.all_words():
                if word.id == word_id:
                    with Image.open(files.page_image(page.index)) as image:
                        pixels = np.asarray(image.convert("L"))
                    return Response(png_bytes(word_crop(pixels, word.bbox)), media_type="image/png")
    raise ApiError(404, ErrorCode.NOT_FOUND)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, settings: SettingsDep, store: StoreDep, queue: QueueDep) -> Response:
    """Cancelar, "Converter outro" ou clicar no logotipo: tudo da conversão é apagado."""
    job = _get_job(store, job_id)
    if job.is_active():
        task_id = store.task_id(job_id)
        if task_id:
            queue.cancel(task_id)
    if job.state is not JobState.EXPIRED:
        store.update(job_id, state=JobState.CANCELLED, error=None)
    _files(settings, job_id).delete()
    return Response(status_code=204)
