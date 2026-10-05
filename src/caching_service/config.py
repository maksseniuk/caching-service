"""Service configuration, read from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CACHE_SERVICE_", env_file=".env")

    database_url: str = "sqlite:///./cache.db"
    # The transformer stands in for a slow external service; a non-zero delay
    # makes the effect of caching visible when exercising the API by hand.
    transformer_delay_seconds: float = 0.0
