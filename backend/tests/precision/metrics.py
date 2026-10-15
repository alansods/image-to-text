"""Métricas que comparam o `Document` produzido pelo pipeline com o gabarito sintético."""

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

import jiwer

from app.models.document import IMAGE_BLOCK_TYPES, Block, BlockType, Document, Word
from tests.precision.truth import TruthWord


def _block_text(block: Block) -> str:
    if block.type is BlockType.TABLE:
        rows: dict[int, list[str]] = {}
        for cell in sorted(block.cells, key=lambda c: (c.row, c.col)):
            rows.setdefault(cell.row, []).append(" ".join(w.text for w in cell.words))
        return "\n".join("\t".join(cells) for _, cells in sorted(rows.items()))
    return " ".join(w.text for w in block.words)


def document_text(document: Document) -> str:
    """Texto em ordem de leitura, com a mesma regra de "Copiar texto"."""
    texts = [
        _block_text(block)
        for page in document.pages
        for block in sorted(page.blocks, key=lambda b: b.order)
        if block.type not in IMAGE_BLOCK_TYPES
    ]
    return "\n\n".join(texts)


def _normalize(text: str) -> str:
    # Diferenças de espaço/quebra de linha não contam como erro de leitura.
    return re.sub(r"\s+", " ", text).strip()


def cer(reference: str, hypothesis: str) -> float:
    return float(jiwer.cer(_normalize(reference), _normalize(hypothesis)))


def wer(reference: str, hypothesis: str) -> float:
    return float(jiwer.wer(_normalize(reference), _normalize(hypothesis)))


def emphasis_accuracy(truth: Sequence[TruthWord], predicted: Sequence[Word]) -> float:
    """Fração das palavras do gabarito lidas com o negrito/itálico certo (não lidas contam erro)."""
    if not truth:
        return 1.0
    matcher = SequenceMatcher(
        a=[w.text for w in truth], b=[w.text for w in predicted], autojunk=False
    )
    correct = 0
    for match in matcher.get_matching_blocks():
        for offset in range(match.size):
            expected = truth[match.a + offset]
            got = predicted[match.b + offset]
            correct += expected.bold == got.bold and expected.italic == got.italic
    return correct / len(truth)


def page_layout(document: Document) -> list[bool]:
    """Uma entrada por página: se ela está em branco."""
    return [page.blank for page in document.pages]


def figure_counts(document: Document) -> list[int]:
    return [sum(b.type in IMAGE_BLOCK_TYPES for b in page.blocks) for page in document.pages]
