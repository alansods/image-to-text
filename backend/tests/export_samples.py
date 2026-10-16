"""Documento de exemplo para os testes de exportação: cobre cada requisito de document-export."""

from pathlib import Path

import numpy as np
from PIL import Image

from app.models.document import (
    Alignment,
    BBox,
    Block,
    BlockType,
    Cell,
    Document,
    ListItem,
    Page,
    PageSize,
    Word,
    WordStatus,
)

A4 = PageSize(w_pt=595.0, h_pt=842.0)
LANDSCAPE = PageSize(w_pt=842.0, h_pt=595.0)
W, H = 2480, 3508  # A4 a 300 DPI


def words(prefix: str, text: str, x: float, y: float, bold: set[str] | None = None) -> list[Word]:
    result = []
    for i, token in enumerate(text.split()):
        result.append(
            Word(
                id=f"{prefix}w{i}",
                text=token,
                bbox=BBox(x=x + i * 140, y=y, w=120, h=46),
                confidence=0.99,
                bold=token in (bold or set()),
                status=WordStatus.ACCEPTED,
            )
        )
    return result


def text_block(
    block_id: str,
    order: int,
    text: str,
    y: float,
    *,
    kind: BlockType = BlockType.PARAGRAPH,
    align: Alignment = Alignment.LEFT,
    rel: float = 1.0,
    x: float = 300,
    w: float = 1880,
    column: int = 0,
    bold: set[str] | None = None,
) -> Block:
    found = words(block_id, text, x, y, bold)
    return Block(
        id=block_id,
        type=kind,
        bbox=BBox(x=x, y=y, w=w, h=60),
        order=order,
        column=column,
        align=align,
        rel_size=rel,
        words=found,
        confidence=0.99,
    )


def figure(block_id: str, order: int, y: float, w: float = 600, h: float = 300) -> Block:
    return Block(
        id=block_id,
        type=BlockType.FIGURE,
        bbox=BBox(x=300, y=y, w=w, h=h),
        order=order,
        image_ref=f"crops/{block_id}.png",
        confidence=0.9,
    )


def sample_document(folder: Path) -> Document:
    """3 páginas A4 (a 2ª em branco) + 1 paisagem; crops gravados em `folder/crops`."""
    (folder / "crops").mkdir(parents=True, exist_ok=True)
    for name, size in [("p0-logo", (600, 300)), ("p2-sig", (800, 200)), ("p3-chart", (900, 500))]:
        image = np.full((size[1], size[0], 3), 255, np.uint8)
        image[20:-20, 20:-20] = (30, 60, 150)
        Image.fromarray(image).save(folder / "crops" / f"{name}.png")

    edited = words("p0-b2", "assinado por SILVA", 300, 900)
    edited[2] = edited[2].model_copy(update={"status": WordStatus.EDITED})

    listing = Block(
        id="p0-b4",
        type=BlockType.LIST,
        bbox=BBox(x=300, y=1300, w=1800, h=200),
        order=5,
        words=words("p0-b4", "a) recebimento b) digitalização", 300, 1300),
        items=[ListItem(word_start=0), ListItem(word_start=2, level=1)],
        confidence=0.99,
    )
    table = Block(
        id="p0-b5",
        type=BlockType.TABLE,
        bbox=BBox(x=300, y=1600, w=1800, h=400),
        order=6,
        cells=[
            Cell(row=0, col=0, col_span=2, words=words("p0-c0", "Período", 300, 1600)),
            Cell(row=0, col=2, words=words("p0-c1", "Saldo", 1500, 1600)),
            *[
                Cell(
                    row=r,
                    col=c,
                    words=words(f"p0-c{r}{c}", f"{r}.{c}00,00", 300 + c * 600, 1600 + r * 100),
                )
                for r in (1, 2, 3)
                for c in (0, 1, 2)
            ],
        ],
        confidence=0.99,
    )
    page0 = Page(
        index=0,
        width=W,
        height=H,
        page_size=A4,
        image_ref="pages/0.png",
        blocks=[
            text_block(
                "p0-h", 0, "Relatório mensal", 120, kind=BlockType.HEADER, align=Alignment.RIGHT
            ),
            figure("p0-logo", 1, 250),
            text_block(
                "p0-b1", 2, "CONTRATO DE SERVIÇOS", 600, kind=BlockType.HEADING,
                align=Alignment.CENTER, rel=1.6, bold={"CONTRATO", "DE", "SERVIÇOS"},
            ),
            Block(
                id="p0-b2", type=BlockType.PARAGRAPH, bbox=BBox(x=300, y=900, w=1880, h=60),
                order=3, align=Alignment.JUSTIFY, words=edited, confidence=0.99,
            ),
            text_block(
                "p0-b3", 4, "O CONTRATANTE declara", 1100, align=Alignment.JUSTIFY,
                bold={"CONTRATANTE"},
            ),
            listing,
            table,
            text_block("p0-f", 7, "Página 1", 3300, kind=BlockType.FOOTER, align=Alignment.CENTER),
        ],
    )  # fmt: skip
    page1 = Page(index=1, width=W, height=H, page_size=A4, image_ref="pages/1.png", blank=True)
    page2 = Page(
        index=2,
        width=W,
        height=H,
        page_size=A4,
        columns=2,
        image_ref="pages/2.png",
        blocks=[
            text_block("p2-t", 0, "Duas colunas", 200, kind=BlockType.HEADING, rel=1.4),
            text_block("p2-l", 1, "coluna esquerda texto", 500, x=300, w=850, column=0),
            text_block("p2-r", 2, "coluna direita texto", 500, x=1300, w=850, column=1),
            figure("p2-sig", 3, 2800, w=800, h=200),
        ],
    )
    page3 = Page(
        index=3,
        width=H,
        height=W,
        page_size=LANDSCAPE,
        image_ref="pages/3.png",
        blocks=[figure("p3-chart", 0, 300, w=900, h=500)],
    )
    return Document(id="d1", source_file="contrato.pdf", pages=[page0, page1, page2, page3])
