## Context

Projeto novo, sem código. Motivação e escopo em `proposal.md`; comportamento em `specs/`; telas em `docs/layout/rotas-e-paginas.md`. Restrições que moldam a arquitetura:

- 100% gratuito, sem conta e sem IA externa: todo reconhecimento roda no nosso backend e nada fica guardado além de 1 hora.
- Frontend na Vercel; o backend não cabe lá (modelos de OCR passam de 250 MB, jobs longos estouram o timeout, sem GPU). Backend em Docker no Hugging Face Spaces (grátis, CPU, 16 GB) ou Oracle Cloud Always Free (ARM, 24 GB).
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
- O percentual é calculado como (páginas concluídas + fração da etapa atual) / total e guardado como máximo já publicado, para nunca diminuir.

### D3. Arquivos em disco local, descartados em até 1 hora
Arquivos em `/data/jobs/<id>/` (original, páginas alinhadas e normalizadas, recortes, resultado JSON, documentos gerados). `DELETE /jobs/{id}` apaga na hora (cancelar, "Converter outro", logotipo). Celery Beat roda a cada 5 minutos e apaga jobs com mais de 60 minutos; a limpeza também roda na inicialização. Sem banco de dados: estado em Redis com TTL de 1 h, resultado em JSON no disco.
- Alternativa: TTL de 24 h — descartada: o produto promete não guardar nada além do necessário para baixar.
- Alternativa: apagar no primeiro download — descartada: impediria baixar Word e PDF da mesma conversão.
- O frontend não usa localStorage/IndexedDB para dados da conversão nem para o idioma.

### D4. Pré-processamento com OpenCV; PDF com pypdfium2
- Orientação: classificador de orientação do PaddleOCR (0/90/180/270); inclinação: `minAreaRect` sobre texto binarizado.
- Perspectiva: maior contorno quadrilátero (Canny + `approxPolyDP`) + `warpPerspective`; se a área for < 50% da imagem, não corrige.
- Limpeza: CLAHE, `fastNlMeansDenoising`, remoção de sombra por divisão pelo fundo estimado.
- Upscale: se a altura média de caractere estimada < 20 px, ampliar (INTER_CUBIC) até ~30 px.
- Duas saídas por página: `aligned` (original apenas rotacionado/retificado, usada em recortes e imagens do documento) e `normalized` (contrastada, usada só para leitura).
- Tamanho de folha: do PDF, via `page.get_size()` (pontos); de imagem, A4 com orientação pela proporção (spec `document-export`).
- pypdfium2 em vez de pdf2image/poppler: licença permissiva, sem dependência de sistema, rápido.

### D5. Layout e OCR primário: PaddleOCR PP-StructureV3
Entrega blocos tipados, ordem de leitura (inclusive colunas), estrutura de tabela e texto com confiança num único passe. Mapeamento de rótulos do modelo → tipos da spec em `pipeline/layout.py`. Complementos nossos:
- Colunas: agrupamento dos blocos de texto por faixas de x (histograma das bordas esquerdas); número de colunas por página.
- Alinhamento: comparação das margens esquerda/direita de cada linha do bloco com as margens do bloco (desvio < 2% da largura = alinhado naquele lado; ambos = justificado; centros iguais = centralizado).
- Tamanho relativo: altura mediana das letras do bloco ÷ altura mediana da página.
- Alternativas: Surya (licença restritiva); Docling (OCR fraco e pesado); LayoutParser (desatualizado).

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

### D12. Conjunto de teste de precisão
`backend/tests/fixtures/precision/` com pares imagem + gabarito (`.txt` com o texto e `.json` com ênfase, alinhamento e página de cada bloco): impresso, foto torta, tabela, duas colunas com figuras, capa com logotipo, manuscrito, PDF multipágina. Teste `@pytest.mark.precision` calcula CER/WER com `jiwer`, acerto de ênfase, e confere a paginação do DOCX/PDF gerado. Roda fora do ciclo rápido (é lento).

## Risks / Trade-offs

- [Modelos pesados em CPU estouram 40 s/página] → modelos carregados uma vez por worker; árbitro só em divergências; ênfase calculada só em palavras de texto; medir em `tests/perf`.
- [Detecção de negrito/itálico abaixo de 95%] → limiares calibrados no conjunto de teste; se não atingir, a spec é revista antes de seguir.
- [Texto transborda a página no Word] → redução de fonte por seção com verificação de páginas (D10).
- [LibreOffice aumenta a imagem Docker em ~500 MB] → aceito; instalar só `libreoffice-writer-nogui`.
- [HF Spaces hiberna e o 1º acesso demora ~1 min] → a tela de progresso fica em 0% com "Lendo seu documento…"; documentar Oracle Free como opção sempre ligada.
- [Erros correlacionados entre os dois OCRs] → completude + conferência humana cobrem; Tesseract como terceiro voto é evolução possível.
- [Manuscrito abaixo da meta] → meta de CER só para impresso; manuscrito medido e reportado, sem bloquear.
- [Disco cheio no plano grátis] → descarte em 1 h, limite de 50 páginas e 20 MB.
- [Abuso do serviço público] → 3 conversões ativas por IP.

## Migration Plan

Projeto novo: sem migração. Deploy inicial: `frontend` na Vercel com `NEXT_PUBLIC_API_URL`; `backend` como imagem Docker no HF Spaces. Rollback: voltar para a imagem/commit anterior em cada plataforma.

## Open Questions

- Versão exata do PP-StructureV3 / PaddleOCR-VL a fixar: decidir na implementação pelo melhor resultado no conjunto de teste em CPU ARM e x86.
- Limiares de negrito/itálico (D8): calibrar no conjunto de teste.
