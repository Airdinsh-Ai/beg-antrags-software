import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    secret_key: str = "dev-secret-key-change-me-before-any-real-deployment"
    access_token_expire_minutes: int = 60
    openai_api_key: str = ""
    upload_verzeichnis: str = "uploads"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


settings = Settings()

# Der Langfuse-OpenAI-Wrapper (langfuse.openai, siehe app/llm/client.py) liest
# seine Zugangsdaten aus os.environ, nicht aus diesem Settings-Objekt -
# pydantic-settings laedt .env nur hierhin, nicht in die Prozessumgebung.
# Hier einmalig nachziehen, damit der Drop-in-Wrapper ohne Zusatzcode
# funktioniert (Systemarchitektur Abschnitt 5).
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
