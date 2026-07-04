"""Zoho Commerce payload builder and publisher."""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from app.core.config import settings
from app.zoho import ZohoAuth
from app.zoho.exceptions import ZohoAuthError, ZohoTokenRefreshError

logger = logging.getLogger(__name__)


class HtmlSanitizer:
    """Minimal HTML allowlist sanitizer for AI-generated descriptions."""

    ALLOWED_TAGS = {
        "p", "strong", "em", "ul", "ol", "li", "section", "h2", "h3", "table", "thead", "tbody",
        "tr", "th", "td", "pre", "code", "br", "span",
    }
    ALLOWED_ATTRS = {"style", "border"}

    def sanitize(self, html: str) -> str:
        """Strip dangerous tags and event-handler attributes from generated HTML."""

        soup = BeautifulSoup(html or "", "html.parser")
        for tag in list(soup.find_all(True)):
            if tag.name not in self.ALLOWED_TAGS:
                tag.unwrap()
                continue
            for attr in list(tag.attrs):
                if attr not in self.ALLOWED_ATTRS or attr.lower().startswith("on"):
                    del tag.attrs[attr]
        return str(soup)


class ZohoPayloadBuilder:
    """Map validated AI products into Zoho Commerce product payloads."""

    def __init__(self, sanitizer: Optional[HtmlSanitizer] = None) -> None:
        self._sanitizer = sanitizer or HtmlSanitizer()

    def build(self, ai_product: Dict[str, Any], category_id: Optional[str] = None, source_url: str = "", generated_sku: str = "", brand_name: str = "", brand_id: str = "") -> Dict[str, Any]:
        """Return a Zoho Commerce product payload from an AI product dictionary."""

        name = ai_product.get("product_title", "Unnamed Product")
        dims = self._dimensions(ai_product)
        rate = self._selling_price(ai_product)
        payload: Dict[str, Any] = {
            "name": name,
            "url": self._slugify(name),
            "variant_type": "inventory",
            "show_in_storefront": True,
            "is_returnable": False,
            "is_featured": False,
            "unit": "Nos",
            "brand": brand_name or ai_product.get("brand", "") or "Generic",
            "product_short_description": self._sanitizer.sanitize(ai_product.get("short_description_html") or ai_product.get("seo_description", "")),
            "product_description": self._sanitizer.sanitize(ai_product.get("long_description_html", "")),
            "seo_title": ai_product.get("seo_title", "")[:70],
            "seo_description": ai_product.get("meta_description", "")[:160],
            "seo_keyword": self._seo_keywords(ai_product),
            "tags": self._tags(ai_product),
            "variants": [
                {
                    "rate": rate,
                    "label_rate": self._label_rate(ai_product, rate),
                    "sku": generated_sku or ai_product.get("sku", ""),
                    "initial_stock": "0",
                    "reorder_level": "5",
                    "status": "active",
                    "hsn_or_sac": ai_product.get("hsn_code", ""),
                    "ean": "",
                    "upc": "",
                    "isbn": "",
                    "part_number": "",
                    "custom_fields": self._build_custom_fields(source_url),
                    "package_details": {
                        "weight": str(ai_product.get("weight_kg", "")),
                        "height": dims["H"],
                        "length": dims["L"],
                        "width": dims["W"],
                    },
                    "custom_fields": [],
                }
            ],
        }

        # Attach category if provided
        if category_id:
            payload["category_id"] = category_id

        return payload

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-{2,}", "-", text)
        return text[:80]

    @staticmethod
    def _tags(ai_product: Dict[str, Any]) -> List[str]:
        tags = ai_product.get("tags", [])
        if isinstance(tags, list):
            return [str(tag) for tag in tags]
        if isinstance(tags, str):
            return [tag.strip() for tag in tags.split(",") if tag.strip()]
        return []

    @staticmethod
    def _seo_keywords(ai_product: Dict[str, Any]) -> str:
        keywords = ai_product.get("seo_keywords", [])
        if isinstance(keywords, list):
            return ", ".join(str(keyword) for keyword in keywords)
        if isinstance(keywords, dict):
            flattened: List[str] = []
            for group in keywords.values():
                if isinstance(group, list):
                    flattened.extend(str(keyword) for keyword in group)
            return ", ".join(flattened)
        return str(keywords)

    @staticmethod
    def _selling_price(ai_product: Dict[str, Any]) -> str:
        price = ai_product.get("selling_price", {})
        if isinstance(price, dict):
            value = price.get("final_selling_price") or price.get("after_margin") or price.get("after_gst") or price.get("vendor_base_price") or price.get("quartz_base_price") or 0
            return str(value)
        return str(price or 0)

    @staticmethod
    def _label_rate(ai_product: Dict[str, Any], rate: str) -> str:
        """Retail price = selling price + 5-15% (random), always >= selling price."""
        rate_float = float(rate) if rate else 0.0
        if rate_float <= 0:
            return rate
        # Add a random 5-15% markup for retail (MRP)
        markup = random.uniform(0.05, 0.15)
        retail = round(rate_float * (1 + markup), 2)
        return str(retail)

    @staticmethod
    def _dimensions(ai_product: Dict[str, Any]) -> Dict[str, str]:
        dims = ai_product.get("dimensions_cm", {})
        if isinstance(dims, dict):
            return {"L": str(dims.get("L", "")), "W": str(dims.get("W", "")), "H": str(dims.get("H", ""))}
        parts = re.findall(r"\d+(?:\.\d+)?", str(dims))[:3]
        parts += [""] * (3 - len(parts))
        return {"L": parts[0], "W": parts[1], "H": parts[2]}

    @staticmethod
    def _build_custom_fields(source_url: str) -> List[Dict[str, Any]]:
        """Build variant-level custom_fields using real Zoho customfield_id values.

        Company Division is a DROPDOWN field - Zoho requires the option_id as value.
        Ref Link is a URL field - Zoho accepts the URL string directly.
        """
        company_div_id = settings.zoho_cf_company_division_id
        company_div_option_id = settings.zoho_cf_company_division_option_id
        ref_link_id = settings.zoho_cf_ref_link_id

        if company_div_id and ref_link_id:
            logger.info("Using configured customfield_id values for variant custom fields.")
            fields: List[Dict[str, Any]] = [
                {
                    "customfield_id": company_div_id,
                    "value": company_div_option_id or "Yantronix",
                },
                {
                    "customfield_id": ref_link_id,
                    "value": source_url,
                },
            ]
            return fields

        # Fallback: api_name (Zoho's convention is cf_ + field_name)
        logger.warning(
            "ZOHO_CF_COMPANY_DIVISION_ID / ZOHO_CF_REF_LINK_ID not set in .env. "
            "Custom fields will attempt api_name fallback."
        )
        return [
            {"api_name": "cf_company_division", "value": "Yantronix"},
            {"api_name": "cf_ref_link", "value": source_url},
        ]


class ZohoPublisher:
    """Publish Zoho payloads with dry-run support and lazy OAuth setup."""

    def __init__(self, payload_builder: Optional[ZohoPayloadBuilder] = None) -> None:
        self._payload_builder = payload_builder or ZohoPayloadBuilder()
        self._auth: Optional[ZohoAuth] = None

    def publish(self, ai_product: Dict[str, Any], category_id: Optional[str] = None, source_url: str = "", generated_sku: str = "", brand_name: str = "", brand_id: str = "") -> Dict[str, Any]:
        """Build and publish a product payload, or return dry-run data in test mode."""

        payload = self._payload_builder.build(
            ai_product, 
            category_id=category_id,
            source_url=source_url,
            generated_sku=generated_sku,
            brand_name=brand_name,
            brand_id=brand_id,
        )
        if settings.test_mode:
            logger.info("TEST MODE — payload built, not sent to Zoho.")
            print("\n" + "=" * 60)
            print("🧪 TEST MODE — Zoho payload (not sent):")
            print("=" * 60)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print("=" * 60 + "\n")
            return {"test_mode": True, "payload": payload}

        headers = self._auth_headers()
        api_url = f"{settings.zoho_api_domain}/store/api/v1/products"

        logger.info("Publishing product to Zoho: %s", api_url)
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 401:
            # Token expired — invalidate and retry once
            logger.warning("Got 401 from Zoho, refreshing token and retrying...")
            self._get_auth().invalidate()
            response = requests.post(api_url, json=payload, headers=self._auth_headers(), timeout=30)

        if not response.ok:
            raise requests.HTTPError(
                f"Zoho API error {response.status_code}: {response.text[:500]}",
                response=response,
            )

        result = response.json()
        # Zoho wraps success in {"code": 0, "message": "success", "product": {...}}
        code = result.get("code", result.get("status_code", -1))
        if str(code) not in ("0", "200", "success"):
            raise ValueError(
                f"Zoho returned error code={code}: {result.get('message', str(result)[:200])}"
            )

        # Extract the created product ID for the audit log and response
        product_data = result.get("product", result.get("payload", {}).get("product", {}))
        zoho_product_id = str(product_data.get("product_id", "")) if product_data else ""

        logger.info("Product published to Zoho successfully. zoho_product_id=%s", zoho_product_id)
        return {
            "success": True,
            "zoho_product_id": zoho_product_id,
            "result": result,
        }

    def _auth_headers(self) -> Dict[str, str]:
        """Return Zoho auth headers while preserving detailed auth errors."""

        try:
            return self._get_auth().auth_headers()
        except (ZohoAuthError, ZohoTokenRefreshError):
            logger.exception("Failed to get Zoho access token")
            raise

    def _get_auth(self) -> ZohoAuth:
        """Create ZohoAuth lazily so dry-run mode does not require credentials."""

        if self._auth is None:
            self._auth = ZohoAuth()
        return self._auth


publisher = ZohoPublisher()
