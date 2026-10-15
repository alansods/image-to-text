"""Configuração do backend, lida de variáveis de ambiente (prefixo ITT_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ITT_", env_file=".env", extra="ignore")

    # Origens do frontend que podem chamar a API (CORS). Separadas por vírgula no ambiente.
    cors_origins: list[str] = ["http://localhost:3000"]
    redis_url: str = "redis://localhost:6379/0"
    # Pasta onde ficam os arquivos de cada conversão (apagados em até 1 h).
    data_dir: str = "/data/jobs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
