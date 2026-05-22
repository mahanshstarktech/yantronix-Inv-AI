import json
def build_ai_prompt(product: dict) -> str:
    """
    Build a structured prompt for AI content generation.
    Reads from the actual shape produced by extract_quartz_product() in main.py:
        - title          : str
        - vendor_sku     : str
        - description_raw: str
        - specifications : dict
        - pricing.base_price    : float
        - pricing.selling_price : float
    """

    # ── Read fields using the ACTUAL keys from the scraper ──────────────
    pricing       = product.get("pricing") or {}
    quartz_price  = float(pricing.get("base_price") or 0)

    # Use the already-calculated selling price from the scraper.
    # Fall back to the formula only if the stored value is missing.
    selling_price = float(
        pricing.get("selling_price")
        or round(quartz_price * 1.18 * 1.05, 2)
    )

    name          = product.get("title", "")
    sku           = product.get("vendor_sku", "")
    description   = product.get("description_raw", "")
    
    # specifications is a dict — convert to readable lines for the prompt
    specs_raw = product.get("specifications", "")
    if isinstance(specs_raw, dict):
        specs = "\n".join(f"{k}: {v}" for k, v in specs_raw.items())
    else:
        specs = str(specs_raw)
    

    prompt = f"""
You are a professional electronics product data extractor and e-commerce listing generator.

Generate a COMPLETE structured product listing for the following product.
Return ONLY a valid JSON object. No explanation. No markdown. No extra text.

---
PRODUCT NAME     : {name}
SKU              : {sku}
QUARTZ PRICE     : ₹{quartz_price}
SELLING PRICE    : ₹{selling_price}  (calculated as: Quartz Price × 1.18 × 1.05)
RAW DESCRIPTION  : {description}
RAW SPECS        : {specs}
---

OUTPUT FORMAT (strict JSON):
{{
  "product_title":      "<Clear, SEO-friendly full title with key specs in brackets>",
  "seo_title":          "<Optimized title, 60–70 characters max>",
  "meta_description":   "<150–160 characters, includes key specs + use case>",
  "hsn_code":           "<6-digit GST HSN code>",
  "sku":                "<SKU from product page>",
  "weight_kg":          "<realistic weight in kg as float e.g. 0.025>",
  "dimensions_cm":      "<L × W × H in cm e.g. '3.2 × 1.4 × 0.8'>",
  "tags":               ["tag1", "tag2", "tag3"],
  "seo_keywords": {{
    "primary":          ["kw1", "kw2", "kw3", "kw4", "kw5"],
    "secondary":        ["kw1", "kw2", "kw3", "kw4", "kw5"],
    "long_tail":        ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5"],
    "negative":         ["kw1", "kw2", "kw3", "kw4"]
  }},
  "selling_price": {{
    "quartz_base_price":  {quartz_price},
    "after_gst":          {round(quartz_price * 1.18, 2)},
    "after_margin":       {selling_price},
    "final_selling_price": {selling_price}
  }},
  "short_description_html": "<ul>...</ul> HTML with key specs as bullet points",
  "long_description_html":  "<Full HTML with h2, h3, p, table, ul, pre/code sections>"
}}

STRICT RULES:
- Product title format  : "Name Variant ChipName (SpecDetail) – Use Case"
- Tags must include     : product type, chip/module name, use case, platform (Arduino/ESP32/RPi)
- Always include in specs: Voltage, Interface type, Output type, Chip/IC name if applicable
- Short description     : HTML <ul> with all key specs as <li> items
- Long description      : Full HTML — include h2 title, intro paragraphs, Key Features ul,
                          Technical Specs table, Pin Description table (if applicable),
                          Compatible Platforms ul, Applications ul, Usage Notes ul,
                          Sample Code pre/code block (if applicable), Package Contents ul
- Use correct technical terms: GPIO, ADC, PWM, UART, I2C, SPI, TTL, MEMS, DMP etc.
- If any spec is missing from the raw data, estimate it realistically — do NOT leave blank
- Output must be valid JSON only — no trailing commas, no comments
"""
    return prompt.strip()