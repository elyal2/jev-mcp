"""Configuración tipada del servidor, leída del entorno / .env.

El servidor MCP corre fuera del sandbox de la app, así que aquí SÍ se pueden
leer variables de entorno y ficheros locales, a diferencia de las skills.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes del servidor Jev MCP.

    La clave se acepta bajo dos nombres por compatibilidad: JEV_API_KEY
    (wrappers de terceros) y TYPESAFE_API_KEY (oficial). El validador
    resuelve el primero no vacío.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jev_api_key: str = Field(default="", alias="JEV_API_KEY")
    typesafe_api_key: str = Field(default="", alias="TYPESAFE_API_KEY")

    base_url: str = Field(default="https://api.typesafe.ai/v1/systemone", alias="JEV_BASE_URL")
    model: str = Field(default="jev-latest", alias="JEV_MODEL")
    timeout: float = Field(default=30.0, alias="JEV_TIMEOUT")

    transport: str = Field(default="stdio", alias="JEV_TRANSPORT")
    http_host: str = Field(default="127.0.0.1", alias="JEV_HTTP_HOST")
    http_port: int = Field(default=8787, alias="JEV_HTTP_PORT")

    log_level: str = Field(default="INFO", alias="JEV_LOG_LEVEL")

    retry_max_attempts: int = Field(default=5, alias="JEV_RETRY_MAX_ATTEMPTS")
    retry_base_delay: float = Field(default=2.0, alias="JEV_RETRY_BASE_DELAY")
    retry_cap_delay: float = Field(default=32.0, alias="JEV_RETRY_CAP_DELAY")

    @property
    def api_key(self) -> str:
        """Clave efectiva: JEV_API_KEY tiene prioridad, luego TYPESAFE_API_KEY."""
        return (self.jev_api_key or self.typesafe_api_key).strip()

    def require_key(self) -> str:
        key = self.api_key
        if not key:
            raise RuntimeError(
                "Falta la clave de API. Define JEV_API_KEY o TYPESAFE_API_KEY "
                "en el entorno o en el fichero .env del servidor."
            )
        return key


settings = Settings()
