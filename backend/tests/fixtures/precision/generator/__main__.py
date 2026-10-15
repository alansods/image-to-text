"""Regenera os casos: `uv run python -m tests.fixtures.precision.generator [caso ...]`."""

import sys
from pathlib import Path

from tests.fixtures.precision.generator.cases import generate

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    for truth in generate(ROOT, sys.argv[1:] or None):
        words = len(truth.words())
        print(f"{truth.case}: {len(truth.pages)} página(s), {words} palavras -> {truth.input}")
