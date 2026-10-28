from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AO02_",
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="forbid",
    )
    app_name: str = "XOR Capacity Observatory"
    environment: Literal["development", "test", "production"] = "development"
    llm_provider: Literal["deterministic", "openai", "gemini"] = "deterministic"
    openai_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
