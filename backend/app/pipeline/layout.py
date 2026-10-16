"""Detecção de layout (spec layout-detection, design D5).

O modelo `PP-DocLayout_plus-L` encontra os blocos; a organização é nossa: duas passadas de
confiança, correção de "texto" que na verdade é desenho, ordem de leitura com colunas,
alinhamento, tamanho relativo e agrupamento de listas. Coordenadas em pixels da página
pré-processada.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import pairwise
from statistics import median
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from app.models.document import Alignment, BBox, Block, BlockType, ListItem
from app.pipeline.base import Image
from app.pipeline.preprocess import median_char_height

Gray = NDArray[np.uint8]

STRONG_SCORE = 0.5
WEAK_SCORE = 0.3
# Caixa fraca só entra se quase não se sobrepõe a nada já aceito.
MAX_WEAK_OVERLAP = 0.3
# Bloco que ocupa ao menos isto da largura útil separa seções (título, resumo, parágrafo largo).
FULL_WIDTH = 0.6

_LABELS: dict[str, BlockType] = {
    "doc_title": BlockType.HEADING,
    "paragraph_title": BlockType.HEADING,
    "header": BlockType.HEADER,
    "header_image": BlockType.FIGURE,
    "footer": BlockType.FOOTER,
    "footer_image": BlockType.FIGURE,
    "number": BlockType.FOOTER,
    "table": BlockType.TABLE,
    "image": BlockType.FIGURE,
    "chart": BlockType.FIGURE,
    "seal": BlockType.FIGURE,
    "formula": BlockType.FORMULA,
}
# Rótulos de texto que podem esconder um desenho (assinatura, logotipo).
_TEXTUAL = {"text", "doc_title", "paragraph_title", "header", "footer", "abstract", "content"}
_EDGE_TYPES = {BlockType.HEADER, BlockType.FOOTER}


def map_label(label: str) -> BlockType:
    """Rótulo do modelo → tipo da spec. Legendas, notas, referências etc. viram parágrafo."""
    return _LABELS.get(label, BlockType.PARAGRAPH)


@dataclass(frozen=True)
class Candidate:
    label: str
    score: float
    bbox: BBox


@dataclass(frozen=True)
class LayoutBlock:
    type: BlockType
    bbox: BBox
    order: int
    column: int
    align: Alignment
    rel_size: float
    score: float
    label: str


@dataclass(frozen=True)
class PageLayout:
    blocks: list[LayoutBlock]  # na ordem de leitura
    columns: int


# ------------------------------------------------------------------ detecção (5.1)


@lru_cache(maxsize=1)
def _layout_model() -> Any:
    from paddleocr import LayoutDetection

    # MKL-DNN desligado: no PaddlePaddle 3.3 em Linux x86 este modelo falha com ele ligado
    # ("ConvertPirAttribute2RuntimeAttribute not support"). Sem ele: ~1 s/página em x86 nativo.
    return LayoutDetection(model_name="PP-DocLayout_plus-L", enable_mkldnn=False)


def _intersection(a: BBox, b: BBox) -> float:
    w = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    h = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    return max(0.0, w) * max(0.0, h)


def merge_passes(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Aceita as caixas confiáveis; as fracas só onde não há nada (ex.: título de capa)."""
    accepted = [c for c in candidates if c.score >= STRONG_SCORE]
    weak = sorted((c for c in candidates if c.score < STRONG_SCORE), key=lambda c: -c.score)
    for candidate in weak:
        area = candidate.bbox.w * candidate.bbox.h
        if all(
            _intersection(candidate.bbox, other.bbox) / min(area, other.bbox.w * other.bbox.h)
            < MAX_WEAK_OVERLAP
            for other in accepted
        ):
            accepted.append(candidate)
    return accepted


def detect_blocks(image: Image) -> list[Candidate]:
    rgb = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    result = _layout_model().predict(
        np.ascontiguousarray(rgb), batch_size=1, threshold=WEAK_SCORE, layout_nms=True
    )[0]
    height, width = image.shape[:2]
    candidates = []
    for found in result["boxes"]:
        x1, y1, x2, y2 = (float(v) for v in found["coordinate"])
        x1, y1 = max(0.0, x1), max(0.0, y1)
        x2, y2 = min(float(width), x2), min(float(height), y2)
        if x2 - x1 >= 2 and y2 - y1 >= 2:
            candidates.append(
                Candidate(
                    label=str(found["label"]),
                    score=float(found["score"]),
                    bbox=BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1),
                )
            )
    return merge_passes(candidates)


# ------------------------------------------------------------------ desenho disfarçado (5.4)


def _crop(gray: Gray, bbox: BBox) -> Gray:
    return gray[int(bbox.y) : int(bbox.y + bbox.h), int(bbox.x) : int(bbox.x + bbox.w)]


def _ink_stats(gray: Gray) -> NDArray[np.int32]:
    ink = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)[1]
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    return np.asarray(stats[1:count], dtype=np.int32)


def looks_like_image(crop: Gray, char_height: float) -> bool:
    """Bloco rotulado como texto que na verdade é desenho.

    - logotipo: tem uma forma grande e cheia (o símbolo), bem maior que qualquer letra;
    - assinatura: poucas manchas, uma delas um traço contínuo atravessando o bloco.
    """
    if crop.size == 0 or char_height <= 0:
        return False
    stats = _ink_stats(crop)
    if len(stats) == 0:
        return False
    widths = stats[:, cv2.CC_STAT_WIDTH]
    heights = stats[:, cv2.CC_STAT_HEIGHT]
    areas = stats[:, cv2.CC_STAT_AREA]
    fill = areas / np.maximum(widths * heights, 1)
    solid_blob = (heights >= 2 * char_height) & (areas >= 6 * char_height**2) & (fill >= 0.4)
    if solid_blob.any():
        return True
    letter_like = heights >= 0.4 * char_height
    long_stroke = (widths >= 0.6 * crop.shape[1]) & (widths >= 3 * char_height)
    return int(letter_like.sum()) <= 3 and bool(long_stroke.any())


# ------------------------------------------------------------------ ordem de leitura (5.2)


def _span(items: Sequence[Candidate], axis: str) -> tuple[float, float]:
    if axis == "x":
        return min(c.bbox.x for c in items), max(c.bbox.x + c.bbox.w for c in items)
    return min(c.bbox.y for c in items), max(c.bbox.y + c.bbox.h for c in items)


def _split_by_x_gaps(items: list[Candidate]) -> list[list[Candidate]]:
    """Agrupa blocos em faixas verticais separadas por espaço vazio (as colunas)."""
    groups: list[list[Candidate]] = []
    right = -1.0
    for item in sorted(items, key=lambda c: c.bbox.x):
        if groups and item.bbox.x < right:
            groups[-1].append(item)
        else:
            groups.append([item])
        right = max(right, item.bbox.x + item.bbox.w)
    return groups


def _side_by_side(groups: list[list[Candidate]]) -> bool:
    """Colunas de verdade ficam lado a lado, não uma acima da outra."""
    for left, right in pairwise(groups):
        top_l, bottom_l = _span(left, "y")
        top_r, bottom_r = _span(right, "y")
        overlap = min(bottom_l, bottom_r) - max(top_l, top_r)
        if overlap < 0.3 * min(bottom_l - top_l, bottom_r - top_r):
            return False
    return True


def reading_order(candidates: Sequence[Candidate]) -> tuple[list[tuple[Candidate, int]], int]:
    """Ordem de leitura com colunas: cabeçalho, corpo (seção por seção, coluna por coluna), rodapé.

    Blocos de largura total separam seções; dentro de cada seção, colunas lado a lado são lidas
    inteiras da esquerda para a direita. Devolve (bloco, coluna) em ordem e o número de colunas.
    """
    by_y = lambda c: (c.bbox.y, c.bbox.x)  # noqa: E731
    headers = sorted((c for c in candidates if map_label(c.label) is BlockType.HEADER), key=by_y)
    footers = sorted((c for c in candidates if map_label(c.label) is BlockType.FOOTER), key=by_y)
    body = sorted((c for c in candidates if map_label(c.label) not in _EDGE_TYPES), key=by_y)

    ordered: list[tuple[Candidate, int]] = [(c, 0) for c in headers]
    columns = 1
    if body:
        left, right = _span(body, "x")
        usable = max(right - left, 1.0)
        section: list[Candidate] = []

        def flush() -> None:
            nonlocal columns
            if not section:
                return
            groups = _split_by_x_gaps(section)
            if len(groups) > 1 and _side_by_side(groups):
                if all(len(g) >= 2 for g in groups):
                    columns = max(columns, len(groups))
                for index, group in enumerate(groups):
                    ordered.extend((c, index) for c in sorted(group, key=by_y))
            else:
                ordered.extend((c, 0) for c in sorted(section, key=by_y))
            section.clear()

        for candidate in body:
            if candidate.bbox.w >= FULL_WIDTH * usable:
                flush()
                ordered.append((candidate, 0))
            else:
                section.append(candidate)
        flush()
    ordered.extend((c, 0) for c in footers)
    return ordered, columns


# ------------------------------------------------------------------ alinhamento e tamanho (5.3)


def _line_right_edges(crop: Gray, char_height: float) -> list[int]:
    """Borda direita da tinta de cada linha de texto do bloco.

    Acentos e descendentes ficam separados da linha por faixas vazias finas: faixas próximas são
    unidas, e faixas finas demais para serem uma linha são descartadas.
    """
    ink = crop < 140
    rows = np.flatnonzero(ink.any(axis=1))
    if len(rows) == 0:
        return []
    max_gap = max(3.0, 0.35 * char_height)
    bands: list[list[int]] = [[int(rows[0]), int(rows[0])]]
    for y in rows[1:]:
        if y - bands[-1][1] <= max_gap:
            bands[-1][1] = int(y)
        else:
            bands.append([int(y), int(y)])
    edges = []
    for top, bottom in bands:
        if bottom - top + 1 >= 0.5 * char_height:
            columns = np.flatnonzero(ink[top : bottom + 1].any(axis=0))
            edges.append(int(columns[-1]))
    return edges


def alignment(bbox: BBox, extent: tuple[float, float], crop: Gray, char_height: float) -> Alignment:
    left_gap = bbox.x - extent[0]
    right_gap = extent[1] - (bbox.x + bbox.w)
    tolerance = max(15.0, 0.03 * (extent[1] - extent[0]))
    if left_gap <= tolerance and right_gap <= tolerance:
        # Bloco ocupa a largura toda: justificado se as linhas (menos a última) chegam até a margem
        # direita da área de texto. Linhas justificadas chegam ao pixel; a tolerância pequena evita
        # confundir com um parágrafo à esquerda cuja linha, por acaso, terminou perto da margem.
        edges = [bbox.x + e for e in _line_right_edges(crop, char_height)]
        flush = max(4.0, 0.3 * char_height)
        if len(edges) >= 2 and all(e >= extent[1] - flush for e in edges[:-1]):
            return Alignment.JUSTIFY
        return Alignment.LEFT
    if left_gap > tolerance and abs(left_gap - right_gap) <= max(
        tolerance, 0.15 * (left_gap + right_gap)
    ):
        return Alignment.CENTER
    if right_gap <= tolerance:
        return Alignment.RIGHT
    return Alignment.LEFT


def _letter_height(crop: Gray) -> float:
    """Altura mediana das manchas com cara de letra dentro de um bloco (sem limite pela página)."""
    stats = _ink_stats(crop)
    if len(stats) == 0:
        return 0.0
    heights = stats[:, cv2.CC_STAT_HEIGHT]
    widths = stats[:, cv2.CC_STAT_WIDTH]
    letters = heights[(heights >= 4) & (widths <= heights * 3)]
    return float(np.median(letters)) if len(letters) else 0.0


def relative_size(crop: Gray, body_char_height: float) -> float:
    height = _letter_height(crop)
    if height <= 0 or body_char_height <= 0:
        return 1.0
    return round(height / body_char_height, 2)


# Altura da maiúscula ÷ altura do "x" (Times 1,48; Helvetica 1,37): bloco só de maiúsculas e
# algarismos é medido pela maiúscula e pareceria 1,4 vez maior do que é.
CAPS_TO_X_HEIGHT = 1.4
# A partir desta fração de maiúsculas/algarismos, o bloco conta como "todo em maiúsculas".
CAPS_SHARE = 0.6


def size_for_text(rel_size: float, text: str) -> float:
    """Corrige o tamanho relativo depois da leitura, quando o texto é todo em maiúsculas."""
    chars = [c for c in text if c.isalnum()]
    if not chars:
        return rel_size
    tall = sum(c.isupper() or c.isdigit() for c in chars) / len(chars)
    return round(rel_size / CAPS_TO_X_HEIGHT, 2) if tall >= CAPS_SHARE else rel_size


# ------------------------------------------------------------------ tudo junto


def analyze_layout(aligned: Image, normalized: Gray) -> PageLayout:
    char_height = median_char_height(normalized)
    # Desenhos são avaliados no original: a limpeza de sombra clareia formas escuras grandes.
    original = np.asarray(
        aligned if aligned.ndim == 2 else cv2.cvtColor(aligned, cv2.COLOR_RGB2GRAY), dtype=np.uint8
    )
    candidates = []
    for candidate in detect_blocks(aligned):
        if candidate.label in _TEXTUAL and looks_like_image(
            _crop(original, candidate.bbox), char_height
        ):
            candidate = replace(candidate, label="image")
        candidates.append(candidate)

    ordered, columns = reading_order(candidates)
    body = [c for c, _ in ordered if map_label(c.label) not in _EDGE_TYPES] or [
        c for c, _ in ordered
    ]
    page_extent = _span(body, "x") if body else (0.0, float(normalized.shape[1]))
    page_width = page_extent[1] - page_extent[0]
    column_extents: dict[int, tuple[float, float]] = {}
    if columns > 1:
        for index in range(columns):
            # Blocos de largura total (título, resumo) não pertencem a coluna nenhuma.
            members = [
                c
                for c, col in ordered
                if col == index and c in body and c.bbox.w < FULL_WIDTH * page_width
            ]
            if members:
                column_extents[index] = _span(members, "x")

    blocks = []
    for order, (candidate, column) in enumerate(ordered):
        block_type = map_label(candidate.label)
        crop = _crop(normalized, candidate.bbox)
        full_width = candidate.bbox.w >= FULL_WIDTH * page_width
        extent = page_extent if full_width else column_extents.get(column, page_extent)
        is_image = block_type in {BlockType.FIGURE, BlockType.FORMULA, BlockType.TABLE}
        blocks.append(
            LayoutBlock(
                type=block_type,
                bbox=candidate.bbox,
                order=order,
                column=0 if full_width else column,
                align=alignment(candidate.bbox, extent, crop, char_height),
                rel_size=1.0 if is_image else relative_size(crop, char_height),
                score=candidate.score,
                label=candidate.label,
            )
        )
    return PageLayout(blocks=blocks, columns=columns)


# ------------------------------------------------------------------ listas (5.5)

_MARKER = re.compile(
    r"^(\(?[A-Za-z]\)|\(?\d{1,3}[.)]|\(?[ivxlcIVXLC]{1,5}[.)]|[•·▪◦\-–—*])$"  # noqa: RUF001
)


def _is_list_item(block: Block) -> bool:
    return (
        block.type is BlockType.PARAGRAPH
        and bool(block.words)
        and bool(_MARKER.match(block.words[0].text))
    )


def _levels(lefts: list[float], tolerance: float = 15) -> list[int]:
    distinct: list[float] = []
    for left in sorted(set(lefts)):
        if not distinct or left - distinct[-1] > tolerance:
            distinct.append(left)
    return [max(i for i, d in enumerate(distinct) if left >= d - tolerance) for left in lefts]


def _merge_list(items: list[Block]) -> Block:
    words = [w for item in items for w in item.words]
    starts = []
    position = 0
    for item in items:
        starts.append(position)
        position += len(item.words)
    levels = _levels([item.bbox.x for item in items])
    x1 = min(i.bbox.x for i in items)
    y1 = min(i.bbox.y for i in items)
    x2 = max(i.bbox.x + i.bbox.w for i in items)
    y2 = max(i.bbox.y + i.bbox.h for i in items)
    first = items[0]
    return first.model_copy(
        update={
            "type": BlockType.LIST,
            "bbox": BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1),
            "words": words,
            "items": [
                ListItem(word_start=s, level=lv) for s, lv in zip(starts, levels, strict=True)
            ],
            "align": Alignment.LEFT,
            "confidence": float(median(i.confidence for i in items)),
        }
    )


def group_lists(blocks: Sequence[Block]) -> list[Block]:
    """Junta parágrafos seguidos que começam com marcador ("a)", "1.", "•"...) numa lista."""
    result: list[Block] = []
    run: list[Block] = []

    def close_run() -> None:
        if len(run) >= 2:
            result.append(_merge_list(run))
        else:
            result.extend(run)
        run.clear()

    for block in sorted(blocks, key=lambda b: b.order):
        if _is_list_item(block) and (not run or block.column == run[-1].column):
            run.append(block)
        else:
            close_run()
            result.append(block)
    close_run()
    return [b.model_copy(update={"order": i}) for i, b in enumerate(result)]
