"""Arquivos de uma conversão em disco: `<data_dir>/<id>/`. Tudo é apagado de uma vez."""

import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_job_id() -> str:
    """Identificador imprevisível: sem login, quem conhece o id acessa a conversão."""
    return secrets.token_urlsafe(16)


class JobFiles:
    def __init__(self, root: Path, job_id: str) -> None:
        if not _ID_PATTERN.match(job_id):
            raise ValueError("identificador de conversão inválido")
        self.root = root
        self.dir = root / job_id

    def create(self, created_at: datetime) -> None:
        for sub in ("pages", "crops", "exports"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        (self.dir / "created_at").write_text(created_at.isoformat(), encoding="utf-8")

    def created_at(self) -> datetime:
        return datetime.fromisoformat((self.dir / "created_at").read_text(encoding="utf-8"))

    def exists(self) -> bool:
        return self.dir.is_dir()

    def source(self, extension: str) -> Path:
        return self.dir / f"source.{extension}"

    def find_source(self) -> Path:
        return next(self.dir.glob("source.*"))

    def page_image(self, index: int) -> Path:
        return self.dir / "pages" / f"{index}.png"

    @property
    def result(self) -> Path:
        return self.dir / "result.json"

    def delete(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def job_dirs(root: Path) -> list[JobFiles]:
    if not root.is_dir():
        return []
    return [
        JobFiles(root, d.name) for d in root.iterdir() if d.is_dir() and _ID_PATTERN.match(d.name)
    ]
