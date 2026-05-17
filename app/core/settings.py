import os
from pathlib import Path

from pydantic_settings import BaseSettings

APP_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = {"env_prefix": "AGENT_", "env_file": ".env", "extra": "ignore"}

    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "tencent/hy3-preview:free"

    db_file: str = "./sessions.db"

    @property
    def db_path(self) -> str:
        expanded = Path(os.path.expanduser(self.db_file))
        if expanded.is_absolute():
            return str(expanded.resolve())
        return str((APP_ROOT / expanded).resolve())

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    def ensure_db_dir(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)


settings = Settings()
