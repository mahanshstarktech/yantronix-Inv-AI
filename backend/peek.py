import psycopg2
import json
import os

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
        r.data->>'title' as title,
        a.ai_data
    FROM ai_products a
    JOIN raw_products r ON r.id = a.raw_product_id
    ORDER BY a.id DESC
    LIMIT 10
""")

rows = cur.fetchall()

if not rows:
    print("No AI products found in database yet.")
else:
    # ── Full raw dump ──────────────────────────────────────────────────────
    for row in rows:
        id, title, ai_data = row
        print("\n" + "="*60)
        print(f"ID: {id} | TITLE: {title}")
        print("RAW AI DATA:")
        print(json.dumps(ai_data, indent=2))

    # ── Friendly summary ───────────────────────────────────────────────────
    for row in rows:
        id, title, ai_data = row
        print("\n" + "="*60)
        print(f"ID: {id}")
        print(f"TITLE:        {title}")
        print("-"*60)
        print(f"SEO TITLE:    {ai_data.get('seo_title', 'N/A')}")
        print(f"SEO DESC:     {ai_data.get('meta_description', 'N/A')}")   # fixed: was 'seo_description'
        print(f"HSN CODE:     {ai_data.get('hsn_code', 'N/A')}")
        print(f"TAGS:         {', '.join(ai_data.get('tags', []))}")

        keywords = ai_data.get('seo_keywords', {})
        if isinstance(keywords, dict):
            print(f"KEYWORDS:     {', '.join(keywords.get('primary', []))}")
        else:
            print(f"KEYWORDS:     {keywords}")

        print(f"\nSHORT DESC:\n{ai_data.get('short_description_html', 'N/A')}")

cur.close()
conn.close()
