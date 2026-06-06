"""Compatibility wrappers around the MongoDB product repository."""

from __future__ import annotations

from typing import Optional

from app.models.product import AIProduct, RawProductData
from app.repositories.product_repository import repository


def save_raw_product(product_data: dict, url: str) -> str:
    """Save raw extracted data and return the stringified ObjectId."""

    payload = dict(product_data)
    payload["source_url"] = url
    return repository.save_raw_product(RawProductData.model_validate(payload))


def save_ai_product(raw_product_id: str, ai_data: dict) -> None:
    """Save AI generated data linked to the raw product."""

    repository.save_ai_product(raw_product_id, AIProduct.model_validate(ai_data))


def get_raw_product(product_id: str) -> Optional[dict]:
    """Retrieve raw product data by its stringified ObjectId."""

    return repository.get_raw_product(product_id)


def get_ai_product(raw_product_id: str) -> Optional[dict]:
    """Return the AI-generated data for a product, or None if not ready yet."""

    return repository.get_ai_product(raw_product_id)


def get_existing_completed_product_by_url(url: str) -> Optional[str]:
    """Check if there is already an AI-generated product for this source URL."""

    return repository.get_existing_completed_product_by_url(url)
