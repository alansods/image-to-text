"""Gabarito de um caso de teste de precisão (`expected.json`).

Escrito pelo gerador sintético, que conhece cada palavra que desenha. O texto em ordem de leitura
segue a mesma regra de "Copiar texto": blocos separados por linha em branco, células por tabulação.
"""

from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import IMAGE_BLOCK_TYPES, Alignment, BlockType


class _Truth(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TruthWord(_Truth):
    text: str
    bold: bool = False
    italic: bool = False


class TruthCell(_Truth):
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    words: list[TruthWord] = Field(default_factory=list)


class TruthBlock(_Truth):
    type: BlockType
    align: Alignment = Alignment.LEFT
    rel_size: float = 1.0
    column: int = 0
    words: list[TruthWord] = Field(default_factory=list)
    cells: list[TruthCell] = Field(default_factory=list)

    def all_words(self) -> Iterator[TruthWord]:
        yield from self.words
        for cell in sorted(self.cells, key=lambda c: (c.row, c.col)):
            yield from cell.words

    def text(self) -> str:
        if self.type is BlockType.TABLE:
            rows: dict[int, list[TruthCell]] = {}
            for cell in self.cells:
                rows.setdefault(cell.row, []).append(cell)
            return "\n".join(
                "\t".join(
                    " ".join(w.text for w in c.words) for c in sorted(cells, key=lambda c: c.col)
                )
                for _, cells in sorted(rows.items())
            )
        return " ".join(w.text for w in self.words)


class TruthPage(_Truth):
    index: int
    w_pt: float
    h_pt: float
    blank: bool = False
    columns: int = 1
    # Já na ordem de leitura.
    blocks: list[TruthBlock] = Field(default_factory=list)


class Truth(_Truth):
    case: str
    input: str
    description: str = ""
    # Manuscrito: medido e reportado, sem bloquear (spec text-recognition vale para impresso).
    handwriting: bool
    pages: list[TruthPage]

    def text_blocks(self) -> Iterator[TruthBlock]:
        for page in self.pages:
            for block in page.blocks:
                if block.type not in IMAGE_BLOCK_TYPES:
                    yield block

    def text(self) -> str:
        return "\n\n".join(block.text() for block in self.text_blocks())

    def words(self) -> list[TruthWord]:
        return [w for block in self.text_blocks() for w in block.all_words()]

    def page_layout(self) -> list[bool]:
        return [page.blank for page in self.pages]

    def figure_counts(self) -> list[int]:
        return [sum(b.type in IMAGE_BLOCK_TYPES for b in page.blocks) for page in self.pages]
