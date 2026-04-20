import requests
import os

# -----------------------------
# Key mapping
# AI generator returns these keys (from prompts.py):
#   product_title, short_description_html, selling_price.final_selling_price, sku
# -----------------------------

ZOHO_TOKEN = os.getenv("ZOHO_TOKEN", "")
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"  # default: test mode ON

def build_zoho_payload(product: dict) -> dict:
    """Map AI-generated keys to Zoho Commerce API fields."""
    return {
        "name":         product.get("product_title", "Unnamed Product"),
        "description":  product.get("short_description_html", ""),
        "price":        product.get("selling_price", {}).get("final_selling_price", 0),
        "sku":          product.get("sku", ""),
        "tags":         ", ".join(product.get("tags", [])),
        "seo_title":    product.get("seo_title", ""),
        "seo_desc":     product.get("meta_description", ""),
    }

def publish_to_zoho(product: dict) -> dict:
    payload = build_zoho_payload(product)

    # ── TEST MODE ──────────────────────────────────────────
    if TEST_MODE:
        print("\n" + "="*60)
        print("🧪 TEST MODE — Zoho payload that would be sent:")
        print("="*60)
        for key, value in payload.items():
            print(f"  {key:<12}: {value}")
        print("="*60 + "\n")
        return {"test_mode": True, "payload": payload}

    # ── REAL MODE ──────────────────────────────────────────
    if not ZOHO_TOKEN:
        raise ValueError("ZOHO_TOKEN not set. Add it to your .env file.")

    url = "https://commerce.zoho.com/store/api/v1/products"
    headers = {
        "Authorization": f"Zoho-oauthtoken {ZOHO_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()