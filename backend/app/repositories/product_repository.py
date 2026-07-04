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
        self.publish_log: Collection = self._db["publish_log"]
        self.sequences: Collection = self._db["sequences"]

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
            self.publish_log.create_index("raw_product_id")
            self.publish_log.create_index("published_at")
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
        """Check if a product from this URL is already queued or processed."""
        docs = self.raw_products.find({"source_url": url}).sort("_id", -1)
        for doc in docs:
            # Must also check ai_products to see if it reached at least COMPLETE state
            ai_doc = self.get_ai_product(str(doc["_id"]))
            if ai_doc:
                return str(doc["_id"])
        return None

    def get_next_sku_sequence(self, sequence_name: str = "product_sku", start_at: int = 150) -> int:
        """Atomically fetch and increment the SKU sequence."""
        result = self.sequences.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        seq = result.get("seq", start_at)
        # If it just initialized via upsert, it will be 1, but we want it to start at 150
        if seq == 1 and start_at > 1:
            result = self.sequences.find_one_and_update(
                {"_id": sequence_name},
                {"$set": {"seq": start_at}},
                return_document=True,
            )
            seq = result.get("seq", start_at)
        return seq

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

    def save_publish_result(
        self,
        raw_product_id: str,
        result: Dict[str, Any],
        category_id: Optional[str] = None,
        test_mode: bool = False,
    ) -> None:
        """Record a publish event for audit trail."""

        now = datetime.now(timezone.utc)
        try:
            self.publish_log.insert_one({
                "raw_product_id": ObjectId(raw_product_id),
                "published_at": now,
                "category_id": category_id,
                "test_mode": test_mode,
                "result": result,
            })
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to save publish log: %s", exc)

    def get_all_products(self, limit: int = 100) -> list:
        """Return a list of all AI-generated products for a future dashboard."""

        try:
            docs = list(
                self.ai_products.find({}, {"ai_data.product_title": 1, "raw_product_id": 1, "created_at": 1})
                .sort("created_at", -1)
                .limit(limit)
            )
            return [
                {
                    "product_id": str(d["raw_product_id"]),
                    "product_title": d.get("ai_data", {}).get("product_title", "Untitled"),
                    "created_at": d.get("created_at", "").isoformat() if d.get("created_at") else "",
                }
                for d in docs
            ]
        except Exception:
            return []


repository = ProductRepository(settings.mongo_uri, settings.mongo_db_name)
