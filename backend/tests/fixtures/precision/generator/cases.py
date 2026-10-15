"""Os casos do conjunto de precisão. Cada função desenha o documento, gera a entrada degradada
e devolve o gabarito. Textos e nomes são fictícios."""

from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from app.models.document import Alignment, BlockType
from tests.fixtures.precision.generator import degrade, drawings
from tests.fixtures.precision.generator.layout import CellSpec, Composer
from tests.precision.truth import Truth, TruthPage

A4_PORTRAIT = (595.28, 841.89)


def _a4_for_image(width: int, height: int) -> tuple[float, float]:
    """Entrada de imagem vira 1 página A4, em retrato ou paisagem (spec document-export)."""
    return A4_PORTRAIT if height >= width else (A4_PORTRAIT[1], A4_PORTRAIT[0])


def _with_page_sizes(pages: list[TruthPage], sizes: list[tuple[float, float]]) -> list[TruthPage]:
    return [
        p.model_copy(update={"w_pt": w, "h_pt": h}) for p, (w, h) in zip(pages, sizes, strict=True)
    ]


# ---------------------------------------------------------------- composições reutilizadas


def _contract(composer: Composer) -> None:
    c = composer
    c.new_page()
    c.paragraph(
        "**CONTRATO DE PRESTAÇÃO DE SERVIÇOS**",
        align=Alignment.CENTER,
        size=15,
        block_type=BlockType.HEADING,
        space_after=14,
    )
    c.paragraph(
        "Pelo presente instrumento particular, de um lado **JOÃO PEREIRA DA SILVA,** inscrito no "
        "CPF sob o nº 000.111.222-33, residente na Rua das Acácias, 214, doravante denominado "
        "**CONTRATANTE,** e de outro lado **OFICINA GRÁFICA BOA VISTA LTDA.,** inscrita no CNPJ "
        "sob o nº 00.000.000/0001-91, doravante denominada **CONTRATADA,** têm entre si justo e "
        "contratado o seguinte:"
    )
    c.paragraph(
        "**Cláusula 1ª** — O objeto do presente contrato é a prestação de serviços de "
        "digitalização de acervo documental, conforme as condições abaixo:"
    )
    c.bullet_list(
        [
            ("a)", "recebimento e triagem dos documentos;"),
            ("b)", "digitalização em alta resolução, com conferência página a página;"),
            ("c)", "entrega dos arquivos em até 15 (quinze) dias úteis."),
        ]
    )
    c.paragraph(
        "**Cláusula 2ª** — Pelos serviços, o **CONTRATANTE** pagará à **CONTRATADA** o valor "
        "total de R$ 2.500,00 (dois mil e quinhentos reais), em duas parcelas iguais de "
        "R$ 1.250,00, com vencimento em 10/03/2026 e 10/04/2026."
    )
    c.paragraph(
        "§ 1º — O atraso no pagamento implicará multa de 2% (dois por cento) e juros de 1% ao "
        "mês, calculados _pro rata die._"
    )
    c.paragraph(
        "**Cláusula 3ª** — Fica eleito o foro da Comarca de São Paulo para dirimir quaisquer "
        "dúvidas oriundas deste contrato, com renúncia a qualquer outro, por mais privilegiado "
        "que seja."
    )
    c.spacer(10)
    c.paragraph("São Paulo, 15 de outubro de 2026.", align=Alignment.CENTER, space_after=18)
    c.figure(drawings.signature, 150, 40)
    c.paragraph("**CONTRATANTE**", align=Alignment.CENTER, size=10)


def _memo(composer: Composer) -> None:
    c = composer
    c.new_page()
    c.paragraph(
        "**COMUNICADO INTERNO Nº 18/2026**",
        align=Alignment.LEFT,
        size=13,
        block_type=BlockType.HEADING,
        space_after=12,
    )
    c.paragraph("Para: equipe de atendimento", align=Alignment.LEFT, space_after=2)
    c.paragraph("Assunto: novo horário de funcionamento", align=Alignment.LEFT, space_after=12)
    c.paragraph(
        "A partir de 3 de novembro, o atendimento ao público passará a funcionar das 8h às 17h, "
        "de segunda a sexta-feira. Aos sábados, o expediente será das 9h às 13h, apenas para "
        "retirada de documentos já agendada."
    )
    c.paragraph(
        "Pedimos que todos atualizem os avisos afixados no balcão e confirmem a escala da "
        "semana com a coordenação até o dia 30. Dúvidas podem ser enviadas ao ramal 2045."
    )
    c.paragraph("Atenciosamente,", align=Alignment.LEFT, space_after=4)
    c.paragraph("Coordenação Administrativa", align=Alignment.LEFT)


# ---------------------------------------------------------------- casos


def contrato_impresso(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    composer = Composer(tmp / "vetor.pdf")
    _contract(composer)
    pages = composer.save()
    scans = [degrade.scan(p, rng) for p in degrade.render(tmp / "vetor.pdf")]
    degrade.save_scanned_pdf(scans, out / "input.pdf")
    return Truth(
        case="contrato_impresso",
        input="input.pdf",
        description="Contrato escaneado: título centralizado, parágrafos justificados, negrito, "
        "lista, valores e assinatura.",
        handwriting=False,
        pages=_with_page_sizes(pages, degrade.pdf_page_sizes(out / "input.pdf")),
    )


def contrato_foto(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    composer = Composer(tmp / "vetor.pdf")
    _contract(composer)
    pages = composer.save()
    image = degrade.photo(degrade.render(tmp / "vetor.pdf")[0], rng)
    degrade.save_jpeg(image, out / "input.jpg")
    w_pt, h_pt = _a4_for_image(image.shape[1], image.shape[0])
    return Truth(
        case="contrato_foto",
        input="input.jpg",
        description="O mesmo contrato fotografado: perspectiva, inclinação de 7°, sombra e ruído.",
        handwriting=False,
        pages=[pages[0].model_copy(update={"w_pt": w_pt, "h_pt": h_pt})],
    )


def recibo_tabela(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    c = Composer(tmp / "vetor.pdf", family="sans", body_size=10)
    c.new_page()
    c.paragraph(
        "**RECIBO DE PRESTAÇÃO DE SERVIÇOS**",
        align=Alignment.LEFT,
        size=14,
        block_type=BlockType.HEADING,
        space_after=10,
    )
    c.paragraph(
        "Recebemos de Maria Fernanda Costa a importância de R$ 1.234,56 referente aos serviços "
        "abaixo, prestados em setembro de 2026.",
        align=Alignment.LEFT,
        space_after=14,
    )
    c.table(
        [
            [CellSpec("Item"), CellSpec("Descrição"), CellSpec("Qtd."), CellSpec("Valor (R$)")],
            [
                CellSpec("1"),
                CellSpec("Digitalização de páginas"),
                CellSpec("820"),
                CellSpec("738,00"),
            ],
            [
                CellSpec("2"),
                CellSpec("Conferência e indexação"),
                CellSpec("820"),
                CellSpec("410,00"),
            ],
            [CellSpec("3"), CellSpec("Mídia de entrega"), CellSpec("2"), CellSpec("86,56")],
            [CellSpec("Total", col_span=3), CellSpec("1.234,56")],
        ],
        [40, 250, 60, 101],
    )
    c.figure(drawings.stamp, 70, 70, align=Alignment.RIGHT)
    c.paragraph(
        "Curitiba, 2 de outubro de 2026. Este recibo dá plena quitação dos valores acima.",
        align=Alignment.LEFT,
    )
    pages = c.save()
    scans = [degrade.scan(p, rng) for p in degrade.render(tmp / "vetor.pdf")]
    degrade.save_scanned_pdf(scans, out / "input.pdf")
    return Truth(
        case="recibo_tabela",
        input="input.pdf",
        description="Recibo com tabela de 5×4, célula mesclada no total e carimbo.",
        handwriting=False,
        pages=_with_page_sizes(pages, degrade.pdf_page_sizes(out / "input.pdf")),
    )


def artigo_duas_colunas(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    c = Composer(tmp / "vetor.pdf", body_size=10, margin=60)
    c.new_page()
    c.paragraph(
        "**Low-Cost Digitization of Paper Archives**",
        align=Alignment.CENTER,
        size=17,
        block_type=BlockType.HEADING,
        space_after=6,
        full_width=True,
    )
    c.paragraph(
        "_Resumo: este artigo descreve um processo simples para digitalizar arquivos em papel "
        "com equipamentos comuns._",
        align=Alignment.CENTER,
        size=10,
        space_after=14,
        full_width=True,
    )
    c.columns(2, gap=22)
    c.paragraph(
        "**Introduction.** Small offices keep thousands of pages in cabinets, and most of them "
        "were never converted into searchable files. Scanning alone is not enough: the text "
        "must be extracted, checked and stored in a format people can edit."
    )
    c.paragraph(
        "We compared three workflows over a period of six weeks. Each workflow processed the "
        "same set of 1,200 pages, including contracts, invoices and handwritten notes. The "
        "results show that _careful review of uncertain words_ matters more than the choice "
        "of scanner."
    )
    c.paragraph(
        "**Method.** Every page was scanned at 300 dpi and read twice by independent "
        "recognizers. When the two readings disagreed, the word was flagged for a person to "
        "confirm. No page was edited by hand before the comparison."
    )
    c.paragraph(
        "The total cost of the setup was below US$ 400, and the team needed less than one "
        "day of training to operate it."
    )
    c.column_break()
    c.figure(drawings.bar_chart, 200, 120)
    c.paragraph(
        "_Figure 1. Pages processed per week in each workflow._", align=Alignment.CENTER, size=9
    )
    c.paragraph(
        "**Results.** The double-reading workflow reduced character errors from 2.4% to 0.6% "
        "and took only 9% more time than a single reading. Most remaining errors involved "
        "similar shapes such as 1 and l, or 0 and O."
    )
    c.paragraph(
        "**Conclusion.** A free and careful process is possible today, as long as people "
        "review what the machine is not sure about."
    )
    pages = c.save()
    scans = [degrade.scan(p, rng, tilt_deg=-0.3) for p in degrade.render(tmp / "vetor.pdf")]
    degrade.save_scanned_pdf(scans, out / "input.pdf")
    return Truth(
        case="artigo_duas_colunas",
        input="input.pdf",
        description="Artigo em inglês em duas colunas, resumo em português, gráfico com legenda.",
        handwriting=False,
        pages=_with_page_sizes(pages, degrade.pdf_page_sizes(out / "input.pdf")),
    )


def relatorio_tres_paginas(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    c = Composer(tmp / "vetor.pdf")
    # Página 1: capa.
    c.new_page()
    c.figure(drawings.logo, 190, 44, align=Alignment.LEFT, space_after=60)
    c.figure(drawings.cover_illustration, 451, 300, space_after=40)
    c.paragraph(
        "**RELATÓRIO ANUAL 2026**",
        align=Alignment.CENTER,
        size=24,
        block_type=BlockType.HEADING,
        space_after=10,
    )
    c.paragraph("Programa de Preservação Documental", align=Alignment.CENTER, size=14)
    # Página 2: texto com cabeçalho e rodapé.
    c.new_page(footer="2")
    c.header("Relatório anual 2026 — Oficina Gráfica Boa Vista")
    c.paragraph("**1. Apresentação**", align=Alignment.LEFT, size=14, block_type=BlockType.HEADING)
    c.paragraph(
        "Em 2026, o programa digitalizou 48.300 páginas de documentos históricos de quatro "
        "municípios. Todo o material foi conferido por duas pessoas antes de ser publicado no "
        "acervo digital."
    )
    c.paragraph("As principais entregas do ano foram:", align=Alignment.LEFT)
    c.bullet_list(
        [
            ("•", "catálogo das atas da Câmara Municipal de 1890 a 1950;"),
            ("•", "mapas cadastrais restaurados e digitalizados em alta resolução;"),
            ("•", "oficina de preservação para 120 servidores públicos."),
        ]
    )
    c.paragraph(
        "Os resultados detalhados por município estão nos anexos, publicados separadamente."
    )
    # Página 3: em branco (verso da folha).
    c.new_page(blank=True)
    pages = c.save()
    scans = [degrade.scan(p, rng) for p in degrade.render(tmp / "vetor.pdf")]
    degrade.save_scanned_pdf(scans, out / "input.pdf")
    return Truth(
        case="relatorio_tres_paginas",
        input="input.pdf",
        description="PDF de 3 páginas: capa com logotipo e ilustração, texto com cabeçalho e "
        "rodapé, página em branco.",
        handwriting=False,
        pages=_with_page_sizes(pages, degrade.pdf_page_sizes(out / "input.pdf")),
    )


def print_tela(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    c = Composer(tmp / "vetor.pdf", page_size=(450, 330), margin=24, family="sans", body_size=9)
    c.new_page()
    c.paragraph(
        "**Pedido confirmado**",
        align=Alignment.LEFT,
        size=13,
        block_type=BlockType.HEADING,
        space_after=6,
    )
    c.paragraph(
        "Olá, Ana! Recebemos o seu pedido nº 58213 em 14/10/2026 às 16:42. O pagamento de "
        "R$ 189,90 foi aprovado e a entrega está prevista para 21/10/2026.",
        align=Alignment.LEFT,
    )
    c.paragraph("Itens do pedido:", align=Alignment.LEFT, space_after=2)
    c.bullet_list(
        [
            ("•", "1× Caderno universitário 200 folhas — R$ 42,90"),
            ("•", "2× Caneta gel 0,5 mm azul — R$ 17,00"),
            ("•", "1× Mochila escolar cinza — R$ 130,00"),
        ]
    )
    c.paragraph(
        "Acompanhe a entrega pelo código BR4471029. Em caso de dúvida, responda esta mensagem.",
        align=Alignment.LEFT,
    )
    pages = c.save()
    image = degrade.render(tmp / "vetor.pdf", dpi=96)[0]
    degrade.save_png(image, out / "input.png")
    w_pt, h_pt = _a4_for_image(image.shape[1], image.shape[0])
    return Truth(
        case="print_tela",
        input="input.png",
        description="Captura de tela pequena (~600 px de largura) com fonte pequena.",
        handwriting=False,
        pages=[pages[0].model_copy(update={"w_pt": w_pt, "h_pt": h_pt})],
    )


def cabeca_para_baixo(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    composer = Composer(tmp / "vetor.pdf")
    _memo(composer)
    pages = composer.save()
    page = degrade.scan(degrade.render(tmp / "vetor.pdf")[0], rng)
    image = np.rot90(page, 2).copy()
    degrade.save_jpeg(image, out / "input.jpg", quality=88)
    w_pt, h_pt = _a4_for_image(image.shape[1], image.shape[0])
    return Truth(
        case="cabeca_para_baixo",
        input="input.jpg",
        description="Comunicado escaneado de cabeça para baixo (180°).",
        handwriting=False,
        pages=[pages[0].model_copy(update={"w_pt": w_pt, "h_pt": h_pt})],
    )


def enfase_mista(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    c = Composer(tmp / "vetor.pdf", body_size=12)
    c.new_page()
    c.paragraph(
        "**Orientações para a prova**",
        align=Alignment.LEFT,
        size=16,
        block_type=BlockType.HEADING,
        space_after=12,
    )
    c.paragraph(
        "A prova terá **duração máxima de quatro horas** e começará _pontualmente_ às 8h. "
        "Não será permitida a entrada após o **fechamento dos portões,** em nenhuma hipótese."
    )
    c.paragraph(
        "Leve **documento oficial com foto** e caneta esferográfica de tinta _azul ou preta,_ "
        "fabricada em material transparente. O uso de **_calculadora, relógio digital ou "
        "celular_** resultará na eliminação do candidato."
    )
    c.paragraph(
        "As respostas devem ser transcritas para a **folha de respostas,** que é o _único "
        "documento válido_ para a correção. Rasuras na folha **não serão aceitas.**"
    )
    c.paragraph(
        "_Observação:_ os candidatos poderão levar o caderno de questões somente após **duas "
        "horas** do início da prova.",
        align=Alignment.LEFT,
    )
    pages = c.save()
    scans = [degrade.scan(p, rng) for p in degrade.render(tmp / "vetor.pdf")]
    degrade.save_scanned_pdf(scans, out / "input.pdf")
    return Truth(
        case="enfase_mista",
        input="input.pdf",
        description="Texto com negrito, itálico e negrito-itálico misturados no meio das frases.",
        handwriting=False,
        pages=_with_page_sizes(pages, degrade.pdf_page_sizes(out / "input.pdf")),
    )


def manuscrito(out: Path, rng: np.random.Generator, tmp: Path) -> Truth:
    c = Composer(tmp / "vetor.pdf", family="hand", body_size=20, leading=1.25)
    c.new_page()
    c.paragraph("Lista da semana", align=Alignment.LEFT, size=26, block_type=BlockType.HEADING)
    c.bullet_list(
        [
            ("-", "pagar a conta de luz até sexta"),
            ("-", "levar o carro na revisão (km 45.000)"),
            ("-", "comprar presente para a Júlia"),
            ("-", "ligar para o dentista às 14h"),
        ]
    )
    c.paragraph(
        "Não esquecer: reunião do condomínio na quinta, às 19h30, no salão de festas.",
        align=Alignment.LEFT,
    )
    pages = c.save()
    page = degrade.scan(degrade.render(tmp / "vetor.pdf", dpi=200)[0], rng, tilt_deg=1.2)
    degrade.save_jpeg(page, out / "input.jpg", quality=85)
    w_pt, h_pt = _a4_for_image(page.shape[1], page.shape[0])
    return Truth(
        case="manuscrito",
        input="input.jpg",
        description="Anotações em letra cursiva (fonte Caveat). Medido e reportado, sem bloquear.",
        handwriting=True,
        pages=[pages[0].model_copy(update={"w_pt": w_pt, "h_pt": h_pt})],
    )


CaseFn = Callable[[Path, np.random.Generator, Path], Truth]

CASES: dict[str, CaseFn] = {
    fn.__name__: fn
    for fn in [
        contrato_impresso,
        contrato_foto,
        recibo_tabela,
        artigo_duas_colunas,
        relatorio_tres_paginas,
        print_tela,
        cabeca_para_baixo,
        enfase_mista,
        manuscrito,
    ]
}


def generate(root: Path, names: list[str] | None = None) -> list[Truth]:
    truths = []
    for index, (name, fn) in enumerate(CASES.items()):
        if names and name not in names:
            continue
        out = root / name
        out.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory() as tmp:
            truth = fn(out, np.random.default_rng(1000 + index), Path(tmp))
        (out / "expected.json").write_text(
            truth.model_dump_json(indent=2, exclude_defaults=True) + "\n", encoding="utf-8"
        )
        (out / "expected.txt").write_text(truth.text() + "\n", encoding="utf-8")
        truths.append(truth)
    return truths
