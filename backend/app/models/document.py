"""Formato interno único do documento convertido.

Consumido pela tela de resultado (via JSON e tipos TypeScript gerados) e pelos exportadores
de Word e PDF. Coordenadas (`BBox`) em pixels da imagem da página; tamanho de folha em pontos.
"""

from collections.abc import Iterator
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ILLEGIBLE = "[ilegível]"


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        # No JSON devolvido pela API, campos com valor padrão sempre vêm preenchidos.
        json_schema_serialization_defaults_required=True,
    )


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    FORMULA = "formula"
    HEADER = "header"
    FOOTER = "footer"


class Alignment(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class WordStatus(StrEnum):
    ACCEPTED = "accepted"
    RESOLVED = "resolved"
    UNCERTAIN = "uncertain"
    EDITED = "edited"


class ResolvedBy(StrEnum):
    CONFIDENCE = "confidence"
    REREAD = "reread"
    ARBITER = "arbiter"


class ReadingSource(StrEnum):
    PADDLE = "paddle"
    DOCTR = "doctr"
    ARBITER = "arbiter"


IMAGE_BLOCK_TYPES = frozenset({BlockType.FIGURE, BlockType.FORMULA})


class BBox(_Model):
    """Caixa delimitadora em pixels da imagem da página."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class PageSize(_Model):
    """Tamanho da folha em pontos (1/72 de polegada), usado para repetir a paginação."""

    w_pt: float = Field(gt=0)
    h_pt: float = Field(gt=0)


class Alternative(_Model):
    """Uma leitura possível de uma palavra, mostrada na conferência."""

    text: str
    confidence: float = Field(ge=0, le=1)
    source: ReadingSource


class Word(_Model):
    id: str
    text: str
    bbox: BBox
    confidence: float = Field(ge=0, le=1)
    bold: bool = False
    italic: bool = False
    alternatives: list[Alternative] = Field(default_factory=list)
    status: WordStatus
    resolved_by: ResolvedBy | None = None

    @model_validator(mode="after")
    def _check_status_rules(self) -> Self:
        texts = [alternative.text for alternative in self.alternatives]
        if len(texts) != len(set(texts)):
            raise ValueError("as alternativas de uma palavra precisam ser distintas")
        if (
            self.status is WordStatus.UNCERTAIN
            and self.text != ILLEGIBLE
            and len(self.alternatives) < 2
        ):
            raise ValueError("palavra em dúvida precisa de pelo menos 2 alternativas")
        if (self.status is WordStatus.RESOLVED) != (self.resolved_by is not None):
            raise ValueError("resolved_by é obrigatório em palavra resolvida e só nela")
        return self


class Cell(_Model):
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    col_span: int = Field(default=1, ge=1)
    words: list[Word] = Field(default_factory=list)


class Block(_Model):
    id: str
    type: BlockType
    bbox: BBox
    order: int = Field(ge=0)
    column: int = Field(default=0, ge=0)
    align: Alignment = Alignment.LEFT
    # Altura da letra do bloco ÷ altura da letra do texto principal da página.
    rel_size: float = Field(default=1.0, gt=0)
    words: list[Word] = Field(default_factory=list)
    cells: list[Cell] = Field(default_factory=list)
    image_ref: str | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _check_content_matches_type(self) -> Self:
        if self.type in IMAGE_BLOCK_TYPES:
            if self.image_ref is None:
                raise ValueError("bloco de imagem precisa de image_ref (recorte do original)")
            if self.words or self.cells:
                raise ValueError("bloco de imagem não tem palavras nem células")
        elif self.type is BlockType.TABLE:
            if not self.cells:
                raise ValueError("bloco tabela precisa de células")
        elif not self.words:
            raise ValueError("bloco de texto precisa de palavras")
        return self

    def all_words(self) -> Iterator[Word]:
        yield from self.words
        for cell in self.cells:
            yield from cell.words


class Page(_Model):
    index: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    page_size: PageSize
    columns: int = Field(default=1, ge=1)
    image_ref: str
    blank: bool = False
    blocks: list[Block] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_blocks(self) -> Self:
        if self.blank and self.blocks:
            raise ValueError("página em branco não tem blocos")
        orders = [block.order for block in self.blocks]
        if len(orders) != len(set(orders)):
            raise ValueError("ordem de leitura repetida na página")
        return self


class Document(_Model):
    id: str
    source_file: str
    pages: list[Page]

    @model_validator(mode="after")
    def _check_document(self) -> Self:
        if [page.index for page in self.pages] != list(range(len(self.pages))):
            raise ValueError("as páginas precisam ser numeradas em sequência a partir de 0")
        seen_blocks: set[str] = set()
        seen_words: set[str] = set()
        for page in self.pages:
            for block in page.blocks:
                if block.id in seen_blocks:
                    raise ValueError(f"id de bloco repetido: {block.id}")
                seen_blocks.add(block.id)
                for word in block.all_words():
                    if word.id in seen_words:
                        raise ValueError(f"id de palavra repetido: {word.id}")
                    seen_words.add(word.id)
        return self

    def words_in_reading_order(self) -> Iterator[Word]:
        for page in self.pages:
            for block in sorted(page.blocks, key=lambda b: b.order):
                yield from block.all_words()

    def uncertain_words(self) -> list[Word]:
        return [w for w in self.words_in_reading_order() if w.status is WordStatus.UNCERTAIN]

    def uncertain_count(self) -> int:
        return len(self.uncertain_words())
