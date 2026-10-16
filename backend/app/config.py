"""Configuração do backend, lida de variáveis de ambiente (prefixo ITT_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ITT_", env_file=".env", extra="ignore")

    # Origens do frontend que podem chamar a API (CORS). Lista JSON no ambiente.
    cors_origins: list[str] = ["http://localhost:3000"]
    redis_url: str = "redis://localhost:6379/0"
    # Pasta onde ficam os arquivos de cada conversão (apagados em até 1 h).
    data_dir: str = "/data/jobs"
    # Limites da spec file-upload e job-processing.
    max_upload_bytes: int = 20 * 1024 * 1024
    max_active_jobs: int = 3
    # Só ligue se a API estiver atrás de um proxy confiável que preencha X-Forwarded-For;
    # do contrário, qualquer um forjaria o cabeçalho para driblar o limite por endereço.
    trust_forwarded_for: bool = False
    # Árbitro PaddleOCR-VL nas divergências que sobram (design D7). Pesado em CPU: desligado.
    arbiter_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
