# Imagem do backend (api e worker usam a mesma imagem, com comandos diferentes).
# Modelos de OCR são baixados no build (a 1ª conversão não espera download).
FROM python:3.12-slim

# Bibliotecas de sistema do OpenCV (libgl1, libglib2.0-0) e do PaddlePaddle (libgomp1);
# LibreOffice sem interface para Word → PDF (8.3) e fontes Liberation (medidas iguais às da
# Times New Roman/Arial usadas no Word).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
        libreoffice-writer-nogui fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

WORKDIR /srv

# Dependências primeiro (camada reaproveitada enquanto o lockfile não mudar).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/jobs \
    && chown -R app:app /data
USER app

# Modelos de orientação (4.2), layout (5.1), dos dois leitores (6.1, 6.2) e de tabelas (7.3), baixados para o cache
# do usuário app. O árbitro (6.5) fica desligado e não é baixado: com ITT_ARBITER_ENABLED=true,
# o modelo PaddleOCR-VL é baixado na primeira divergência.
RUN python -c "from app.pipeline.preprocess import _orientation_model; _orientation_model()" \
    && python -c "from app.pipeline.layout import _layout_model; _layout_model()" \
    && python -c "from app.pipeline.ocr_paddle import _ocr, _recognizer; _ocr(); _recognizer()" \
    && python -c "from app.pipeline.ocr_doctr import _models; _models()" \
    && python -c "from app.pipeline.tables import CELL_MODELS, _cell_model, _classifier; _classifier(); [_cell_model(m) for m in CELL_MODELS.values()]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
