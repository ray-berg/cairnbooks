from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    DATABASE_URL: str = "postgresql+asyncpg://cairn:cairn@localhost:5432/cairnbooks"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
