"""
zoho/config.py
Loads and validates all Zoho credentials from environment / .env file.
Import this once at startup — raises ZohoAuthError immediately if anything
is missing so you find out at boot, not mid-request.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from .exceptions import ZohoAuthError

# Walk up from this file to find the .env at the project root
_HERE = Path(__file__).resolve().parent          # backend/zoho/
_ENV  = _HERE.parent.parent / ".env"             # project root/.env
load_dotenv(_ENV)


def _require(key: str) -> str:
    """Return env var value or raise ZohoAuthError."""
    value = os.getenv(key, "").strip()
    if not value:
        raise ZohoAuthError(
            f"Missing required environment variable: {key}. "
            f"Add it to your .env file."
        )
    return value


class ZohoConfig:
    """All Zoho credentials, loaded from environment variables."""

    # ── OAuth credentials ──────────────────────────────────────────────────
    CLIENT_ID:       str = ""
    CLIENT_SECRET:   str = ""
    REFRESH_TOKEN:   str = ""

    # ── Organisation ──────────────────────────────────────────────────────
    ORGANIZATION_ID: str = ""

    # ── Endpoints ─────────────────────────────────────────────────────────
    # Accounts URL: used for token refresh calls
    ACCOUNTS_URL:    str = ""
    # API Domain: used for Commerce API calls (set by Zoho in token response)
    API_DOMAIN:      str = ""

    @classmethod
    def load(cls) -> "ZohoConfig":
        """
        Load and validate all required credentials.
        Returns a fully-populated ZohoConfig instance.
        """
        cfg = cls()
        cfg.CLIENT_ID       = _require("ZOHO_CLIENT_ID")
        cfg.CLIENT_SECRET   = _require("ZOHO_CLIENT_SECRET")
        cfg.REFRESH_TOKEN   = _require("ZOHO_REFRESH_TOKEN")
        cfg.ORGANIZATION_ID = _require("ZOHO_ORGANIZATION_ID")
        cfg.ACCOUNTS_URL    = os.getenv(
            "ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in"
        ).rstrip("/")
        cfg.API_DOMAIN      = os.getenv(
            "ZOHO_API_DOMAIN", "https://www.zohoapis.in"
        ).rstrip("/")
        return cfg

    @property
    def token_refresh_url(self) -> str:
        return f"{self.ACCOUNTS_URL}/oauth/v2/token"
