"""Estrutura de tabelas (spec table-extraction, design D15).

Um classificador do PaddleOCR diz se a tabela tem grade; o detector de células do tipo certo
(`RT-DETR-L_wired/wireless_table_cell_det`) devolve a caixa de cada célula, e a grade sai das
bordas alinhadas (caixa que atravessa várias linhas/colunas = célula mesclada). O texto vem
da leitura dupla da tabela inteira; cada palavra vai para a célula que contém o seu centro.
Estrutura que não fecha vira imagem do original (nada se perde).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np

from app.models.document import BBox, Cell, Word
from app.pipeline.base import Image

CLASSIFIER = "PP-LCNet_x1_0_table_cls"
CELL_MODELS = {
    "wired_table": "RT-DETR-L_wired_table_cell_det",
    "wireless_table": "RT-DETR-L_wireless_table_cell_det",
}
MIN_CELL_SCORE = 0.3
# Bordas a menos que isto (fração da altura típica da célula) são a mesma linha de grade.
EDGE_TOLERANCE = 0.3


@dataclass(frozen=True)
class CellBox:
    row: int
    col: int
    row_span: int
    col_span: int
    bbox: BBox


@lru_cache(maxsize=1)
def _classifier() -> Any:
    from paddleocr import TableClassification

    return TableClassification(model_name=CLASSIFIER, enable_mkldnn=False)


@lru_cache(maxsize=2)
def _cell_model(name: str) -> Any:
    from paddleocr import TableCellsDetection

    return TableCellsDetection(model_name=name, enable_mkldnn=False)


def _grid_lines(edges: list[float], tolerance: float) -> list[float]:
    """Agrupa bordas próximas numa só linha de grade (média do grupo)."""
    lines: list[list[float]] = []
    for edge in sorted(edges):
        if lines and edge - lines[-1][-1] <= tolerance:
            lines[-1].append(edge)
        else:
            lines.append([edge])
    return [sum(group) / len(group) for group in lines]


def _nearest(lines: list[float], value: float) -> int:
    return min(range(len(lines)), key=lambda i: abs(lines[i] - value))


def grid_from_boxes(boxes: Sequence[Sequence[float]], origin: tuple[float, float]) -> list[CellBox]:
    """Células (x1, y1, x2, y2 no recorte) → posição na grade, com mesclas, em coordenadas da
    página. Ordem: por linha, depois por coluna."""
    if not boxes:
        return []
    heights = sorted(b[3] - b[1] for b in boxes)
    tolerance = EDGE_TOLERANCE * heights[len(heights) // 2]
    columns = _grid_lines([v for b in boxes for v in (b[0], b[2])], tolerance)
    rows = _grid_lines([v for b in boxes for v in (b[1], b[3])], tolerance)
    ox, oy = origin
    cells = []
    for x1, y1, x2, y2 in boxes:
        col, last_col = _nearest(columns, x1), _nearest(columns, x2)
        row, last_row = _nearest(rows, y1), _nearest(rows, y2)
        if last_col <= col or last_row <= row:
            continue
        cells.append(
            CellBox(
                row,
                col,
                last_row - row,
                last_col - col,
                BBox(x=ox + x1, y=oy + y1, w=x2 - x1, h=y2 - y1),
            )
        )
    return sorted(cells, key=lambda c: (c.row, c.col))


def table_structure(image: Image, origin: tuple[float, float]) -> list[CellBox]:
    """Células da tabela no recorte RGB `image`, em coordenadas da página."""
    bgr = np.ascontiguousarray(image[:, :, ::-1])
    kind = _classifier().predict(bgr)[0]["label_names"][0]
    model = _cell_model(CELL_MODELS.get(kind, CELL_MODELS["wired_table"]))
    found = model.predict(bgr, threshold=MIN_CELL_SCORE)[0]["boxes"]
    return grid_from_boxes([[float(v) for v in b["coordinate"]] for b in found], origin)


def trustworthy(cells: Sequence[CellBox]) -> bool:
    """A grade fecha: ao menos 2 linhas e 2 colunas, cada posição coberta por uma só célula."""
    if not cells:
        return False
    rows = max(c.row + c.row_span for c in cells)
    cols = max(c.col + c.col_span for c in cells)
    if rows < 2 or cols < 2:
        return False
    covered: dict[tuple[int, int], int] = {}
    for c in cells:
        for r in range(c.row, c.row + c.row_span):
            for k in range(c.col, c.col + c.col_span):
                covered[(r, k)] = covered.get((r, k), 0) + 1
    return len(covered) == rows * cols and all(n == 1 for n in covered.values())


def _contains(box: BBox, x: float, y: float) -> bool:
    return box.x <= x <= box.x + box.w and box.y <= y <= box.y + box.h


def assign_words(cells: Sequence[CellBox], words: Sequence[Word]) -> list[Cell] | None:
    """Põe cada palavra na célula que contém o centro dela; `None` se alguma ficar de fora ou
    se não houver palavra nenhuma (grade "vista" num desenho ou em papel em branco)."""
    if not words:
        return None
    grouped: list[list[Word]] = [[] for _ in cells]
    for word in words:
        cx, cy = word.bbox.x + word.bbox.w / 2, word.bbox.y + word.bbox.h / 2
        index = next((i for i, c in enumerate(cells) if _contains(c.bbox, cx, cy)), None)
        if index is None:
            return None
        grouped[index].append(word)
    return [
        Cell(
            row=c.row,
            col=c.col,
            row_span=c.row_span,
            col_span=c.col_span,
            bbox=c.bbox,
            words=group,
        )
        for c, group in zip(cells, grouped, strict=True)
    ]
