## Why

Digitalizar documentos (contratos, apostilas, notas, formulários, prints) hoje exige redigitar ou usar OCRs que perdem trechos, trocam caracteres, descartam figuras, desmontam tabelas e bagunçam a paginação — e os bons costumam ser pagos ou pedem cadastro. O projeto começa do zero e precisa de uma linha de base de specs que defina, antes de qualquer código, o comportamento do MVP: uma ferramenta simples, sem conta e sem opções, que converte uma imagem ou PDF em texto e em um documento novo fiel ao original, depois que o usuário confere as palavras duvidosas.

## What Changes

- Site de um endereço só, com três telas: envio, progresso e resultado. Barra com logotipo e seletor de idioma da interface (PT | EN), rodapé com ©, tema claro, funcionando no celular.
- Envio de um arquivo por vez (JPG, PNG, WEBP, HEIC ou PDF) por clique, arrastar, colar ou câmera; a conversão começa na hora, sem escolher modo nem idioma.
- Pré-processamento que endireita, corrige perspectiva, limpa e amplia a imagem, preservando o original.
- Detecção de layout em blocos tipados com ordem de leitura, colunas, alinhamento, tamanho relativo e elementos não-texto (capa, logotipo, foto, assinatura, carimbo).
- Reconhecimento sempre com duas leituras independentes, português e inglês automáticos, com negrito e itálico por palavra.
- Reconciliação das leituras com regras determinísticas, árbitro opcional e marcação explícita do que segue em dúvida; transcrição sempre literal.
- Checagem de completude que reprocessa regiões não cobertas e transforma linhas não lidas em dúvidas.
- Extração de tabelas com células mescladas; tabela não estruturável entra como imagem.
- Processamento assíncrono com percentual, cancelamento e descarte de todos os arquivos em no máximo 1 hora.
- Tela de resultado com o documento em folhas por página, conferência obrigatória de cada palavra em dúvida (recorte do original, alternativas com o caractere divergente destacado, campo para digitar) antes de liberar a saída.
- Saídas: copiar texto, baixar Word ou baixar PDF — documentos novos, com texto editável, mesma paginação, organização, formatação e imagens do original.

## Capabilities

### New Capabilities
- `site-interface`: endereço único com três telas, barra de navegação, idioma da interface PT/EN, rodapé, tema claro, celular e acessibilidade.
- `file-upload`: formas de envio, um arquivo por conversão, início imediato sem opções, formatos aceitos e limites.
- `image-preprocessing`: normalização da imagem (inclinação, perspectiva, ruído, contraste, resolução), tamanho de folha e preservação do original.
- `layout-detection`: blocos tipados com caixa, ordem de leitura, colunas, alinhamento, tamanho relativo e elementos não-texto.
- `text-recognition`: duas leituras de cada bloco com palavras, posição, confiança, idioma automático e negrito/itálico.
- `reading-reconciliation`: combinação das leituras, resolução de divergências, árbitro, marcação de dúvidas e transcrição literal.
- `completeness-check`: garantia de que todo conteúdo da imagem foi coberto, com linhas não lidas viradas dúvidas.
- `table-extraction`: estrutura de tabelas (linhas, colunas, mesclas) e conteúdo das células.
- `job-processing`: ciclo de vida da conversão, progresso, cancelamento, falhas, descarte em até 1 hora e limite de uso.
- `review-editor`: resultado em folhas por página e conferência obrigatória das palavras em dúvida antes de copiar ou baixar.
- `document-export`: copiar texto e gerar Word e PDF novos, fiéis à paginação, organização, formatação e imagens do original.

### Modified Capabilities
<!-- Nenhuma: projeto novo, sem specs existentes. -->

## Impact

- Novos projetos `frontend/` (Next.js) e `backend/` (FastAPI + worker Celery), além de `docker-compose.yml`.
- API HTTP nova: `GET /health`, `POST /jobs`, `GET /jobs/{id}`, `DELETE /jobs/{id}`, `GET /jobs/{id}/result`, `GET /jobs/{id}/crops/{word_id}`, `PATCH /jobs/{id}/result`, `GET /jobs/{id}/export?fmt=docx|pdf`.
- Dependências gratuitas e open source: OpenCV, scikit-image, pypdfium2, PaddleOCR (PP-StructureV3 e PaddleOCR-VL), docTR, rapidfuzz, python-docx, LibreOffice (conversão DOCX → PDF), Redis, Celery.
- Nenhuma dependência paga, nenhuma conta de usuário e nenhum envio de dados a terceiros.

## Fora de escopo

- Login, contas de usuário, histórico de conversões e qualquer dado guardado depois da sessão.
- Vários arquivos na mesma conversão.
- Escolha de modo de leitura ou de idioma do conteúdo pelo usuário.
- Outros formatos de saída (ODT, HTML, Markdown, TXT, XLSX, CSV, JSON, PDF pesquisável sobre a imagem original).
- Edição livre do texto, troca de tipo de bloco ou ajuste de layout na tela de resultado; a correção é feita só nas palavras em dúvida.
- Reproduzir a fonte exata (família tipográfica) do original; o MVP preserva tamanho relativo, negrito e itálico.
- Tema escuro e interface em idiomas além de português e inglês; conteúdo em idiomas além de português e inglês.
- APIs pagas de IA (Claude, OpenAI, Google Vision etc.).
- Reconhecimento de fórmulas matemáticas como texto (fórmulas entram como imagem).
- Processamento em GPU e modelos de visão grandes (Qwen2.5-VL) — previstos como evolução.
- Aplicativo mobile nativo.
