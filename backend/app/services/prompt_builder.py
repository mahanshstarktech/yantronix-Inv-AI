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
You are a professional electronics product data extractor and e-commerce listing writer
for an Indian electronics store named Yantronix.

Below is raw visible text scraped from a supplier product page. Extract facts from it and
create a complete, publication-ready e-commerce product listing.

Return ONLY one valid JSON object. No markdown fences. No explanation. No extra text.
Every string value must be single-line JSON text. Use \\n for internal line breaks inside strings.

SOURCE URL: {source_url}
{price_hint}
--- RAW PAGE TEXT START ---
{raw_text}
--- RAW PAGE TEXT END ---

OUTPUT FORMAT (all fields required):
{{
  "product_title": "Full descriptive title: Brand ProductName – Key Spec (ChipName, Interface) – Use Case",
  "seo_title": "60–70 character keyword-rich SEO title",
  "meta_description": "150–160 character meta description with specs and CTA",
  "seo_description": "2–3 sentence SEO paragraph for an India/Yantronix product page",
  "hsn_code": "6-digit GST HSN code",
  "sku": "SKU extracted from page or inferred from product name/model",
  "brand": "Exact brand name as printed on product/page. Use 'Generic' only if truly absent.",
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
  "short_description_html": "<div class=\\"product-short-descriptions\\"><section><ul><li>Key spec bullet 1</li><li>Key spec bullet 2</li>... (8–12 bullets total, each a single important fact)</ul></section></div>",
  "long_description_html": "<div class=\\"product-detail-description\\"><h2>FULL PRODUCT NAME – Subtitle</h2><p>Introductory paragraph with bold product name and key specs...</p><p>Second paragraph covering core technology...</p><h3>🔧 Key Features</h3><ul><li><strong>Feature:</strong> Detail.</li>...</ul><h3>💡 Applications &amp; Use Cases</h3><ul><li>Use case 1.</li>...</ul><h3>⚙️ Technical Specifications</h3><table border=\\"1\\" cellpadding=\\"6\\" cellspacing=\\"0\\" style=\\"border-collapse:collapse;width:100%\\"><tbody><tr><td><strong>Parameter</strong></td><td>Value</td></tr>...</tbody></table><h3>📦 Package Includes</h3><ul><li>1 × Product Name</li>...</ul></div>"
}}

STRICT RULES:
1. Extract real supplier facts when present. Do not invent chip names, voltage ratings, or dimensions.
2. If a value is missing, estimate only weight/dimensions/pricing realistically; otherwise use empty string or 0.
3. Pricing formula: after_gst = base × 1.18, after_margin = after_gst × 1.05. Round to 2 decimals.
4. HSN examples: sensors/modules 854370, PCB kits 853400, power modules 850440, RF modules 852691.
5. `tags` must be a flat list: product type, chip/interface, use cases, compatible boards, audience, India terms.
6. `seo_keywords` must be a flat list: short-tail, long-tail, buy/shop phrases, India price terms.
7. HTML must not include script, iframe, form, event-handler attributes, or external JavaScript.
8. short_description_html: Must use the exact wrapper <div class="product-short-descriptions"><section><ul> with 8–12 <li> bullets covering the most important product facts.
9. long_description_html: Must use the exact wrapper <div class="product-detail-description"> with:
   - An <h2> with the product name
   - 2–3 introductory <p> paragraphs
   - <h3>🔧 Key Features</h3> section with <ul><li><strong>Name:</strong> value</li></ul>
   - <h3>💡 Applications & Use Cases</h3> section
   - <h3>⚙️ Technical Specifications</h3> section with a full <table>
   - <h3>📦 Package Includes</h3> section listing exactly what is in the box
10. Output must be parseable JSON with no trailing commas.
""".strip()
