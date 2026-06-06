"""MongoDB repository for product documents.

Repository methods hide ObjectId conversion and MongoDB collection details from
API/services. Keeping persistence behind this boundary makes the rest of the
application easier to test and evolve.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection

from app.core.config import settings
from app.models.product import AIProduct, ProductStatus, RawProductData


class ProductRepository:
    """Mongo-backed repository for raw and AI-generated product data."""

    def __init__(self, mongo_uri: str, db_name: str) -> None:
        self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        self._db = self._client[db_name]
        self.raw_products: Collection = self._db["raw_products"]
        self.ai_products: Collection = self._db["ai_products"]

    def ensure_indexes(self) -> None:
        """Create indexes used by duplicate checks and status lookups.

        Index creation is best-effort so the application can still boot in
        local development before MongoDB is started. The first database call
        will still surface connectivity problems clearly.
        """

        try:
            self.raw_products.create_index("source_url")
            self.raw_products.create_index("status")
            self.ai_products.create_index("raw_product_id", unique=True)
        except Exception:
            pass

    def save_raw_product(self, product: RawProductData) -> str:
        """Insert raw product data and return the generated Mongo ObjectId."""

        now = datetime.now(timezone.utc)
        doc = {
            "source_url": product.source_url,
            "vendor": product.vendor,
            "status": ProductStatus.QUEUED.value,
            "error_message": None,
            "data": product.as_mongo(),
            "created_at": now,
            "updated_at": now,
        }
        result = self.raw_products.insert_one(doc)
        return str(result.inserted_id)

    def get_raw_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Return stored raw product data by id, or None for invalid/missing ids."""

        doc = self._find_raw_doc(product_id)
        return doc.get("data") if doc else None

    def get_raw_document(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Return the complete raw product document including status metadata."""

        return self._find_raw_doc(product_id)

    def save_ai_product(self, raw_product_id: str, ai_product: AIProduct) -> None:
        """Upsert generated AI product data for a raw product."""

        object_id = ObjectId(raw_product_id)
        now = datetime.now(timezone.utc)
        self.ai_products.update_one(
            {"raw_product_id": object_id},
            {
                "$set": {
                    "raw_product_id": object_id,
                    "ai_data": ai_product.as_mongo(),
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        self.mark_status(raw_product_id, ProductStatus.COMPLETE)

    def get_ai_product(self, raw_product_id: str) -> Optional[Dict[str, Any]]:
        """Return generated product data by raw product id."""

        try:
            doc = self.ai_products.find_one({"raw_product_id": ObjectId(raw_product_id)})
        except Exception:
            return None
        return doc.get("ai_data") if doc else None

    def get_existing_completed_product_by_url(self, url: str) -> Optional[str]:
        """Return the newest completed raw product id for an already-generated URL."""

        docs = self.raw_products.find({"source_url": url}).sort("_id", -1)
        for doc in docs:
            raw_id = doc["_id"]
            if self.ai_products.find_one({"raw_product_id": raw_id}):
                return str(raw_id)
        return None

    def mark_status(
        self,
        product_id: str,
        status: ProductStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Update product processing status and optional failure reason."""

        self.raw_products.update_one(
            {"_id": ObjectId(product_id)},
            {
                "$set": {
                    "status": status.value,
                    "error_message": error_message,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    def _find_raw_doc(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Find a raw product document, safely handling invalid ObjectIds."""

        try:
            return self.raw_products.find_one({"_id": ObjectId(product_id)})
        except Exception:
            return None


repository = ProductRepository(settings.mongo_uri, settings.mongo_db_name)
