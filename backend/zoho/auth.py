"""
zoho/auth.py
Production-ready Zoho OAuth authentication class.

Usage:
    from zoho import ZohoAuth
    auth = ZohoAuth()
    token = auth.get_access_token()   # auto-refreshes when needed
"""

import logging
import time
import threading
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ZohoConfig
from .exceptions import ZohoAuthError, ZohoTokenRefreshError

logger = logging.getLogger(__name__)


# ── Token cache dataclass ─────────────────────────────────────────────────────

@dataclass
class _TokenCache:
    access_token: str = ""
    expires_at:   float = 0.0        # UNIX timestamp
    token_type:   str = "Bearer"

    def is_valid(self, buffer_seconds: int = 300) -> bool:
        """
        Returns True if the token exists and won't expire
        within the next `buffer_seconds` (default: 5 minutes).
        """
        return bool(self.access_token) and time.time() < (self.expires_at - buffer_seconds)


# ── Session factory ───────────────────────────────────────────────────────────

def _build_session(
    total_retries: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: tuple = (429, 500, 502, 503, 504),
) -> requests.Session:
    """
    Create a requests.Session with:
      - Connection pooling
      - Automatic retry with exponential back-off
      - Retries only on safe, idempotent status codes
    """
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,         # waits: 1s, 2s, 4s …
        status_forcelist=status_forcelist,
        allowed_methods=["POST"],              # token endpoint is POST
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ── ZohoAuth ─────────────────────────────────────────────────────────────────

class ZohoAuth:
    """
    Thread-safe Zoho OAuth token manager.

    - Uses the Refresh Token grant flow (no user login required).
    - Caches the access token in memory.
    - Auto-refreshes when the token is missing or within 5 minutes of expiry.
    - Uses a requests.Session with retry/back-off for resilience.

    Example:
        auth = ZohoAuth()
        headers = auth.auth_headers()     # ready-to-use dict for API calls
    """

    # How many seconds before expiry to proactively refresh (5 minutes)
    _REFRESH_BUFFER_SECONDS = 300
    # Default request timeout (connect, read) in seconds
    _TIMEOUT = (5, 15)

    def __init__(self, config: ZohoConfig | None = None):
        self._config  = config or ZohoConfig.load()
        self._cache   = _TokenCache()
        self._lock    = threading.Lock()      # prevents thundering herd on refresh
        self._session = _build_session()

        logger.info(
            "ZohoAuth initialized. accounts_url=%s org_id=%s",
            self._config.ACCOUNTS_URL,
            self._config.ORGANIZATION_ID,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_access_token(self) -> str:
        """
        Return a valid access token, refreshing silently if needed.
        Thread-safe — multiple workers can call this concurrently.
        """
        with self._lock:
            if not self._cache.is_valid(self._REFRESH_BUFFER_SECONDS):
                self._refresh()
            return self._cache.access_token

    def auth_headers(self) -> dict:
        """
        Return the complete HTTP headers dict needed for Zoho Commerce API calls.
        Includes Authorization and organisation ID.
        """
        return {
            "Authorization":                   f"Zoho-oauthtoken {self.get_access_token()}",
            "X-com-zoho-store-organizationid": self._config.ORGANIZATION_ID,
            "Content-Type":                    "application/json",
        }

    def invalidate(self) -> None:
        """
        Force-expire the cached token.
        The next call to get_access_token() will trigger a refresh.
        Useful after a 401 response from the Commerce API.
        """
        with self._lock:
            self._cache.access_token = ""
            self._cache.expires_at   = 0.0
        logger.debug("Token cache invalidated.")

    # ── Private ───────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        """
        POST to Zoho token endpoint and update the in-memory cache.
        Must be called while holding self._lock.
        """
        url = self._config.token_refresh_url
        payload = {
            "refresh_token": self._config.REFRESH_TOKEN,
            "client_id":     self._config.CLIENT_ID,
            "client_secret": self._config.CLIENT_SECRET,
            "grant_type":    "refresh_token",
        }

        logger.info("Refreshing Zoho access token from %s …", url)

        try:
            response = self._session.post(
                url,
                data=payload,
                timeout=self._TIMEOUT,
            )
        except requests.exceptions.Timeout as exc:
            raise ZohoTokenRefreshError(
                f"Token refresh timed out after {self._TIMEOUT[1]}s"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise ZohoTokenRefreshError(
                f"Network error reaching Zoho token endpoint: {exc}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ZohoTokenRefreshError(
                f"Unexpected error during token refresh: {exc}"
            ) from exc

        # ── HTTP-level error ──────────────────────────────────────────────
        if not response.ok:
            raise ZohoTokenRefreshError(
                "Zoho token endpoint returned an error",
                status_code=response.status_code,
                body=response.text[:500],
            )

        # ── Parse response ────────────────────────────────────────────────
        try:
            data = response.json()
        except ValueError as exc:
            raise ZohoTokenRefreshError(
                f"Token response is not valid JSON: {response.text[:200]}"
            ) from exc

        access_token = data.get("access_token", "")
        expires_in   = int(data.get("expires_in", 3600))
        token_type   = data.get("token_type", "Bearer")

        if not access_token:
            # Zoho returns {"error": "invalid_code"} etc.
            error = data.get("error", "unknown_error")
            raise ZohoTokenRefreshError(
                f"Zoho did not return an access_token. error='{error}'",
                body=str(data),
            )

        # ── Update cache ──────────────────────────────────────────────────
        self._cache.access_token = access_token
        self._cache.expires_at   = time.time() + expires_in
        self._cache.token_type   = token_type

        logger.info(
            "Access token refreshed. expires_in=%ds token_type=%s",
            expires_in,
            token_type,
        )
