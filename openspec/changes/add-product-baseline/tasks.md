> Ordem obrigatória em cada item: spec ajustada → teste falhando → implementação → teste passando.

## 1. Estrutura do projeto

- [x] 1.1 Criar `backend/` (Python 3.12, `pyproject.toml`, ruff, mypy, pytest) com FastAPI e rota `GET /health`
- [x] 1.2 Criar `frontend/` (Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, Vitest, Playwright, ESLint) com fontes IBM Plex Sans/Mono e Source Serif 4
- [x] 1.3 Criar `docker-compose.yml` (api + worker + redis) e `backend/Dockerfile` enxuto (modelos e LibreOffice entram nas tasks 5.1, 6.2 e 8.3)
- [x] 1.4 Montar o conjunto de teste `backend/tests/fixtures/precision/` (imagens + gabaritos de texto, ênfase e paginação) e o teste `@pytest.mark.precision` (D12)

## 2. Formato interno

- [x] 2.1 Modelos Pydantic `Document`, `Page` (tamanho de folha, colunas), `Block` (alinhamento, tamanho relativo), `Word` (negrito, itálico, alternativas), `Cell`, `Job` (D1) com testes de validação
- [x] 2.2 Gerar JSON Schema e tipos TypeScript do frontend a partir dos modelos; script `npm run gen:types`

## 3. Conversão e fila (specs file-upload, job-processing)

- [x] 3.1 `POST /jobs` com um arquivo: validação de formato por conteúdo, 20 MB, 50 páginas, PDF com senha, mais de um arquivo
- [x] 3.2 Worker Celery com estados e percentual que nunca diminui; `GET /jobs/{id}`
- [x] 3.3 `GET /jobs/{id}/result` e `GET /jobs/{id}/crops/{word_id}` quando concluída
- [x] 3.4 `DELETE /jobs/{id}` (cancelar / converter outro) com interrupção em até 10 s e remoção de arquivos
- [x] 3.5 Falha por página (página vira imagem + "[ilegível]") e falha total
- [x] 3.6 Descarte em até 1 h (Celery Beat a cada 5 min + limpeza na inicialização) e estado "expirada"
- [x] 3.7 Limite de 3 conversões ativas por IP

## 4. Pré-processamento (spec image-preprocessing)

- [ ] 4.1 Rasterização de PDF a ≥ 300 DPI com tamanho de folha por página; A4 por proporção para imagens
- [ ] 4.2 Orientação (0/90/180/270) e inclinação (residual ≤ 0,5°)
- [ ] 4.3 Correção de perspectiva com fallback sem correção
- [ ] 4.4 Limpeza (contraste, ruído, sombra) e upscale de texto pequeno
- [ ] 4.5 Página em branco mantida; saídas `aligned` e `normalized` preservando o original

## 5. Layout (spec layout-detection)

- [ ] 5.1 Integração PP-StructureV3 (modelos baixados no build da imagem) e mapeamento de rótulos → tipos de bloco
- [ ] 5.2 Ordem de leitura, colunas, cabeçalho e rodapé
- [ ] 5.3 Alinhamento e tamanho relativo por bloco
- [ ] 5.4 Blocos figura (capa, logotipo, foto, assinatura, carimbo) e fórmula com recortes do original; legenda como bloco separado
- [ ] 5.5 Listas com marcadores e níveis

## 6. Reconhecimento e reconciliação (specs text-recognition, reading-reconciliation)

- [ ] 6.1 Leitura por bloco com PaddleOCR (palavra, caixa, confiança), PT e EN sem escolha
- [ ] 6.2 Segunda leitura com docTR (modelos baixados no build da imagem)
- [ ] 6.3 Alinhamento das leituras e regra de concordância
- [ ] 6.4 Resolução por confiança e por releitura ampliada, com etapa registrada
- [ ] 6.5 Árbitro PaddleOCR-VL atrás de `ARBITER_ENABLED`, com validação da resposta contra as alternativas
- [ ] 6.6 Transcrição literal e "[ilegível]"; alternativas distintas e contagem de dúvidas por página/documento
- [ ] 6.7 Negrito e itálico por palavra (D8)
- [ ] 6.8 Rodar o teste de precisão e ajustar até CER ≤ 1%, WER ≤ 2% e ênfase ≥ 95% em impresso

## 7. Completude e tabelas (specs completeness-check, table-extraction)

- [ ] 7.1 Detecção de regiões órfãs, filtro de ruído e novos blocos na posição de leitura
- [ ] 7.2 Contagem de linhas por bloco, releitura e linhas faltantes como "[ilegível]" em dúvida
- [ ] 7.3 Estrutura de tabela com mesclas, cabeçalho e tabelas sem bordas
- [ ] 7.4 Células lidas pela leitura dupla; células vazias; tabela não estruturável como imagem

## 8. Exportação (spec document-export)

- [ ] 8.1 `PATCH /jobs/{id}/result` para gravar as palavras conferidas
- [ ] 8.2 DOCX: seção por página com tamanho de folha, colunas, alinhamento, tamanho relativo, negrito/itálico, listas, tabelas com mescla, imagens proporcionais, cabeçalho/rodapé
- [ ] 8.3 PDF via LibreOffice (`libreoffice-writer-nogui` na imagem) a partir do DOCX e verificação/ajuste de paginação (D10)
- [ ] 8.4 `GET /jobs/{id}/export?fmt=docx|pdf` com nome base do arquivo enviado e tratamento de falha

## 9. Frontend — moldura e envio (specs site-interface, file-upload)

- [ ] 9.1 Layout base: barra com logotipo e seletor PT | EN, rodapé, tema claro, 404, dicionários pt/en com idioma inicial do navegador
- [ ] 9.2 Tela de envio: escolher arquivo, arrastar, colar, "Tirar foto" no celular, HEIC → JPG no navegador, validações e mensagens
- [ ] 9.3 Tela de progresso: "Lendo seu documento…", nome do arquivo, percentual, "Cancelar", falhas e retorno ao envio

## 10. Frontend — resultado e conferência (specs review-editor, document-export)

- [ ] 10.1 Documento em folhas por página com "Página N de T", alinhamento, ênfase, listas, colunas, tabelas e imagens
- [ ] 10.2 Destaque das dúvidas (âmbar + sublinhado ondulado), aviso "Confira N palavras antes de baixar" e "Conferir próxima"
- [ ] 10.3 Quadro de conferência (popover / bottom sheet): recorte, alternativas monoespaçadas com diferença destacada, "Ou digite a correta", Esc para fechar
- [ ] 10.4 Resolver e avançar para a próxima dúvida atravessando páginas; envio das escolhas ao servidor
- [ ] 10.5 "Tudo conferido" com "Copiar texto" (→ "Copiado"), "Baixar Word" e "Baixar PDF"; "Converter outro" e logotipo apagando a conversão

## 11. Deploy e verificação final

- [ ] 11.1 Deploy do frontend na Vercel e do backend no Hugging Face Spaces (supervisord: api + worker + redis)
- [ ] 11.2 Teste E2E (Playwright) do fluxo enviar → progresso → conferir dúvidas → baixar Word e PDF, em desktop e celular, em PT e EN
- [ ] 11.3 Rodar `pytest`, `ruff check .` e `mypy app` no backend; `npm test`, `npm run lint` e `npx tsc --noEmit` no frontend
