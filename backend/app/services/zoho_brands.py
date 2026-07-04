"""Zoho Commerce brand fetcher with in-memory caching.

Fetches all brands from Zoho Commerce, caches them, and provides
brand matching logic to find the best match for a product.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from app.core.config import settings
from app.zoho import ZohoAuth
from app.zoho.exceptions import ZohoAuthError, ZohoTokenRefreshError

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600  # 10 minutes

GENERIC_BRAND = {"brand_id": "", "name": "Generic"}


class ZohoBrandService:
    """Fetch and cache Zoho Commerce brands, with simple fuzzy-match lookup."""

    def __init__(self, auth: Optional[ZohoAuth] = None) -> None:
        self._auth: Optional[ZohoAuth] = auth
        self._cached_at: float = 0.0
        self._cache: Optional[List[Dict[str, Any]]] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def get_brands(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Return a flat list of Zoho brands, using cache if still fresh."""

        if not force_refresh and self._cache is not None and (time.time() - self._cached_at) < _CACHE_TTL_SECONDS:
            logger.debug("Returning cached Zoho brands (age=%.0fs)", time.time() - self._cached_at)
            return self._cache

        brands = self._fetch_all_brands()
        self._cache = brands
        self._cached_at = time.time()
        logger.info("Fetched %d Zoho brands.", len(brands))
        return brands

    def find_best_match(self, ai_brand: str) -> Dict[str, Any]:
        """Match AI-extracted brand to a Zoho brand.

        Match strategy:
        1. Exact name match (case-insensitive)
        2. Partial name match (brand contains ai_brand or vice versa)
        3. Fallback: Generic
        """
        if not ai_brand or not ai_brand.strip():
            return GENERIC_BRAND

        brands = self.get_brands()
        ai_brand_lower = ai_brand.strip().lower()

        # 1. Exact match
        for b in brands:
            if b.get("name", "").lower() == ai_brand_lower:
                logger.info("Exact brand match found: %s -> %s", ai_brand, b["name"])
                return b

        # 2. Partial match – brand name contains the AI brand string or vice versa
        for b in brands:
            b_name = b.get("name", "").lower()
            if ai_brand_lower in b_name or b_name in ai_brand_lower:
                logger.info("Partial brand match found: %s -> %s", ai_brand, b["name"])
                return b

        logger.info("No brand match found for '%s', falling back to Generic.", ai_brand)
        return GENERIC_BRAND

    def invalidate_cache(self) -> None:
        """Force the next call to re-fetch from Zoho."""
        self._cache = None
        self._cached_at = 0.0

    # ── Private ───────────────────────────────────────────────────────────────

    def _fetch_all_brands(self) -> List[Dict[str, Any]]:
        """Paginate through all Zoho Commerce brands and return flat list."""

        api_url = f"{settings.zoho_api_domain}/store/api/v1/brands"
        headers = self._get_auth_headers()
        all_items: List[Dict[str, Any]] = []
        page = 1

        while True:
            params = {"page": page, "per_page": 200}
            try:
                resp = requests.get(api_url, headers=headers, params=params, timeout=15)
            except requests.RequestException as exc:
                raise RuntimeError(f"Network error fetching Zoho brands: {exc}") from exc

            if resp.status_code == 401:
                self._get_auth().invalidate()
                headers = self._get_auth_headers()
                resp = requests.get(api_url, headers=headers, params=params, timeout=15)

            if not resp.ok:
                logger.warning(
                    "Zoho brands API returned %s: %s. Using empty brand list.",
                    resp.status_code, resp.text[:200]
                )
                break

            data = resp.json()
            payload = data.get("payload", data)
            items = payload.get("brands", [])

            if not items:
                break

            all_items.extend(items)

            pagination = payload.get("pagination", {})
            has_more = pagination.get("has_more_page", False)
            if not has_more:
                break
            page += 1

        return all_items

    def _get_auth_headers(self) -> Dict[str, str]:
        """Return Zoho auth headers, creating ZohoAuth lazily."""
        try:
            return self._get_auth().auth_headers()
        except (ZohoAuthError, ZohoTokenRefreshError) as exc:
            raise RuntimeError(f"Zoho authentication failed: {exc}") from exc

    def _get_auth(self) -> ZohoAuth:
        if self._auth is None:
            self._auth = ZohoAuth()
        return self._auth


# Singleton used by routes and publisher
zoho_brand_service = ZohoBrandService()
