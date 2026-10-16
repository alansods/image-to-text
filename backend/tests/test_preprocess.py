"""Pré-processamento (spec image-preprocessing), testado com o conjunto sintético de precisão."""

import io
import math
from functools import cache
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from app.pipeline.base import PageInput
from app.pipeline.preprocess import (
    clean,
    correct_perspective,
    deskew,
    detect_orientation,
    fix_orientation,
    is_blank,
    load_pages,
    median_char_height,
    preprocess,
)

FIXTURES = Path(__file__).parent / "fixtures" / "precision"
A4_RATIO = 841.89 / 595.28


@cache
def fixture_pages(case: str) -> tuple[PageInput, ...]:
    return tuple(load_pages(next((FIXTURES / case).glob("input.*"))))


def gray(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    return image if image.ndim == 2 else np.asarray(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY))


def rotate(image: NDArray[np.uint8], degrees: float) -> NDArray[np.uint8]:
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return np.asarray(cv2.warpAffine(image, matrix, (w, h), borderValue=(255, 255, 255)))


def horizontal_line_angle(image: NDArray[np.uint8]) -> float:
    """Medida independente da inclinação: ângulo das linhas longas (bordas da tabela) por Hough."""
    binary = cv2.threshold(gray(image), 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    lines = cv2.HoughLinesP(
        binary, 1, math.pi / 1800, threshold=300, minLineLength=image.shape[1] // 3, maxLineGap=5
    )
    assert lines is not None, "nenhuma linha longa encontrada"
    angles = [
        math.degrees(math.atan2(y2 - y1, x2 - x1))
        for x1, y1, x2, y2 in lines[:, 0]
        if abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) < 20
    ]
    return float(np.median(np.abs(angles)))


class TestLoadPages:
    def test_pdf_pages_keep_order_and_sheet_size(self) -> None:
        pages = fixture_pages("relatorio_tres_paginas")

        assert [p.index for p in pages] == [0, 1, 2]
        for page in pages:
            assert page.page_size.w_pt == pytest.approx(595.3, abs=1)
            assert page.page_size.h_pt == pytest.approx(841.9, abs=1)
            # Pelo menos 300 DPI.
            assert page.image.shape[1] >= page.page_size.w_pt / 72 * 300 - 2
            assert page.image.ndim == 3  # colorido: logotipos e fotos entram com cor

    def test_image_is_one_a4_page_oriented_by_its_proportion(self, tmp_path: Path) -> None:
        path = tmp_path / "deitada.png"
        Image.new("RGB", (800, 500), "white").save(path)

        (page,) = load_pages(path)

        assert page.page_size.w_pt > page.page_size.h_pt  # A4 paisagem

    def test_phone_photo_exif_rotation_is_applied(self, tmp_path: Path) -> None:
        image = Image.new("RGB", (400, 300), "white")
        exif = image.getexif()
        exif[0x0112] = 6  # "girar 90° no sentido horário para exibir"
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", exif=exif)
        path = tmp_path / "celular.jpg"
        path.write_bytes(buffer.getvalue())

        (page,) = load_pages(path)

        assert page.image.shape[:2] == (400, 300)


class TestOrientation:
    @pytest.mark.parametrize("quarter_turns", [0, 1, 2, 3])
    def test_detects_and_fixes_rotated_pages(self, quarter_turns: int) -> None:
        upright = fixture_pages("contrato_impresso")[0].image
        rotated = np.ascontiguousarray(np.rot90(upright, quarter_turns))

        fixed = fix_orientation(rotated, detect_orientation(rotated))

        assert fixed.shape == upright.shape
        assert np.array_equal(fixed, upright)

    def test_upside_down_scan(self) -> None:
        image = fixture_pages("cabeca_para_baixo")[0].image

        assert detect_orientation(image) == 180


class TestDeskew:
    @pytest.mark.parametrize("tilt", [7.0, -4.0])
    def test_residual_tilt_is_at_most_half_a_degree(self, tilt: float) -> None:
        page = fixture_pages("recibo_tabela")[0].image
        tilted = rotate(page, tilt)

        straight, _angle = deskew(tilted)

        assert horizontal_line_angle(straight) <= 0.5

    def test_straight_page_is_left_alone(self) -> None:
        page = fixture_pages("recibo_tabela")[0].image

        _, angle = deskew(page)

        assert abs(angle) <= 0.6  # só a inclinação de scanner já presente no caso


class TestPerspective:
    def test_photo_on_desk_becomes_the_sheet_alone(self) -> None:
        photo = fixture_pages("contrato_foto")[0].image

        sheet = correct_perspective(photo)

        assert sheet is not None
        h, w = sheet.shape[:2]
        assert max(h, w) / min(h, w) == pytest.approx(A4_RATIO, rel=0.03)
        border = np.concatenate(
            [sheet[:15].reshape(-1, 3), sheet[-15:].reshape(-1, 3), sheet[:, :15].reshape(-1, 3)]
        )
        assert gray(border.reshape(1, -1, 3)).mean() > 170  # papel, não mesa

    def test_scanned_page_has_no_sheet_outline_to_fix(self) -> None:
        assert correct_perspective(fixture_pages("contrato_impresso")[0].image) is None


class TestCleaning:
    def test_removes_shadow_gradient(self) -> None:
        page = gray(fixture_pages("enfase_mista")[0].image)
        shadow = np.linspace(0.55, 1.0, page.shape[1], dtype=np.float32)[None, :]
        shaded = (page.astype(np.float32) * shadow).astype(np.uint8)

        cleaned = clean(shaded)

        margin = cleaned[60:400, :]  # faixa do topo, só papel
        assert int(np.percentile(margin, 50)) >= 235
        assert margin[:, :200].mean() - margin[:, -200:].mean() < 10

    def test_small_screenshot_text_gets_upscaled(self) -> None:
        result = preprocess(fixture_pages("print_tela")[0])

        assert median_char_height(result.normalized) >= 28
        assert result.aligned.shape[:2] == result.normalized.shape[:2]


class TestBlank:
    def test_only_the_blank_page_of_the_set_is_blank(self) -> None:
        cases = sorted(p.name for p in FIXTURES.iterdir() if (p / "expected.json").exists())
        flags = {
            (case, page.index): is_blank(clean(gray(page.image)))
            for case in cases
            for page in fixture_pages(case)
        }

        assert [key for key, blank in flags.items() if blank] == [("relatorio_tres_paginas", 2)]


class TestPreprocess:
    def test_photo_comes_out_upright_flat_and_with_both_versions(self) -> None:
        result = preprocess(fixture_pages("contrato_foto")[0])

        assert result.perspective_corrected
        h, w = result.aligned.shape[:2]
        assert h / w == pytest.approx(A4_RATIO, rel=0.03)
        assert result.aligned.ndim == 3 and result.normalized.ndim == 2
        assert result.normalized.shape == (h, w)
        assert not result.blank

    def test_upside_down_page_is_turned(self) -> None:
        result = preprocess(fixture_pages("cabeca_para_baixo")[0])

        assert result.rotation == 180
        assert detect_orientation(result.aligned) == 0
