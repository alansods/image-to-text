"""Formato interno Document → Page → Block → Word/Cell e suas regras de validação."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.models.document import (
    ILLEGIBLE,
    Alignment,
    Alternative,
    BBox,
    Block,
    BlockType,
    Cell,
    Document,
    ListItem,
    Page,
    PageSize,
    ReadingSource,
    ResolvedBy,
    Word,
    WordStatus,
)


def make_word(word_id: str = "w1", text: str = "contrato", **overrides: Any) -> Word:
    data: dict[str, Any] = {
        "id": word_id,
        "text": text,
        "bbox": BBox(x=10, y=10, w=80, h=20),
        "confidence": 0.98,
        "status": WordStatus.ACCEPTED,
    }
    data.update(overrides)
    return Word(**data)


def make_uncertain_word(word_id: str = "w9") -> Word:
    return make_word(
        word_id,
        "SlLVA",
        confidence=0.64,
        status=WordStatus.UNCERTAIN,
        alternatives=[
            Alternative(text="SILVA", confidence=0.82, source=ReadingSource.PADDLE),
            Alternative(text="SlLVA", confidence=0.64, source=ReadingSource.DOCTR),
        ],
    )


def make_paragraph(block_id: str = "b1", order: int = 0, words: list[Word] | None = None) -> Block:
    return Block(
        id=block_id,
        type=BlockType.PARAGRAPH,
        bbox=BBox(x=0, y=0, w=500, h=100),
        order=order,
        align=Alignment.JUSTIFY,
        words=words if words is not None else [make_word()],
        confidence=0.95,
    )


def make_page(index: int = 0, blocks: list[Block] | None = None, blank: bool = False) -> Page:
    return Page(
        index=index,
        width=2480,
        height=3508,
        page_size=PageSize(w_pt=595.3, h_pt=841.9),
        image_ref=f"pages/{index}.png",
        blank=blank,
        blocks=blocks if blocks is not None else [make_paragraph()],
    )


class TestWord:
    def test_confidence_must_be_between_0_and_1(self) -> None:
        with pytest.raises(ValidationError):
            make_word(confidence=1.2)

    def test_emphasis_defaults_to_plain(self) -> None:
        word = make_word()

        assert word.bold is False
        assert word.italic is False

    def test_uncertain_word_needs_two_alternatives(self) -> None:
        with pytest.raises(ValidationError, match="alternativas"):
            make_word(
                status=WordStatus.UNCERTAIN,
                alternatives=[
                    Alternative(text="SILVA", confidence=0.8, source=ReadingSource.PADDLE)
                ],
            )

    def test_illegible_uncertain_word_may_have_no_alternatives(self) -> None:
        word = make_word(text=ILLEGIBLE, confidence=0.0, status=WordStatus.UNCERTAIN)

        assert word.text == "[ilegível]"

    def test_alternatives_must_be_distinct(self) -> None:
        with pytest.raises(ValidationError, match="distintas"):
            make_word(
                status=WordStatus.UNCERTAIN,
                alternatives=[
                    Alternative(text="SILVA", confidence=0.8, source=ReadingSource.PADDLE),
                    Alternative(text="SILVA", confidence=0.7, source=ReadingSource.DOCTR),
                ],
            )

    def test_resolved_word_records_which_step_resolved_it(self) -> None:
        with pytest.raises(ValidationError, match="resolved_by"):
            make_word(status=WordStatus.RESOLVED)

        word = make_word(status=WordStatus.RESOLVED, resolved_by=ResolvedBy.CONFIDENCE)
        assert word.resolved_by is ResolvedBy.CONFIDENCE

    def test_only_resolved_words_have_resolved_by(self) -> None:
        with pytest.raises(ValidationError, match="resolved_by"):
            make_word(resolved_by=ResolvedBy.REREAD)

    def test_bbox_needs_positive_size(self) -> None:
        with pytest.raises(ValidationError):
            BBox(x=0, y=0, w=0, h=10)


class TestBlock:
    def test_figure_needs_crop_of_original(self) -> None:
        with pytest.raises(ValidationError, match="image_ref"):
            Block(
                id="b2",
                type=BlockType.FIGURE,
                bbox=BBox(x=0, y=0, w=100, h=50),
                order=0,
                confidence=1.0,
            )

    def test_figure_has_no_words(self) -> None:
        with pytest.raises(ValidationError, match="palavras"):
            Block(
                id="b2",
                type=BlockType.FIGURE,
                bbox=BBox(x=0, y=0, w=100, h=50),
                order=0,
                image_ref="crops/b2.png",
                words=[make_word()],
                confidence=1.0,
            )

    def test_table_needs_cells(self) -> None:
        with pytest.raises(ValidationError, match="células"):
            Block(
                id="b3",
                type=BlockType.TABLE,
                bbox=BBox(x=0, y=0, w=400, h=200),
                order=0,
                confidence=0.9,
            )

    def test_text_block_needs_words(self) -> None:
        with pytest.raises(ValidationError, match="palavras"):
            make_paragraph(words=[])

    def test_relative_size_defaults_to_body_text(self) -> None:
        assert make_paragraph().rel_size == 1.0

    def test_cell_spans_are_at_least_one(self) -> None:
        with pytest.raises(ValidationError):
            Cell(row=0, col=0, row_span=0, col_span=1, words=[])


class TestPage:
    def test_blank_page_has_no_blocks(self) -> None:
        with pytest.raises(ValidationError, match="em branco"):
            make_page(blank=True)

        assert make_page(blank=True, blocks=[]).blocks == []

    def test_reading_order_is_unique_within_page(self) -> None:
        with pytest.raises(ValidationError, match="ordem"):
            make_page(blocks=[make_paragraph("b1", 0), make_paragraph("b2", 0)])

    def test_columns_default_to_one(self) -> None:
        assert make_page().columns == 1


class TestDocument:
    def test_pages_are_numbered_in_sequence(self) -> None:
        with pytest.raises(ValidationError, match="páginas"):
            Document(id="d1", source_file="contrato.pdf", pages=[make_page(0), make_page(2)])

    def test_word_ids_are_unique_in_document(self) -> None:
        page0 = make_page(0, [make_paragraph("b1", 0, [make_word("w1")])])
        page1 = make_page(1, [make_paragraph("b2", 0, [make_word("w1")])])

        with pytest.raises(ValidationError, match="w1"):
            Document(id="d1", source_file="contrato.pdf", pages=[page0, page1])

    def test_counts_uncertain_words_including_table_cells(self) -> None:
        table = Block(
            id="b2",
            type=BlockType.TABLE,
            bbox=BBox(x=0, y=200, w=400, h=100),
            order=1,
            cells=[Cell(row=0, col=0, words=[make_uncertain_word("w3")])],
            confidence=0.9,
        )
        page = make_page(0, [make_paragraph("b1", 0, [make_uncertain_word("w2")]), table])
        document = Document(id="d1", source_file="contrato.pdf", pages=[page])

        assert document.uncertain_count() == 2
        assert [w.id for w in document.uncertain_words()] == ["w2", "w3"]

    def test_round_trips_through_json(self) -> None:
        document = Document(id="d1", source_file="contrato.pdf", pages=[make_page(0)])

        assert Document.model_validate_json(document.model_dump_json()) == document

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            Document.model_validate(
                {"id": "d1", "source_file": "a.pdf", "pages": [], "language": "pt"}
            )


class TestListItems:
    def make_list(self, items: list[ListItem], words: int = 4) -> Block:
        return Block(
            id="l1",
            type=BlockType.LIST,
            bbox=BBox(x=0, y=0, w=300, h=60),
            order=0,
            words=[make_word(f"w{i}", f"p{i}") for i in range(words)],
            items=items,
            confidence=0.9,
        )

    def test_list_records_where_each_item_starts_and_its_level(self) -> None:
        block = self.make_list([ListItem(word_start=0, level=0), ListItem(word_start=2, level=1)])

        assert [(i.word_start, i.level) for i in block.items] == [(0, 0), (2, 1)]

    def test_list_needs_items(self) -> None:
        with pytest.raises(ValidationError, match="itens"):
            self.make_list([])

    def test_first_item_starts_at_first_word_and_items_go_forward(self) -> None:
        with pytest.raises(ValidationError, match="itens"):
            self.make_list([ListItem(word_start=1, level=0)])
        with pytest.raises(ValidationError, match="itens"):
            self.make_list([ListItem(word_start=0, level=0), ListItem(word_start=0, level=0)])
        with pytest.raises(ValidationError, match="itens"):
            self.make_list([ListItem(word_start=0, level=0), ListItem(word_start=9, level=0)])

    def test_only_lists_have_items(self) -> None:
        with pytest.raises(ValidationError, match="itens"):
            Block(
                id="b1",
                type=BlockType.PARAGRAPH,
                bbox=BBox(x=0, y=0, w=10, h=10),
                order=0,
                words=[make_word()],
                items=[ListItem(word_start=0, level=0)],
                confidence=0.9,
            )
