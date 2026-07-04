"""Application settings loaded from environment variables.

The settings object centralizes all runtime configuration so services do not
read environment variables directly. This keeps modules testable and follows
the dependency-inversion principle: business logic depends on a typed settings
contract instead of the process environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


def _bool_env(key: str, default: bool) -> bool:
    """Return a boolean value from common string environment forms."""

    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_env(key: str, default: str) -> Tuple[str, ...]:
    """Return a tuple from a comma-separated environment variable."""

    value = os.getenv(key, default)
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    """Typed runtime settings for the Yantronix backend."""

    app_name: str = os.getenv("APP_NAME", "Yantronix Scraper API")
    allowed_origins: Tuple[str, ...] = _csv_env("ALLOWED_ORIGINS", "http://localhost:3000")

    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    mongo_db_name: str = os.getenv("MONGO_DB_NAME", "scraper_db")

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
    gemini_max_output_tokens: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "12000"))
    max_raw_text_chars: int = int(os.getenv("MAX_RAW_TEXT_CHARS", "12000"))

    scrape_timeout_seconds: int = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "15"))
    min_scraped_text_chars: int = int(os.getenv("MIN_SCRAPED_TEXT_CHARS", "100"))

    rate_limit_extract_per_minute: int = int(os.getenv("RATE_LIMIT_EXTRACT_PER_MINUTE", "10"))
    rate_limit_generate_per_minute: int = int(os.getenv("RATE_LIMIT_GENERATE_PER_MINUTE", "5"))
    rate_limit_publish_per_minute: int = int(os.getenv("RATE_LIMIT_PUBLISH_PER_MINUTE", "3"))
    rate_limit_ai_calls_per_hour: int = int(os.getenv("RATE_LIMIT_AI_CALLS_PER_HOUR", "20"))

    test_mode: bool = _bool_env("TEST_MODE", True)
    zoho_api_domain: str = os.getenv("ZOHO_API_DOMAIN", "https://commerce.zoho.in").rstrip("/")
    zoho_store_domain: str = os.getenv("ZOHO_STORE_DOMAIN", "")


settings = Settings()
