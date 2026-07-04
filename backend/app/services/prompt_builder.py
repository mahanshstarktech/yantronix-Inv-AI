"""Prompt builder for structured AI product generation."""

from __future__ import annotations

from typing import Any, Dict


def build_ai_prompt(product: Dict[str, Any], max_raw_text_chars: int) -> str:
    """Build a bounded prompt that asks for the canonical `AIProduct` schema."""

    raw_text = str(product.get("raw_page_text", ""))[:max_raw_text_chars]
    source_url = product.get("source_url", "")
    pricing = product.get("pricing") or {}
    quartz_price = float(pricing.get("base_price") or 0)
    selling_price = float(pricing.get("selling_price") or round(quartz_price * 1.18 * 1.05, 2))

    price_hint = ""
    if quartz_price:
        price_hint = (
            f"KNOWN SUPPLIER BASE PRICE : ₹{quartz_price}\n"
            f"CALCULATED SELLING PRICE: ₹{selling_price} (formula: base × 1.18 GST × 1.05 margin)\n"
        )

    return f"""
You are a professional electronics product data extractor and e-commerce listing generator
for an Indian electronics store named Yantronix.

Below is raw visible text scraped from a supplier product page. Extract facts from it and
create a complete e-commerce product listing.

Return ONLY one valid JSON object. No markdown. No explanation. No extra text.
Every string value must be single-line JSON text. Use \\n for internal line breaks.

SOURCE URL: {source_url}
{price_hint}
--- RAW PAGE TEXT START ---
{raw_text}
--- RAW PAGE TEXT END ---

OUTPUT FORMAT (all fields required):
{{
  "product_title": "Full descriptive title: Product Name – Key Spec (ChipName, Interface) – Use Case",
  "seo_title": "60–70 character keyword-rich SEO title",
  "meta_description": "150–160 character meta description with specs and CTA",
  "seo_description": "2–3 sentence SEO paragraph for an India/Yantronix product page",
  "hsn_code": "6-digit GST HSN code",
  "sku": "SKU extracted from page or inferred from product name",
  "brand": "Extracted brand name, or empty string if unknown",
  "weight_kg": 0.025,
  "dimensions_cm": "L × W × H in cm, for example 3.2 × 1.4 × 0.8",
  "selling_price": {{
    "quartz_base_price": 0.0,
    "vendor_base_price": 0.0,
    "after_gst": 0.0,
    "after_margin": 0.0,
    "final_selling_price": 0.0,
    "currency": "INR"
  }},
  "tags": ["20+ specific tags"],
  "seo_keywords": ["25+ flat keyword strings"],
  "short_description_html": "single-line safe HTML summary",
  "long_description_html": "single-line safe HTML with Overview, Technical Specifications, Features, Platforms, Applications, Usage Notes, Package Contents, and Safety Warning when applicable"
}}

STRICT RULES:
1. Extract real supplier facts when present. Do not invent chip names, voltage ratings, or dimensions if a field is visible.
2. If a value is missing, estimate only weight/dimensions/pricing realistically; otherwise use an empty string or 0.
3. Pricing formula: after_gst = base × 1.18, after_margin = after_gst × 1.05. Round prices to 2 decimals.
4. Use correct common HSN examples: sensors/modules 854370, PCB kits 853400, power modules 850440, high-voltage/igniters 853610, RF modules 852691.
5. `tags` must be a flat list of strings with product type, chip/interface, use cases, compatible boards, audience, India terms, and Yantronix terms.
6. `seo_keywords` must be a flat list of strings with short-tail, long-tail, buy/shop phrases, India price terms, and negative intent words such as "free" or "crack".
7. HTML fields must not include script, iframe, form, event-handler attributes, or external JavaScript.
8. Output must be parseable JSON with no trailing commas.
""".strip()
