"""
Munim — Application Configuration
===================================
All settings are loaded from environment variables via Pydantic Settings.
Never hardcode secrets. Never commit .env files.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    FILE_DELETE_AFTER_DAYS: int = 30
    MAX_FILE_SIZE_MB: int = 50
    APP_URL: str = "http://localhost:3000"  # Set to your public URL when deployed

    # Database (Neon PostgreSQL)
    DATABASE_URL: str

    # LLM — Google Gemini
    GOOGLE_API_KEY: str = ""
    # LLM — Groq (free: 14,400 req/day) — console.groq.com
    GROQ_API_KEY: str = ""
    # LLM — Mistral AI (free tier) — console.mistral.ai
    MISTRAL_API_KEY: str = ""
    # LLM — Together AI (free credits) — api.together.ai
    TOGETHER_API_KEY: str = ""
    # LLM — OpenRouter (free :free models) — openrouter.ai
    OPENROUTER_API_KEY: str = ""

    # Celery + Redis (Upstash)
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    USE_CELERY: str = "false"   # Set to "true" only when a Celery worker is running

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "munim-uploads"
    R2_PUBLIC_URL: str = ""

    # WhatsApp — Meta Business API
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""  # Meta App Secret — used for HMAC signature verification
    WHATSAPP_BOT_PHONE: str = ""   # Bot's actual phone number digits (no +), e.g. 919876543210

    # WhatsApp — Twilio (alternative, easier for testing)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"  # Twilio sandbox number

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    NEXTAUTH_SECRET: str = ""

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # Monitoring
    SENTRY_DSN: str = ""

    # Email
    RESEND_API_KEY: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
