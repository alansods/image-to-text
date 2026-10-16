"""Tamanho relativo dos blocos medido no documento inteiro (design D16).

Na página, o "texto típico" pode ser o próprio título (capa com quase só título), e o tamanho
relativo perde a referência. Depois de lidas todas as páginas, cada bloco de texto passa a ter
`rel_size` = altura mediana das suas palavras ÷ altura mediana das palavras dos parágrafos do
documento. Medido: altura da palavra em pontos ≈ corpo da fonte (razão de 0,94 a 1,13).
"""

from statistics import median

from app.models.document import ILLEGIBLE, Block, BlockType, Document

TEXT_TYPES = {
    BlockType.HEADING,
    BlockType.PARAGRAPH,
    BlockType.LIST,
    BlockType.HEADER,
    BlockType.FOOTER,
}


def _heights(block: Block, points_per_pixel: float) -> list[float]:
    return [w.bbox.h * points_per_pixel for w in block.words if w.text != ILLEGIBLE]


def normalize_sizes(document: Document) -> Document:
    body = [
        h
        for page in document.pages
        for block in page.blocks
        if block.type is BlockType.PARAGRAPH
        for h in _heights(block, page.page_size.w_pt / page.width)
    ]
    if not body:
        return document
    reference = median(body)
    pages = []
    for page in document.pages:
        scale = page.page_size.w_pt / page.width
        blocks = []
        for block in page.blocks:
            heights = _heights(block, scale) if block.type in TEXT_TYPES else []
            if heights:
                block = block.model_copy(update={"rel_size": round(median(heights) / reference, 2)})
            blocks.append(block)
        pages.append(page.model_copy(update={"blocks": blocks}))
    return document.model_copy(update={"pages": pages})
