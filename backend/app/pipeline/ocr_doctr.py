"""Segunda leitura com docTR (spec text-recognition, design D6).

Detector `db_resnet50` e reconhecedor multilíngue (PARSeq) publicado no Hugging Face, que
conhece os acentos do português. O vocabulário dele não tem ª, º, — e aspas curvas: a
reconciliação trata esses caracteres como "cegos" (D7).
"""

from functools import lru_cache
from typing import Any

import cv2
import numpy as np

from app.models.document import BBox, ReadingSource
from app.pipeline.reading import Gray, ReadWord

DETECTION_MODEL = "db_resnet50"
RECOGNITION_REPO = "Felix92/doctr-torch-parseq-multilingual-v1"
# O detector redimensiona a entrada para 1024 px: recortes pequenos são colados num fundo
# branco desse tamanho, senão as letras ficam gigantes e a detecção se desfaz.
DETECTION_SIZE = 1024
# Calibração (D7): o docTR multilíngue dá confiança ~1,0 até a leituras erradas e erra ~15 vezes
# mais que o PaddleOCR no conjunto de teste. Sem isso, a leitura dele venceria as dúvidas.
CONFIDENCE_SCALE = 0.9


@lru_cache(maxsize=1)
def _models() -> tuple[Any, Any]:
    from doctr.models import from_hub, ocr_predictor, recognition_predictor

    recognizer = from_hub(RECOGNITION_REPO)
    pages = ocr_predictor(
        det_arch=DETECTION_MODEL,
        reco_arch=recognizer,
        pretrained=True,
        assume_straight_pages=True,
    )
    return pages, recognition_predictor(recognizer)


def _rgb(image: Gray) -> Any:
    return np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_GRAY2RGB))


class DoctrReader:
    source = ReadingSource.DOCTR

    @property
    def vocab(self) -> str:
        return str(_models()[0].reco_predictor.model.vocab)

    def read_block(
        self, image: Gray, origin: tuple[float, float], sensitive: bool = False
    ) -> list[ReadWord]:
        crop_h, crop_w = image.shape[:2]
        height, width = max(crop_h, DETECTION_SIZE), max(crop_w, DETECTION_SIZE)
        canvas = np.full((height, width), 255, dtype=np.uint8)
        canvas[:crop_h, :crop_w] = image
        ox, oy = origin
        page = _models()[0]([_rgb(canvas)]).pages[0]
        words = []
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    (x1, y1), (x2, y2) = word.geometry
                    left, top = x1 * width, y1 * height
                    right, bottom = min(x2 * width, crop_w), min(y2 * height, crop_h)
                    if left >= crop_w or top >= crop_h:
                        continue
                    box = BBox(
                        x=ox + left,
                        y=oy + top,
                        w=max(right - left, 1.0),
                        h=max(bottom - top, 1.0),
                    )
                    confidence = float(word.confidence) * CONFIDENCE_SCALE
                    words.append(ReadWord(word.value, box, confidence, self.source))
        return words

    def read_snippet(self, image: Gray) -> tuple[str, float]:
        [(text, confidence)] = _models()[1]([_rgb(image)])
        return str(text).strip(), float(confidence) * CONFIDENCE_SCALE
