"""Tabelas sintéticas para os testes de estrutura (spec table-extraction)."""

import io

import numpy as np
import pypdfium2 as pdfium
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

SCALE = 300 / 72


def _render(table: Table) -> np.ndarray:
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4).build([table])
    page = pdfium.PdfDocument(buffer.getvalue())[0]
    return np.ascontiguousarray(page.render(scale=SCALE).to_numpy()[:, :, :3])


def merged_header_table() -> np.ndarray:
    """Com grade: "Período" ocupa 2 colunas no cabeçalho; uma célula vazia (Mar/Saídas)."""
    data = [
        ["Mês", "Período", "", "Saldo"],
        ["", "Entradas", "Saídas", ""],
        ["Janeiro", "1.200,00", "800,00", "400,00"],
        ["Fevereiro", "950,00", "1.100,00", "-150,00"],
        ["Março", "1.500,00", "", "1.500,00"],
    ]
    table = Table(data, colWidths=[110, 90, 90, 90])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
                ("SPAN", (1, 0), (2, 0)),
                ("SPAN", (0, 0), (0, 1)),
                ("SPAN", (3, 0), (3, 1)),
                ("FONT", (0, 0), (-1, -1), "Helvetica", 11),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return _render(table)


def borderless_table() -> np.ndarray:
    """Sem grade: colunas só pelo alinhamento."""
    data = [
        ["Produto", "Qtd.", "Preço"],
        ["Caneta azul", "12", "2,50"],
        ["Caderno", "3", "18,90"],
        ["Grampeador", "1", "32,00"],
    ]
    table = Table(data, colWidths=[160, 70, 80])
    table.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 11)]))
    return _render(table)
