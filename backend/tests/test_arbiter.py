"""Árbitro opcional (spec reading-reconciliation, design D7). Modelo falso."""

import numpy as np
import pytest

from app.models.document import ILLEGIBLE
from app.pipeline.arbiter import VlArbiter, validate_choice

OPTIONS = ["Silva", "Sllva"]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Silva", "Silva"),
        (" Silva\n", "Silva"),
        ("Sllva", "Sllva"),
        (ILLEGIBLE, ILLEGIBLE),
        ("Silveira", None),
        ("", None),
    ],
)
def test_only_existing_readings_or_illegible_are_accepted(
    answer: str, expected: str | None
) -> None:
    assert validate_choice(answer, OPTIONS) == expected


def test_quotes_and_dashes_do_not_count_as_new_text() -> None:
    assert validate_choice('"Lei"', ["“Lei”", "Lel"]) == "“Lei”"


class FakeModel:
    def __init__(self, answers: list[str]) -> None:
        self.answers = answers
        self.calls = 0

    def __call__(self, image: np.ndarray) -> str:
        self.calls += 1
        return self.answers.pop(0)


def test_reads_the_word_and_answers_an_option() -> None:
    model = FakeModel(["Silva"])
    arbiter = VlArbiter(model)
    word = np.zeros((20, 60), dtype=np.uint8)

    assert arbiter.choose(word, word, OPTIONS) == "Silva"
    assert model.calls == 1


def test_uses_the_line_when_the_word_alone_is_not_enough() -> None:
    model = FakeModel(["Sil", "assinado por João Silva em"])
    word = np.zeros((20, 60), dtype=np.uint8)

    assert VlArbiter(model).choose(word, word, OPTIONS) == "Silva"


def test_gives_up_when_nothing_matches() -> None:
    model = FakeModel(["Silveira", "assinado por João Silveira"])
    word = np.zeros((20, 60), dtype=np.uint8)

    assert VlArbiter(model).choose(word, word, OPTIONS) is None
