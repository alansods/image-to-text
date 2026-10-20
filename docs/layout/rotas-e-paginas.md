# image-to-text — Rotas, telas e fluxo (prompt de layout)

> Descreve o layout aprovado no protótipo (canvas "image-to-text — Fluxo completo (Contraste)", 2026-10-17; substitui o de 2026-10-15). Comportamentos detalhados estão nas specs em `openspec/`; em caso de conflito, a spec vence e este documento deve ser atualizado.

## 1. Produto

**image-to-text** converte uma imagem ou um PDF escaneado em texto e em um documento novo (Word ou PDF) fiel ao original: mesma paginação, organização, formatação e imagens. Sem conta, sem opções, nada guardado.

O diferencial visível: o sistema **marca as palavras em que tem dúvida** e só libera a cópia e o download depois que o usuário confere cada uma contra o original.

**Público**: pessoas comuns e profissionais digitalizando contratos, notas, apostilas, formulários e prints. Não são técnicos.

**Idioma da interface**: português do Brasil e inglês, com seletor PT | EN.

## 2. Direção visual

- **Tom**: ferramenta calma e direta, sem marketing. Pouca informação na tela.
- **Tema**: só claro, estilo "Contraste". Toda tela começa com uma **faixa azul-escura** `#0F2347` (barra superior + título da tela, texto `#E8EEF9` / secundário `#B8C6E2`) e o conteúdo principal num **cartão branco que sobe sobre a faixa** (cantos 22–24 px, sombra suave). Fundo `#F3F5FA`, bordas `#DBE1EC`, texto `#121A2B` / secundário `#4F5B72`.
- **Cores**: ações em azul `#2563D9` (botões em pílula; um tom mais escuro que o `#2F6FED` do protótipo para o texto branco passar de 4,5:1), secundárias em azul-claro `#E5EEFF` com texto azul-escuro; **âmbar só para o que pede atenção** (palavras em dúvida, contagem de dúvidas, aviso de baixa qualidade: fundo `#FCEFC7`, texto `#7A4F00`, sublinhado `#D49400`); verde `#1F7A45` para corrigido (`#8FE0B0` sobre a faixa); vermelho `#B42318` só para erro.
- **Tipografia**: IBM Plex Sans na interface; **Source Serif 4 no documento convertido**; IBM Plex Mono para percentuais e para as **opções de conferência** (diferencia I/l/1 e O/0).
- **Componentes**: shadcn/ui (cantos 8 px, bordas finas, sombras sutis). Ícones Lucide.
- **Acessibilidade**: WCAG 2.1 AA; foco visível; tudo por teclado; dúvida **nunca só por cor** (fundo âmbar + sublinhado ondulado); alvos de toque ≥ 44 px.
- **Responsivo**: funciona a partir de 360 px; no celular há "Tirar foto" e a conferência abre como painel inferior (bottom sheet).

## 3. Estrutura global

**Barra superior** (todas as telas, sobre a faixa escura): logotipo "image-to-text" (quadrado azul com a folha) à esquerda — volta ao envio e apaga a conversão em andamento — e seletor de idioma **PT | EN** em pílula à direita (troca instantânea). Nada mais.

**Rodapé** (todas as telas, branco): logotipo à esquerda e "© 2026 image-to-text" à direita. Nada mais.

## 4. Rotas

| Rota | Conteúdo |
|---|---|
| `/` | As três telas, que se substituem no mesmo endereço: **Envio → Convertendo → Resultado** |
| `*` | Faixa escura em tela cheia: "404", "Página não encontrada", "Esse endereço não existe. O site tem uma página só: a de enviar o arquivo." + botão "Voltar ao início" |

Recarregar a página volta para o Envio vazio (nada é guardado).

## 5. Telas

### 5.1 Envio (página inicial)

1. **Faixa**: etiqueta "Grátis · sem cadastro · nada fica guardado"; título "Transforme imagens em texto" / "Turn images into text"; subtítulo "Envie uma foto, print ou PDF escaneado. Em instantes você tem o texto pronto para copiar ou baixar em Word ou PDF."
2. **Cartão de envio** (sobe sobre a faixa, máx. 720 px): área tracejada clicável inteira com ícone, botão em pílula "Escolher arquivo", "ou arraste aqui, ou cole com Ctrl+V" e as etiquetas JPG · PNG · WEBP · HEIC · PDF · até 20 MB. No celular, no lugar da área: "Tirar foto" (primário) e "Escolher arquivo" (azul-claro) e a linha de formatos.
3. **Como funciona** — "Da imagem ao documento em quatro passos": linha do tempo com ícone em círculo, "PASSO N", título e uma frase — Envie o arquivo · A leitura começa sozinha · Confira as dúvidas · Baixe ou copie. Horizontal em telas largas, vertical no celular.
4. **Chamada final** (bloco azul): "Pronto para começar?" / "Sem cadastro e sem custo. Seu arquivo é apagado em até 1 hora." + botão branco "Escolher arquivo" (abre a mesma escolha).

Ao receber um arquivo válido, vai direto para **Convertendo** (sem botão "Converter", sem opções).

Erros aparecem dentro do cartão, abaixo da área, em vermelho: formato não suportado, maior que 20 MB, mais de 20 páginas, PDF com senha, mais de um arquivo, falha de envio, limite de conversões simultâneas, "Não foi possível ler esse arquivo." (falha total).

### 5.2 Convertendo

Faixa: "Lendo seu documento…" + "Pode deixar esta página aberta. O resultado aparece aqui quando terminar." Cartão (máx. 640 px): ilustração animada (folha com uma faixa de leitura descendo e linhas de texto aparecendo; parada com "reduzir movimento"); frase da etapa real ("Na fila, já vai começar…", "Preparando a página 2 de 5", "Encontrando títulos, parágrafos, tabelas e imagens", "Lendo o texto da página 2 de 5", "Montando o documento"); durante a leitura, uma dica menor que troca a cada ~6 s; barra de progresso com "contrato.pdf … 62%" (percentual em mono); etapas "Preparar · Estrutura · Leitura · Montagem" (feitas em azul-claro, a atual em azul); botão discreto "Cancelar" (volta ao Envio e apaga a conversão). Ao chegar a 100%, troca sozinho para **Resultado**.

### 5.3 Resultado

Faixa: situação ("Quase pronto" em âmbar enquanto houver dúvidas; "✓ Tudo conferido" em verde depois) e o **nome do arquivo como título**. Coluna central (máx. 780 px):
1. **Cartão** (sobe sobre a faixa):
   - **Se alguma página tiver baixa qualidade**: aviso **amarelo** com ícone de alerta, "A página 5 tem baixa qualidade. Confira o texto e a formatação (negrito, itálico) com atenção." (cita as páginas; em imagem única, "A imagem tem baixa qualidade…"). Não bloqueia copiar nem baixar.
   - **Enquanto houver dúvidas**: círculo âmbar com o número + "Confira N palavras antes de baixar" / "Elas estão marcadas no texto. Escolha a forma certa de cada uma." + botão "Conferir próxima". **Não há** copiar nem baixar.
   - **Sem dúvidas**: grade 2×2 ocupando a largura — **"Baixar PDF" e "Baixar Word"** em azul (destaque) na primeira linha; "Copiar texto" (vira "Copiado") e "Converter outro" em azul-claro na segunda.
2. **Enquanto houver dúvidas**, "Converter outro" **não aparece** (só depois de tudo conferido; o logotipo continua voltando ao envio).
   **Barra fixa no pé da tela** (só quando o cartão do topo saiu da tela e o quadro de conferência está fechado): branca com o círculo âmbar, "Faltam N palavras para conferir" + "Conferir próxima"; ao resolver a última, vira azul-escura com "✓ Tudo conferido — Seu documento está pronto." + "Baixar PDF" e "Baixar Word" (entrada animada curta, parada com "reduzir movimento"). Não rola a página nem tira o foco. No celular fica colada na borda de baixo; no computador, flutuando centralizada (máx. 780 px).
3. **Documento**: uma folha (proporção da página original) por página, com rótulo "PÁGINA N DE T" acima e o número no rodapé da folha. Texto em Source Serif, com títulos, alinhamento, negrito/itálico, listas, colunas, tabelas e imagens (logotipo, assinatura, capa) como no original.
4. **Palavras em dúvida**: fundo âmbar + sublinhado ondulado, são botões.

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
[Resultado] Conferir próxima → escolhe/digita (pode trocar depois) → (vê a correção em verde) → Conferir próxima … → Tudo conferido
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
