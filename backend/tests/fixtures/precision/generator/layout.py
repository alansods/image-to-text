"""Diagramador mínimo sobre o ReportLab que desenha palavra a palavra e anota o gabarito.

Cada bloco desenhado vira um `TruthBlock` com tipo, alinhamento, tamanho relativo, coluna e
palavras (com negrito/itálico). Marcação de ênfase no texto de entrada, só na borda de palavras:
`**negrito**`, `_itálico_` e `**_ambos_**`.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from app.models.document import Alignment, BlockType
from tests.precision.truth import TruthBlock, TruthCell, TruthPage, TruthWord

FONTS_DIR = Path(__file__).parent / "fonts"

# As 14 fontes padrão do PDF dispensam arquivo e são renderizadas pelo pdfium igual em toda máquina.
FAMILIES: dict[str, dict[tuple[bool, bool], str]] = {
    "serif": {
        (False, False): "Times-Roman",
        (True, False): "Times-Bold",
        (False, True): "Times-Italic",
        (True, True): "Times-BoldItalic",
    },
    "sans": {
        (False, False): "Helvetica",
        (True, False): "Helvetica-Bold",
        (False, True): "Helvetica-Oblique",
        (True, True): "Helvetica-BoldOblique",
    },
    "hand": dict.fromkeys([(False, False), (True, False), (False, True), (True, True)], "Caveat"),
}

DrawFn = Callable[[Canvas, float, float, float, float], None]


def register_fonts() -> None:
    if "Caveat" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Caveat", str(FONTS_DIR / "Caveat.ttf")))


def parse_markup(markup: str) -> list[TruthWord]:
    """`"Pelo **CONTRATANTE,** e _outro_"` → palavras com a ênfase de cada uma."""
    words: list[TruthWord] = []
    bold = italic = False
    for token in markup.split():
        text = token
        while text.startswith(("**", "_")):
            if text.startswith("**"):
                bold, text = True, text[2:]
            else:
                italic, text = True, text[1:]
        closes_bold = closes_italic = False
        while text.endswith(("**", "_")) and len(text) > 1:
            if text.endswith("**"):
                closes_bold, text = True, text[:-2]
            else:
                closes_italic, text = True, text[:-1]
        words.append(TruthWord(text=text, bold=bold, italic=italic))
        bold = bold and not closes_bold
        italic = italic and not closes_italic
    return words


@dataclass
class CellSpec:
    text: str
    col_span: int = 1
    row_span: int = 1


@dataclass
class _PageState:
    truth: TruthPage
    footer: str | None = None
    footer_family: str | None = None


@dataclass
class Composer:
    path: Path
    page_size: tuple[float, float] = A4
    margin: float = 72
    family: str = "serif"
    body_size: float = 11
    leading: float = 1.4
    pages: list[TruthPage] = field(default_factory=list)

    def __post_init__(self) -> None:
        register_fonts()
        self.canvas = Canvas(str(self.path), pagesize=self.page_size, invariant=True)
        self.width, self.height = self.page_size
        self._page: _PageState | None = None
        self._columns = 1
        self._column = 0
        self._gap = 20.0
        self._top = 0.0
        self._y = 0.0

    # ---------- páginas e colunas ----------

    def new_page(self, *, footer: str | None = None, blank: bool = False) -> None:
        self._finish_page()
        truth = TruthPage(index=len(self.pages), w_pt=self.width, h_pt=self.height, blank=blank)
        self.pages.append(truth)
        self._page = _PageState(truth=truth, footer=footer)
        self._columns, self._column = 1, 0
        self._top = self._y = self.height - self.margin

    def columns(self, count: int, gap: float = 20) -> None:
        """Divide o restante da página em colunas a partir da posição atual."""
        assert self._page is not None
        self._columns, self._column, self._gap = count, 0, gap
        self._top = self._y
        self._page.truth.columns = max(self._page.truth.columns, count)

    def column_break(self) -> None:
        """Continua o texto no topo da próxima coluna."""
        assert self._column + 1 < self._columns, "não há próxima coluna"
        self._column += 1
        self._y = self._top

    def spacer(self, height: float) -> None:
        self._y -= height

    @property
    def _column_width(self) -> float:
        usable = self.width - 2 * self.margin
        return (usable - self._gap * (self._columns - 1)) / self._columns

    @property
    def _column_x(self) -> float:
        return self.margin + self._column * (self._column_width + self._gap)

    def _reserve(self, height: float) -> None:
        """Garante espaço para um bloco inteiro: pula de coluna (ou falha) se não couber."""
        if self._y - height >= self.margin + 24:
            return
        if self._column + 1 < self._columns:
            self._column += 1
            self._y = self._top
            return
        raise ValueError("bloco não cabe na página: ajuste o caso de teste")

    def _record(self, block: TruthBlock) -> None:
        assert self._page is not None
        self._page.truth.blocks.append(block)

    # ---------- texto ----------

    def _font(self, family: str, word: TruthWord) -> str:
        return FAMILIES[family][(word.bold, word.italic)]

    def _lines(
        self, words: list[TruthWord], family: str, size: float, width: float
    ) -> list[list[tuple[TruthWord, float]]]:
        space = pdfmetrics.stringWidth(" ", FAMILIES[family][(False, False)], size)
        lines: list[list[tuple[TruthWord, float]]] = [[]]
        used = 0.0
        for word in words:
            w = pdfmetrics.stringWidth(word.text, self._font(family, word), size)
            needed = w if not lines[-1] else used + space + w
            if lines[-1] and needed > width:
                lines.append([])
                used = 0.0
                needed = w
            lines[-1].append((word, w))
            used = needed
        return lines

    def _draw_lines(
        self,
        lines: list[list[tuple[TruthWord, float]]],
        family: str,
        size: float,
        align: Alignment,
        x0: float,
        width: float,
        indent: float = 0,
    ) -> None:
        space = pdfmetrics.stringWidth(" ", FAMILIES[family][(False, False)], size)
        for index, line in enumerate(lines):
            self._y -= size * self.leading
            line_x0 = x0 + (indent if index > 0 else 0)
            line_width = width - (indent if index > 0 else 0)
            natural = sum(w for _, w in line) + space * (len(line) - 1)
            gap = space
            if align is Alignment.CENTER:
                x = line_x0 + (line_width - natural) / 2
            elif align is Alignment.RIGHT:
                x = line_x0 + line_width - natural
            else:
                x = line_x0
                last = index == len(lines) - 1
                if align is Alignment.JUSTIFY and not last and len(line) > 1:
                    gap = space + (line_width - natural) / (len(line) - 1)
            for word, w in line:
                self.canvas.setFont(self._font(family, word), size)
                self.canvas.drawString(x, self._y, word.text)
                x += w + gap

    def paragraph(
        self,
        markup: str,
        *,
        align: Alignment = Alignment.JUSTIFY,
        size: float | None = None,
        block_type: BlockType = BlockType.PARAGRAPH,
        family: str | None = None,
        space_after: float = 8,
        full_width: bool = False,
        fixed: bool = False,
    ) -> None:
        """Parágrafo no fluxo; `fixed` desenha na posição atual sem checar espaço (margens)."""
        family = family or self.family
        size = size or self.body_size
        words = parse_markup(markup)
        x0 = self.margin if full_width else self._column_x
        width = (self.width - 2 * self.margin) if full_width else self._column_width
        lines = self._lines(words, family, size, width)
        if not fixed:
            self._reserve(len(lines) * size * self.leading)
        self._draw_lines(lines, family, size, align, x0, width)
        self._y -= space_after
        self._record(
            TruthBlock(
                type=block_type,
                align=align,
                rel_size=round(size / self.body_size, 2),
                column=0 if full_width else self._column,
                words=words,
            )
        )

    def bullet_list(
        self, items: list[tuple[str, str]], *, indent: float = 18, space_after: float = 8
    ) -> None:
        """Lista: cada item é (marcador, texto). O marcador faz parte do texto lido."""
        family, size = self.family, self.body_size
        all_words: list[TruthWord] = []
        total_lines = 0
        laid_out = []
        for marker, markup in items:
            words = [TruthWord(text=marker), *parse_markup(markup)]
            lines = self._lines(words, family, size, self._column_width - indent)
            laid_out.append(lines)
            total_lines += len(lines)
            all_words.extend(words)
        self._reserve(total_lines * size * self.leading)
        for lines in laid_out:
            self._draw_lines(
                lines,
                family,
                size,
                Alignment.LEFT,
                self._column_x + indent / 2,
                self._column_width - indent,
                indent=indent / 2,
            )
        self._y -= space_after
        self._record(
            TruthBlock(
                type=BlockType.LIST, align=Alignment.LEFT, column=self._column, words=all_words
            )
        )

    def header(self, markup: str, *, align: Alignment = Alignment.RIGHT, size: float = 8) -> None:
        """Cabeçalho de página: desenhado no topo da margem."""
        y_before = self._y
        self._y = self.height - self.margin / 2 + size * self.leading
        self.paragraph(
            markup,
            align=align,
            size=size,
            block_type=BlockType.HEADER,
            space_after=0,
            full_width=True,
            fixed=True,
        )
        self._y = y_before

    # ---------- tabela ----------

    def table(
        self,
        rows: list[list[CellSpec]],
        col_widths: list[float],
        *,
        size: float | None = None,
        header_bold: bool = True,
        space_after: float = 12,
    ) -> None:
        """Tabela com bordas; células mescladas via col_span/row_span (sem repetir as cobertas)."""
        size = size or self.body_size
        row_h = size * 2.0
        self._reserve(row_h * len(rows))
        x0, top = self._column_x, self._y
        col_x = [x0 + sum(col_widths[:i]) for i in range(len(col_widths) + 1)]
        covered: set[tuple[int, int]] = set()
        cells: list[TruthCell] = []
        self.canvas.setLineWidth(0.8)
        for r, row in enumerate(rows):
            c = 0
            for spec in row:
                while (r, c) in covered:
                    c += 1
                for dr in range(spec.row_span):
                    for dc in range(spec.col_span):
                        covered.add((r + dr, c + dc))
                x, w = col_x[c], col_x[c + spec.col_span] - col_x[c]
                y_top, h = top - r * row_h, row_h * spec.row_span
                self.canvas.rect(x, y_top - h, w, h, stroke=1, fill=0)
                markup = f"**{spec.text}**" if (header_bold and r == 0 and spec.text) else spec.text
                words = parse_markup(markup) if spec.text else []
                tx = x + 5
                ty = y_top - h / 2 - size * 0.35
                for word in words:
                    font = self._font(self.family, word)
                    self.canvas.setFont(font, size)
                    self.canvas.drawString(tx, ty, word.text)
                    tx += pdfmetrics.stringWidth(word.text + " ", font, size)
                cells.append(
                    TruthCell(
                        row=r, col=c, row_span=spec.row_span, col_span=spec.col_span, words=words
                    )
                )
                c += spec.col_span
        self._y = top - row_h * len(rows) - space_after
        self._record(TruthBlock(type=BlockType.TABLE, column=self._column, cells=cells))

    # ---------- figuras ----------

    def figure(
        self,
        draw: DrawFn,
        width: float,
        height: float,
        *,
        align: Alignment = Alignment.CENTER,
        space_after: float = 8,
        full_width: bool = False,
    ) -> None:
        x0 = self.margin if full_width else self._column_x
        avail = (self.width - 2 * self.margin) if full_width else self._column_width
        self._reserve(height)
        if align is Alignment.CENTER:
            x = x0 + (avail - width) / 2
        elif align is Alignment.RIGHT:
            x = x0 + avail - width
        else:
            x = x0
        self._y -= height
        self.canvas.saveState()
        draw(self.canvas, x, self._y, width, height)
        self.canvas.restoreState()
        self._y -= space_after
        self._record(
            TruthBlock(type=BlockType.FIGURE, align=align, column=0 if full_width else self._column)
        )

    # ---------- fim ----------

    def _finish_page(self) -> None:
        if self._page is None:
            return
        if self._page.footer:
            self._y = self.margin / 2 + 8 * self.leading
            self.paragraph(
                self._page.footer,
                align=Alignment.CENTER,
                size=9,
                block_type=BlockType.FOOTER,
                space_after=0,
                full_width=True,
                fixed=True,
            )
        self.canvas.showPage()
        self._page = None

    def save(self) -> list[TruthPage]:
        self._finish_page()
        self.canvas.save()
        return self.pages
