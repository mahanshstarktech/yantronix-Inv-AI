"""
publish.py — Zoho Commerce Product Publisher
Uses ZohoAuth for automatic token management.

TEST_MODE=true  → dry-run (prints payload, no API call)
TEST_MODE=false → live publish to Zoho Commerce
"""

import os
import re
import json
import logging

import requests
from dotenv import load_dotenv

load_dotenv()

from zoho import ZohoAuth
from zoho.exceptions import ZohoAuthError, ZohoTokenRefreshError

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TEST_MODE  = os.getenv("TEST_MODE", "true").lower() == "true"
API_DOMAIN = os.getenv("ZOHO_API_DOMAIN", "https://commerce.zoho.in")

ZOHO_API_URL = f"{API_DOMAIN}/store/api/v1/products"

# Singleton auth instance — shared across all publish calls
_auth = ZohoAuth()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:80]


def _tags_list(ai_product: dict) -> list:
    tags = ai_product.get("tags", [])
    if isinstance(tags, list):
        return [str(t) for t in tags]
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    return []


def _seo_keywords_str(ai_product: dict) -> str:
    kw = ai_product.get("seo_keywords", [])
    if isinstance(kw, list):
        return ", ".join(str(k) for k in kw)
    return str(kw)


def _selling_price(ai_product: dict) -> str:
    sp = ai_product.get("selling_price", {})
    if isinstance(sp, dict):
        price = (
            sp.get("final_selling_price")
            or sp.get("after_margin")
            or sp.get("after_gst")
            or sp.get("base_price")
            or 0
        )
    else:
        price = sp or 0
    return str(price)


def _label_rate(ai_product: dict) -> str:
    sp = ai_product.get("selling_price", {})
    if isinstance(sp, dict):
        return str(sp.get("base_price") or sp.get("final_selling_price") or 0)
    return "0"


def _dim(ai_product: dict, key: str) -> str:
    dims = ai_product.get("dimensions_cm", {})
    if isinstance(dims, dict):
        return str(dims.get(key, ""))
    return ""


# ── Payload Builder ───────────────────────────────────────────────────────────

def build_zoho_payload(ai_product: dict) -> dict:
    """
    Map AI-generated product dict → Zoho Commerce POST /products payload.

    AI keys (from prompts.py / ai_generator.py):
      product_title, seo_title, meta_description, seo_description,
      seo_keywords, hsn_code, sku, weight_kg, dimensions_cm (L/W/H),
      selling_price (dict), tags (list), long_description_html
    """
    name = ai_product.get("product_title", "Unnamed Product")

    return {
        # ── Core ──────────────────────────────────────────────────────────
        "name":               name,
        "url":                _slugify(name),
        "variant_type":       "inventory",
        "show_in_storefront": True,
        "is_returnable":      False,
        "is_featured":        False,

        # ── Descriptions ──────────────────────────────────────────────────
        "product_short_description": ai_product.get("seo_description", ""),
        "product_description":       ai_product.get("long_description_html", ""),

        # ── SEO ───────────────────────────────────────────────────────────
        "seo_title":       ai_product.get("seo_title", "")[:70],
        "seo_description": ai_product.get("meta_description", "")[:160],
        "seo_keyword":     _seo_keywords_str(ai_product),

        # ── Tags ──────────────────────────────────────────────────────────
        "tags": _tags_list(ai_product),

        # ── Single variant (electronics = one SKU per product) ─────────── 
        "variants": [
            {
                "rate":          _selling_price(ai_product),
                "label_rate":    _label_rate(ai_product),
                "sku":           ai_product.get("sku", ""),
                "initial_stock": "0",
                "reorder_level": "5",
                "status":        "active",
                "hsn_or_sac":    ai_product.get("hsn_code", ""),
                "ean":           "",
                "upc":           "",
                "isbn":          "",
                "part_number":   "",
                "package_details": {
                    "weight": str(ai_product.get("weight_kg", "")),
                    "height": _dim(ai_product, "H"),
                    "length": _dim(ai_product, "L"),
                    "width":  _dim(ai_product, "W"),
                },
                "custom_fields": [],
            }
        ],
    }


# ── Publisher ─────────────────────────────────────────────────────────────────

def publish_to_zoho(ai_product: dict) -> dict:
    """
    Build the Zoho payload and POST to Commerce API.

    TEST_MODE=true  → print payload, return dry-run result (no API call)
    TEST_MODE=false → auto-refresh token via ZohoAuth, call live API
    """
    payload = build_zoho_payload(ai_product)

    # ── TEST MODE ────────────────────────────────────────────────────────
    if TEST_MODE:
        logger.info("TEST MODE — payload printed, not sent to Zoho.")
        print("\n" + "=" * 60)
        print("🧪 TEST MODE — Zoho payload (not sent):")
        print("=" * 60)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("=" * 60 + "\n")
        return {"test_mode": True, "payload": payload}

    # ── REAL MODE ────────────────────────────────────────────────────────
    try:
        headers = _auth.auth_headers()   # auto-refreshes if token is near expiry
    except (ZohoAuthError, ZohoTokenRefreshError) as exc:
        logger.error("Failed to get Zoho access token: %s", exc)
        raise

    logger.info("Publishing product '%s' to Zoho Commerce …", payload["name"])

    response = requests.post(
        ZOHO_API_URL,
        json=payload,
        headers=headers,
        timeout=30,
    )

    # ── 401 → force token refresh and retry once ─────────────────────────
    if response.status_code == 401:
        logger.warning("Received 401 — invalidating token and retrying once …")
        _auth.invalidate()
        headers = _auth.auth_headers()
        response = requests.post(ZOHO_API_URL, json=payload, headers=headers, timeout=30)

    if not response.ok:
        raise requests.HTTPError(
            f"Zoho API error {response.status_code}: {response.text}",
            response=response,
        )

    result = response.json()

    if result.get("code") != 0:
        raise ValueError(
            f"Zoho error code {result.get('code')}: {result.get('message')}"
        )

    product_id = result["product"]["product_id"]
    logger.info("✅ Product published. product_id=%s", product_id)
    return result