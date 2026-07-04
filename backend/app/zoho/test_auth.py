"""
zoho/test_auth.py
Quick smoke-test for the ZohoAuth module.

Run from the backend directory:
    python -m zoho.test_auth

What it does:
  1. Loads environment variables from .env
  2. Instantiates ZohoAuth
  3. Fetches an access token
  4. Prints a masked version (first 8 + last 6 chars) for security
  5. Calls get_access_token() a second time to verify cache hit (no network call)
"""

import logging
import sys
import time

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("zoho.test_auth")


def mask_token(token: str) -> str:
    """Show only first 8 and last 6 characters to avoid logging secrets."""
    if len(token) < 20:
        return "***"
    return f"{token[:8]}…{token[-6:]}"


def main() -> None:
    logger.info("=" * 55)
    logger.info("Zoho Auth — Smoke Test")
    logger.info("=" * 55)

    try:
        from zoho import ZohoAuth
        from zoho.exceptions import ZohoAuthError, ZohoTokenRefreshError
    except ImportError as exc:
        logger.error("Import failed: %s", exc)
        logger.error("Run this from the backend/ directory: python -m zoho.test_auth")
        sys.exit(1)

    # ── 1. Instantiate ────────────────────────────────────────────────────────
    logger.info("Instantiating ZohoAuth …")
    try:
        auth = ZohoAuth()
    except ZohoAuthError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    # ── 2. First call — should trigger a network refresh ──────────────────────
    logger.info("Fetching access token (1st call — expect network request) …")
    t0 = time.perf_counter()
    try:
        token1 = auth.get_access_token()
    except ZohoTokenRefreshError as exc:
        logger.error("Token refresh failed: %s", exc)
        sys.exit(1)
    elapsed1 = time.perf_counter() - t0

    logger.info("✅ Token received in %.2fs", elapsed1)
    logger.info("   Masked token  : %s", mask_token(token1))
    logger.info("   Expires at    : %s", time.strftime(
        "%Y-%m-%d %H:%M:%S", time.localtime(auth._cache.expires_at)
    ))

    # ── 3. Second call — should be instant (cache hit) ────────────────────────
    logger.info("Fetching access token (2nd call — expect cache hit) …")
    t1 = time.perf_counter()
    token2 = auth.get_access_token()
    elapsed2 = time.perf_counter() - t1

    assert token1 == token2, "Cache miss! Tokens differ — unexpected."
    logger.info("✅ Cache hit confirmed in %.4fs (no network call)", elapsed2)

    # ── 4. Verify auth_headers() shape ────────────────────────────────────────
    headers = auth.auth_headers()
    assert "Authorization" in headers, "Missing Authorization header"
    assert "X-com-zoho-store-organizationid" in headers, "Missing Org ID header"
    logger.info("✅ auth_headers() structure: %s", list(headers.keys()))

    logger.info("=" * 55)
    logger.info("All checks passed. ZohoAuth is working correctly.")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
