from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://workout:workout@db:5432/workout_tracker"
    SECRET_KEY: str = "change-me-in-production"

    OIDC_ISSUER_URL: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = ""

    OLLAMA_URL: str = "http://10.10.10.55:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    ANTHROPIC_API_KEY: Optional[str] = None

    ALERT_WEBHOOK_URL: Optional[str] = None
    SCRAPER_CRON: str = "0 5 * * *"
    BASE_URL: str = "http://localhost:8000"

    BLOG_URL: str = "https://www.fullrangepvd.com/blog"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
