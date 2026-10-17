"""Traço decidido pela forma (spec reading-reconciliation, design D19).

Os leitores confundem hífen, travessões e sublinhado: leem o travessão curto como "-" (e
concordam, sem dúvida nenhuma), ou "-" de um lado e "_"/"--" do outro. A tinta resolve:
medimos o traço na altura do meio das letras, sem a linha do sublinhado, e comparamos o
comprimento com a altura das maiúsculas da linha. Medido em contratos reais e no conjunto de
teste: hífen 0,32 a 0,45, travessão curto 0,72 a 0,77, travessão longo 1,28 a 1,65.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from app.models.document import BBox
from app.pipeline.reading import Gray

DASH_CHARS = frozenset("-‐‑‒–—―~=")  # noqa: RUF001
HYPHEN_MAX = 0.58
EN_DASH_MAX = 1.05
# Linha de sublinhado: traço horizontal mais longo que isto (vezes a altura das maiúsculas).
UNDERLINE_MIN = 2.5
# O traço fica entre 15% e 85% da altura das maiúsculas acima da linha de base.
STROKE_LOW = 0.15
STROKE_HIGH = 0.85
# Traço: comprido (≥ 1,8 vez a espessura) e fino (≤ 35% da altura das maiúsculas).
MIN_ELONGATION = 1.8
MAX_THICKNESS = 0.35
# Letras em volta para comparar o tamanho; menos que isso, não dá para medir.
MIN_LETTERS = 3
# Quanto da linha olhar dos dois lados do traço (vezes a altura da caixa do traço).
CONTEXT = 6


def is_dash_reading(texts: list[str]) -> bool:
    """As leituras são só símbolos soltos com ao menos um traço (sem letras nem algarismos)?

    Leituras só com "_" ficam de fora: linha de preencher ("______") é conteúdo, e pedaço de
    sublinhado tem regra própria na reconciliação.
    """
    seen = [t for t in texts if t.strip()]
    if not seen or any(c.isalnum() for t in seen for c in t):
        return False
    return any(c in DASH_CHARS for t in seen for c in t)


def _symbol(length: float) -> str:
    if length < HYPHEN_MAX:
        return "-"
    return "–" if length <= EN_DASH_MAX else "—"  # noqa: RUF001


@dataclass(frozen=True)
class LineInk:
    """Tinta em volta de uma caixa, sem as linhas de sublinhado, e as medidas da linha."""

    x0: int  # canto da região na página
    y0: int
    stats: np.ndarray  # manchas (x, y, w, h, área), já sem o fundo
    cap: float  # altura das maiúsculas
    letters: list[np.ndarray]  # manchas com altura de letra

    def baseline(self, center_y: float) -> float | None:
        """Linha de base pelas letras da mesma linha (a janela pega a linha de cima)."""
        beside = [s[1] + s[3] for s in self.letters if s[1] <= center_y <= s[1] + s[3]]
        return float(np.median(beside)) if len(beside) >= 2 else None


def line_ink(gray: Gray, box: BBox) -> LineInk | None:
    """Medidas da linha em volta da caixa; `None` sem letras em volta para comparar."""
    size = max(box.h, 10)
    reach = size * CONTEXT
    x0, x1 = max(int(box.x - reach), 0), min(int(box.x + box.w + reach), gray.shape[1])
    y0 = max(int(box.y - size * 4), 0)
    y1 = min(int(box.y + box.h + size * 3), gray.shape[0])
    region = gray[y0:y1, x0:x1]
    if region.size == 0:
        return None
    ink = (region < 128).astype(np.uint8)

    count, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    # Altura das maiúsculas pelas manchas com jeito de letra (não traços nem sublinhado).
    tall = [int(s[3]) for s in stats[1:count] if 2 * s[3] >= s[2] and s[4] > 10]
    if len(tall) < MIN_LETTERS:
        return None
    cap = float(np.percentile(tall, 85))

    # Tira as linhas de sublinhado (traços bem mais longos que qualquer travessão).
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(int(cap * UNDERLINE_MIN), 3), 1))
    lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
    ink = np.asarray(cv2.subtract(ink, lines), dtype=np.uint8)

    count, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    letters = [s for s in stats[1:count] if s[3] >= 0.6 * cap]
    if len(letters) < MIN_LETTERS:
        return None
    return LineInk(x0, y0, stats[1:count], cap, letters)


def dash_shape(gray: Gray, box: BBox) -> tuple[str, BBox | None] | None:
    """Símbolo do traço na caixa e onde está o traço na página.

    `("", None)`: não há traço na altura das letras (só sublinhado) — o trecho é formatação.
    `None`: não há letras em volta para comparar; a reconciliação segue as regras normais.
    """
    line = line_ink(gray, box)
    if line is None:
        return None
    cap = line.cap
    left, right = box.x - line.x0, box.x + box.w - line.x0
    strokes = []
    for x, y, w, h, area in line.stats:
        center_x, center_y = x + w / 2, y + h / 2
        if not left - 2 <= center_x <= right + 2 or area < 4:
            continue
        if w < MIN_ELONGATION * h or h > MAX_THICKNESS * cap:
            continue
        baseline = line.baseline(center_y)
        if baseline is None:
            continue
        height = (baseline - center_y) / cap
        if STROKE_LOW <= height <= STROKE_HIGH:
            strokes.append((int(w), int(x), int(y), int(h)))
    if not strokes:
        return "", None
    w, x, y, h = max(strokes)
    return _symbol(w / cap), BBox(x=x + line.x0, y=y + line.y0, w=w, h=h)
