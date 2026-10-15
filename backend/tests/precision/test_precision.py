"""Teste lento de precisão contra o conjunto sintético (spec text-recognition, document-export).

Rodar com: `uv run pytest -m precision -s`. Fica pulado até o pipeline existir: espera uma função
`app.pipeline.convert.convert_file(path) -> Document`, que entra nas tasks 4 a 7.
"""

from dataclasses import dataclass
from pathlib import Path
from statistics import mean

import pytest

from tests.fixtures.precision.generator.cases import CASES
from tests.precision.metrics import (
    cer,
    document_text,
    emphasis_accuracy,
    figure_counts,
    page_layout,
    wer,
)
from tests.precision.test_fixtures import ROOT, load_truth

pytestmark = pytest.mark.precision

MAX_CER = 0.01
MAX_WER = 0.02
MIN_EMPHASIS = 0.95


@dataclass
class CaseResult:
    case: str
    handwriting: bool
    cer: float
    wer: float
    emphasis: float
    pages_ok: bool
    figures_ok: bool


def test_printed_documents_meet_precision_targets() -> None:
    convert = pytest.importorskip(
        "app.pipeline.convert", reason="pipeline ainda não existe"
    ).convert_file

    rows: list[CaseResult] = []
    for case in sorted(CASES):
        truth = load_truth(case)
        document = convert(Path(ROOT / case / truth.input))
        text = document_text(document)
        words = [w for page in document.pages for block in page.blocks for w in block.all_words()]
        rows.append(
            CaseResult(
                case=case,
                handwriting=truth.handwriting,
                cer=cer(truth.text(), text),
                wer=wer(truth.text(), text),
                emphasis=emphasis_accuracy(truth.words(), words),
                pages_ok=page_layout(document) == truth.page_layout(),
                figures_ok=figure_counts(document) == truth.figure_counts(),
            )
        )

    for row in rows:
        print(
            f"{row.case:<24} CER {row.cer:.2%}  WER {row.wer:.2%}  ênfase {row.emphasis:.1%}  "
            f"páginas {'ok' if row.pages_ok else 'ERRO'}  "
            f"figuras {'ok' if row.figures_ok else 'ERRO'}"
            + ("  (manuscrito: só reportado)" if row.handwriting else "")
        )

    printed = [r for r in rows if not r.handwriting]
    assert mean(r.cer for r in printed) <= MAX_CER
    assert mean(r.wer for r in printed) <= MAX_WER
    assert mean(r.emphasis for r in printed) >= MIN_EMPHASIS
    assert all(r.pages_ok for r in rows), "número de páginas ou página em branco diferente"
    assert all(r.figures_ok for r in rows), "figura perdida ou a mais"
