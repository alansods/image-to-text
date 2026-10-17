## Context

Projeto novo, sem código. Motivação e escopo em `proposal.md`; comportamento em `specs/`; telas em `docs/layout/rotas-e-paginas.md`. Restrições que moldam a arquitetura:

- 100% gratuito, sem conta e sem IA externa: todo reconhecimento roda no nosso backend e nada fica guardado além de 1 hora.
- Frontend na Vercel; o backend não cabe lá (modelos de OCR passam de 250 MB, jobs longos estouram o timeout, sem GPU). Backend em Docker no Hugging Face Spaces (grátis, CPU x86, 16 GB).
- O backend roda só em **x86 (linux/amd64)**: o PaddlePaddle não publica pacote para Linux ARM. A imagem Docker é fixada em `linux/amd64` (no Mac com chip M, o Docker local roda por emulação, ~4× mais lento; os testes com pytest rodam nativos no macOS). Por isso o Oracle Cloud Always Free (ARM) deixou de ser opção de hospedagem. Alternativa descartada por ora: trocar o PaddlePaddle pelo ONNX Runtime (roda em ARM), sem garantia de que todos os modelos necessários tenham versão ONNX.
- Servidor só com CPU: o pipeline precisa caber em ~40 s/página (sempre leitura dupla).
- O documento gerado precisa repetir a paginação, a organização, a formatação e as imagens do original.

## Goals / Non-Goals

**Goals:**
- Pipeline modular, com etapas puras (imagem/dados in → dados out) testáveis isoladamente.
- Formato interno único (`Document`) consumido pela tela de resultado e pelos dois exportadores.
- Precisão mensurável automaticamente (CER/WER e acerto de ênfase) contra gabaritos versionados.
- Paginação do Word/PDF verificável automaticamente (número de páginas e página de cada bloco).

**Non-Goals:**
- Escalar para muitos usuários simultâneos (o plano grátis atende uso pessoal/equipe pequena).
- GPU, modelos de visão grandes e autoscaling.
- Reproduzir a família tipográfica do original.

## Decisions

### D1. Monorepo com `frontend/` e `backend/`
Um repositório, dois projetos. Os tipos do `Document` são definidos em Pydantic (`backend/app/models/document.py`) e o JSON Schema gerado (`model_json_schema`) alimenta os tipos TypeScript do frontend (`json-schema-to-typescript`), evitando divergência manual.
- Alternativa: dois repositórios — descartada, contratos dessincronizariam.

### D2. FastAPI + Celery + Redis, com polling
FastAPI recebe o upload e serve resultados; um worker Celery executa o pipeline por página e publica o percentual no Redis; o cliente consulta `GET /jobs/{id}` a cada 1,5 s.
- Alternativas: RQ (sem cancelamento robusto/`revoke`); SSE/WebSocket (melhor UX, mas HF Spaces e proxies gratuitos derrubam conexões longas). Pode evoluir para SSE sem mudar specs.
- Em HF Spaces (um contêiner só), api + worker + redis rodam juntos via `supervisord`; localmente, `docker-compose` separa os três.
- O agendador (Celery Beat, limpeza a cada 5 min) roda embutido no worker (`-B`): há um único worker, então não há agendamento duplicado.
- A API e o worker não conhecem o OCR: o worker chama `Pipeline.load_pages` e `Pipeline.process_page` (funções puras) e o orquestrador grava imagens, publica o percentual e trata falhas e cancelamento.
- O percentual é calculado como (páginas concluídas + fração da etapa atual) / total e guardado como máximo já publicado, para nunca diminuir.

### D3. Arquivos em disco local, descartados em até 1 hora
Arquivos em `/data/jobs/<id>/` (original, páginas alinhadas e normalizadas, recortes, resultado JSON, documentos gerados). `DELETE /jobs/{id}` apaga na hora (cancelar, "Converter outro", logotipo). Celery Beat roda a cada 5 minutos e apaga jobs com mais de 60 minutos; a limpeza também roda na inicialização. Sem banco de dados: estado em Redis com TTL de 1 h, resultado em JSON no disco.
- Alternativa: TTL de 24 h — descartada: o produto promete não guardar nada além do necessário para baixar.
- Alternativa: apagar no primeiro download — descartada: impediria baixar Word e PDF da mesma conversão.
- O frontend não usa localStorage/IndexedDB para dados da conversão nem para o idioma.

### D4. Pré-processamento com OpenCV; PDF com pypdfium2
- Ordem: perspectiva → orientação → inclinação → limpeza → página em branco → ampliação.
- Imagens: rotação do EXIF aplicada ao abrir (fotos de celular vêm "deitadas" com a rotação só anotada).
- Perspectiva: a folha é a maior região clara (Otsu sobre a imagem reduzida) aproximada por 4 cantos (`approxPolyDP`) + `warpPerspective`; se a região ocupar < 50% da foto ou praticamente a imagem toda (scan), não corrige.
- Orientação: classificador `PP-LCNet_x1_0_doc_ori` do PaddleOCR (0/90/180/270, ~0,02 s/página); o rótulo é a rotação no sentido horário, desfeita com `np.rot90(img, rótulo/90)`.
- Inclinação: ângulo que maximiza a variância da projeção horizontal do texto binarizado (busca grossa ±15° a cada 0,5° em imagem reduzida, refino ±0,6° a cada 0,05°). Alternativa descartada: `minAreaRect` sobre o texto — erra quando há figuras, carimbos ou assinaturas na página.
- Limpeza: sombra removida dividindo pelo fundo estimado (fechamento morfológico + mediana), CLAHE e `fastNlMeansDenoising`.
- Página em branco: nenhuma mancha escura (limiar fixo 140) com área de letra pequena.
- Ampliação: se a altura mediana das letras < 20 px, amplia (INTER_CUBIC) as duas versões até ~32 px (as bordas suavizadas "encolhem" ~10% na binarização), mantendo as coordenadas de `aligned` e `normalized` iguais.
- Medido: ~1 s por página A4 a 300 DPI (CPU).
- Dependências: PaddleOCR/PaddlePaddle entram já aqui (orientação), não na 5.1. O PaddleX confere o pacote `opencv-contrib-python==4.10.0.84` pelo nome, então usamos exatamente ele como única instalação do OpenCV (com `libgl1`/`libglib2.0-0` na imagem Docker). Alternativa descartada: a variante "headless" com o mesmo `cv2` — o PaddleX a recusa, e duas instalações de `cv2` juntas quebram de forma imprevisível.
- Duas saídas por página: `aligned` (original apenas rotacionado/retificado, usada em recortes e imagens do documento) e `normalized` (contrastada, usada só para leitura).
- Tamanho de folha: do PDF, via `page.get_size()` (pontos); de imagem, A4 com orientação pela proporção (spec `document-export`).
- pypdfium2 em vez de pdf2image/poppler: licença permissiva, sem dependência de sistema, rápido.

### D5. Layout: modelo `PP-DocLayout_plus-L` + organização própria
Só o modelo de layout do PaddleOCR (sem o pipeline PP-StructureV3 completo): ~0,8 s e 1,3 GB por página. A leitura do texto fica toda na task 6, por bloco, como a spec pede. Em `pipeline/layout.py`:
- Duas passadas de confiança: aceita caixas ≥ 0,5 e só aproveita as de 0,3 a 0,5 em áreas vazias (sobreposição < 30%). Recupera, por exemplo, o título de uma capa sem duplicar caixas.
- Rótulos do modelo → tipos da spec (`doc_title`/`paragraph_title` → título; `number`/`footer` → rodapé; `image`/`chart`/`seal` → figura; legendas, notas, referências → parágrafo).
- "Texto" que é desenho vira figura, avaliado na imagem alinhada (a limpeza de sombra clareia formas escuras grandes): forma grande e cheia (símbolo de logotipo) ou poucas manchas com um traço atravessando o bloco (assinatura).
- Ordem de leitura: cabeçalho → corpo → rodapé. No corpo, blocos com ≥ 60% da largura útil separam seções; dentro de cada seção, grupos lado a lado (sem sobreposição em x e com sobreposição em y) são colunas, lidas inteiras da esquerda para a direita. A página só conta como multicoluna se cada coluna tiver ≥ 2 blocos (duas assinaturas lado a lado não são colunas). Alternativa descartada: XY-cut clássico — intercala colunas quando os espaços entre parágrafos coincidem em altura.
- Alinhamento comparando o bloco com a área de texto (página ou coluna; blocos de largura total não contam para a coluna); bloco de largura total é justificado se as linhas, menos a última, chegam à margem direita (tolerância de 0,3 altura de letra). Ambiguidade aceita: linha única cheia, ou parágrafo de 2 linhas que é o mais largo da página.
- Tamanho relativo: altura mediana das letras do bloco ÷ do texto da página.
- Listas: parágrafos seguidos começando com marcador (`a)`, `1.`, `iv)`, `•`, `-`…) viram um bloco lista com `items` (palavra inicial e nível pelo recuo). Precisa do texto lido: aplicada na task 6.
- Alternativa descartada: PP-StructureV3 completo — ~10 s e 4,7 GB por página no teste, estouro de memória com a detecção de texto "server", e lê a página inteira (duplicaria o custo da task 6).
- MKL-DNN desligado no modelo de layout: no PaddlePaddle 3.3 em Linux x86 ele falha com MKL-DNN ligado (erro do conversor PIR); encontrado no teste de ponta a ponta no Docker.
- O extra `paddleocr[doc-parser]` não é necessário para o modelo de layout (e traria ~30 dependências, incluindo o cliente `openai`); fica fora.

### D6. Leitores: PaddleOCR (modelo para português) e docTR multilíngue
- **Primário:** PaddleOCR com `lang="pt"`, que na versão 3.7 usa `PP-OCRv6_medium_det` + `PP-OCRv6_medium_rec` (latino, lê também inglês). Medido na página 1 dos casos sintéticos: CER 0,08% (impresso), 0,16% (foto), ~11 s/página no Mac. Confiança é por linha; a caixa de cada palavra sai de `return_word_box`.
- **Secundário:** docTR com detector `db_resnet50` e reconhecedor `Felix92/doctr-torch-parseq-multilingual-v1` (Hugging Face, Apache 2.0), baixados no build. Arquitetura diferente, erros pouco correlacionados — essencial para a votação valer. Medido: CER 2,5–2,7%, ~8 s/página. Sempre executado (não há modo de leitura única).
- O vocabulário do docTR multilíngue **não tem** ª, º, —, –, “ e ”; isso é tratado na comparação (D7, regra de caracteres cegos).
- O detector do docTR redimensiona a entrada para 1024 px: recortes menores são colados num fundo branco de 1024 px (num rodapé de 214×70 px ele lia lixo).
- As caixas por palavra do PaddleOCR vêm de fragmentos que podem juntar acentuadas vizinhas ("á à"); cada fragmento é repartido por caractere.
- Releitura (D7.4) usa só os reconhecedores (`TextRecognition` do PaddleOCR e `recognition_predictor` do docTR) no recorte da palavra ampliado 2×, sem detecção.
- O docTR declara `opencv-python`; ele é bloqueado por `override-dependencies` no `pyproject.toml`, pois o `opencv-contrib-python` exigido pelo PaddleX já fornece o `cv2`.
- Alternativas: docTR de fábrica (vocabulário francês, sem ã/õ/á/í/ó/ú — CER 5%, WER 25%); Tesseract (fraco em fotos, mais um programa no servidor); outro modelo do próprio PaddleOCR (erros correlacionados, votação perde valor); EasyOCR (mais lento em CPU).

### D7. Reconciliação
0. **Calibração:** a confiança do docTR é multiplicada por 0,9. Medido: ele dá ~1,0 até a leituras erradas ("_`{|}" para "—", "~" para "-") e erra ~15× mais que o PaddleOCR; sem isso, a leitura dele seria a padrão nas dúvidas e venceria pela regra de confiança.
1. **Alinhamento por sobreposição:** palavras das duas leituras de um bloco (em coordenadas da página) se ligam quando a interseção cobre ≥ 50% da menor caixa; cada grupo ligado é uma unidade de comparação. Assim "CONTRA" + "TO" (docTR) se compara com "CONTRATO" (PaddleOCR). Palavras sem par viram divergência contra vazio (texto `""` como alternativa = "não há palavra aqui"). As unidades seguem a ordem das linhas (de cima para baixo, da esquerda para a direita).
2. **Normalização só para comparar** (NFC, aspas e hífens/travessões equivalentes, espaços ignorados dentro da unidade); o texto final mantém a grafia do PaddleOCR. **Espaços:** o texto aceito junta os espaços das duas leituras — o PaddleOCR às vezes cola palavras ("R$17,00"), o docTR separa pela posição. Palavras do docTR com vão < 0,2 da altura são uma palavra partida ("CONTRA" + "TO") e se juntam sem espaço.
2b. **Indicador ordinal:** "°" (grau) grudado numa letra vira "º" nas duas leituras e na releitura ("n°" → "nº"). Os dois leitores confundem os sinais (medido: todo "nº" dos contratos saía "n°"), e grau só aparece depois de número ("25°C"), que fica intacto. Decisão do usuário: visualmente igual, mas a troca afeta busca, copiar/colar em sistemas e leitores de tela. Alternativas: deixar "n°" (A) ou marcar todo "n°" como dúvida (C, cliques demais).
3. **Caracteres cegos:** caractere que o PaddleOCR leu e que não existe no vocabulário do docTR (ª, º, —, –…) casa com qualquer caractere ou com nada na leitura do docTR. Unidade cujo texto do PaddleOCR é só de caracteres cegos (um "—" solto) é aceita com a leitura dele, seja qual for a do docTR (que ali não tem como acertar).
4. Regras na ordem da spec: confiança (Δ ≥ 0,15 e ≥ 0,90) → releitura do recorte ampliado 2× com os dois reconhecedores → árbitro. O recorte da releitura tem margem de 0,25 da altura em cima/embaixo (acentos) e só 0,1 dos lados (com margem maior ele pegava a letra vizinha: "o" virou "on").
5. Palavra em dúvida fica com a leitura de maior confiança; as alternativas são os textos distintos das duas leituras, por confiança.
6. Árbitro: PaddleOCR-VL recebe o recorte da palavra com margem + linha de contexto e escolhe entre as alternativas; resposta validada contra {alternativas, "[ilegível]"} (ignorando aspas/traços/espaços); se o recorte da palavra não decide, lê a linha e aceita a opção que aparece nela como palavra inteira, se só uma aparecer. Usa `DocVLM(model_name="PaddleOCR-VL-0.9B")` com a pergunta "OCR:" (precisa de `sentencepiece` e `einops`). Medido no Mac: ~3 s por palavra, ~16 s por linha, por isso fica desligado por padrão (`ITT_ARBITER_ENABLED`) e o modelo não é baixado no build.
7. Bloco de texto em que nenhum leitor encontrou palavra vira uma palavra "[ilegível]" em dúvida com a caixa do bloco. Até a task 7, tabelas entram como imagem do original.
- Alternativas: ROVER/votação por caractere — ganho marginal com só dois leitores; pareamento 1:1 por IoU — quebra quando um leitor separa uma palavra em duas.

### D8. Negrito e itálico por palavra
Nenhum dos OCRs gratuitos devolve ênfase, então ela é medida na imagem `normalized`, por palavra:
- **Negrito:** largura das hastes = média do miolo (percentis 25–75) dos trechos contínuos de tinta em cada linha de pixels, dividida pelo tamanho relativo do bloco e comparada à mediana da página; ≥ 1,26× = negrito. Medido no conjunto de teste: palavras normais até 1,22, negrito a partir de 1,30 (negrito+itálico tem hastes mais finas). A medida "tinta ÷ esqueleto" (`skeletonize`) foi a primeira tentativa e descartada: as serifas e galhos do esqueleto diluem a diferença (maiúsculas em negrito davam só 1,35×).
- **Itálico:** ângulo de cisalhamento que maximiza a soma dos quadrados da projeção vertical (−20° a +20°); inclinação ≥ 8° = itálico. Medido: itálico 16°, normal 0°.
- **Palavras curtas** (< 3 caracteres: "a", "de") têm pouca tinta: entre duas vizinhas que concordam, seguem as vizinhas; na borda do bloco vale a própria medida.
- **Tamanho de blocos em maiúsculas:** o tamanho relativo da D5 mede a altura mediana das manchas, que num bloco só de maiúsculas/algarismos (≥ 60%) é a altura da maiúscula, ~1,4× a do "x". Depois da leitura, `size_for_text` divide por 1,4 (título 16 pt/11 pt: medido 1,91 → 1,36; gabarito 1,36). Corrige também o tamanho do título no Word/PDF.
- **Limitações conhecidas:** prints de baixa resolução ampliados 4× borram todas as letras igualmente e comprimem a diferença do negrito (título de print: 91,5% de acerto no caso); capas com quase só título ficam sem "texto típico" de referência na página; manuscrito sai como itálico (letra inclinada) — só reportado, fora da meta.
- Alternativas: classificador treinado de atributos de fonte — sem modelo aberto confiável para PT; descartado no MVP. Pedir ao árbitro VL — caro em CPU para todas as palavras.

### D9. Checagem de completude
- **Regiões órfãs (7.1):** tinta da página normalizada (limiar 140) fora de todos os blocos (com margem de 10 px); manchas menores que 0,4 altura de letra nas duas direções são poeira; o resto é agrupado por dilatação de 1 altura de letra. Cada região é lida pelos dois leitores: com palavras vira parágrafo; sem palavras vira figura (recorte do original). Entra antes do primeiro bloco abaixo dela que se sobrepõe na horizontal (nota de rodapé → fim da página).
- **Linhas por bloco (7.2):** faixas horizontais ocupadas por manchas com altura de letra (0,5–2,5 alturas típicas); faixa sem nenhum centro de palavra lida é relida sozinha pelos dois leitores; sem leitura, vira "[ilegível]" em dúvida com a caixa da linha (o recorte da conferência mostra a linha).
- Medido: nenhum bloco órfão nem linha faltante falsos nos 9 casos do conjunto.

### D10. Exportação: DOCX com python-docx, PDF pelo LibreOffice
- DOCX direto do `Document` (`app/export/docx_export.py`): uma seção por página original, com o tamanho de folha da página (paisagem quando mais larga); margens pela posição do conteúdo no original (18–90 pt); blocos "cabeçalho"/"rodapé" viram cabeçalho/rodapé da seção (não vinculados à anterior); página com colunas usa seções contínuas (blocos com ≥ 60% da largura do conteúdo atravessam as colunas; quebra de coluna entre colunas); tamanho = corpo do documento × tamanho relativo (D16); *runs* com negrito/itálico por palavra (palavras seguidas com a mesma ênfase num só run); listas com o marcador original como texto e recuo por nível; tabelas "Table Grid" com `merge` e larguras de coluna proporcionais (`gridCol` + largura das células: o LibreOffice segue a grade, o Word as células); figuras como imagem inline com largura proporcional; espaço antes de cada bloco = vão do original menos 0,3 do corpo, até 3 linhas. Fonte Times New Roman (Liberation Serif no servidor, mesmas medidas).
- Paginação garantida (`app/export/pdf_export.py`): o DOCX é convertido em PDF e as páginas são contadas; se passar do número de páginas do original, as fontes são reduzidas 5% e tudo é regerado (até 6 tentativas). O mesmo par DOCX/PDF é servido nos dois downloads e fica em cache até a próxima conferência (`PATCH` apaga).
- PDF: `soffice --headless --convert-to pdf` com perfil temporário próprio por chamada (conversões simultâneas não disputam o perfil); `libreoffice-writer-nogui` + `fonts-liberation` na imagem. Sem LibreOffice (desenvolvimento local), o Word é gerado sem a conferência de paginação e o PDF falha com `export_failed`.
- `PATCH /jobs/{id}/result` com `{"words": [{"id", "text"}]}`: texto aparado, 1–200 caracteres; palavra desconhecida → 404; status "editada".
- `GET /jobs/{id}/export?fmt=docx|pdf`: nome base do arquivo enviado; falha → 500 `{"error": "export_failed"}` sem tocar na conferência.
- Medido (Docker, x86 emulado): Word + PDF de 1–3 páginas em ~2 s.
- Copiar texto: montado no frontend a partir do `Document` (sem chamada ao servidor).
- Limitação: a família da fonte do original (com/sem serifa) não é detectada; tudo sai em serifa.
- Alternativas: desenhar o PDF direto (ReportLab) — duas implementações de layout que divergiriam; OCRmyPDF/PDF pesquisável — mantém a imagem escaneada, e o produto pede documento novo com texto.

### D11. Frontend
Next.js 16 App Router com uma rota (`/`) e uma máquina de estados de tela (`upload → converting → result`) no componente cliente `ConverterApp`; `not-found.tsx` para o 404. Estado do servidor com `fetch` + polling de 1,5 s em `useEffect` (só três chamadas simples: não valeu uma dependência como TanStack Query). Textos em `lib/i18n.tsx` (dicionários `pt`/`en` tipados, mesmas chaves) com contexto React; idioma inicial lido do navegador com `useSyncExternalStore` (servidor e hidratação em português, sem divergência), sem persistência. Conferência: palavras em dúvida como `<button>`; quadro próprio (`WordCheck`) renderizado com `createPortal` no `body` — HTML não aceita formulário dentro de `<p>` — posicionado abaixo da palavra no desktop e como painel inferior abaixo de 640 px (só CSS); foco na primeira opção, Esc/clique fora/fechar fecham; opções em IBM Plex Mono com a diferença por caractere pela maior subsequência comum; cada escolha é gravada (`PATCH`) antes de avançar para a próxima dúvida. A folha usa a proporção do papel e tamanhos em `cqw` (container query) com mínimo legível no celular; o layout (cabeçalho, colunas, rodapé, margens) segue as mesmas regras do Word. HEIC convertido no navegador (`heic2any`, carregado sob demanda). Câmera com `<input type="file" accept="image/*" capture="environment">`; "Tirar foto" só aparece em telas de toque (`pointer: coarse`). O ano do rodapé é lido no cliente (o Next 16 recusa relógio no HTML pré-renderizado).
- Rota auxiliar `GET /jobs/{id}/images/{block_id}` serve o recorte das figuras para as folhas; o recorte de conferência (`/crops/{word_id}`) vem com a palavra contornada em âmbar; `Content-Disposition` exposto no CORS para o download sair com o nome do arquivo enviado. Alternativa vazia ("não há palavra aqui") aparece como "(nenhuma palavra)" e grava texto vazio, que o Word/PDF/cópia ignoram.
- Alternativa: `next-intl` com rotas por idioma — descartada: só dois idiomas, sem rotas, e a troca precisa ser instantânea.
- Alternativa: uma rota por tela (`/jobs/[id]`, `/review`, `/export`) — descartada: sem histórico nem conta, o identificador na URL não serve para nada além de criar estados órfãos ao recarregar.
- Alternativa: shadcn `Popover`/`Drawer` — descartado: dois componentes e duas dependências para um quadro que o CSS já adapta.

### D12. Conjunto de teste de precisão (sintético)
`backend/tests/fixtures/precision/` com pares entrada + gabarito (`expected.txt` com o texto em ordem de leitura e `expected.json` com páginas, blocos, alinhamento, ênfase por palavra e figuras): contrato impresso, contrato fotografado, tabela com mescla, duas colunas com figura (inglês), PDF de 3 páginas com capa e página em branco, print pequeno, página de cabeça para baixo, ênfase mista e manuscrito.
- Gerados por código (`tests/fixtures/precision/generator/`, semente fixa): o documento é montado com ReportLab palavra a palavra (o gerador conhece posição, ênfase, alinhamento e página de tudo o que desenha), rasterizado com pypdfium2 a 300 DPI, salvo como PDF escaneado (só imagens) ou foto, e degradado com OpenCV (perspectiva, inclinação, rotação, sombra, ruído, JPEG). Fontes: as 14 fontes padrão do PDF (Times, Helvetica) — renderizadas pelo pdfium de forma idêntica em qualquer máquina — e Caveat (OFL) para o "manuscrito".
- Os arquivos gerados são versionados, para os testes não dependerem do gerador.
- Teste `@pytest.mark.precision` calcula CER/WER com `jiwer`, acerto de ênfase, número de páginas e de figuras; fica pulado até o pipeline existir (task 6.8). Roda fora do ciclo rápido (é lento).
- ReportLab e jiwer são dependências só de desenvolvimento.
- Alternativas: documentos reais anotados à mão — gabarito caro e sujeito a erro; desenhar com Pillow — justificação de texto e tabelas artesanais e pouco realistas.

## Risks / Trade-offs

- [Modelos pesados em CPU estouram 40 s/página] → modelos carregados uma vez por worker; árbitro só em divergências; ênfase calculada só em palavras de texto; medir em `tests/perf`.
- [Detecção de negrito/itálico abaixo de 95%] → limiares calibrados no conjunto de teste; se não atingir, a spec é revista antes de seguir.
- [Texto transborda a página no Word] → redução de fonte por seção com verificação de páginas (D10).
- [LibreOffice aumenta a imagem Docker em ~500 MB] → aceito; instalar só `libreoffice-writer-nogui`.
- [HF Spaces hiberna e o 1º acesso demora ~1 min] → a tela de progresso fica em 0% com "Lendo seu documento…".
- [Erros correlacionados entre os dois OCRs] → completude + conferência humana cobrem; Tesseract como terceiro voto é evolução possível.
- [Manuscrito abaixo da meta] → meta de CER só para impresso; manuscrito medido e reportado, sem bloquear.
- [Disco cheio no plano grátis] → descarte em 1 h, limite de 50 páginas e 20 MB.
- [Abuso do serviço público] → 3 conversões ativas por IP.

## Migration Plan

Projeto novo: sem migração. Deploy inicial: `frontend` na Vercel com `NEXT_PUBLIC_API_URL`; `backend` como imagem Docker no HF Spaces. Rollback: voltar para a imagem/commit anterior em cada plataforma.

### D13. Avaliação de qualidade da página
Pedido do usuário: em imagem ruim, **avisar** (não recusar) que pode haver inconsistências; recusa só quando nada é legível (já existe: falha "unreadable"). Cada página ganha `quality = {low, reasons[]}` no resultado, com motivos:
- `resolution`: altura típica da letra na imagem original abaixo do mínimo de leitura (o pré-processamento precisou ampliar muito);
- `blur`: nitidez baixa — variância do Laplaciano nas regiões de texto;
- `contrast`: diferença pequena entre tinta e papel;
- `uncertain_reading`: mais de 10% das palavras da página em dúvida ou "[ilegível]".
Medido (página 1 dos casos + versões degradadas na hora): ampliação ≥ 2× só no print (4×); nitidez (percentil 90 do |Laplaciano| na faixa em volta da tinta, dentro dos blocos de texto, ÷ contraste) 0,35–0,69 nas páginas boas e 0,10–0,27 nas desfocadas (σ 1,5–2) → limite 0,30; contraste (mediana do papel − mediana da tinta nos blocos de texto) 136–242 nas boas → limite 80. Medir na página inteira não serve: a ilustração da capa (degradês) derrubava a nitidez para 0,06. Os limites são calibrados no conjunto de teste: os casos impressos nítidos não podem disparar o aviso; o print de tela (letras de ~7 px ampliadas 4×) e uma foto desfocada sim. A tela mostra o aviso acima das folhas (task 10.6).
- Resultado medido: nenhum caso nítido do conjunto é marcado; print → `resolution` + `blur`; manuscrito → `uncertain_reading`; versões desbotadas → `contrast`; desfoque σ 2 → `blur`. Desfoque leve (σ 1) às vezes não é marcado, mas a leitura continua boa (CER ≤ 0,3%).
- Alternativas: recusar a imagem — descartado pelo usuário (muitas vezes só existe aquela foto, e ela ainda rende texto aproveitável); não marcar ênfase em imagem ruim — descartado no MVP, o aviso já pede conferência da formatação.

### D14. Robustez: contraste baixo e texto classificado como imagem
A medição de qualidade (D13) revelou duas falhas silenciosas, com texto inteiro perdido sem dúvida nem aviso:
- **Contraste baixo virava página em branco:** com tinta cinza-clara (cinza 150–213), `is_blank` não achava manchas. Correção: esticar o contraste (percentis 0,5 e 99,5 → 0 e 255) antes da limpeza e da checagem de branco, quando a faixa útil é estreita; página realmente branca não tem faixa para esticar.
- **Foto levemente desfocada virava uma "fórmula"/"imagem" de página inteira** no `PP-DocLayout_plus-L` (mesmo com σ 1, só na foto; a versão impressa resiste). Correção: depois da detecção, bloco figura/fórmula que contém linhas de texto (manchas do tamanho de letra alinhadas em fileiras) é redividido em parágrafos pelas linhas de texto e lido como texto; figuras de verdade (logotipo, gráfico, assinatura) não têm fileiras regulares de letras.
- **Causa real da "fórmula" de página inteira:** o endireitamento. Na foto desfocada, Otsu direto marcava ~41% da página (sombra/fundo) como tinta e a busca "achava" −15° numa folha reta; a página entortada confundia o detector. Correção: binarizar a página já sem sombra (`_flatten`, a mesma divisão pelo fundo da limpeza, sem o filtro de ruído lento). A proteção "texto dentro de figura" fica como rede de segurança: linhas = faixas horizontais ocupadas por manchas com altura de letra/palavra (≥ 4 manchas, ≥ 10% da largura); ≥ 3 linhas com ≥ 50% da tinta = texto; parágrafos separados por vão > 1,1 altura de letra; o que sobra com tamanho de desenho volta como figura. Nenhuma figura de verdade do conjunto (logotipos, gráfico, ilustração, assinaturas, carimbo) é afetada.
- Medido depois das correções: contrato/artigo desbotados e desfocados (σ 1–2) lidos com CER 0–0,49%.
- Alternativas: rodar o detector numa versão nitidificada (testado: a versão limpa da página dá o mesmo erro); recusar a imagem (descartado pelo usuário, D13).

### D15. Tabelas
- Classificador `PP-LCNet_x1_0_table_cls` (com/sem grade) + detector de células `RT-DETR-L_wired_table_cell_det` / `RT-DETR-L_wireless_table_cell_det` (0,4–0,7 s por tabela). A grade sai das bordas das caixas: bordas a menos de 0,3 altura típica de célula são a mesma linha/coluna de grade; caixa que atravessa várias = célula mesclada.
- Texto: a tabela inteira passa pela leitura dupla e reconciliação (D7); cada palavra vai para a célula que contém o centro dela. Ênfase medida também nas células.
- Não estruturável → imagem do original: grade com buraco ou sobreposição, menos de 2×2, palavra fora de todas as células ou tabela sem nenhuma palavra.
- Medido: recibo (18 células, "Total" com 3 colunas) CER 0%; cabeçalho mesclado (linhas e colunas) e célula vazia corretos; tabela sem bordas (12 células) correta.
- Alternativas: `SLANeXt_wired/wireless` (estrutura certa, mas caixas das células distorcidas em tabelas largas — células "fora" da tabela); `SLANet_plus` (errou a mescla); grade por OpenCV (falha sem bordas).

### D16. Tamanho relativo medido no documento inteiro
Depois de lidas todas as páginas, `rel_size` de cada bloco de texto = altura mediana das suas palavras ÷ altura mediana das palavras dos parágrafos do documento (`app/pipeline/sizes.py`). Na página, o "texto típico" de uma capa é o próprio título (o título de 24 pt saía como 13 pt). Medido: altura da palavra em pontos ≈ corpo da fonte (razão 0,94–1,13). O mesmo número serve à tela e aos exportadores.

### D17. Deploy gratuito
- Backend no Hugging Face Spaces (Docker, CPU basic grátis: 2 vCPU, 16 GB, x86): estágio `space` do mesmo `backend/Dockerfile` acrescenta `redis-server` e `supervisor`, que sobe redis (sem persistência), worker Celery com o agendador de limpeza e a API na porta 7860; tudo como o usuário 1000 que o Space usa. `docker compose` constrói o estágio `app` (sem supervisord). Testado localmente: os três processos sobem e um recibo é convertido e exportado.
- Frontend na Vercel com `frontend/` como raiz e `NEXT_PUBLIC_API_URL` apontando para o Space; o Space libera o site em `ITT_CORS_ORIGINS`. Páginas estáticas (build de produção verificado).
- Passo a passo para o usuário em `docs/deploy.md`.
- Alternativas: Render/Railway grátis — pouca memória para os modelos (512 MB–1 GB); três Spaces separados (api, worker, redis) — o grátis não tem rede privada entre Spaces.

### D18. Ajustes com um contrato real escaneado (teste do usuário)
O primeiro teste com um documento real (contrato de 5 páginas escaneado, com rubricas, assinaturas e preenchimento à mão) mostrou problemas que o conjunto sintético não tinha:
- **Detector do PaddleOCR sem nenhuma linha** em parágrafos inteiros (nada com o corte padrão; detecta tudo numa cópia reduzida). Quando o PaddleOCR vê menos da metade das palavras do docTR num bloco, relê o bloco no **modo sensível**: detecção numa cópia com letras de ~10 px e leitura na resolução original. Baixar o corte de confiança das caixas (0,4) também detectava, mas cortava letras e lia lixo — descartado.
- **Ordem em linha curva**: as unidades seguem a ordem do leitor principal (que acompanha a linha inteira); o que só o docTR viu entra depois da vizinha à esquerda na mesma linha.
- **Releitura com o segundo leitor falhando**: títulos sublinhados — o docTR lê "_" (0,18). Regra nova da spec: vale a releitura do principal quando ela repete a leitura dele com ≥ 0,97 e o segundo fica abaixo de 0,90; pontuação final colada pelo sublinhado ("CLÁUSULA.") não conta.
- **Assinatura, rubrica e preenchimento à mão**: bloco com ≥ 50% de dúvidas e menos de 50% da tinta em manchas do tamanho de letra impressa vira figura (medido: impresso 0,71–1,00; à mão 0,00–0,31). Sem tinta não conta (região em branco).
- **Sujeira do scanner**: região órfã precisa de 0,6 altura de letra (era 0,4; riscos de 4 × 11 px viravam "1" e "e").
- **Tamanho da letra em pontos (`font_pt`)**: altura da tinta de cada palavra ÷ (topo − base das letras que ela tem: baixa 0,52; maiúscula/haste/algarismo 0,72; minúscula acentuada 0,75; maiúscula acentuada 0,90; perna 0,21), sem as linhas de sublinhado; mediana do bloco. Medido em texto renderizado: erro ≤ 5% (11 pt → 10,6–11,5; 16 pt → 15,3). No documento, diferença < 15% do corpo vira o corpo. Word, PDF e tela usam `font_pt`.
- **Orientação**: só gira com confiança ≥ 60% do classificador (páginas impressas 92–93%; a página de assinaturas deu 37% para 270° e saía deitada).
- **Ordem das palavras**: linhas montadas encadeando da esquerda para a direita cada palavra à vizinha com altura sobreposta (≥ 25%), linhas ordenadas pela altura do começo — o PaddleOCR às vezes parte uma linha curva e entrega primeiro o pedaço da direita (mais alto). Pedaços que começam na mesma altura (separados por um sublinhado) vão da esquerda para a direita.
- **Cabeçalho/rodapé curto** (número da página) alinha pela posição na página; **vãos verticais** do original são mantidos até 60% da folha (Word e tela), e a conferência de paginação reduz fontes se algo transbordar.
- **Texto × figura**: texto com ≥ 50% da área dentro de uma figura fica só na imagem; o que só encosta continua texto e é pintado de branco no recorte da figura (a página original não é alterada).
- **Posição horizontal das imagens**: no Word/PDF e na tela, recuo = distância do início do conteúdo (a rubrica volta para a direita).
- **Conferência** (pedido do usuário): não pula sozinha para a próxima dúvida — o quadro fecha com o foco na palavra corrigida, marcada em verde só na tela; "Conferir próxima" segue da última conferida. A palavra corrigida continua clicável para trocar a escolha. A opção "Manter como no original" (recorte da palavra no meio do texto) foi retirada a pedido do usuário: recorte de imagem dentro da linha não é aceitável no documento final; assinaturas e escrita à mão já viram figura na detecção de layout, e o resto se resolve digitando ou com "(nenhuma palavra)".

### D19. Traço decidido pela forma (hífen × travessões × sublinhado)
- **Problema** (contrato real): os dois leitores leem o travessão curto "–" como "-" e concordam (troca silenciosa); em títulos sublinhados, pedaços do sublinhado viram "_" ou lixo ("|}~°£"), e um leitor lê "--"/"_" onde o outro lê "-".
- **Decisão**: trecho só de símbolos com algum traço (sem letras/algarismos) é medido na imagem (`pipeline/dashes.py`): tira as linhas horizontais mais longas que 2,5 alturas de maiúscula (sublinhado), procura um traço fino entre 15% e 85% da altura acima da linha de base e compara o comprimento com a altura das maiúsculas: < 0,58 hífen, ≤ 1,05 "–", acima "—". Sem traço → descartado; sem letras em volta para comparar → regras normais. Pedaço só de "_" colado num traço da mesma linha é descartado (é o sublinhado debaixo dele). O mesmo traço visto por dois pedaços vira uma palavra só. `resolved_by = "shape"` quando os leitores divergiam.
- **Medidas** (contrato real + conjunto de teste): hífen 0,32–0,45; "–" 0,72–0,77; "—" 1,28–1,65 — faixas bem separadas.
- **Fora**: hífen dentro de palavra ("mão-de-obra", CPF) já sai certo e não é medido; "______" lido pelos dois leitores (linha de preencher) continua conteúdo.
- **Resultado no contrato**: todos os títulos com "–" (antes "-"), sem "_"/lixo, dúvidas 17 → 13.

## Open Questions

- Limites da avaliação de qualidade (D13): calibrar no conjunto de teste.
