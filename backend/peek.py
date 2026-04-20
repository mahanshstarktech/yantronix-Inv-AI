import psycopg2
import json

conn = psycopg2.connect(
    dbname="scraper_db",
    user="mahanshgaur",
    host="localhost",
    port="5432"
)

cur = conn.cursor()
cur.execute("""
    SELECT 
        r.id,
        r.data->>'title' as title,
        a.ai_data
    FROM ai_products a
    JOIN raw_products r ON r.id = a.raw_product_id
""")

rows = cur.fetchall()

for row in rows:
    id, title, ai_data = row
    print("\n" + "="*60)
    print(f"ID: {id} | TITLE: {title}")
    print("RAW AI DATA:")
    print(json.dumps(ai_data, indent=2))  # print everything as-is
    
for row in rows:
    id, title, ai_data = row
    print("\n" + "="*60)
    print(f"ID: {id}")
    print(f"TITLE: {title}")
    print("-"*60)
    print(f"SEO TITLE:    {ai_data.get('seo_title', 'N/A')}")
    print(f"SEO DESC:     {ai_data.get('seo_description', 'N/A')}")
    print(f"HSN CODE:     {ai_data.get('hsn_code', 'N/A')}")
    print(f"TAGS:         {', '.join(ai_data.get('tags', []))}")
    print(f"KEYWORDS:     {', '.join(ai_data.get('seo_keywords', []))}")
    print(f"\nSHORT DESC:\n{ai_data.get('short_description', 'N/A')}")

cur.close()
conn.close()