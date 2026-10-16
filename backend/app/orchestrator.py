"""Executa uma conversão página a página: percentual, cancelamento e falhas."""

import logging

from PIL import Image as PILImage

from app.job_store import JobStore
from app.models.document import (
    ILLEGIBLE,
    BBox,
    Block,
    BlockType,
    Document,
    Page,
    Word,
    WordStatus,
)
from app.models.job import JobState
from app.pipeline.base import Image, PageInput, Pipeline, PipelineUnavailableError
from app.storage import JobFiles

log = logging.getLogger(__name__)


def _percent(pages_done: float, total: int) -> int:
    """Proporcional às páginas; 100% só quando o documento está gravado."""
    return min(99, int(pages_done / total * 100))


def _save_png(image: Image, path: str) -> None:
    PILImage.fromarray(image).save(path, "PNG")


def _failed_page(page: PageInput) -> Page:
    """Página que não pôde ser lida: entra como a imagem original e uma dúvida "[ilegível]"."""
    height, width = page.image.shape[:2]
    whole = BBox(x=0, y=0, w=width, h=height)
    prefix = f"p{page.index}-"
    return Page(
        index=page.index,
        width=width,
        height=height,
        page_size=page.page_size,
        image_ref=f"pages/{page.index}.png",
        blocks=[
            Block(
                id=f"{prefix}failed-image",
                type=BlockType.FIGURE,
                bbox=whole,
                order=0,
                image_ref=f"pages/{page.index}.png",
                confidence=0,
            ),
            Block(
                id=f"{prefix}failed-text",
                type=BlockType.PARAGRAPH,
                bbox=whole,
                order=1,
                words=[
                    Word(
                        id=f"{prefix}failed-word",
                        text=ILLEGIBLE,
                        bbox=whole,
                        confidence=0,
                        status=WordStatus.UNCERTAIN,
                    )
                ],
                confidence=0,
            ),
        ],
    )


def _cancelled(store: JobStore, job_id: str) -> bool:
    job = store.get(job_id)
    return job is None or job.state in {JobState.CANCELLED, JobState.EXPIRED}


def run_job(job_id: str, store: JobStore, files: JobFiles, pipeline: Pipeline) -> None:
    job = store.get(job_id)
    if job is None or job.state is not JobState.QUEUED:
        return
    store.update(job_id, state=JobState.PROCESSING, progress=0)

    try:
        inputs = pipeline.load_pages(files.find_source())
    except PipelineUnavailableError:
        store.update(job_id, state=JobState.FAILED, error="pipeline_unavailable")
        return
    except Exception:
        log.exception("não foi possível abrir o arquivo da conversão %s", job_id)
        store.update(job_id, state=JobState.FAILED, error="unreadable")
        return

    total = len(inputs)
    pages: list[Page] = []
    failures = 0
    for page_input in inputs:
        if _cancelled(store, job_id):
            files.delete()
            return
        index = page_input.index

        def report(fraction: float, index: int = index) -> None:
            fraction = min(max(fraction, 0.0), 1.0)
            store.set_progress(job_id, _percent(index + fraction, total))

        try:
            result = pipeline.process_page(page_input, f"p{index}-", report)
            _save_png(result.aligned, str(files.page_image(index)))
            for block_id, crop in result.crops.items():
                _save_png(crop, str(files.dir / "crops" / f"{block_id}.png"))
            pages.append(result.page)
        except PipelineUnavailableError:
            store.update(job_id, state=JobState.FAILED, error="pipeline_unavailable")
            return
        except Exception:
            log.exception("falha na página %s da conversão %s", index, job_id)
            failures += 1
            _save_png(page_input.image, str(files.page_image(index)))
            pages.append(_failed_page(page_input))
        store.set_progress(job_id, _percent(index + 1, total))

    if _cancelled(store, job_id):
        files.delete()
        return
    if failures == total:
        store.update(job_id, state=JobState.FAILED, error="unreadable")
        return

    document = Document(id=job_id, source_file=job.source_file, pages=pages)
    files.result.write_text(document.model_dump_json(), encoding="utf-8")
    store.update(job_id, state=JobState.DONE, progress=100)
