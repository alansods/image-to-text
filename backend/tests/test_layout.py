"""Detecção de layout (spec layout-detection): tipos, ordem de leitura, colunas, alinhamento,
tamanho relativo, elementos não-texto e listas."""

from functools import cache
from pathlib import Path
from typing import ClassVar

import cv2
import numpy as np
import pytest

from app.models.document import (
    Alignment,
    BBox,
    Block,
    BlockType,
    Word,
    WordStatus,
)
from app.pipeline.base import PageInput
from app.pipeline.layout import (
    Candidate,
    PageLayout,
    analyze_layout,
    group_lists,
    map_label,
    mark_letterhead,
    merge_passes,
    reading_order,
    size_for_text,
    text_paragraphs,
)
from app.pipeline.preprocess import load_pages, median_char_height, preprocess
from tests.precision.truth import Truth

FIXTURES = Path(__file__).parent / "fixtures" / "precision"


def box(x: float, y: float, w: float, h: float) -> BBox:
    return BBox(x=x, y=y, w=w, h=h)


def cand(
    x: float, y: float, w: float, h: float, label: str = "text", score: float = 0.9
) -> Candidate:
    return Candidate(label=label, score=score, bbox=box(x, y, w, h))


# ------------------------------------------------------------------ geometria pura


class TestLabels:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("doc_title", BlockType.HEADING),
            ("paragraph_title", BlockType.HEADING),
            ("text", BlockType.PARAGRAPH),
            ("figure_title", BlockType.PARAGRAPH),
            ("abstract", BlockType.PARAGRAPH),
            ("table", BlockType.TABLE),
            ("image", BlockType.FIGURE),
            ("chart", BlockType.FIGURE),
            ("seal", BlockType.FIGURE),
            ("formula", BlockType.FORMULA),
            ("header", BlockType.HEADER),
            ("footer", BlockType.FOOTER),
            ("number", BlockType.FOOTER),
        ],
    )
    def test_model_labels_map_to_spec_types(self, label: str, expected: BlockType) -> None:
        assert map_label(label) is expected


class TestTwoPasses:
    def test_keeps_confident_boxes_and_fills_gaps_with_weaker_ones(self) -> None:
        strong = [cand(0, 0, 100, 50, "header", 0.77), cand(0, 100, 500, 300, "image", 0.98)]
        weak = [
            cand(0, 0, 60, 50, "header", 0.44),  # duplicata do cabeçalho: descartada
            cand(50, 500, 400, 40, "doc_title", 0.37),  # área vazia: aproveitada
            cand(80, 560, 300, 30, "text", 0.46),  # área vazia: aproveitada
            cand(50, 500, 400, 90, "text", 0.36),  # cobre as duas anteriores: descartada
        ]

        merged = merge_passes(strong + weak)

        assert sorted((c.label, c.score) for c in merged) == [
            ("doc_title", 0.37),
            ("header", 0.77),
            ("image", 0.98),
            ("text", 0.46),
        ]


class TestReadingOrder:
    def test_single_column_top_to_bottom(self) -> None:
        blocks = [cand(100, 300, 800, 50), cand(100, 100, 800, 50), cand(100, 200, 300, 50)]

        ordered, columns = reading_order(blocks)

        assert [c.bbox.y for c, _ in ordered] == [100, 200, 300]
        assert columns == 1

    def test_two_columns_left_column_first_even_with_aligned_gaps(self) -> None:
        title = cand(100, 50, 1000, 40)
        left = [cand(100, 120, 480, 200), cand(100, 350, 480, 200), cand(100, 600, 480, 100)]
        right = [cand(620, 120, 480, 150), cand(620, 290, 480, 260), cand(620, 600, 480, 120)]

        ordered, columns = reading_order([*right, title, *left])

        assert [c for c, _ in ordered] == [title, *left, *right]
        assert [col for _, col in ordered] == [0, 0, 0, 0, 1, 1, 1]
        assert columns == 2

    def test_header_first_and_footer_last(self) -> None:
        footer = cand(500, 1000, 30, 20, "number")
        header = cand(700, 10, 300, 20, "header")
        body = cand(100, 100, 800, 300)

        ordered, _ = reading_order([footer, body, header])

        assert [c for c, _ in ordered] == [header, body, footer]

    def test_side_by_side_signatures_are_not_page_columns(self) -> None:
        text = cand(100, 100, 1000, 300)
        signatures = [cand(150, 500, 300, 60, "image"), cand(700, 500, 300, 60, "image")]

        _, columns = reading_order([text, *signatures])

        assert columns == 1


class TestLetterhead:
    """Papel timbrado: letra de 40 px, texto entre x=500 e x=2700, de y=1000 a y=2100."""

    CHAR = 40.0
    BODY: ClassVar = [
        cand(500, 1000, 2200, 300),
        cand(510, 1400, 2190, 300),
        cand(500, 1800, 2200, 300),
    ]

    def marked(self, *extra: Candidate) -> list[Candidate]:
        return mark_letterhead([*self.BODY, *extra], self.CHAR)

    def test_logo_of_letters_left_of_the_margin_becomes_an_image(self) -> None:
        logo = cand(150, 170, 1160, 390, "doc_title")

        result = self.marked(logo)

        assert Candidate("letterhead", logo.score, logo.bbox) in result
        assert logo not in result

    def test_address_and_decorative_stroke_become_one_image(self) -> None:
        stroke = cand(150, 4030, 135, 380, "footer")
        address = cand(300, 4100, 750, 230)

        images = [c for c in self.marked(stroke, address) if c.label == "letterhead"]

        assert images == [Candidate("letterhead", 0.9, box(150, 4030, 900, 380))]

    def test_logo_subtitle_inside_the_margin_joins_the_logo(self) -> None:
        logo = cand(150, 170, 1160, 300, "doc_title")
        subtitle = cand(700, 500, 400, 50)
        header = cand(1430, 250, 1270, 60, "header")

        result = self.marked(logo, subtitle, header)

        assert Candidate("letterhead", 0.9, box(150, 170, 1160, 380)) in result
        assert subtitle not in result
        assert header in result

    def test_header_and_page_number_inside_the_margins_stay_text(self) -> None:
        header = cand(1430, 250, 1270, 60, "header")
        number = cand(1600, 3960, 30, 50, "number")
        title = cand(730, 670, 1780, 70, "paragraph_title")

        result = self.marked(header, number, title)

        assert result == [*self.BODY, header, number, title]

    def test_body_paragraph_outside_the_bands_is_untouched(self) -> None:
        wide = cand(150, 2400, 2700, 300)

        assert wide in self.marked(wide)

    def test_sheet_inside_a_larger_page_still_has_its_letterhead_found(self) -> None:
        # Folha escaneada no meio de uma página maior (5560 px de altura), com moldura em volta.
        body = [cand(1270, 990, 1765, 72), *(cand(1050, y, 2200, 300) for y in (1350, 2000, 3800))]
        logo = cand(700, 490, 1150, 390, "doc_title")  # acaba em 16% da página
        header = cand(1960, 575, 1265, 63, "header")
        stroke = cand(700, 4310, 140, 380, "image")  # arco, já visto como imagem
        address = cand(850, 4385, 750, 235)  # começa em 79% da página
        number = cand(2136, 4243, 33, 55, "number")

        result = mark_letterhead([*body, logo, header, stroke, address, number], 32.0)

        letterheads = [c for c in result if c.label == "letterhead"]
        assert [c.bbox for c in letterheads] == [logo.bbox, box(700, 4310, 900, 380)]
        assert header in result
        assert number in result
        assert all(c in result for c in body)

    def test_page_without_body_paragraphs_is_untouched(self) -> None:
        cover = [cand(150, 170, 1160, 390, "doc_title"), cand(800, 2000, 1600, 100, "doc_title")]

        assert mark_letterhead(cover, self.CHAR) == cover


def word(word_id: str, text: str, x: float = 0) -> Word:
    return Word(
        id=word_id, text=text, bbox=box(x, 0, 10, 10), confidence=0.9, status=WordStatus.ACCEPTED
    )


def paragraph(block_id: str, order: int, texts: list[str], x: float = 100) -> Block:
    return Block(
        id=block_id,
        type=BlockType.PARAGRAPH,
        bbox=box(x, order * 50, 400, 40),
        order=order,
        words=[word(f"{block_id}w{i}", t, x) for i, t in enumerate(texts)],
        confidence=0.9,
    )


class TestLists:
    def test_consecutive_marked_paragraphs_become_one_list_with_levels(self) -> None:
        blocks = [
            paragraph("p0", 0, ["As", "entregas:"]),
            paragraph("p1", 1, ["1.", "catálogo"]),
            paragraph("p2", 2, ["a)", "atas"], x=140),
            paragraph("p3", 3, ["b)", "mapas"], x=140),
            paragraph("p4", 4, ["2.", "oficina"]),
            paragraph("p5", 5, ["Fim."]),
        ]

        result = group_lists(blocks)

        assert [b.type for b in result] == [
            BlockType.PARAGRAPH,
            BlockType.LIST,
            BlockType.PARAGRAPH,
        ]
        lst = result[1]
        assert [w.text for w in lst.words] == [
            "1.",
            "catálogo",
            "a)",
            "atas",
            "b)",
            "mapas",
            "2.",
            "oficina",
        ]
        assert [(i.word_start, i.level) for i in lst.items] == [(0, 0), (2, 1), (4, 1), (6, 0)]
        assert [b.order for b in result] == [0, 1, 2]

    @pytest.mark.parametrize("marker", ["a)", "(b)", "1.", "10)", "•", "-", "–", "iv)"])  # noqa: RUF001
    def test_recognizes_common_markers(self, marker: str) -> None:
        blocks = [paragraph("p1", 0, [marker, "um"]), paragraph("p2", 1, [marker, "dois"])]

        assert group_lists(blocks)[0].type is BlockType.LIST

    def test_single_marked_paragraph_is_not_a_list(self) -> None:
        blocks = [paragraph("p1", 0, ["1.", "Introdução"]), paragraph("p2", 1, ["Texto."])]

        assert [b.type for b in group_lists(blocks)] == [BlockType.PARAGRAPH] * 2


# ------------------------------------------------------------------ integração com o modelo


def fixture_page(case: str, page_index: int = 0) -> PageInput:
    return load_pages(next((FIXTURES / case).glob("input.*")))[page_index]


@cache
def layout_of(case: str, page_index: int = 0) -> PageLayout:
    pre = preprocess(fixture_page(case, page_index))
    return analyze_layout(pre.aligned, pre.normalized)


def truth(case: str) -> Truth:
    return Truth.model_validate_json((FIXTURES / case / "expected.json").read_text())


def texts_by_y(layout: PageLayout) -> list[BlockType]:
    return [b.type for b in sorted(layout.blocks, key=lambda b: b.bbox.y)]


class TestContract:
    def test_title_is_centered_and_larger(self) -> None:
        first = layout_of("contrato_impresso").blocks[0]

        assert first.type is BlockType.HEADING
        assert first.align is Alignment.CENTER
        assert first.rel_size > 1.2

    def test_paragraphs_are_justified_and_place_line_centered(self) -> None:
        blocks = layout_of("contrato_impresso").blocks
        paragraphs = [b for b in blocks if b.type is BlockType.PARAGRAPH]

        assert paragraphs[0].align is Alignment.JUSTIFY  # "Pelo presente instrumento..."
        place = next(b for b in paragraphs if b.bbox.w < 800 and b.bbox.y > 1700)
        assert place.align is Alignment.CENTER  # "São Paulo, 15 de outubro de 2026."

    def test_signature_is_a_figure(self) -> None:
        figures = [b for b in layout_of("contrato_impresso").blocks if b.type is BlockType.FIGURE]

        assert len(figures) == 1
        assert 1900 < figures[0].bbox.y < 2100  # a rubrica, entre a data e "CONTRATANTE"

    def test_reading_order_follows_the_page(self) -> None:
        blocks = layout_of("contrato_impresso").blocks

        assert [b.bbox.y for b in blocks] == sorted(b.bbox.y for b in blocks)
        assert [b.order for b in blocks] == list(range(len(blocks)))


class TestTwoColumnArticle:
    def test_has_two_columns_and_reads_left_column_first(self) -> None:
        layout = layout_of("artigo_duas_colunas")
        body = [b for b in layout.blocks if b.bbox.y > 470]

        assert layout.columns == 2
        columns = [b.column for b in body]
        assert columns == sorted(columns)
        assert set(columns) == {0, 1}

    def test_caption_comes_right_after_the_chart(self) -> None:
        blocks = layout_of("artigo_duas_colunas").blocks
        index = next(i for i, b in enumerate(blocks) if b.type is BlockType.FIGURE)

        caption = blocks[index + 1]
        assert caption.type is BlockType.PARAGRAPH
        assert caption.bbox.y > blocks[index].bbox.y


class TestOtherDocuments:
    def test_receipt_has_table_and_stamp(self) -> None:
        types = [b.type for b in layout_of("recibo_tabela").blocks]

        assert types.count(BlockType.TABLE) == 1
        assert types.count(BlockType.FIGURE) == 1

    def test_cover_keeps_logo_illustration_title_and_subtitle(self) -> None:
        blocks = layout_of("relatorio_tres_paginas", 0).blocks
        figures = [b for b in blocks if b.type is BlockType.FIGURE]
        texts = [b for b in blocks if b.type is not BlockType.FIGURE]

        assert len(figures) == 2  # logotipo e ilustração
        assert len(texts) >= 2  # título e subtítulo recuperados
        assert all(b.align is Alignment.CENTER for b in texts)

    def test_header_first_and_page_number_last(self) -> None:
        blocks = layout_of("relatorio_tres_paginas", 1).blocks

        assert blocks[0].type is BlockType.HEADER
        assert blocks[0].align is Alignment.RIGHT
        assert blocks[-1].type is BlockType.FOOTER

    @pytest.mark.parametrize(
        "case",
        [
            "contrato_impresso",
            "contrato_foto",
            "recibo_tabela",
            "artigo_duas_colunas",
            "relatorio_tres_paginas",
            "print_tela",
            "cabeca_para_baixo",
            "enfase_mista",
            "manuscrito",
            "contrato_timbrado",
        ],
    )
    def test_figure_count_matches_truth_on_every_non_blank_page(self, case: str) -> None:
        expected = truth(case)
        for page in expected.pages:
            if page.blank:
                continue
            found = [b for b in layout_of(case, page.index).blocks if b.type is BlockType.FIGURE]
            assert len(found) == expected.figure_counts()[page.index], (case, page.index)


class TestLetterheadContract:
    def test_logo_and_address_are_images_header_and_number_stay_text(self) -> None:
        layout = layout_of("contrato_timbrado")
        height = max(b.bbox.y + b.bbox.h for b in layout.blocks)
        figures = sorted(
            (b for b in layout.blocks if b.type is BlockType.FIGURE), key=lambda b: b.bbox.y
        )
        types = [b.type for b in layout.blocks]

        assert len(figures) == 2
        assert figures[0].bbox.y < 0.1 * height  # logotipo
        assert figures[1].bbox.y > 0.85 * height  # endereço com o arco
        assert types.count(BlockType.HEADER) == 1
        assert types.count(BlockType.FOOTER) == 1

    def test_sheet_inside_a_larger_page_keeps_letterhead_and_platform_line_as_images(self) -> None:
        layout = layout_of("contrato_timbrado_moldura")
        letterheads = [b for b in layout.blocks if b.label == "letterhead"]
        types = [b.type for b in layout.blocks]

        assert len(letterheads) == 3  # logotipo, endereço com o arco e linha da plataforma
        assert types.count(BlockType.HEADER) == 1
        assert types.count(BlockType.FOOTER) == 1


def test_layout_coordinates_match_the_page_image() -> None:
    layout = layout_of("recibo_tabela")
    page = preprocess(load_pages(FIXTURES / "recibo_tabela" / "input.pdf")[0])

    h, w = page.normalized.shape
    assert all(b.bbox.x >= 0 and b.bbox.x + b.bbox.w <= w + 1 for b in layout.blocks)
    assert all(b.bbox.y >= 0 and b.bbox.y + b.bbox.h <= h + 1 for b in layout.blocks)
    assert isinstance(np.asarray(page.aligned), np.ndarray)


class TestSizeForText:
    # A altura medida é a da maiúscula quando o bloco é todo em maiúsculas (D5).
    def test_all_caps_block_is_measured_by_cap_height(self) -> None:
        assert size_for_text(1.91, "CONTRATO DE PRESTAÇÃO DE SERVIÇOS") == 1.36
        assert size_for_text(1.54, "COMUNICADO INTERNO Nº 18/2026") == 1.1

    def test_mixed_case_text_keeps_the_measured_size(self) -> None:
        assert size_for_text(1.0, "Pelo presente instrumento, JOÃO PEREIRA") == 1.0
        assert size_for_text(1.4, "Relatório Anual") == 1.4

    def test_text_without_letters_keeps_the_measured_size(self) -> None:
        assert size_for_text(1.2, "— · —") == 1.2


class TestTextInsideFigures:
    """Texto não vira imagem (spec layout-detection, D14)."""

    def test_blurred_photo_paragraphs_are_read_as_text(self) -> None:
        page = load_pages(FIXTURES / "contrato_foto" / "input.jpg")[0]
        blurred = np.ascontiguousarray(cv2.GaussianBlur(page.image, (0, 0), 1.5))
        pre = preprocess(PageInput(page.index, blurred, page.page_size))
        blocks = analyze_layout(pre.aligned, pre.normalized).blocks

        texts = [b for b in blocks if b.type not in {BlockType.FIGURE, BlockType.FORMULA}]
        images = [b for b in blocks if b.type in {BlockType.FIGURE, BlockType.FORMULA}]
        assert len(texts) >= 8
        assert len(images) == 1  # a rubrica
        assert [b.bbox.y for b in blocks] == sorted(b.bbox.y for b in blocks)

    def test_paragraphs_inside_a_region_are_found(self) -> None:
        # A página inteira do contrato como se fosse uma única "figura".
        pre = preprocess(fixture_page("contrato_impresso"))
        expected = [
            b
            for b in layout_of("contrato_impresso").blocks
            if b.type in {BlockType.HEADING, BlockType.PARAGRAPH}
        ]

        found = text_paragraphs(pre.normalized, median_char_height(pre.normalized))

        assert len(found) >= len(expected) - 2
        assert [b.y for b in found] == sorted(b.y for b in found)

    @pytest.mark.parametrize(
        ("case", "index"),
        [
            ("contrato_impresso", 0),
            ("contrato_foto", 0),
            ("recibo_tabela", 0),
            ("artigo_duas_colunas", 0),
            ("relatorio_tres_paginas", 0),
            ("print_tela", 0),
        ],
    )
    def test_real_figures_have_no_text_lines(self, case: str, index: int) -> None:
        page = fixture_page(case, index)
        pre = preprocess(page)
        for block in analyze_layout(pre.aligned, pre.normalized).blocks:
            if block.type is BlockType.FIGURE:
                b = block.bbox
                crop = pre.normalized[int(b.y) : int(b.y + b.h), int(b.x) : int(b.x + b.w)]
                assert text_paragraphs(crop, median_char_height(pre.normalized)) == [], (case, b)
