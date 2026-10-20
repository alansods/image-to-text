"""Validação do arquivo enviado (spec file-upload, lado do servidor)."""

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from app.errors import ErrorCode, UploadRejectedError
from app.validation import SourceKind, inspect_source, save_limited
from tests.conftest import image_bytes, pdf_bytes, png_bytes

WriteFile = Callable[[str, bytes], Path]


class TestFormat:
    @pytest.mark.parametrize(
        ("fmt", "extension"), [("JPEG", "jpg"), ("PNG", "png"), ("WEBP", "webp")]
    )
    def test_accepts_images_by_content(
        self, write_file: WriteFile, fmt: str, extension: str
    ) -> None:
        info = inspect_source(write_file("foto", image_bytes(fmt)))

        assert info.kind is SourceKind.IMAGE
        assert info.extension == extension
        assert info.pages == 1

    def test_accepts_pdf_and_counts_pages(self, write_file: WriteFile) -> None:
        info = inspect_source(write_file("doc", pdf_bytes(pages=3)))

        assert info.kind is SourceKind.PDF
        assert info.extension == "pdf"
        assert info.pages == 3

    def test_rejects_gif(self, write_file: WriteFile) -> None:
        with pytest.raises(UploadRejectedError) as error:
            inspect_source(write_file("anim.gif", image_bytes("GIF")))

        assert error.value.code is ErrorCode.UNSUPPORTED_FORMAT

    def test_rejects_executable_with_png_extension(self, write_file: WriteFile) -> None:
        with pytest.raises(UploadRejectedError) as error:
            inspect_source(write_file("foto.png", b"MZ\x90\x00\x03" + b"\x00" * 200))

        assert error.value.code is ErrorCode.UNSUPPORTED_FORMAT

    def test_rejects_png_header_with_garbage(self, write_file: WriteFile) -> None:
        with pytest.raises(UploadRejectedError) as error:
            inspect_source(write_file("foto.png", png_bytes()[:16] + b"lixo" * 20))

        assert error.value.code is ErrorCode.UNSUPPORTED_FORMAT


class TestPdfLimits:
    def test_rejects_pdf_over_20_pages(self, write_file: WriteFile) -> None:
        with pytest.raises(UploadRejectedError) as error:
            inspect_source(write_file("grande.pdf", pdf_bytes(pages=25)))

        assert error.value.code is ErrorCode.TOO_MANY_PAGES

    def test_accepts_exactly_20_pages(self, write_file: WriteFile) -> None:
        assert inspect_source(write_file("limite.pdf", pdf_bytes(pages=20))).pages == 20

    def test_rejects_password_protected_pdf(self, write_file: WriteFile) -> None:
        with pytest.raises(UploadRejectedError) as error:
            inspect_source(write_file("senha.pdf", pdf_bytes(password="segredo")))

        assert error.value.code is ErrorCode.PDF_PASSWORD


class TestSize:
    def test_saves_file_within_limit(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.bin"

        save_limited(io.BytesIO(b"x" * 100), dest, max_bytes=100)

        assert dest.read_bytes() == b"x" * 100

    def test_rejects_file_over_limit_and_leaves_nothing(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.bin"

        with pytest.raises(UploadRejectedError) as error:
            save_limited(io.BytesIO(b"x" * 101), dest, max_bytes=100)

        assert error.value.code is ErrorCode.FILE_TOO_LARGE
        assert not dest.exists()
