from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CACHE_SERVICE_", env_file=".env")

    database_url: str = "sqlite:///./cache.db"
    transformer_delay_seconds: float = 0.0
