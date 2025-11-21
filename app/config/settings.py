"""Configurações da aplicação usando Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas de variáveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://amorinha_user:amorinha_password@localhost:5432/amorinha_db",
        description="URL de conexão do banco de dados PostgreSQL",
    )

    # Security
    secret_key: str = Field(
        default="change-this-secret-key-in-production",
        description="Chave secreta para assinatura de tokens JWT",
    )
    algorithm: str = Field(default="HS256", description="Algoritmo de criptografia JWT")
    access_token_expire_minutes: int = Field(
        default=43200, description="Tempo de expiração do access token em minutos (30 dias)"
    )
    refresh_token_expire_days: int = Field(
        default=7, description="Tempo de expiração do refresh token em dias"
    )

    # Google AI
    google_api_key: str = Field(default="", description="API Key do Google Gemini")
    gemini_model: str = Field(
        default="gemini-2.5-flash", description="Modelo do Gemini para geração"
    )
    embedding_model: str = Field(
        default="models/embedding-001", description="Modelo para embeddings"
    )
    # Configurações de geração
    max_output_tokens: int = Field(
        default=15000, description="Número máximo de tokens na resposta (padrão: 8192)"
    )
    top_k: int = Field(
        default=55, description="Top K para sampling (padrão: 40)"
    )
    
    # Tavily Search
    tavily_api_key: str = Field(default="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", description="API Key do Tavily para busca web")

    # Storage
    storage_path: Path = Field(
        default=Path("./storage"), description="Diretório base de storage"
    )
    upload_dir: Path = Field(
        default=Path("./storage/documents"), description="Diretório para upload de arquivos"
    )
    export_dir: Path = Field(
        default=Path("./storage/exports"), description="Diretório para arquivos exportados"
    )
    max_upload_size_mb: int = Field(
        default=10, description="Tamanho máximo de upload em MB", ge=1, le=100
    )

    # Application
    debug: bool = Field(default=False, description="Modo debug")
    app_name: str = Field(default="Amorinha", description="Nome da aplicação")
    app_version: str = Field(default="0.1.0", description="Versão da aplicação")
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000"], description="Origens permitidas para CORS"
    )

    # Server
    host: str = Field(default="0.0.0.0", description="Host do servidor")
    port: int = Field(default=8000, description="Porta do servidor", ge=1, le=65535)
    workers: int = Field(default=1, description="Número de workers", ge=1, le=8)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | List[str] | None) -> List[str]:
        """Parse origins string separada por vírgulas em lista."""
        # Se for None ou string vazia, retornar default
        if v is None or (isinstance(v, str) and not v.strip()):
            return ["http://localhost:3000"]
        
        # Se for string, tentar parse como JSON primeiro, senão tratar como CSV
        if isinstance(v, str):
            v = v.strip()
            # Se começar com [ ou {, tentar parse JSON
            if v.startswith("[") or v.startswith("{"):
                try:
                    import json
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if origin]
                    elif isinstance(parsed, str):
                        return [parsed.strip()] if parsed.strip() else ["http://localhost:3000"]
                except (json.JSONDecodeError, ValueError):
                    # Se falhar, tratar como string simples
                    pass
            
            # Tratar como string separada por vírgulas
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            return origins if origins else ["http://localhost:3000"]
        
        # Se já for lista, retornar como está
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if origin]
        
        # Fallback para default
        return ["http://localhost:3000"]

    @property
    def max_upload_size_bytes(self) -> int:
        """Retorna tamanho máximo de upload em bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    def create_storage_dirs(self) -> None:
        """Cria diretórios de storage se não existirem."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        (self.storage_path / "temp").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Retorna instância singleton de Settings."""
    return Settings()


settings = get_settings()

