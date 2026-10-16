# Imagem do backend (api e worker usam a mesma imagem, com comandos diferentes).
# Modelos de OCR são baixados no build (a 1ª conversão não espera download); LibreOffice entra na 8.3.
FROM python:3.12-slim

# Bibliotecas de sistema do OpenCV (libgl1, libglib2.0-0) e do PaddlePaddle (libgomp1).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
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

# Modelo de orientação de página (task 4.2), baixado para o cache do usuário app.
RUN python -c "from app.pipeline.preprocess import _orientation_model; _orientation_model()"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
