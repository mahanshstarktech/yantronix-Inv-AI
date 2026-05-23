import json
def build_ai_prompt(product: dict) -> str:
    """
    Build a structured prompt for AI content generation.
    Now reads raw_page_text (the html→text dump) instead of pre-parsed fields.
    All pricing is derived from whatever price Gemini can find in the raw text.
    """

    raw_text = product.get("raw_page_text", "")
    source_url = product.get("source_url", "")

    # Pricing is still available if the scraper wrote it, but Gemini will
    # re-extract from raw text if these are blank / zero.

    pricing       = product.get("pricing") or {}
    quartz_price  = float(pricing.get("base_price") or 0)

    # Use the already-calculated selling price from the scraper.
    # Fall back to the formula only if the stored value is missing.
    selling_price = float(
        pricing.get("selling_price")
        or round(quartz_price * 1.18 * 1.05, 2)
    )

    price_hint = ""
    if quartz_price:
        price_hint = (
            f"KNOWN QUARTZ BASE PRICE : ₹{quartz_price}\n"
            f"CALCULATED SELLING PRICE: ₹{selling_price}  "
            f"(formula: base × 1.18 GST × 1.05 margin)\n"
        )

    prompt = f"""
You are a professional electronics product data extractor and e-commerce listing generator
for an Indian electronics store (Yantronix).
 
Below is the raw plain-text content scraped from a supplier product page.
Extract every piece of product information from it and generate a COMPLETE,
richly detailed e-commerce product listing.
 
Return ONLY a single valid JSON object. No explanation. No markdown. No extra text.
CRITICAL: Every string value must be on one line — use \\n for line breaks, never a literal newline.
 
SOURCE URL: {source_url}
{price_hint}
--- RAW PAGE TEXT START ---
{raw_text[:12000]}
--- RAW PAGE TEXT END ---
 
OUTPUT FORMAT (strict JSON — every field is required):
{{
  "product_title":      "<Full descriptive title: Product Name – Key Spec (ChipName, Interface) – Use Case>",
  "seo_title":          "<60–70 char SEO title, keyword-rich>",
  "meta_description":   "<150–160 char meta: key specs + target audience + call-to-action>",
  "seo_description":    "<2–3 sentence paragraph for product page SEO, includes city/India, specs, audience>",
  "hsn_code":           "<6-digit GST HSN code>",
  "sku":                "<SKU extracted from page, or best guess from product name>",
  "weight_kg":          <realistic float, e.g. 0.025>,
  "dimensions_cm":      "<L × W × H e.g. '3.2 × 1.4 × 0.8'>",
  "selling_price": {{
    "quartz_base_price":   <float>,
    "after_gst":           <float — base × 1.18>,
    "after_margin":        <float — after_gst × 1.05>,
    "final_selling_price": <float — same as after_margin>
  }},
  "tags":               ["<20+ specific tags: product type, chip/IC name, interface, use case, platform, audience, country>"],
  "seo_keywords":       ["<25+ flat list of keyword strings: short-tail, long-tail, negative, India-specific, buy/shop phrases>"],
  "short_description_html": "<single-line HTML: <p>intro with <strong> highlights</strong></p><ul><li><strong>Spec:</strong> Value</li>...</ul><p>⚠️ warning if HV/dangerous</p>>",
  "long_description_html":  "<single-line HTML with ALL of: <section><h2>Overview</h2><p>...</p></section> <section><h2>Technical Specifications</h2><table border=\\"1\\">...</table></section> <section><h2>How It Works</h2>...</section> <section><h2>Key Features</h2><ul>...</ul></section> <section><h2>Pin Description</h2><table>...</table></section> <section><h2>Compatible Platforms</h2><ul>...</ul></section> <section><h2>Applications</h2><ul>...</ul></section> <section><h2>Assembly / Usage Notes</h2><ul>...</ul></section> <section><h2>Sample Code</h2><pre><code>...</code></pre></section> <section><h2>Package Contents</h2><ul>...</ul></section> <section><h2>Safety Warning</h2><p style=\\"color:#cc0000\\">...</p></section> — omit sections that genuinely don't apply>"
}}
 
STRICT RULES:
1. PRODUCT TITLE format: "Name Variant – Key Spec (ChipName, Interface) – Use Case"
   Example: "Arc Cigarette Lighter Parts – DIY Electronic Lighter Kit (High Voltage Arc Igniter Module, DC 3–5V)"
 
2. TAGS must include ALL of:
   - product type keywords (module, kit, sensor, board…)
   - chip/IC/transistor names exactly as on the page
   - interface types (I2C, SPI, UART, GPIO…)
   - use cases (robotics, drone, IoT, DIY, maker…)
   - compatible platforms (Arduino, ESP32, Raspberry Pi, STM32…)
   - audience (hobbyist, student, maker, beginner…)
   - country-specific (India, buy online India…)
   - Minimum 20 tags
 
3. SEO KEYWORDS must be a flat list (not a dict) of 25+ strings including:
   - short-tail: "arc lighter kit", "MPU6050 module"
   - long-tail: "buy arc lighter kit online India", "MPU6050 gyroscope Arduino project"
   - buy/shop phrases: "buy X online", "X price India", "X shop"
   - negative intent words to avoid bidding waste: "free", "crack"
   - vendor-specific: "quartzcomponents X", "yantronix X"
 
4. SHORT DESCRIPTION HTML must contain:
   - An intro <p> with <strong> on the product name and 2–3 key specs
   - A <ul> with every spec as <li><strong>Label:</strong> Value</li>
   - A warning <p> if the product is high-voltage, high-current, or otherwise hazardous
 
5. LONG DESCRIPTION HTML must be a single line (\\n escaped, never literal newlines).
   Include ALL applicable sections listed in the format above.
   Technical Specs section MUST be a full HTML <table> with every spec from the page.
   If a Pin Description table exists on the page, include it.
   Include a Sample Code block (Arduino/MicroPython snippet) if the product is a sensor/module.
   If the product is a kit, include detailed Assembly Tips section.
 
6. PRICING: Extract the base price from raw text if the known price hint is 0.
   Apply: after_gst = base × 1.18, after_margin = after_gst × 1.05.
   Round all prices to 2 decimal places.
 
7. HSN CODE: Use the correct 6-digit GST HSN code for the product category.
   Common examples: sensors/modules 854370, PCB kits 853400, power modules 850440,
   high-voltage/igniters 853610, RF modules 852691.
 
8. WEIGHT and DIMENSIONS: Use values from the page. If not present, estimate realistically.
 
9. Output must be valid JSON — no trailing commas, no comments, no markdown fences.
10. If a field cannot be determined at all, use an empty string "" or 0 — never omit the key.
"""
    return prompt.strip()