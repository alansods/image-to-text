"""Rotas /jobs (specs file-upload e job-processing, lado do servidor)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import fakeredis
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings, get_settings
from app.dependencies import JobQueue, get_job_store, get_queue
from app.job_store import JobStore
from app.main import app
from app.models.document import BBox, Block, BlockType, Document, Page, PageSize, Word, WordStatus
from app.models.job import JobState
from app.storage import JobFiles
from tests.conftest import image_bytes, pdf_bytes, png_bytes

T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


class FakeQueue(JobQueue):
    def __init__(self) -> None:
        self.enqueued: list[str] = []
        self.cancelled: list[str] = []

    def enqueue(self, job_id: str) -> str:
        self.enqueued.append(job_id)
        return f"task-{job_id}"

    def cancel(self, task_id: str) -> None:
        self.cancelled.append(task_id)


class Clock:
    now = T0

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(clock: Clock) -> JobStore:
    return JobStore(fakeredis.FakeRedis(), now=clock)


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=str(tmp_path), max_upload_bytes=200_000)


@pytest.fixture
def client(store: JobStore, queue: FakeQueue, settings: Settings) -> Iterator[TestClient]:
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client: TestClient, name: str, content: bytes) -> dict[str, object]:
    response = client.post("/jobs", files={"file": (name, content)})
    return {"status": response.status_code, "json": response.json()}


class TestCreate:
    def test_valid_image_creates_queued_job_and_enqueues_it(
        self, client: TestClient, queue: FakeQueue, store: JobStore, settings: Settings
    ) -> None:
        response = client.post("/jobs", files={"file": ("foto.png", png_bytes())})

        assert response.status_code == 201
        job = response.json()
        assert job["state"] == "queued" and job["progress"] == 0
        assert job["source_file"] == "foto.png"
        assert queue.enqueued == [job["id"]]
        assert store.task_id(job["id"]) == f"task-{job['id']}"
        assert JobFiles(Path(settings.data_dir), job["id"]).source("png").is_file()

    def test_keeps_only_the_base_name_of_the_uploaded_file(self, client: TestClient) -> None:
        response = client.post("/jobs", files={"file": ("../../etc/contrato.pdf", pdf_bytes())})

        assert response.json()["source_file"] == "contrato.pdf"

    def test_two_files_are_rejected(self, client: TestClient, queue: FakeQueue) -> None:
        response = client.post(
            "/jobs",
            files=[("file", ("a.png", png_bytes())), ("file", ("b.png", png_bytes()))],
        )

        assert response.status_code == 400
        assert response.json() == {"error": "multiple_files"}
        assert queue.enqueued == []

    def test_gif_is_rejected(self, client: TestClient) -> None:
        assert upload(client, "a.gif", image_bytes("GIF")) == {
            "status": 415,
            "json": {"error": "unsupported_format"},
        }

    def test_file_over_limit_is_rejected_and_not_kept(
        self, client: TestClient, settings: Settings
    ) -> None:
        assert upload(client, "grande.png", b"\x89PNG\r\n\x1a\n" + b"0" * 300_000) == {
            "status": 413,
            "json": {"error": "file_too_large"},
        }
        assert list(Path(settings.data_dir).iterdir()) == []

    def test_pdf_with_password_is_rejected(self, client: TestClient) -> None:
        assert upload(client, "s.pdf", pdf_bytes(password="x"))["json"] == {"error": "pdf_password"}

    def test_fourth_active_job_from_same_address_is_rejected(
        self, client: TestClient, queue: FakeQueue
    ) -> None:
        for _ in range(3):
            assert upload(client, "a.png", png_bytes())["status"] == 201

        assert upload(client, "a.png", png_bytes()) == {
            "status": 429,
            "json": {"error": "too_many_active_jobs"},
        }
        assert len(queue.enqueued) == 3

    def test_finished_jobs_do_not_count_for_the_limit(
        self, client: TestClient, store: JobStore
    ) -> None:
        ids = [upload(client, "a.png", png_bytes())["json"]["id"] for _ in range(3)]  # type: ignore[index]
        store.update(str(ids[0]), state=JobState.DONE, progress=100)

        assert upload(client, "a.png", png_bytes())["status"] == 201


class TestRead:
    def test_get_returns_state_and_progress(self, client: TestClient, store: JobStore) -> None:
        job_id = client.post("/jobs", files={"file": ("a.png", png_bytes())}).json()["id"]
        store.update(job_id, state=JobState.PROCESSING)
        store.set_progress(job_id, 42)

        body = client.get(f"/jobs/{job_id}").json()

        assert body["state"] == "processing" and body["progress"] == 42

    def test_unknown_job_is_not_found(self, client: TestClient) -> None:
        response = client.get("/jobs/nao-existe")

        assert response.status_code == 404
        assert response.json() == {"error": "not_found"}

    def test_job_older_than_one_hour_is_expired_and_has_no_result(
        self, client: TestClient, store: JobStore, clock: Clock
    ) -> None:
        job_id = client.post("/jobs", files={"file": ("a.png", png_bytes())}).json()["id"]
        store.update(job_id, state=JobState.DONE, progress=100)
        clock.now = T0 + timedelta(minutes=61)

        assert client.get(f"/jobs/{job_id}").json()["state"] == "expired"
        assert client.get(f"/jobs/{job_id}/result").status_code == 410

    def test_result_before_done_is_not_ready(self, client: TestClient) -> None:
        job_id = client.post("/jobs", files={"file": ("a.png", png_bytes())}).json()["id"]

        response = client.get(f"/jobs/{job_id}/result")

        assert response.status_code == 409
        assert response.json() == {"error": "not_ready"}


def finish_with_document(store: JobStore, settings: Settings, job_id: str) -> None:
    files = JobFiles(Path(settings.data_dir), job_id)
    page_image = np.full((200, 300), 255, np.uint8)
    page_image[90:110, 100:160] = 0
    Image.fromarray(page_image).save(files.page_image(0))
    word = Word(
        id="p0-w0",
        text="SlLVA",
        bbox=BBox(x=100, y=90, w=60, h=20),
        confidence=0.6,
        status=WordStatus.ACCEPTED,
    )
    block = Block(
        id="p0-b0",
        type=BlockType.PARAGRAPH,
        bbox=BBox(x=0, y=0, w=300, h=200),
        order=0,
        words=[word],
        confidence=0.6,
    )
    document = Document(
        id=job_id,
        source_file="a.png",
        pages=[
            Page(
                index=0,
                width=300,
                height=200,
                page_size=PageSize(w_pt=841.89, h_pt=595.28),
                image_ref="pages/0.png",
                blocks=[block],
            )
        ],
    )
    files.result.write_text(document.model_dump_json())
    store.update(job_id, state=JobState.DONE, progress=100)


class TestResult:
    def test_done_job_returns_document(
        self, client: TestClient, store: JobStore, settings: Settings
    ) -> None:
        job_id = client.post("/jobs", files={"file": ("a.png", png_bytes())}).json()["id"]
        finish_with_document(store, settings, job_id)

        document = Document.model_validate(client.get(f"/jobs/{job_id}/result").json())

        assert document.pages[0].blocks[0].words[0].text == "SlLVA"

    def test_word_crop_is_a_png_around_the_word(
        self, client: TestClient, store: JobStore, settings: Settings
    ) -> None:
        job_id = client.post("/jobs", files={"file": ("a.png", png_bytes())}).json()["id"]
        finish_with_document(store, settings, job_id)

        response = client.get(f"/jobs/{job_id}/crops/p0-w0")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")

    def test_unknown_word_crop_is_not_found(
        self, client: TestClient, store: JobStore, settings: Settings
    ) -> None:
        job_id = client.post("/jobs", files={"file": ("a.png", png_bytes())}).json()["id"]
        finish_with_document(store, settings, job_id)

        assert client.get(f"/jobs/{job_id}/crops/nada").status_code == 404


class TestDelete:
    def test_cancel_stops_task_and_deletes_files(
        self, client: TestClient, queue: FakeQueue, store: JobStore, settings: Settings
    ) -> None:
        job_id = client.post("/jobs", files={"file": ("a.png", png_bytes())}).json()["id"]
        store.update(job_id, state=JobState.PROCESSING)

        response = client.delete(f"/jobs/{job_id}")

        assert response.status_code == 204
        assert queue.cancelled == [f"task-{job_id}"]
        assert not JobFiles(Path(settings.data_dir), job_id).exists()
        body = client.get(f"/jobs/{job_id}").json()
        assert body["state"] == "cancelled" and body["error"] is None

    def test_convert_another_deletes_finished_job_files(
        self, client: TestClient, store: JobStore, settings: Settings
    ) -> None:
        job_id = client.post("/jobs", files={"file": ("a.png", png_bytes())}).json()["id"]
        finish_with_document(store, settings, job_id)

        client.delete(f"/jobs/{job_id}")

        assert not JobFiles(Path(settings.data_dir), job_id).exists()
        assert client.get(f"/jobs/{job_id}/result").status_code in {404, 410}

    def test_delete_unknown_job_is_not_found(self, client: TestClient) -> None:
        assert client.delete("/jobs/nao-existe").status_code == 404
