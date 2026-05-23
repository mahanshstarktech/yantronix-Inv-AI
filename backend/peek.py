import psycopg2
import json
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname = os.getenv("DB_NAME", "scraper_db"),
    user   = os.getenv("DB_USER", "mahanshgaur"),
    host   = os.getenv("DB_HOST", "localhost"),
    port   = os.getenv("DB_PORT", "5432"),
)

cur = conn.cursor()
cur.execute("""
    SELECT
        r.id,
        r.source_url,
        a.ai_data
    FROM ai_products a
    JOIN raw_products r ON r.id = a.raw_product_id
    ORDER BY a.id DESC
    LIMIT 5
""")

rows = cur.fetchall()

if not rows:
    print("No AI products found in database yet.")
else:
    for row in rows:
        product_id, source_url, ai = row
        div = "=" * 70

        print(f"\n{div}")
        print(f"  PRODUCT ID  : {product_id}")
        print(f"  SOURCE URL  : {source_url}")
        print(div)

        # ── 1. Titles & meta ─────────────────────────────────────────────
        print(f"\n1. PRODUCT TITLE\n   {ai.get('product_title', 'N/A')}")
        print(f"\n2. SEO TITLE\n   {ai.get('seo_title', 'N/A')}")
        print(f"\n3. META DESCRIPTION\n   {ai.get('meta_description', 'N/A')}")
        print(f"\n4. SEO DESCRIPTION\n   {ai.get('seo_description', 'N/A')}")

        # ── 2. Identifiers & physical ─────────────────────────────────────
        print(f"\n5. HSN CODE     : {ai.get('hsn_code', 'N/A')}")
        print(f"   SKU          : {ai.get('sku', 'N/A')}")
        print(f"   WEIGHT (kg)  : {ai.get('weight_kg', 'N/A')}")
        print(f"   DIMENSIONS   : {ai.get('dimensions_cm', 'N/A')}")

        # ── 3. Pricing ────────────────────────────────────────────────────
        sp = ai.get("selling_price", {})
        print(f"\n6. PRICING")
        print(f"   Quartz base  : ₹{sp.get('quartz_base_price', 0)}")
        print(f"   After GST    : ₹{sp.get('after_gst', 0)}")
        print(f"   After margin : ₹{sp.get('after_margin', 0)}")
        print(f"   FINAL PRICE  : ₹{sp.get('final_selling_price', 0)}")

        # ── 4. Tags ───────────────────────────────────────────────────────
        tags = ai.get("tags", [])
        print(f"\n7. TAGS ({len(tags)})")
        print("   " + ", ".join(tags))

        # ── 5. SEO Keywords ───────────────────────────────────────────────
        kw = ai.get("seo_keywords", [])
        print(f"\n8. SEO KEYWORDS ({len(kw)})")
        # Print in rows of 3 for readability
        for i in range(0, len(kw), 3):
            print("   " + ",  ".join(kw[i:i+3]))

        # ── 6. Short description ──────────────────────────────────────────
        short = ai.get("short_description_html", "N/A")
        print(f"\n9. SHORT DESCRIPTION HTML")
        # Replace escaped \n with real newlines for display
        print(short.replace("\\n", "\n"))

        # ── 7. Long description (first 2000 chars to avoid wall of text) ──
        long = ai.get("long_description_html", "N/A")
        long_display = long.replace("\\n", "\n")
        print(f"\n10. LONG DESCRIPTION HTML (first 2000 chars)")
        print(long_display[:2000])
        if len(long_display) > 2000:
            print(f"\n    ... [{len(long_display) - 2000} more characters] ...")

        print(f"\n{div}\n")

cur.close()
conn.close()