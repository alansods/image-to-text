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

### D6. OCR secundário: docTR
Arquitetura diferente (DBNet + PARSeq/CRNN), erros pouco correlacionados com o PaddleOCR — essencial para a votação valer. Sempre executado (não há modo de leitura única).
- Alternativas: Tesseract (fraco em fotos; possível terceiro voto futuro); EasyOCR (mais lento em CPU).

### D7. Reconciliação
1. Alinhar as duas sequências de palavras por bloco pela posição (IoU ≥ 0,3) e, no desempate, `rapidfuzz.fuzz.ratio`. Palavras sem par viram divergência contra vazio.
2. Normalização só para comparar (NFC, aspas/hífens equivalentes); o texto final mantém a grafia original.
3. Regras na ordem da spec: confiança (Δ ≥ 0,15 e ≥ 0,90) → releitura do recorte ampliado 2× → árbitro.
4. Árbitro: PaddleOCR-VL recebe o recorte da palavra com margem + linha de contexto e escolhe entre as alternativas; resposta validada contra {alternativas, "[ilegível]"}. Liga/desliga por `ARBITER_ENABLED`.
- Alternativa: ROVER/votação por caractere — ganho marginal com só dois leitores.

### D8. Negrito e itálico por palavra
Nenhum dos OCRs gratuitos devolve ênfase, então ela é medida na imagem `normalized`, por palavra:
- Negrito: espessura média do traço = área de tinta ÷ comprimento do esqueleto (`skimage.morphology.skeletonize`), comparada à mediana do mesmo tamanho relativo de letra na página; acima de 1,35× = negrito.
- Itálico: ângulo de cisalhamento que maximiza a variância da projeção vertical (testando −20° a +20°); inclinação ≥ 8° = itálico.
- Os limiares saem do conjunto de teste (D11), com meta ≥ 95% de acerto da spec.
- Alternativas: classificador treinado de atributos de fonte — sem modelo aberto confiável para PT; descartado no MVP. Pedir ao árbitro VL — caro em CPU para todas as palavras.

### D9. Checagem de completude
Binarização (Otsu adaptativo) da página normalizada → componentes conectados → máscara do que está fora dos blocos. Componentes maiores que o menor caractere detectado são agrupados (dilatação) em regiões órfãs, reprocessadas como blocos. Linhas por bloco: perfil de projeção horizontal; cada linha visível sem transcrição vira uma palavra "[ilegível]" em dúvida com a caixa da linha.

### D10. Exportação: DOCX com python-docx, PDF pelo LibreOffice
- DOCX direto do `Document`: uma seção por página original, com o tamanho de folha da página e quebra de seção na troca; número de colunas da página como colunas da seção; parágrafos com alinhamento, tamanho de fonte = tamanho base × tamanho relativo; *runs* com negrito/itálico por palavra; listas com o marcador original como texto (para não depender da numeração automática do Word); tabelas com `merge`; figuras como imagem inline com largura proporcional (largura do recorte ÷ largura da página × largura útil).
- Paginação garantida: depois de gerar, o DOCX é convertido em PDF e as páginas são contadas; se alguma página original transbordou, a fonte daquela seção é reduzida em passos de 5% e o documento regerado (até 6 tentativas). O mesmo PDF é o "Baixar PDF".
- PDF: `soffice --headless --convert-to pdf` sobre o DOCX gerado. Word e PDF ficam idênticos.
- Copiar texto: montado no frontend a partir do `Document` (sem chamada ao servidor).
- Cada formato é um módulo em `backend/app/export/` com `export(document, options) -> Path`.
- Alternativas: desenhar o PDF direto (ReportLab) — duas implementações de layout que divergiriam; OCRmyPDF/PDF pesquisável — mantém a imagem escaneada, e o produto pede documento novo com texto.

### D11. Frontend
Next.js App Router com uma rota (`/`) e uma máquina de estados de tela (`upload → converting → result`) em um componente cliente; `not-found.tsx` para o 404. Estado do servidor com TanStack Query (polling, retry). Textos da interface em dicionários `pt.ts`/`en.ts` com um contexto React; idioma inicial por `navigator.language`, sem persistência. Conferência: palavras em dúvida como `<button>`; quadro com shadcn `Popover` no desktop e `Drawer` (bottom sheet) abaixo de 768 px; opções em IBM Plex Mono com diferença por caractere calculada no cliente; resoluções enviadas por `PATCH /jobs/{id}/result` assim que escolhidas. HEIC convertido no navegador (`heic2any`) antes do envio. Câmera com `<input type="file" accept="image/*" capture="environment">`.
- Alternativa: `next-intl` com rotas por idioma — descartada: só dois idiomas, sem rotas, e a troca precisa ser instantânea.
- Alternativa: uma rota por tela (`/jobs/[id]`, `/review`, `/export`) — descartada: sem histórico nem conta, o identificador na URL não serve para nada além de criar estados órfãos ao recarregar.

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

## Open Questions

- Versão exata do PP-StructureV3 / PaddleOCR-VL a fixar: decidir na implementação pelo melhor resultado no conjunto de teste em CPU x86.
- Limiares de negrito/itálico (D8): calibrar no conjunto de teste.
