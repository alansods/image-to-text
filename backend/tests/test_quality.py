"""Avaliação de qualidade da página (spec image-preprocessing, design D13)."""

from functools import cache
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.models.document import (
    ILLEGIBLE,
    Alternative,
    BBox,
    Block,
    BlockType,
    QualityIssue,
    ReadingSource,
    Word,
    WordStatus,
)
from app.pipeline.base import PageInput
from app.pipeline.layout import analyze_layout
from app.pipeline.preprocess import load_pages, preprocess
from app.pipeline.quality import TEXT_TYPES, image_issues, reading_issues

FIXTURES = Path(__file__).parent / "fixtures" / "precision"


@cache
def page_of(case: str, index: int = 0) -> PageInput:
    return load_pages(next((FIXTURES / case).glob("input.*")))[index]


def issues_of(page: PageInput) -> list[QualityIssue]:
    pre = preprocess(page)
    layout = analyze_layout(pre.aligned, pre.normalized)
    return image_issues(pre, [b.bbox for b in layout.blocks if b.type in TEXT_TYPES])


def degraded(case: str, change) -> PageInput:  # type: ignore[no-untyped-def]
    page = page_of(case)
    return PageInput(page.index, np.ascontiguousarray(change(page.image)), page.page_size)


@pytest.mark.parametrize(
    ("case", "index"),
    [
        ("contrato_impresso", 0),
        ("contrato_foto", 0),
        ("artigo_duas_colunas", 0),
        ("cabeca_para_baixo", 0),
        ("enfase_mista", 0),
        ("recibo_tabela", 0),
        ("relatorio_tres_paginas", 0),
        ("relatorio_tres_paginas", 1),
    ],
)
def test_sharp_documents_are_not_flagged(case: str, index: int) -> None:
    assert issues_of(page_of(case, index)) == []


def test_small_screenshot_is_flagged_for_resolution() -> None:
    assert QualityIssue.RESOLUTION in issues_of(page_of("print_tela"))


@pytest.mark.parametrize("case", ["contrato_impresso", "contrato_foto"])
def test_blurred_photo_is_flagged_for_blur(case: str) -> None:
    page = degraded(case, lambda im: cv2.GaussianBlur(im, (0, 0), 2.0))
    assert QualityIssue.BLUR in issues_of(page)


def test_faded_page_is_flagged_for_contrast() -> None:
    page = degraded(
        "contrato_impresso", lambda im: (im.astype(np.float32) * 0.25 + 150).astype(np.uint8)
    )
    assert QualityIssue.CONTRAST in issues_of(page)


def paragraph(uncertain: int, total: int) -> Block:
    words = []
    for i in range(total):
        doubt = i < uncertain
        words.append(
            Word(
                id=f"w{i}",
                text=ILLEGIBLE if doubt and i % 2 else "palavra",
                bbox=BBox(x=i * 10, y=0, w=8, h=8),
                confidence=0.9,
                status=WordStatus.UNCERTAIN if doubt else WordStatus.ACCEPTED,
                alternatives=[]
                if not doubt or i % 2
                else [
                    Alternative(text="palavra", confidence=0.8, source=ReadingSource.PADDLE),
                    Alternative(text="paiavra", confidence=0.7, source=ReadingSource.DOCTR),
                ],
            )
        )
    return Block(
        id="b0",
        type=BlockType.PARAGRAPH,
        bbox=BBox(x=0, y=0, w=500, h=10),
        order=0,
        words=words,
        confidence=0.9,
    )


def test_many_doubts_flag_uncertain_reading() -> None:
    assert reading_issues([paragraph(3, 20)]) == [QualityIssue.UNCERTAIN_READING]


def test_few_doubts_are_fine() -> None:
    assert reading_issues([paragraph(2, 20)]) == []
    assert reading_issues([]) == []
