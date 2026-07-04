"""Zoho Commerce custom field fetcher with in-memory caching.

Fetches all product custom fields from Zoho Commerce so we can resolve
real customfield_id values instead of relying on label strings.
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


class ZohoCustomFieldService:
    """Fetch and cache Zoho Commerce product custom fields."""

    def __init__(self, auth: Optional[ZohoAuth] = None) -> None:
        self._auth: Optional[ZohoAuth] = auth
        self._cached_at: float = 0.0
        self._cache: Optional[List[Dict[str, Any]]] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def get_custom_fields(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Return a flat list of Zoho product custom fields, using cache if fresh."""
        if not force_refresh and self._cache is not None and (time.time() - self._cached_at) < _CACHE_TTL_SECONDS:
            return self._cache

        fields = self._fetch_custom_fields()
        self._cache = fields
        self._cached_at = time.time()
        logger.info("Fetched %d Zoho product custom fields.", len(fields))
        return fields

    def find_field_id(self, label: str) -> Optional[str]:
        """Find a custom field's ID by its label (case-insensitive)."""
        label_lower = label.strip().lower()
        for f in self.get_custom_fields():
            if f.get("label", "").strip().lower() == label_lower:
                return str(f.get("customfield_id", ""))
        return None

    def invalidate_cache(self) -> None:
        self._cache = None
        self._cached_at = 0.0

    # ── Private ───────────────────────────────────────────────────────────────

    def _fetch_custom_fields(self) -> List[Dict[str, Any]]:
        """Fetch custom field definitions from Zoho Commerce."""
        headers = self._get_auth_headers()
        all_fields: List[Dict[str, Any]] = []

        # Zoho Commerce endpoint for custom fields definitions
        # Tries multiple common endpoint patterns
        endpoints = [
            f"{settings.zoho_api_domain}/store/api/v1/settings/customfields",
            f"{settings.zoho_api_domain}/store/api/v1/products/customfields",
            f"{settings.zoho_api_domain}/store/api/v1/customfields?entity=products",
        ]

        for endpoint in endpoints:
            try:
                resp = requests.get(endpoint, headers=headers, timeout=15)
                if resp.status_code == 401:
                    self._get_auth().invalidate()
                    headers = self._get_auth_headers()
                    resp = requests.get(endpoint, headers=headers, timeout=15)

                if not resp.ok:
                    logger.debug("Custom fields endpoint %s returned %s", endpoint, resp.status_code)
                    continue

                data = resp.json()
                payload = data.get("payload", data)

                # Try common response keys
                for key in ("custom_fields", "customfields", "fields", "data"):
                    items = payload.get(key, [])
                    if items:
                        all_fields.extend(items)
                        logger.info("Found %d custom fields from endpoint %s", len(items), endpoint)
                        return all_fields

            except requests.RequestException as exc:
                logger.debug("Error fetching custom fields from %s: %s", endpoint, exc)
                continue

        logger.warning("Could not fetch custom fields from any endpoint. Will fall back to label-based matching.")
        return all_fields

    def _get_auth_headers(self) -> Dict[str, str]:
        try:
            return self._get_auth().auth_headers()
        except (ZohoAuthError, ZohoTokenRefreshError) as exc:
            raise RuntimeError(f"Zoho authentication failed: {exc}") from exc

    def _get_auth(self) -> ZohoAuth:
        if self._auth is None:
            self._auth = ZohoAuth()
        return self._auth


# Singleton used by routes and publisher
zoho_custom_field_service = ZohoCustomFieldService()
