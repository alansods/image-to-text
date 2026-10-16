"""Reconciliação das duas leituras de um bloco (spec reading-reconciliation, design D7).

Funções puras: recebem as palavras já lidas e, opcionalmente, quem relê e quem arbitra.
"""

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise

from app.models.document import (
    ILLEGIBLE,
    Alternative,
    BBox,
    ReadingSource,
    ResolvedBy,
    Word,
    WordStatus,
)
from app.pipeline.reading import ReadWord

# Confiança (spec): a leitura vencedora precisa ser ≥ 0,90 e superar a outra em ≥ 0,15.
MIN_CONFIDENCE = 0.90
MIN_MARGIN = 0.15
# Releitura: o principal sozinho decide se repete a leitura com confiança ≥ 0,97 e o segundo
# não consegue ler (< 0,90) — ex.: título sublinhado que o docTR lê como "_" (spec).
SOLO_REREAD = 0.97
SECOND_FAILED = 0.90
# Pontuação colada pelo sublinhado no fim da palavra ("CLÁUSULA.") não conta na comparação.
_TRAILING = ".,;:_-"
# Pedaço de sublinhado só vira palavra se a releitura do principal o confirmar com isto.
UNDERLINE_CONFIRM = 0.5
# Duas caixas se ligam quando a interseção cobre ao menos isto da menor delas.
MIN_OVERLAP = 0.5
# Espaço entre palavras: vão de ao menos isto da altura da palavra (menos é palavra partida).
MIN_SPACE = 0.2

Snippet = tuple[str, float]  # (texto, confiança) de uma releitura
Reread = Callable[[BBox], tuple[Snippet, Snippet]]
Arbiter = Callable[[BBox, list[str]], str | None]

_EQUIVALENT = str.maketrans(
    {
        **dict.fromkeys("“”„«»″", '"'),
        **dict.fromkeys("‘’‚′", "'"),  # noqa: RUF001
        **dict.fromkeys("‐‑‒–—―", "-"),  # noqa: RUF001
    }
)


# "°" (grau) grudado numa letra é o indicador ordinal "º" mal lido: os dois leitores confundem
# os sinais, e grau só vem depois de número ("25°C"). Ver D7.
_DEGREE_AFTER_LETTER = re.compile(r"(?<=[^\W\d_])°")


def fix_ordinal(text: str) -> str:
    return _DEGREE_AFTER_LETTER.sub("º", text)


def normalize_for_compare(text: str) -> str:
    """Só para comparar: NFC, aspas e traços equivalentes, sem espaços."""
    return "".join(unicodedata.normalize("NFC", text).translate(_EQUIVALENT).split())


def agreed_text(primary: str, secondary: str, blind: frozenset[str]) -> str | None:
    """Texto combinado se as leituras concordam; `None` se divergem.

    Compara sem espaços, com aspas e traços equivalentes; caractere que o 2º leitor não
    conhece (`blind`) casa com um ou nenhum. O resultado mantém a grafia do 1º leitor e junta
    os espaços dos dois: o docTR separa as palavras pela posição e pega espaços que o
    PaddleOCR às vezes perde ("R$17,00" → "R$ 17,00").
    """
    chars: list[str] = []
    spaced_after: list[bool] = []  # havia espaço depois do caractere no 1º leitor
    for char in unicodedata.normalize("NFC", primary):
        if char.isspace():
            if chars:
                spaced_after[-1] = True
        else:
            chars.append(char)
            spaced_after.append(False)
    pattern = r"\s*" + "".join(
        (r"([^\s]?)" if char in blind else f"({re.escape(char.translate(_EQUIVALENT))})") + r"(\s*)"
        for char in chars
    )
    target = " ".join(unicodedata.normalize("NFC", secondary).translate(_EQUIVALENT).split())
    found = re.fullmatch(pattern, target)
    if found is None:
        return None
    pieces = []
    for index, char in enumerate(chars):
        pieces.append(char)
        if index < len(chars) - 1 and (spaced_after[index] or found.group(2 * index + 2)):
            pieces.append(" ")
    return "".join(pieces)


def matches(primary: str, secondary: str, blind: frozenset[str]) -> bool:
    """As leituras concordam? (ver `agreed_text`)."""
    return agreed_text(primary, secondary, blind) is not None


# ------------------------------------------------------------------ alinhamento


def _overlap(a: BBox, b: BBox) -> float:
    w = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    h = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    if w <= 0 or h <= 0:
        return 0.0
    return w * h / min(a.w * a.h, b.w * b.h)


def _union(boxes: Sequence[BBox]) -> BBox:
    x1 = min(b.x for b in boxes)
    y1 = min(b.y for b in boxes)
    x2 = max(b.x + b.w for b in boxes)
    y2 = max(b.y + b.h for b in boxes)
    return BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1)


@dataclass
class _Unit:
    primary: list[ReadWord]
    secondary: list[ReadWord]
    # Posição da 1ª palavra do leitor principal na ordem em que ele leu (linha a linha).
    first: int | None = None

    @property
    def bbox(self) -> BBox:
        return _union([w.bbox for w in self.primary + self.secondary])


def _align(primary: Sequence[ReadWord], secondary: Sequence[ReadWord]) -> list[_Unit]:
    """Agrupa as palavras das duas leituras que se sobrepõem (componentes ligados)."""
    words = list(primary) + list(secondary)
    parent = list(range(len(words)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(primary)):
        for j in range(len(primary), len(words)):
            if _overlap(words[i].bbox, words[j].bbox) >= MIN_OVERLAP:
                parent[find(i)] = find(j)

    groups: dict[int, _Unit] = {}
    for index, word in enumerate(words):
        unit = groups.setdefault(find(index), _Unit([], []))
        if index < len(primary):
            unit.primary.append(word)
            unit.first = index if unit.first is None else min(unit.first, index)
        else:
            unit.secondary.append(word)
    for unit in groups.values():
        unit.primary.sort(key=lambda w: w.bbox.x)
        unit.secondary.sort(key=lambda w: w.bbox.x)
    return _in_reading_order(list(groups.values()))


def _same_line(a: BBox, b: BBox) -> bool:
    overlap = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    return overlap > 0.5 * min(a.h, b.h)


def _in_reading_order(units: list[_Unit]) -> list[_Unit]:
    """Na ordem em que o leitor principal leu (ele segue a linha mesmo curva); unidades que só
    o segundo leitor viu entram logo depois da vizinha à esquerda na mesma linha."""
    ordered = sorted((u for u in units if u.first is not None), key=lambda u: u.first or 0)
    for unit in sorted((u for u in units if u.first is None), key=lambda u: (u.bbox.y, u.bbox.x)):
        box = unit.bbox
        left = [
            i
            for i, other in enumerate(ordered)
            if _same_line(other.bbox, box) and other.bbox.x < box.x
        ]
        if left:
            position = max(left, key=lambda i: ordered[i].bbox.x) + 1
        else:
            below = [i for i, other in enumerate(ordered) if other.bbox.y > box.y]
            position = min(below) if below else len(ordered)
        ordered.insert(position, unit)
    return ordered


# ------------------------------------------------------------------ decisão


@dataclass(frozen=True)
class _Reading:
    text: str
    confidence: float
    source: ReadingSource


def _joined(words: list[ReadWord], source: ReadingSource) -> _Reading:
    """Junta as palavras de uma unidade.

    As do PaddleOCR vêm do texto da linha, separadas por espaço de verdade. As do docTR vêm
    da detecção: caixas quase coladas são uma palavra só partida ("CONTRA" + "TO").
    """
    if not words:
        return _Reading("", 0.0, source)
    text = words[0].text
    for before, after in pairwise(words):
        gap = after.bbox.x - (before.bbox.x + before.bbox.w)
        height = max(before.bbox.h, after.bbox.h)
        spaced = source is ReadingSource.PADDLE or gap > MIN_SPACE * height
        text += (" " if spaced else "") + after.text
    return _Reading(text, min(w.confidence for w in words), source)


def _alternatives(readings: Sequence[_Reading], keep_empty: bool) -> list[Alternative]:
    seen: set[str] = set()
    result = []
    for r in sorted(readings, key=lambda r: r.confidence, reverse=True):
        if r.text in seen or (not r.text and not keep_empty):
            continue
        seen.add(r.text)
        result.append(Alternative(text=r.text, confidence=r.confidence, source=r.source))
    return result


def _trim(text: str) -> str:
    """Sem a pontuação que um sublinhado cola no fim da palavra ("CLÁUSULA." → "CLÁUSULA")."""
    return text.rstrip(_TRAILING) or text


def _underline_piece(first: "_Reading", second: "_Reading") -> bool:
    """Só um leitor viu, e o que ele viu são só traços de sublinhado."""
    seen = [r.text for r in (first, second) if r.text]
    return len(seen) == 1 and set(seen[0]) <= {"_"}


def _decide(
    unit: _Unit,
    blind: frozenset[str],
    word_id: str,
    reread: Reread | None,
    arbiter: Arbiter | None,
) -> Word | None:
    first = _joined(unit.primary, ReadingSource.PADDLE)
    second = _joined(unit.secondary, ReadingSource.DOCTR)
    readings = (first, second)
    bbox = unit.bbox

    def word(
        text: str, confidence: float, status: WordStatus, by: ResolvedBy | None = None
    ) -> Word:
        return Word(
            id=word_id,
            text=text,
            bbox=bbox,
            confidence=confidence,
            alternatives=_alternatives(readings, keep_empty=status is WordStatus.UNCERTAIN),
            status=status,
            resolved_by=by,
        )

    # Só caracteres que o docTR não conhece ("—"): a leitura dele ali não tem valor.
    only_blind = bool(first.text) and all(c in blind for c in first.text if not c.isspace())
    if only_blind:
        return word(first.text, first.confidence, WordStatus.ACCEPTED)
    agreed = agreed_text(first.text, second.text, blind) if first.text and second.text else None
    if agreed is not None:
        return word(agreed, max(first.confidence, second.confidence), WordStatus.ACCEPTED)

    again: tuple[Snippet, Snippet] | None = None
    if reread is not None and _underline_piece(first, second):
        again = reread(bbox)
        if again[0][1] < UNDERLINE_CONFIRM:
            return None  # pedaço de sublinhado que só um leitor viu: formatação, não palavra

    best, other = sorted(readings, key=lambda r: r.confidence, reverse=True)
    if best.confidence >= MIN_CONFIDENCE and best.confidence - other.confidence >= MIN_MARGIN:
        return word(best.text, best.confidence, WordStatus.RESOLVED, ResolvedBy.CONFIDENCE)

    if reread is not None:
        (again_first, first_conf), (again_second, second_conf) = again or reread(bbox)
        if again_first and again_second and matches(_trim(again_first), _trim(again_second), blind):
            return word(_trim(again_first), best.confidence, WordStatus.RESOLVED, ResolvedBy.REREAD)
        originals = {normalize_for_compare(_trim(r.text)) for r in readings if r.text}
        repeats = normalize_for_compare(_trim(again_first)) in originals
        if repeats and first_conf >= SOLO_REREAD and second_conf < SECOND_FAILED:
            return word(_trim(again_first), first_conf, WordStatus.RESOLVED, ResolvedBy.REREAD)

    if arbiter is not None:
        options = [a.text for a in _alternatives(readings, keep_empty=False)]
        choice = arbiter(bbox, options)
        if choice == ILLEGIBLE:
            return word(ILLEGIBLE, 0.0, WordStatus.UNCERTAIN)
        if choice in options:
            return word(choice, best.confidence, WordStatus.RESOLVED, ResolvedBy.ARBITER)

    return word(best.text, best.confidence, WordStatus.UNCERTAIN)


def reconcile_block(
    primary: Sequence[ReadWord],
    secondary: Sequence[ReadWord],
    blind: frozenset[str],
    id_prefix: str,
    reread: Reread | None = None,
    arbiter: Arbiter | None = None,
) -> list[Word]:
    """Palavras finais de um bloco, na ordem de leitura, com status e alternativas."""

    def fixed(words: Sequence[ReadWord]) -> list[ReadWord]:
        return [replace(w, text=fix_ordinal(w.text)) for w in words]

    fixed_reread = None
    if reread is not None:
        original = reread

        def fixed_reread(box: BBox) -> tuple[Snippet, Snippet]:
            (first, first_conf), (second, second_conf) = original(box)
            return (fix_ordinal(first), first_conf), (fix_ordinal(second), second_conf)

    decided = [
        _decide(unit, blind, f"{id_prefix}w{index}", fixed_reread, arbiter)
        for index, unit in enumerate(_align(fixed(primary), fixed(secondary)))
    ]
    return [w for w in decided if w is not None]
