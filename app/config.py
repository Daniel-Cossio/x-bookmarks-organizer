"""Configuración del sistema y variables de entorno."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Cargar .env.local si existe (prioridad de desarrollo), sino .env
ROOT_DIR = Path(__file__).resolve().parent.parent
env_local = ROOT_DIR / ".env.local"
env_default = ROOT_DIR / ".env"

if env_local.exists():
    load_dotenv(dotenv_path=env_local)
elif env_default.exists():
    load_dotenv(dotenv_path=env_default)


class Settings:
    def __init__(self):
        self.root_dir: Path = ROOT_DIR
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8085"))
        self.debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

        # Base de datos
        db_env = os.getenv("DB_PATH", "data/bookmarks.db")
        self.db_path: Path = self.root_dir / db_env if not Path(db_env).is_absolute() else Path(db_env)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Twitter / X sesión
        self.twitter_auth_token: str = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
        self.twitter_ct0: str = os.getenv("TWITTER_CT0", "").strip()

        # IA
        self.ai_provider: str = os.getenv("AI_PROVIDER", "heuristic").lower().strip()
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()


settings = Settings()
