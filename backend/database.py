import psycopg2
import json
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ── DB config ────────────────────────────────────────────────────────────────
# Reads from environment variables if present, falls back to local defaults.
DB_CONFIG = dict(
    dbname = os.getenv("DB_NAME", "scraper_db"),
    user   = os.getenv("DB_USER", "mahanshgaur"),
    host   = os.getenv("DB_HOST", "localhost"),
    port   = os.getenv("DB_PORT", "5432"),
)

def get_conn():
    """Open a fresh connection. Always close it after use."""
    return psycopg2.connect(**DB_CONFIG)


def save_raw_product(product_data: dict, url: str) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO raw_products (source_url, vendor, data)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (url, product_data["vendor"], json.dumps(product_data))
        )
        product_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return product_id
    finally:
        conn.close()


def save_ai_product(raw_product_id: int, ai_data: dict) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_products (raw_product_id, ai_data)
            VALUES (%s, %s)
            """,
            (raw_product_id, json.dumps(ai_data))
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def get_raw_product(product_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM raw_products WHERE id = %s", (product_id,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
    finally:
        conn.close()
