import os
from typing import Optional
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId

load_dotenv()

# ── DB config ────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "scraper_db")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

raw_products_collection = db["raw_products"]
ai_products_collection = db["ai_products"]

def save_raw_product(product_data: dict, url: str) -> str:
    """Save raw extracted data and return the stringified ObjectId."""
    doc = {
        "source_url": url,
        "vendor": product_data.get("vendor"),
        "data": product_data
    }
    result = raw_products_collection.insert_one(doc)
    return str(result.inserted_id)

def save_ai_product(raw_product_id: str, ai_data: dict) -> None:
    """Save AI generated data linked to the raw product."""
    doc = {
        "raw_product_id": ObjectId(raw_product_id),
        "ai_data": ai_data
    }
    ai_products_collection.insert_one(doc)

def get_raw_product(product_id: str) -> Optional[dict]:
    """Retrieve raw product data by its stringified ObjectId."""
    try:
        doc = raw_products_collection.find_one({"_id": ObjectId(product_id)})
        return doc.get("data") if doc else None
    except Exception:
        return None

def get_ai_product(raw_product_id: str) -> Optional[dict]:
    """Return the AI-generated data for a product, or None if not ready yet."""
    try:
        doc = ai_products_collection.find_one({"raw_product_id": ObjectId(raw_product_id)})
        return doc.get("ai_data") if doc else None
    except Exception:
        return None
