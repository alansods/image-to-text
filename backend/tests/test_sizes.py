"""Tamanho relativo dos blocos medido no documento inteiro (spec layout-detection, D16)."""

from app.models.document import BBox, Block, BlockType, Document, Page, PageSize, Word, WordStatus
from app.pipeline.sizes import normalize_sizes

A4 = PageSize(w_pt=595, h_pt=842)


def block(block_id: str, order: int, word_height: float, rel: float, kind: BlockType) -> Block:
    words = [
        Word(
            id=f"{block_id}w{i}",
            text="palavra",
            bbox=BBox(x=100 + i * 200, y=100 * order, w=150, h=word_height),
            confidence=0.99,
            status=WordStatus.ACCEPTED,
        )
        for i in range(4)
    ]
    return Block(
        id=block_id, type=kind, bbox=BBox(x=100, y=100 * order, w=900, h=word_height),
        order=order, rel_size=rel, words=words, confidence=0.99,
    )  # fmt: skip


def test_cover_title_is_measured_against_the_body_of_the_whole_document() -> None:
    # Capa: só o título, que na página parecia "1,21" do texto da própria página.
    cover = Page(index=0, width=2480, height=3508, page_size=A4, image_ref="pages/0.png",
                 blocks=[block("t", 0, 110, 1.21, BlockType.HEADING)])  # fmt: skip
    paragraphs = [block(f"p{i}", i, 46, 1.0, BlockType.PARAGRAPH) for i in range(5)]
    body = Page(index=1, width=2480, height=3508, page_size=A4, image_ref="pages/1.png",
                blocks=paragraphs)  # fmt: skip
    document = Document(id="d", source_file="a.pdf", pages=[cover, body])

    result = normalize_sizes(document)

    assert result.pages[0].blocks[0].rel_size == 2.39
    assert {b.rel_size for b in result.pages[1].blocks} == {1.0}


def test_document_without_paragraphs_keeps_sizes() -> None:
    page = Page(index=0, width=2480, height=3508, page_size=A4, image_ref="pages/0.png",
                blocks=[block("t", 0, 110, 1.5, BlockType.HEADING)])  # fmt: skip
    document = Document(id="d", source_file="a.png", pages=[page])

    assert normalize_sizes(document).pages[0].blocks[0].rel_size == 1.5
