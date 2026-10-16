"""Aplicação FastAPI: rotas HTTP consumidas pelo frontend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.jobs import router as jobs_router
from app.config import get_settings
from app.errors import ApiError, api_error_handler


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="image-to-text API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
        # O navegador só lê o nome do arquivo baixado se o cabeçalho for exposto.
        expose_headers=["Content-Disposition"],
    )

    application.add_exception_handler(ApiError, api_error_handler)
    application.include_router(jobs_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
