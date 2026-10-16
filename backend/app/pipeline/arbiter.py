"""Árbitro opcional com PaddleOCR-VL (spec reading-reconciliation, design D7).

Só é chamado para palavras que continuam divergentes depois da releitura, e só pode escolher
uma das leituras existentes ou "[ilegível]": qualquer outra resposta é descartada.
Liga com `ITT_ARBITER_ENABLED=true`.
"""

import re
from collections.abc import Callable
from functools import lru_cache
from typing import Any

import cv2
import numpy as np

from app.models.document import ILLEGIBLE
from app.pipeline.reading import Gray
from app.pipeline.reconcile import normalize_for_compare

MODEL = "PaddleOCR-VL-0.9B"
QUERY = "OCR:"

ReadImage = Callable[[Gray], str]


def validate_choice(answer: str, options: list[str]) -> str | None:
    """A resposta vale só se for uma das opções (ignorando aspas/traços/espaços) ou ilegível."""
    answer = answer.strip()
    if answer == ILLEGIBLE:
        return ILLEGIBLE
    wanted = normalize_for_compare(answer)
    if not wanted:
        return None
    for option in options:
        if normalize_for_compare(option) == wanted:
            return option
    return None


def _in_line(line_text: str, options: list[str]) -> str | None:
    """A opção que aparece como palavra inteira na linha lida, se só uma aparecer."""
    tokens = {normalize_for_compare(t) for t in re.split(r"\s+", line_text) if t}
    found = [o for o in options if normalize_for_compare(o) in tokens]
    return found[0] if len(found) == 1 else None


@lru_cache(maxsize=1)
def _model() -> Any:
    from paddleocr import DocVLM

    return DocVLM(model_name=MODEL)


def _read_with_vl(image: Gray) -> str:
    rgb = np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_GRAY2RGB))
    [result] = list(_model().predict(input={"image": rgb, "query": QUERY}, batch_size=1))
    return str(result["result"])


class VlArbiter:
    def __init__(self, read: ReadImage = _read_with_vl) -> None:
        self._read = read

    def choose(self, word: Gray, line: Gray, options: list[str]) -> str | None:
        choice = validate_choice(self._read(word), options)
        if choice is not None:
            return choice
        return _in_line(self._read(line), options)
