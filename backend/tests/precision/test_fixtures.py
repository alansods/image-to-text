"""Conjunto sintético de precisão: cada caso tem entrada e gabarito coerentes, e é reproduzível."""

from pathlib import Path

import pytest
from PIL import Image

from tests.fixtures.precision.generator.cases import CASES, generate
from tests.precision.truth import Truth

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "precision"


def load_truth(case: str) -> Truth:
    return Truth.model_validate_json((ROOT / case / "expected.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", sorted(CASES))
def test_case_has_input_and_consistent_truth(case: str) -> None:
    truth = load_truth(case)

    assert truth.case == case
    assert (ROOT / case / truth.input).is_file()
    assert (ROOT / case / "expected.txt").read_text(encoding="utf-8") == truth.text() + "\n"
    assert truth.words(), "todo caso precisa ter texto"


def test_set_covers_the_features_the_specs_require() -> None:
    truths = [load_truth(case) for case in CASES]
    blocks = [b for t in truths for p in t.pages for b in p.blocks]

    assert any(len(t.pages) >= 3 for t in truths), "PDF multipágina"
    assert any(p.blank for t in truths for p in t.pages), "página em branco"
    assert any(p.columns == 2 for t in truths for p in t.pages), "duas colunas"
    assert any(c.col_span > 1 for b in blocks for c in b.cells), "célula mesclada"
    assert any(b.type == "figure" for b in blocks), "figuras"
    assert any(b.type == "header" for b in blocks) and any(b.type == "footer" for b in blocks)
    assert {b.align for b in blocks} >= {"left", "center", "right", "justify"}
    words = [w for t in truths for w in t.words()]
    assert any(w.bold for w in words) and any(w.italic for w in words)
    assert any(w.bold and w.italic for w in words), "negrito e itálico juntos"
    assert any(t.handwriting for t in truths), "manuscrito"


def test_generator_is_reproducible(tmp_path: Path) -> None:
    generate(tmp_path, ["print_tela"])

    committed = ROOT / "print_tela"
    assert (tmp_path / "print_tela" / "expected.json").read_text() == (
        committed / "expected.json"
    ).read_text()
    with (
        Image.open(tmp_path / "print_tela" / "input.png") as new,
        Image.open(committed / "input.png") as old,
    ):
        assert new.tobytes() == old.tobytes()
