"""Celery tasks for asynchronous product generation."""

from __future__ import annotations

from app.models.product import ProductStatus
from app.repositories.product_repository import repository
from app.services.ai_service import AIGenerationError, get_product_generator
from .celery_app import celery_app


@celery_app.task
def generate_ai_task(product_id: str) -> None:
    """Generate an AI listing for a raw product and persist the result or failure."""

    print(f"[INFO] Starting AI generation for product_id={product_id}")
    product = repository.get_raw_product(product_id)
    if not product:
        print(f"[ERROR] Product not found for product_id={product_id}")
        return
    if not product.get("raw_page_text"):
        repository.mark_status(product_id, ProductStatus.FAILED, "Scraper returned empty raw_page_text.")
        return

    repository.mark_status(product_id, ProductStatus.PROCESSING)
    try:
        ai_product = get_product_generator().generate(product)
        
        # Generate SKU immediately so the frontend can preview it
        import datetime
        now = datetime.datetime.now()
        year1 = str(now.year)[-2:]
        year2 = str(now.year + 1)[-2:]
        year_str = f"{year1}{year2}"
        seq = repository.get_next_sku_sequence(f"sku_seq_{now.year}")
        ai_product.sku = f"YTX{year_str}{seq:04d}"

        repository.save_ai_product(product_id, ai_product)
        print(f"[INFO] AI product saved for product_id={product_id}")
    except (AIGenerationError, RuntimeError) as exc:
        repository.mark_status(product_id, ProductStatus.FAILED, str(exc))
        print(f"[ERROR] AI generation failed for product_id={product_id}: {exc}")
