"""Leitura de uma página já organizada em blocos (specs text-recognition e reading-reconciliation).

Cada bloco de texto é recortado da página normalizada e lido pelos dois leitores; as leituras
são reconciliadas palavra a palavra. Figuras, fórmulas e (até a task 7) tabelas entram como
recorte do original. Parágrafos com marcador viram listas no fim.
"""

from dataclasses import dataclass
from statistics import mean
from typing import Protocol

import cv2
import numpy as np

from app.models.document import ILLEGIBLE, BBox, Block, BlockType, Page, Word, WordStatus
from app.pipeline.base import Image, PageInput, ProcessedPage
from app.pipeline.emphasis import mark_emphasis
from app.pipeline.layout import LayoutBlock, PageLayout, group_lists, size_for_text
from app.pipeline.preprocess import Preprocessed
from app.pipeline.reading import Gray, Reader
from app.pipeline.reconcile import reconcile_block

# Tabelas viram imagem até a task 7 (table-extraction).
IMAGE_TYPES = frozenset({BlockType.FIGURE, BlockType.FORMULA, BlockType.TABLE})
# Margem em volta do bloco para não cortar acentos e descendentes.
BLOCK_MARGIN = 8
# Releitura (D7): recorte da palavra com margem proporcional à altura, ampliado 2 vezes.
# Em cima e embaixo a margem é folgada para não cortar acentos.
REREAD_MARGIN = 0.25
# De lado a margem é curta: o espaço entre palavras é ~0,3 da altura e a vizinha não pode entrar.
REREAD_SIDE_MARGIN = 0.1
REREAD_SCALE = 2.0


class SecondaryReader(Reader, Protocol):
    @property
    def vocab(self) -> str: ...


class WordArbiter(Protocol):
    def choose(self, word: Gray, line: Gray, options: list[str]) -> str | None:
        """Escolhe uma das opções (ou "[ilegível]") olhando a palavra e a linha em volta."""
        ...


@dataclass(frozen=True)
class Readers:
    primary: Reader
    secondary: SecondaryReader
    arbiter: WordArbiter | None = None


def _crop(image: Gray, x1: float, y1: float, x2: float, y2: float) -> Gray:
    h, w = image.shape[:2]
    top, left = max(0, int(y1)), max(0, int(x1))
    return np.ascontiguousarray(
        image[top : min(h, int(np.ceil(y2))), left : min(w, int(np.ceil(x2)))]
    )


def _block_crop(image: Gray, box: BBox) -> tuple[Gray, tuple[float, float]]:
    x1, y1 = max(0.0, box.x - BLOCK_MARGIN), max(0.0, box.y - BLOCK_MARGIN)
    crop = _crop(image, x1, y1, box.x + box.w + BLOCK_MARGIN, box.y + box.h + BLOCK_MARGIN)
    return crop, (float(int(x1)), float(int(y1)))


def _word_crop(image: Gray, box: BBox) -> Gray:
    vertical, lateral = REREAD_MARGIN * box.h, REREAD_SIDE_MARGIN * box.h
    crop = _crop(
        image, box.x - lateral, box.y - vertical, box.x + box.w + lateral, box.y + box.h + vertical
    )
    return np.asarray(
        cv2.resize(crop, None, fx=REREAD_SCALE, fy=REREAD_SCALE, interpolation=cv2.INTER_CUBIC),
        dtype=np.uint8,
    )


def _read_text_block(
    normalized: Gray, layout_block: LayoutBlock, block_id: str, readers: Readers
) -> Block:
    crop, origin = _block_crop(normalized, layout_block.bbox)
    primary = readers.primary.read_block(crop, origin)
    secondary = readers.secondary.read_block(crop, origin)
    known = set(readers.secondary.vocab)
    blind = frozenset(c for w in primary for c in w.text if c not in known and not c.isspace())

    def reread(box: BBox) -> tuple[str, str]:
        snippet = _word_crop(normalized, box)
        return readers.primary.read_snippet(snippet)[0], readers.secondary.read_snippet(snippet)[0]

    arbiter = None
    if readers.arbiter is not None:
        judge = readers.arbiter
        line_box = layout_block.bbox

        def arbiter(box: BBox, options: list[str]) -> str | None:
            line = _crop(
                normalized,
                line_box.x,
                box.y - box.h / 2,
                line_box.x + line_box.w,
                box.y + box.h * 1.5,
            )
            return judge.choose(_word_crop(normalized, box), line, options)

    words = reconcile_block(primary, secondary, blind, block_id, reread, arbiter)
    if not words:
        words = [
            Word(
                id=f"{block_id}w0",
                text=ILLEGIBLE,
                bbox=layout_block.bbox,
                confidence=0,
                status=WordStatus.UNCERTAIN,
            )
        ]
    return Block(
        id=block_id,
        type=layout_block.type,
        bbox=layout_block.bbox,
        order=layout_block.order,
        column=layout_block.column,
        align=layout_block.align,
        rel_size=size_for_text(layout_block.rel_size, " ".join(w.text for w in words)),
        words=words,
        confidence=mean(w.confidence for w in words),
    )


def recognize_page(
    pre: Preprocessed,
    layout: PageLayout | None,
    page: PageInput,
    id_prefix: str,
    readers: Readers,
) -> ProcessedPage:
    height, width = pre.normalized.shape[:2]
    blocks: list[Block] = []
    crops: dict[str, Image] = {}
    for layout_block in layout.blocks if layout is not None and not pre.blank else []:
        block_id = f"{id_prefix}b{layout_block.order}"
        if layout_block.type in IMAGE_TYPES:
            box = layout_block.bbox
            crops[block_id] = _crop(pre.aligned, box.x, box.y, box.x + box.w, box.y + box.h)
            blocks.append(
                Block(
                    id=block_id,
                    type=BlockType.FIGURE
                    if layout_block.type is BlockType.TABLE
                    else layout_block.type,
                    bbox=box,
                    order=layout_block.order,
                    column=layout_block.column,
                    align=layout_block.align,
                    image_ref=f"crops/{block_id}.png",
                    confidence=layout_block.score,
                )
            )
        else:
            blocks.append(_read_text_block(pre.normalized, layout_block, block_id, readers))

    return ProcessedPage(
        page=Page(
            index=page.index,
            width=width,
            height=height,
            page_size=page.page_size,
            columns=layout.columns if layout is not None else 1,
            image_ref=f"pages/{page.index}.png",
            blank=pre.blank,
            blocks=group_lists(mark_emphasis(blocks, pre.normalized)),
        ),
        aligned=pre.aligned,
        crops=crops,
    )
