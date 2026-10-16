"""Tamanho relativo dos blocos medido no documento inteiro (design D16).

Na página, o "texto típico" pode ser o próprio título (capa com quase só título), e o tamanho
relativo perde a referência. Depois de lidas todas as páginas, cada bloco de texto passa a ter
`rel_size` = altura mediana das suas palavras ÷ altura mediana das palavras dos parágrafos do
documento. Medido: altura da palavra em pontos ≈ corpo da fonte (razão de 0,94 a 1,13).
"""

from collections.abc import Sequence
from statistics import median

import numpy as np

from app.models.document import ILLEGIBLE, Block, BlockType, Document, Word
from app.pipeline.reading import Gray

# A altura das palavras varia ±10% no mesmo corpo de fonte (acentos, maiúsculas, descendentes):
# abaixo desta diferença o bloco é do tamanho do texto principal.
SAME_SIZE = 0.15

TEXT_TYPES = {
    BlockType.HEADING,
    BlockType.PARAGRAPH,
    BlockType.LIST,
    BlockType.HEADER,
    BlockType.FOOTER,
}


# ------------------------------------------------------------------ tamanho em pontos (D18)

# Altura da tinta de uma palavra ÷ corpo da fonte = topo menos base das letras que ela tem (em
# frações do corpo): letra baixa 0,52; maiúscula, haste ou algarismo 0,72; minúscula acentuada
# 0,75; maiúscula acentuada 0,90; perna abaixo da linha (g, p, q, y, ç, Ç) 0,21. Assim
# "QUARTA", "CLÁUSULA" e "agência" do mesmo corpo dão o mesmo tamanho. O pingo do "i" é fino
# demais para contar na altura da tinta.
_X_HEIGHT, _CAP, _ACCENT_LOW, _ACCENT_CAP, _DESCENDER = 0.52, 0.72, 0.75, 0.90, 0.21
_ASCENDERS = set("bdfhklt")
_DESCENDERS = set("gjpqyçÇ")
_ACCENTED_LOW = set("áàâãéêíóôõúü")
_ACCENTED_CAP = set("ÁÀÂÃÉÊÍÓÔÕÚÜ")


def _letter_factor(text: str) -> float | None:
    letters = [c for c in text if c.isalnum()]
    if not letters:
        return None
    top = _X_HEIGHT
    for c in letters:
        if c in _ACCENTED_CAP:
            top = max(top, _ACCENT_CAP)
        elif c in _ACCENTED_LOW:
            top = max(top, _ACCENT_LOW)
        elif c.isupper() or c.isdigit() or c in _ASCENDERS:
            top = max(top, _CAP)
    bottom = _DESCENDER if any(c in _DESCENDERS for c in letters) else 0.0
    return top + bottom


# Medida abaixo disto não é letra de documento (risco, pedaço de assinatura): sem tamanho.
MIN_PLAUSIBLE_PT = 4.0
# Linha de pixels com tinta em mais que isto da largura é sublinhado, não letra.
UNDERLINE = 0.8


def _ink_height(gray: Gray, word: Word) -> int | None:
    b = word.bbox
    crop = gray[max(0, int(b.y)) : int(b.y + b.h), max(0, int(b.x)) : int(b.x + b.w)]
    if crop.size == 0:
        return None
    share = (crop < 140).mean(axis=1)
    rows = np.nonzero((share > 0.02) & (share < UNDERLINE))[0]
    return int(rows[-1] - rows[0] + 1) if len(rows) else None


def estimate_font_pt(words: Sequence[Word], gray: Gray, points_per_pixel: float) -> float | None:
    """Corpo da fonte de um bloco, em pontos: mediana das estimativas palavra a palavra."""
    estimates = []
    for word in words:
        factor = _letter_factor(word.text) if word.text != ILLEGIBLE else None
        height = _ink_height(gray, word) if factor else None
        if factor and height:
            estimates.append(height * points_per_pixel / factor)
    if not estimates:
        return None
    size = median(estimates)
    return round(size, 1) if size >= MIN_PLAUSIBLE_PT else None


def _heights(block: Block, points_per_pixel: float) -> list[float]:
    return [w.bbox.h * points_per_pixel for w in block.words if w.text != ILLEGIBLE]


def normalize_sizes(document: Document) -> Document:
    """`rel_size` (e `font_pt`) de cada bloco de texto em relação ao corpo do documento.

    Com `font_pt` medido, o corpo é a mediana dos parágrafos; sem ele, a altura das palavras.
    Diferença menor que 15% do corpo é o próprio corpo.
    """
    measured = [
        b.font_pt
        for page in document.pages
        for b in page.blocks
        if b.type is BlockType.PARAGRAPH and b.font_pt
    ]
    if measured:
        return _normalize_by_points(document, median(measured))
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
                relative = median(heights) / reference
                size = 1.0 if abs(relative - 1.0) < SAME_SIZE else round(relative, 2)
                block = block.model_copy(update={"rel_size": size})
            blocks.append(block)
        pages.append(page.model_copy(update={"blocks": blocks}))
    return document.model_copy(update={"pages": pages})


def _normalize_by_points(document: Document, body: float) -> Document:
    pages = []
    for page in document.pages:
        blocks = []
        for block in page.blocks:
            if block.type in TEXT_TYPES and block.font_pt:
                relative = block.font_pt / body
                if abs(relative - 1.0) < SAME_SIZE:
                    block = block.model_copy(update={"rel_size": 1.0, "font_pt": body})
                else:
                    block = block.model_copy(update={"rel_size": round(relative, 2)})
            blocks.append(block)
        pages.append(page.model_copy(update={"blocks": blocks}))
    return document.model_copy(update={"pages": pages})
