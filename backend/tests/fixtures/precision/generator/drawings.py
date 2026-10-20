"""Elementos não-texto desenhados nos documentos sintéticos (viram blocos "figura" no gabarito)."""

import math

from reportlab.lib.colors import Color, HexColor
from reportlab.pdfgen.canvas import Canvas

INK_BLUE = HexColor("#2A3E70")


def logo(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    """Logotipo: símbolo + nome da empresa. O texto do logotipo é parte da imagem."""
    r = h / 2
    c.setFillColor(INK_BLUE)
    c.circle(x + r, y + r, r, stroke=0, fill=1)
    c.setFillColor(HexColor("#E9C46A"))
    path = c.beginPath()
    path.moveTo(x + r * 0.45, y + r * 0.55)
    path.lineTo(x + r, y + r * 1.6)
    path.lineTo(x + r * 1.55, y + r * 0.55)
    path.close()
    c.drawPath(path, stroke=0, fill=1)
    c.setFillColor(INK_BLUE)
    c.setFont("Helvetica-Bold", h * 0.3)
    c.drawString(x + h * 1.25, y + h * 0.55, "OFICINA GRÁFICA")
    c.setFont("Helvetica", h * 0.3)
    c.drawString(x + h * 1.25, y + h * 0.15, "BOA VISTA")


def signature(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    """Rubrica cursiva desenhada com curvas."""
    c.setStrokeColor(INK_BLUE)
    c.setLineWidth(1.6)
    path = c.beginPath()
    path.moveTo(x, y + h * 0.35)
    steps = 7
    for i in range(steps):
        x0 = x + w * i / steps
        x1 = x + w * (i + 1) / steps
        path.curveTo(
            x0 + (x1 - x0) * 0.3,
            y + h * (0.95 if i % 2 == 0 else 0.1),
            x0 + (x1 - x0) * 0.7,
            y + h * (0.05 if i % 2 == 0 else 0.9),
            x1,
            y + h * (0.4 + 0.1 * math.sin(i)),
        )
    c.drawPath(path, stroke=1, fill=0)


def bar_chart(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    """Gráfico de barras sem texto (só formas)."""
    c.setStrokeColor(HexColor("#333333"))
    c.setLineWidth(1)
    c.line(x, y, x + w, y)
    c.line(x, y, x, y + h)
    values = [0.35, 0.6, 0.48, 0.82, 0.7]
    bar_w = w / (len(values) * 1.6)
    for i, value in enumerate(values):
        c.setFillColor(Color(0.2, 0.35 + i * 0.08, 0.6))
        c.rect(x + bar_w * (0.6 + i * 1.6), y, bar_w, h * value * 0.95, stroke=0, fill=1)


def cover_illustration(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    """Ilustração de capa: céu, montanhas e sol."""
    c.setFillColor(HexColor("#DCE8F5"))
    c.rect(x, y, w, h, stroke=0, fill=1)
    c.setFillColor(HexColor("#F2C14E"))
    c.circle(x + w * 0.75, y + h * 0.72, h * 0.1, stroke=0, fill=1)
    for color, peaks in [
        ("#7C9CB8", [(0.0, 0.2), (0.3, 0.65), (0.55, 0.3), (0.8, 0.55), (1.0, 0.25)]),
        ("#3F5F7A", [(0.0, 0.05), (0.2, 0.4), (0.45, 0.12), (0.7, 0.45), (1.0, 0.08)]),
    ]:
        c.setFillColor(HexColor(color))
        path = c.beginPath()
        path.moveTo(x, y)
        for px, py in peaks:
            path.lineTo(x + w * px, y + h * py)
        path.lineTo(x + w, y)
        path.close()
        c.drawPath(path, stroke=0, fill=1)


def stamp(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    """Carimbo circular com borda dupla (o texto interno é parte da imagem)."""
    c.setStrokeColor(HexColor("#8E2C2C"))
    c.setLineWidth(2)
    r = min(w, h) / 2
    c.circle(x + w / 2, y + h / 2, r, stroke=1, fill=0)
    c.setLineWidth(1)
    c.circle(x + w / 2, y + h / 2, r * 0.8, stroke=1, fill=0)
    c.setFillColor(HexColor("#8E2C2C"))
    c.setFont("Helvetica-Bold", r * 0.28)
    c.drawCentredString(x + w / 2, y + h / 2 - r * 0.1, "PAGO")


def letterhead_logo(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    """Logotipo de papel timbrado só de letras: nome grande e fino, com subtítulo espaçado."""
    c.setFillColor(HexColor("#7A7A7A"))
    c.setFont("Helvetica", h * 0.62)
    c.drawString(x, y + h * 0.38, "lumiar")
    c.setFont("Helvetica", h * 0.2)
    c.drawString(x + w * 0.42, y, "A R Q U I V O S")


def letterhead_address(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    """Endereço no pé do timbrado, em cinza claro, com um arco decorativo à esquerda."""
    c.setStrokeColor(HexColor("#9A9A9A"))
    c.setLineWidth(3)
    c.arc(x, y, x + h * 0.7, y + h, startAng=100, extent=160)
    c.setFillColor(HexColor("#8A8A8A"))
    c.setFont("Times-Roman", 6.5)
    lines = ["Rua das Palmeiras, 410", "Sala 12, Centro", "Vila Serena - MG", "www.lumiar.exemplo"]
    for i, line in enumerate(lines):
        c.drawString(x + h * 0.5, y + h - 9 * (i + 1), line)
