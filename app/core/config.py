from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    secret_key: str = "dev-secret-key-change-me-before-any-real-deployment"
    access_token_expire_minutes: int = 60


settings = Settings()
