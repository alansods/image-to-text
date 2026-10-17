# image-to-text — Rotas, telas e fluxo (prompt de layout)

> Descreve o layout aprovado no protótipo (canvas "image-to-text — Fluxo de telas", 2026-10-15). Comportamentos detalhados estão nas specs em `openspec/`; em caso de conflito, a spec vence e este documento deve ser atualizado.

## 1. Produto

**image-to-text** converte uma imagem ou um PDF escaneado em texto e em um documento novo (Word ou PDF) fiel ao original: mesma paginação, organização, formatação e imagens. Sem conta, sem opções, nada guardado.

O diferencial visível: o sistema **marca as palavras em que tem dúvida** e só libera a cópia e o download depois que o usuário confere cada uma contra o original.

**Público**: pessoas comuns e profissionais digitalizando contratos, notas, apostilas, formulários e prints. Não são técnicos.

**Idioma da interface**: português do Brasil e inglês, com seletor PT | EN.

## 2. Direção visual

- **Tom**: ferramenta calma e direta, sem marketing. Pouca informação na tela.
- **Tema**: só claro. Fundo papel quente `#FAF8F4`, superfícies brancas, bordas `#E3DED5`, texto `#1C1B19` / secundário `#5F5B54`.
- **Cores**: acento azul-tinta `#1F4E9C`; **âmbar exclusivo para "em dúvida"** (fundo `#FCEFC7`, texto `#7A4F00`, sublinhado `#D49400`); verde `#2B6634` para "Tudo conferido"; vermelho `#A8261B` só para erro.
- **Tipografia**: IBM Plex Sans na interface; **Source Serif 4 no documento convertido**; IBM Plex Mono para percentuais e para as **opções de conferência** (diferencia I/l/1 e O/0).
- **Componentes**: shadcn/ui (cantos 8 px, bordas finas, sombras sutis). Ícones Lucide.
- **Acessibilidade**: WCAG 2.1 AA; foco visível; tudo por teclado; dúvida **nunca só por cor** (fundo âmbar + sublinhado ondulado); alvos de toque ≥ 44 px.
- **Responsivo**: funciona a partir de 360 px; no celular há "Tirar foto" e a conferência abre como painel inferior (bottom sheet).

## 3. Estrutura global

**Barra superior** (todas as telas): logotipo "image-to-text" à esquerda (volta ao envio; apaga a conversão em andamento) e seletor de idioma **PT | EN** à direita (controle segmentado, troca instantânea). Nada mais.

**Rodapé** (todas as telas): logotipo à esquerda e "© 2026 image-to-text" à direita. Nada mais.

## 4. Rotas

| Rota | Conteúdo |
|---|---|
| `/` | As três telas, que se substituem no mesmo endereço: **Envio → Convertendo → Resultado** |
| `*` | "Página não encontrada" + "Voltar ao início" |

Recarregar a página volta para o Envio vazio (nada é guardado).

## 5. Telas

### 5.1 Envio

Coluna central (máx. 760 px):
1. Título: "Transforme imagens em texto" / "Turn images into text".
2. Subtítulo: "Envie uma foto, print ou PDF escaneado. Em instantes você tem o texto pronto para copiar ou baixar em Word ou PDF."
3. **Área de envio** grande, borda tracejada, clicável inteira: ícone de upload, botão primário "Escolher arquivo", "ou arraste aqui, ou cole com Ctrl+V", "JPG, PNG, WEBP, HEIC ou PDF · até 20 MB".
4. No celular, no lugar da área: botões grandes "Tirar foto" (primário) e "Escolher arquivo", e a linha de formatos.

Ao receber um arquivo válido, vai direto para **Convertendo** (sem botão "Converter", sem opções).

Erros aparecem logo abaixo da área, em vermelho: formato não suportado, maior que 20 MB, mais de 50 páginas, PDF com senha, mais de um arquivo, falha de envio, limite de conversões simultâneas, "Não foi possível ler esse arquivo." (falha total).

### 5.2 Convertendo

Centralizado: "Lendo seu documento…", barra de progresso (máx. 420 px), "contrato.pdf · 62%" (percentual em mono), botão discreto "Cancelar" (volta ao Envio e apaga a conversão). Ao chegar a 100%, troca sozinho para **Resultado**.

### 5.3 Resultado

Coluna central (máx. 760 px):
1. Linha superior: ícone + nome do arquivo à esquerda; "Converter outro" (botão discreto) à direita.
2. **Se alguma página tiver baixa qualidade**: aviso discreto "A imagem tem baixa qualidade. Confira o texto e a formatação (negrito, itálico) com atenção." — em documentos com várias páginas, cita as páginas ("páginas 2 e 3"). Não bloqueia copiar nem baixar.
3. **Enquanto houver dúvidas**: aviso âmbar "Confira N palavras antes de baixar" / "Elas estão marcadas no texto. Escolha a forma certa de cada uma." + botão primário "Conferir próxima". **Não há** botões de copiar nem baixar.
4. **Sem dúvidas**: "✓ Tudo conferido" em verde e três botões: "Copiar texto" (primário; vira "Copiado"), "Baixar Word", "Baixar PDF".
5. **Documento**: uma folha A4 (proporção da página original) por página, com rótulo "PÁGINA N DE T" acima e o número no rodapé da folha. Texto em Source Serif, com títulos, alinhamento, negrito/itálico, listas, colunas, tabelas e imagens (logotipo, assinatura, capa) como no original.
6. **Palavras em dúvida**: fundo âmbar + sublinhado ondulado, são botões.

**Quadro de conferência** (popover junto da palavra; bottom sheet no celular):
- "Na imagem:" + recorte ampliado do original com a palavra contornada e um pouco de contexto.
- "Qual está certo?" + uma opção por alternativa, em IBM Plex Mono grande, **com os caracteres diferentes destacados** (fundo âmbar + traço inferior).
- Campo "Ou digite a correta" + botão ✓.
- Escolher ou confirmar resolve a palavra: o quadro fecha, **o foco fica na palavra corrigida**, marcada em verde com sublinhado contínuo (só na tela). "Conferir próxima" leva à próxima dúvida, atravessando páginas. Esc / fechar / clique fora fecham sem resolver. A palavra corrigida continua clicável e reabre o quadro com a escolha atual marcada (✓); palavra removida aparece como "∅" verde, só na tela.

## 6. Fluxo

```
[Envio] escolhe/arrasta/cola/fotografa 1 arquivo
   ▼
[Convertendo] percentual … 100%  (Cancelar → Envio)
   ▼
[Resultado] Conferir próxima → escolhe/digita/mantém original → (vê a correção em verde) → Conferir próxima … → Tudo conferido
   → Copiar texto | Baixar Word | Baixar PDF
   → Converter outro (→ Envio, apaga a conversão)
```

## 7. API consumida

| Tela | Endpoint | Uso |
|---|---|---|
| Envio | `POST /jobs` (multipart: 1 arquivo) | Cria a conversão, retorna `{ id }` |
| Convertendo | `GET /jobs/{id}` (polling 1,5 s) | Estado e percentual |
| Convertendo, Resultado | `DELETE /jobs/{id}` | Cancelar / Converter outro / logotipo |
| Resultado | `GET /jobs/{id}/result` | Páginas, blocos, palavras, alternativas |
| Resultado | `GET /jobs/{id}/crops/{word_id}` | Recorte para o quadro de conferência (palavra contornada em âmbar) |
| Resultado | `GET /jobs/{id}/images/{block_id}` | Imagem do original de uma figura (logotipo, assinatura, capa) nas folhas |
| Resultado | `PATCH /jobs/{id}/result` | Gravar palavras conferidas |
| Resultado | `GET /jobs/{id}/export?fmt=docx\|pdf` | Baixar Word ou PDF |

## 8. Componentes

- `SiteHeader` (logotipo + `LanguageToggle`), `SiteFooter`
- `UploadDropzone` (clique, arrastar, colar, câmera no celular)
- `ConvertingProgress`
- `ResultView` (aviso de qualidade, `ReviewGate` ↔ ações, documento)
- `DocumentPages` → `PageSheet` → `BlockView` (texto, lista, tabela, imagem)
- `WordCheck` (popover no desktop, painel inferior no celular; opções com diferença por caractere)
- Implementação: `components/{site,upload,progress,result,app}/`, `lib/{api,i18n,document,sheet,files}`

## 9. Fora do layout (MVP)

Login, conta, histórico, várias imagens por conversão, opções de modo/idioma do conteúdo, tema escuro, edição livre do texto, outros formatos de saída, páginas "Como funciona", "Perguntas", "Formatos", "Privacidade".
