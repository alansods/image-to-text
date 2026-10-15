"""Métricas do teste de precisão: texto do documento, CER/WER, ênfase, páginas e figuras."""

import pytest

from app.models.document import (
    Alignment,
    BBox,
    Block,
    BlockType,
    Cell,
    Document,
    Page,
    PageSize,
    Word,
    WordStatus,
)
from tests.precision.metrics import (
    cer,
    document_text,
    emphasis_accuracy,
    figure_counts,
    page_layout,
    wer,
)
from tests.precision.truth import Truth, TruthBlock, TruthPage, TruthWord

BOX = BBox(x=0, y=0, w=10, h=10)


def word(word_id: str, text: str, *, bold: bool = False, italic: bool = False) -> Word:
    return Word(
        id=word_id,
        text=text,
        bbox=BOX,
        confidence=0.99,
        bold=bold,
        italic=italic,
        status=WordStatus.ACCEPTED,
    )


def text_block(block_id: str, order: int, words: list[Word]) -> Block:
    return Block(
        id=block_id,
        type=BlockType.PARAGRAPH,
        bbox=BOX,
        order=order,
        align=Alignment.LEFT,
        words=words,
        confidence=0.9,
    )


def page(index: int, blocks: list[Block], *, blank: bool = False) -> Page:
    return Page(
        index=index,
        width=100,
        height=140,
        page_size=PageSize(w_pt=595.28, h_pt=841.89),
        image_ref=f"pages/{index}.png",
        blank=blank,
        blocks=blocks,
    )


def sample_document() -> Document:
    table = Block(
        id="t",
        type=BlockType.TABLE,
        bbox=BOX,
        order=1,
        cells=[
            Cell(row=0, col=0, words=[word("c1", "Parcela")]),
            Cell(row=0, col=1, words=[word("c2", "Valor")]),
            Cell(row=1, col=0, words=[word("c3", "1ª")]),
            Cell(row=1, col=1, words=[word("c4", "R$"), word("c5", "1.250,00")]),
        ],
        confidence=0.9,
    )
    logo = Block(
        id="f", type=BlockType.FIGURE, bbox=BOX, order=0, image_ref="crops/f.png", confidence=1
    )
    paragraph = text_block("p", 2, [word("w1", "Pelo"), word("w2", "CONTRATANTE", bold=True)])
    return Document(
        id="d",
        source_file="contrato.pdf",
        pages=[page(0, [paragraph, logo, table]), page(1, [], blank=True)],
    )


class TestText:
    def test_document_text_follows_reading_order_and_separates_cells_with_tabs(self) -> None:
        assert document_text(sample_document()) == (
            "Parcela\tValor\n1ª\tR$ 1.250,00\n\nPelo CONTRATANTE"
        )

    def test_cer_and_wer_are_zero_for_identical_text(self) -> None:
        assert cer("Ação nº 123", "Ação nº 123") == 0
        assert wer("Ação nº 123", "Ação nº 123") == 0

    def test_cer_counts_a_swapped_character(self) -> None:
        assert cer("SILVA", "SlLVA") == pytest.approx(0.2)

    def test_whitespace_differences_are_ignored(self) -> None:
        assert wer("um  dois\n\ntrês", "um dois três") == 0


class TestEmphasis:
    def test_counts_matching_bold_and_italic(self) -> None:
        truth = [TruthWord(text="Pelo"), TruthWord(text="CONTRATANTE", bold=True)]

        assert (
            emphasis_accuracy(truth, [word("a", "Pelo"), word("b", "CONTRATANTE", bold=True)]) == 1
        )
        assert emphasis_accuracy(truth, [word("a", "Pelo"), word("b", "CONTRATANTE")]) == 0.5

    def test_unread_words_count_as_misses(self) -> None:
        truth = [TruthWord(text="um"), TruthWord(text="dois", italic=True)]

        assert emphasis_accuracy(truth, [word("a", "um")]) == 0.5


class TestPages:
    def test_page_layout_lists_blank_flags(self) -> None:
        assert page_layout(sample_document()) == [False, True]

    def test_figure_counts_per_page(self) -> None:
        assert figure_counts(sample_document()) == [1, 0]

    def test_truth_reports_same_shape(self) -> None:
        truth = Truth(
            case="exemplo",
            input="input.pdf",
            handwriting=False,
            pages=[
                TruthPage(
                    index=0,
                    w_pt=595.28,
                    h_pt=841.89,
                    blocks=[
                        TruthBlock(type=BlockType.FIGURE),
                        TruthBlock(
                            type=BlockType.PARAGRAPH,
                            align=Alignment.JUSTIFY,
                            words=[TruthWord(text="Pelo")],
                        ),
                    ],
                ),
                TruthPage(index=1, w_pt=595.28, h_pt=841.89, blank=True),
            ],
        )

        assert truth.page_layout() == [False, True]
        assert truth.figure_counts() == [1, 0]
        assert truth.text() == "Pelo"
