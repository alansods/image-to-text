"""Contrato entre o orquestrador e o pipeline de conversão.

O pipeline não grava nada em disco nem conhece filas: recebe imagens e devolve dados.
Quem salva as imagens, publica o percentual e trata falhas é `app.orchestrator`.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from app.models.document import Page, PageSize

Image = NDArray[np.uint8]


@dataclass(frozen=True)
class PageInput:
    """Uma página do arquivo enviado, ainda sem tratamento."""

    index: int
    image: Image
    page_size: PageSize


@dataclass(frozen=True)
class ProcessedPage:
    page: Page
    # Original endireitado: fundo das imagens recortadas e dos recortes de conferência.
    aligned: Image
    # Recortes do original para blocos figura/fórmula, por id do bloco.
    crops: dict[str, Image] = field(default_factory=dict)


class PipelineUnavailableError(RuntimeError):
    """O pipeline de reconhecimento ainda não está instalado neste servidor."""


class Pipeline(Protocol):
    def load_pages(self, source: Path) -> list[PageInput]: ...

    def process_page(
        self, page: PageInput, id_prefix: str, report: Callable[[float], None]
    ) -> ProcessedPage:
        """`report(fração)` informa o andamento dentro da página (0 a 1)."""
        ...


class UnavailablePipeline:
    """Usado enquanto as tasks 4 a 7 não existem: toda conversão falha com motivo claro."""

    def load_pages(self, source: Path) -> list[PageInput]:
        raise PipelineUnavailableError

    def process_page(
        self, page: PageInput, id_prefix: str, report: Callable[[float], None]
    ) -> ProcessedPage:
        raise PipelineUnavailableError
