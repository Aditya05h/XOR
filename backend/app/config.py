from pathlib import Path
from typing import Literal

from pydantic import SecretStr, BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Principal(BaseModel):
    role: Literal['operator', 'tenant']
    tenant_id: Literal['T1', 'T2', 'T3'] | None = None

    @model_validator(mode='after')
    def tenant_required(self):
        if self.role == 'tenant' and self.tenant_id is None:
            raise ValueError('tenant identity requires tenant_id')
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AO02_",
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="forbid",
    )
    app_name: str = "XOR Capacity Observatory"
    database_path: Path = Path(__file__).resolve().parents[1] / 'incidents.sqlite3'
    auth_tokens: dict[str, Principal] = {}
    environment: Literal["development", "test", "production"] = "development"
    llm_provider: Literal["deterministic", "openai", "gemini"] = "deterministic"
    openai_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
