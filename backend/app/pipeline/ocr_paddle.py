"""Leitura primária com PaddleOCR (spec text-recognition, design D6).

Modelo latino `PP-OCRv6` (lê português e inglês sem escolha de idioma). O PaddleOCR dá a
confiança por linha e as caixas por fragmento de texto; a caixa de cada palavra é a união dos
fragmentos que a formam.
"""

import re
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

import cv2
import numpy as np

from app.models.document import BBox, ReadingSource
from app.pipeline.reading import Gray, ReadWord

DETECTION_MODEL = "PP-OCRv6_medium_det"
RECOGNITION_MODEL = "PP-OCRv6_medium_rec"

Point = Sequence[float]


@lru_cache(maxsize=1)
def _ocr() -> Any:
    from paddleocr import PaddleOCR

    return PaddleOCR(
        text_detection_model_name=DETECTION_MODEL,
        text_recognition_model_name=RECOGNITION_MODEL,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        return_word_box=True,
        # MKL-DNN quebra modelos do PaddleX em Linux x86 (ver D5).
        enable_mkldnn=False,
    )


@lru_cache(maxsize=1)
def _recognizer() -> Any:
    from paddleocr import TextRecognition

    return TextRecognition(model_name=RECOGNITION_MODEL, enable_mkldnn=False)


def _bgr(image: Gray) -> Any:
    return np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))


def split_words(
    text: str,
    confidence: float,
    tokens: Sequence[str],
    regions: Sequence[Sequence[Point]],
    line_box: Sequence[float],
    origin: tuple[float, float],
) -> list[ReadWord]:
    """Divide uma linha lida em palavras com caixa na página.

    `tokens`/`regions` são os fragmentos do PaddleOCR (`text_word`, `text_word_region`);
    `line_box` é a caixa (x1, y1, x2, y2) da linha. Se os fragmentos não reproduzem o texto,
    a linha é repartida em partes iguais por caractere.
    """
    ox, oy = origin
    x1, y1, x2, y2 = (float(v) for v in line_box)
    spans: list[tuple[float, float, float, float]] = []
    if "".join(tokens) == text and len(tokens) == len(regions):
        for token, region in zip(tokens, regions, strict=True):
            # Um fragmento pode cobrir mais de uma palavra ("á à"): reparte por caractere.
            xs = [float(p[0]) for p in region]
            ys = [float(p[1]) for p in region]
            left, step = min(xs), (max(xs) - min(xs)) / len(token)
            spans.extend(
                (left + i * step, min(ys), left + (i + 1) * step, max(ys))
                for i in range(len(token))
            )
    else:
        step = (x2 - x1) / max(len(text), 1)
        spans = [(x1 + i * step, y1, x1 + (i + 1) * step, y2) for i in range(len(text))]

    words = []
    for match in re.finditer(r"\S+", text):
        boxes = spans[match.start() : match.end()]
        left = min(b[0] for b in boxes)
        top = min(b[1] for b in boxes)
        right = max(b[2] for b in boxes)
        bottom = max(b[3] for b in boxes)
        if right <= left or bottom <= top:
            continue
        words.append(
            ReadWord(
                match.group(),
                BBox(x=ox + left, y=oy + top, w=right - left, h=bottom - top),
                float(confidence),
                ReadingSource.PADDLE,
            )
        )
    return words


class PaddleReader:
    source = ReadingSource.PADDLE

    def read_block(self, image: Gray, origin: tuple[float, float]) -> list[ReadWord]:
        result = _ocr().predict(_bgr(image))[0]
        words: list[ReadWord] = []
        for text, score, tokens, regions, box in zip(
            result["rec_texts"],
            result["rec_scores"],
            result["text_word"],
            result["text_word_region"],
            result["rec_boxes"],
            strict=True,
        ):
            words.extend(split_words(text, score, tokens, regions, box, origin))
        return words

    def read_snippet(self, image: Gray) -> tuple[str, float]:
        result = _recognizer().predict(_bgr(image))[0]
        return str(result["rec_text"]).strip(), float(result["rec_score"])
