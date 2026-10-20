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
from app.pipeline.completeness import BLOCK_MARGIN as ORPHAN_MARGIN
from app.pipeline.completeness import missing_lines, orphan_regions, stray_strokes
from app.pipeline.dashes import dash_shape
from app.pipeline.emphasis import mark_emphasis
from app.pipeline.layout import (
    LayoutBlock,
    PageLayout,
    group_lists,
    looks_handwritten,
    relative_size,
    size_for_text,
)
from app.pipeline.preprocess import Preprocessed, median_char_height
from app.pipeline.quality import TEXT_TYPES, image_issues, reading_issues
from app.pipeline.reading import Gray, Reader
from app.pipeline.reconcile import reconcile_block
from app.pipeline.rings import Height, ring_height
from app.pipeline.sizes import estimate_font_pt
from app.pipeline.tables import assign_words, table_structure, trustworthy

# Tabela só vira imagem quando a estrutura não é confiável (spec table-extraction).
IMAGE_TYPES = frozenset({BlockType.FIGURE, BlockType.FORMULA, BlockType.TABLE})
# Principal com menos da metade das palavras do segundo leitor: relê no modo sensível.
SENSITIVE_RATIO = 0.5
# Largura A4 em pontos: só para chamadas sem o tamanho de folha (testes).
PAGE_WIDTH_PT = 595.0
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


def _read_words(normalized: Gray, region: BBox, word_prefix: str, readers: Readers) -> list[Word]:
    """Lê uma região com os dois leitores e reconcilia (releitura e árbitro inclusos)."""
    crop, origin = _block_crop(normalized, region)
    primary = readers.primary.read_block(crop, origin)
    secondary = readers.secondary.read_block(crop, origin)
    if len(primary) < SENSITIVE_RATIO * len(secondary):
        # O principal viu bem menos que o segundo: relê com o detector mais sensível (D6).
        primary = readers.primary.read_block(crop, origin, sensitive=True)
    known = set(readers.secondary.vocab)
    blind = frozenset(c for w in primary for c in w.text if c not in known and not c.isspace())

    def reread(box: BBox) -> tuple[tuple[str, float], tuple[str, float]]:
        snippet = _word_crop(normalized, box)
        return readers.primary.read_snippet(snippet), readers.secondary.read_snippet(snippet)

    arbiter = None
    if readers.arbiter is not None:
        judge = readers.arbiter

        def arbiter(box: BBox, options: list[str]) -> str | None:
            line = _crop(
                normalized,
                region.x,
                box.y - box.h / 2,
                region.x + region.w,
                box.y + box.h * 1.5,
            )
            return judge.choose(_word_crop(normalized, box), line, options)

    def shape(box: BBox) -> tuple[str, BBox | None] | None:
        return dash_shape(normalized, box)

    def ring(box: BBox) -> Height | None:
        return ring_height(normalized, box)

    return reconcile_block(primary, secondary, blind, word_prefix, reread, arbiter, shape, ring)


def _illegible(word_id: str, box: BBox) -> Word:
    return Word(id=word_id, text=ILLEGIBLE, bbox=box, confidence=0, status=WordStatus.UNCERTAIN)


def _read_text_block(
    normalized: Gray,
    layout_block: LayoutBlock,
    block_id: str,
    readers: Readers,
    points_per_pixel: float | None = None,
) -> Block:
    words = _read_words(normalized, layout_block.bbox, block_id, readers)
    if not words:
        words = [_illegible(f"{block_id}w0", layout_block.bbox)]
    page_scale = (
        PAGE_WIDTH_PT / normalized.shape[1] if points_per_pixel is None else points_per_pixel
    )
    return Block(
        id=block_id,
        type=layout_block.type,
        bbox=layout_block.bbox,
        order=layout_block.order,
        column=layout_block.column,
        align=layout_block.align,
        rel_size=size_for_text(layout_block.rel_size, " ".join(w.text for w in words)),
        font_pt=estimate_font_pt(words, normalized, page_scale),
        words=words,
        confidence=mean(w.confidence for w in words),
    )


def _read_table(
    pre: Preprocessed, layout_block: LayoutBlock, block_id: str, readers: Readers
) -> Block | None:
    """Tabela estruturada com células lidas; `None` se a estrutura não for confiável."""
    box = layout_block.bbox
    x1, y1 = max(0.0, box.x - BLOCK_MARGIN), max(0.0, box.y - BLOCK_MARGIN)
    crop = _crop(pre.aligned, x1, y1, box.x + box.w + BLOCK_MARGIN, box.y + box.h + BLOCK_MARGIN)
    cells = table_structure(crop, (float(int(x1)), float(int(y1))))
    if not trustworthy(cells):
        return None
    filled = assign_words(cells, _read_words(pre.normalized, box, block_id, readers))
    if filled is None:
        return None
    words = [w for cell in filled for w in cell.words]
    return Block(
        id=block_id,
        type=BlockType.TABLE,
        bbox=box,
        order=layout_block.order,
        column=layout_block.column,
        cells=filled,
        confidence=mean(w.confidence for w in words) if words else layout_block.score,
    )


# Metade ou mais das palavras em dúvida + tinta sem forma de letra impressa = escrita à mão.
HANDWRITTEN_DOUBTS = 0.5


def _handwritten(pre: Preprocessed, block: Block, char_height: float) -> bool:
    words = block.words
    if not words:
        return False
    doubtful = sum(w.status is WordStatus.UNCERTAIN for w in words) / len(words)
    b = block.bbox
    crop = _crop(pre.normalized, b.x, b.y, b.x + b.w, b.y + b.h)
    return doubtful >= HANDWRITTEN_DOUBTS and looks_handwritten(crop, char_height)


# Texto com ao menos metade da área dentro de uma figura faz parte da imagem (D18).
INSIDE_FIGURE = 0.5


def _overlap_box(a: BBox, b: BBox) -> tuple[float, float, float, float] | None:
    x1, y1 = max(a.x, b.x), max(a.y, b.y)
    x2, y2 = min(a.x + a.w, b.x + b.w), min(a.y + a.h, b.y + b.h)
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None


def _settle_figure_overlaps(blocks: list[Block], crops: dict[str, Image]) -> list[Block]:
    """Texto não aparece duas vezes: o que está (quase) todo dentro de uma figura fica só na
    imagem; o que só encosta continua texto e é apagado (branco) do recorte da figura."""
    figures = [b for b in blocks if b.id in crops]
    result = []
    for block in blocks:
        if block.id in crops or not block.words:
            result.append(block)
            continue
        area = block.bbox.w * block.bbox.h
        overlaps = [(f, _overlap_box(block.bbox, f.bbox)) for f in figures]
        inside = max(((o[2] - o[0]) * (o[3] - o[1]) / area for _, o in overlaps if o), default=0.0)
        if inside >= INSIDE_FIGURE:
            continue
        for figure, o in overlaps:
            if o is None:
                continue
            crop = crops[figure.id] = np.array(crops[figure.id], copy=True)
            x1, y1 = int(o[0] - figure.bbox.x), int(o[1] - figure.bbox.y)
            x2, y2 = int(np.ceil(o[2] - figure.bbox.x)), int(np.ceil(o[3] - figure.bbox.y))
            crop[max(0, y1) : y2, max(0, x1) : x2] = 255
        result.append(block)
    return result


def _reading_sort(words: list[Word]) -> list[Word]:
    """Linhas de cima para baixo; dentro da linha, da esquerda para a direita."""
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda w: w.bbox.y):
        center = word.bbox.y + word.bbox.h / 2
        first = lines[-1][0].bbox if lines else None
        if first is not None and first.y <= center <= first.y + first.h:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [w for line in lines for w in sorted(line, key=lambda w: w.bbox.x)]


def _fill_missing_lines(
    normalized: Gray, block: Block, char_height: float, readers: Readers
) -> Block:
    """Linha visível sem palavra lida: relê a linha; sem leitura, "[ilegível]" (7.2)."""
    if not block.words:
        return block
    added: list[Word] = []
    lines = missing_lines(normalized, block.bbox, [w.bbox for w in block.words], char_height)
    for index, line in enumerate(lines):
        prefix = f"{block.id}m{index}"
        added.extend(
            _read_words(normalized, line, prefix, readers) or [_illegible(f"{prefix}w0", line)]
        )
    if not added:
        return block
    words = _reading_sort([*block.words, *added])
    return block.model_copy(
        update={"words": words, "confidence": mean(w.confidence for w in words)}
    )


def _orphan_blocks(
    pre: Preprocessed, blocks: list[Block], char_height: float, id_prefix: str, readers: Readers
) -> tuple[list[Block], dict[str, Image]]:
    """Tinta fora de todos os blocos vira bloco novo, lido ou como figura (7.1). Traços soltos
    compridos (borda do papel) entram como figura sem leitura."""
    found: list[Block] = []
    crops: dict[str, Image] = {}
    known = [b.bbox for b in blocks]
    # A região órfã pode abraçar blocos já lidos (o contorno do papel liga tudo): eles saem da
    # imagem lida e de qualquer palavra que caia neles, para nada ser lido duas vezes.
    unread = pre.normalized.copy()
    for b in known:
        top, left = max(0, int(b.y) - ORPHAN_MARGIN), max(0, int(b.x) - ORPHAN_MARGIN)
        unread[top : int(b.y + b.h) + ORPHAN_MARGIN, left : int(b.x + b.w) + ORPHAN_MARGIN] = 255

    def already_read(word: Word) -> bool:
        cx, cy = word.bbox.x + word.bbox.w / 2, word.bbox.y + word.bbox.h / 2
        return any(b.x <= cx <= b.x + b.w and b.y <= cy <= b.y + b.h for b in known)

    regions = orphan_regions(pre.normalized, known, char_height)
    for index, region in enumerate(regions):
        block_id = f"{id_prefix}o{index}"
        words = [w for w in _read_words(unread, region, block_id, readers) if not already_read(w)]
        if words:
            crop, _origin = _block_crop(pre.normalized, region)
            text = " ".join(w.text for w in words)
            found.append(
                Block(
                    id=block_id,
                    type=BlockType.PARAGRAPH,
                    bbox=region,
                    order=0,
                    rel_size=size_for_text(relative_size(crop, char_height), text),
                    words=words,
                    confidence=mean(w.confidence for w in words),
                )
            )
        else:
            r = region
            crops[block_id] = _crop(pre.aligned, r.x, r.y, r.x + r.w, r.y + r.h)
            found.append(
                Block(
                    id=block_id,
                    type=BlockType.FIGURE,
                    bbox=region,
                    order=0,
                    image_ref=f"crops/{block_id}.png",
                    confidence=0,
                )
            )
    for index, r in enumerate(stray_strokes(pre.normalized, known, char_height)):
        block_id = f"{id_prefix}s{index}"
        crops[block_id] = _crop(pre.aligned, r.x, r.y, r.x + r.w, r.y + r.h)
        found.append(
            Block(
                id=block_id,
                type=BlockType.FIGURE,
                bbox=r,
                order=0,
                image_ref=f"crops/{block_id}.png",
                confidence=0,
            )
        )
    return found, crops


def _insert_in_reading_order(blocks: list[Block], extra: list[Block]) -> list[Block]:
    """Cada bloco novo entra antes do primeiro bloco abaixo dele na mesma faixa horizontal."""
    result = sorted(blocks, key=lambda b: b.order)
    for block in extra:
        b = block.bbox

        def below(other: Block, b: BBox = b) -> bool:
            o = other.bbox
            overlaps = min(o.x + o.w, b.x + b.w) > max(o.x, b.x)
            return overlaps and o.y > b.y

        position = next((i for i, other in enumerate(result) if below(other)), len(result))
        result.insert(position, block)
    return [b.model_copy(update={"order": i}) for i, b in enumerate(result)]


def recognize_page(
    pre: Preprocessed,
    layout: PageLayout | None,
    page: PageInput,
    id_prefix: str,
    readers: Readers,
) -> ProcessedPage:
    height, width = pre.normalized.shape[:2]
    char_height = median_char_height(pre.normalized) if not pre.blank else 0.0
    blocks: list[Block] = []
    crops: dict[str, Image] = {}
    for layout_block in layout.blocks if layout is not None and not pre.blank else []:
        block_id = f"{id_prefix}b{layout_block.order}"
        if layout_block.type is BlockType.TABLE:
            table = _read_table(pre, layout_block, block_id, readers)
            if table is not None:
                blocks.append(table)
                continue
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
            block = _read_text_block(
                pre.normalized, layout_block, block_id, readers, page.page_size.w_pt / width
            )
            if _handwritten(pre, block, char_height):
                # Assinatura, rubrica ou preenchimento à mão: fica a imagem do original (D18).
                box = block.bbox
                crops[block_id] = _crop(pre.aligned, box.x, box.y, box.x + box.w, box.y + box.h)
                block = Block(
                    id=block_id,
                    type=BlockType.FIGURE,
                    bbox=box,
                    order=block.order,
                    column=block.column,
                    align=block.align,
                    image_ref=f"crops/{block_id}.png",
                    confidence=layout_block.score,
                )
            blocks.append(block)

    if blocks:
        blocks = [_fill_missing_lines(pre.normalized, b, char_height, readers) for b in blocks]
        extra, extra_crops = _orphan_blocks(pre, blocks, char_height, id_prefix, readers)
        blocks = _insert_in_reading_order(blocks, extra)
        crops.update(extra_crops)
        blocks = _settle_figure_overlaps(blocks, crops)
    blocks = group_lists(mark_emphasis(blocks, pre.normalized))
    issues = []
    if layout is not None and not pre.blank:
        text_boxes = [b.bbox for b in layout.blocks if b.type in TEXT_TYPES]
        issues = image_issues(pre, text_boxes) + reading_issues(blocks)
    return ProcessedPage(
        page=Page(
            index=page.index,
            width=width,
            height=height,
            page_size=page.page_size,
            columns=layout.columns if layout is not None else 1,
            image_ref=f"pages/{page.index}.png",
            blank=pre.blank,
            quality_issues=issues,
            blocks=blocks,
        ),
        aligned=pre.aligned,
        crops=crops,
    )
