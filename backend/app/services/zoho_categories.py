"""Zoho Commerce category fetcher with in-memory caching.

Fetches the full category tree from the Zoho Commerce Admin API, builds a
tree structure for the frontend dropdown, and caches results for 10 minutes
so we don't hammer Zoho on every generate request.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.config import settings
from app.models.product import CategoryNode, CategoryTreeResponse
from app.zoho import ZohoAuth
from app.zoho.exceptions import ZohoAuthError, ZohoTokenRefreshError

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600  # 10 minutes


class ZohoCategoryService:
    """Fetch and cache Zoho Commerce categories, build a tree for the UI."""

    def __init__(self, auth: Optional[ZohoAuth] = None) -> None:
        self._auth: Optional[ZohoAuth] = auth
        self._cached_at: float = 0.0
        self._cache: Optional[CategoryTreeResponse] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def get_categories(self, force_refresh: bool = False) -> CategoryTreeResponse:
        """Return the category tree, using cache if still fresh."""

        if not force_refresh and self._cache and (time.time() - self._cached_at) < _CACHE_TTL_SECONDS:
            logger.debug("Returning cached Zoho categories (age=%.0fs)", time.time() - self._cached_at)
            result = self._cache.model_copy()
            result.cached = True
            return result

        flat_nodes = self._fetch_all_categories()
        tree = self._build_tree(flat_nodes)

        response = CategoryTreeResponse(
            tree=tree,
            flat=flat_nodes,
            total=len(flat_nodes),
            cached=False,
        )
        self._cache = response
        self._cached_at = time.time()
        logger.info("Fetched %d Zoho categories and built category tree.", len(flat_nodes))
        return response

    def invalidate_cache(self) -> None:
        """Force the next call to re-fetch from Zoho."""
        self._cache = None
        self._cached_at = 0.0

    # ── Private ───────────────────────────────────────────────────────────────

    def _fetch_all_categories(self) -> List[CategoryNode]:
        """Paginate through all Zoho Commerce categories and return flat list."""

        api_url = f"{settings.zoho_api_domain}/store/api/v1/categories"
        headers = self._get_auth_headers()
        all_items: List[Dict[str, Any]] = []
        page = 1

        while True:
            params = {"page": page, "per_page": 200}
            try:
                resp = requests.get(api_url, headers=headers, params=params, timeout=15)
            except requests.RequestException as exc:
                raise RuntimeError(f"Network error fetching Zoho categories: {exc}") from exc

            if resp.status_code == 401:
                # Token expired — invalidate and retry once
                self._get_auth().invalidate()
                headers = self._get_auth_headers()
                resp = requests.get(api_url, headers=headers, params=params, timeout=15)

            if not resp.ok:
                raise RuntimeError(
                    f"Zoho categories API returned {resp.status_code}: {resp.text[:300]}"
                )

            data = resp.json()
            # Zoho wraps in payload.categories or directly in categories
            payload = data.get("payload", data)
            items = payload.get("categories", [])

            if not items:
                break

            all_items.extend(items)

            # Check pagination
            pagination = payload.get("pagination", {})
            has_more = pagination.get("has_more_page", False)
            if not has_more:
                break
            page += 1

        return [self._parse_node(item) for item in all_items]

    @staticmethod
    def _parse_node(item: Dict[str, Any]) -> CategoryNode:
        """Convert a raw Zoho category dict to a CategoryNode."""
        return CategoryNode(
            category_id=str(item.get("category_id", "")),
            name=str(item.get("name", "")),
            parent_category_id=str(item.get("parent_category_id", "0")),
            depth=int(item.get("depth", 0)),
            visibility=bool(item.get("visibility", True)),
            children=[],
        )

    @staticmethod
    def _build_tree(flat: List[CategoryNode]) -> List[CategoryNode]:
        """Build a nested tree from a flat category list using parent_category_id."""

        node_map: Dict[str, CategoryNode] = {n.category_id: n for n in flat}
        roots: List[CategoryNode] = []

        for node in flat:
            parent_id = node.parent_category_id
            if parent_id in ("0", "-1", "", None) or parent_id not in node_map:
                roots.append(node)
            else:
                node_map[parent_id].children.append(node)

        # Sort roots and children by name for consistent display
        roots.sort(key=lambda n: n.name)
        for node in node_map.values():
            node.children.sort(key=lambda n: n.name)

        return roots

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


# Singleton used by routes
zoho_category_service = ZohoCategoryService()
