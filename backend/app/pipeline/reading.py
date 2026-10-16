"""Formato comum das leituras: cada leitor devolve palavras assim, em coordenadas da página."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from app.models.document import BBox, ReadingSource

Gray = NDArray[np.uint8]


@dataclass(frozen=True)
class ReadWord:
    text: str
    bbox: BBox
    confidence: float
    source: ReadingSource


class Reader(Protocol):
    source: ReadingSource

    def read_block(self, image: Gray, origin: tuple[float, float]) -> list[ReadWord]:
        """Lê um recorte de bloco; `origin` é a posição do recorte na página."""
        ...

    def read_snippet(self, image: Gray) -> tuple[str, float]:
        """Lê um recorte pequeno (uma palavra) só com o reconhecedor, sem detecção."""
        ...
