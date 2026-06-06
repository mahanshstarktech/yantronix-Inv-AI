"""HTTP routes for the product-listing workflow."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.rate_limiter import LimitPolicy, client_key, rate_limiter
from app.models.product import (
    ExtractRequest,
    ExtractResponse,
    GenerateRequest,
    GenerateResponse,
    ProductStatus,
    RawProductData,
    StatusResponse,
)
from app.repositories.product_repository import repository
from app.services.scraper import HtmlTextExtractor, scraper_service
from app.services.publisher import publisher
from app.workers.tasks import generate_ai_task

router = APIRouter()


@router.post("/extract", response_model=ExtractResponse)
def extract_website(data: ExtractRequest, request: Request) -> ExtractResponse:
    """Fetch a supplier URL and return sanitized text for user review."""

    rate_limiter.check(
        client_key(request),
        LimitPolicy("extract", settings.rate_limit_extract_per_minute, 60),
    )
    return ExtractResponse(**scraper_service.extract(data.url))


@router.post("/generate", response_model=GenerateResponse)
def generate_listing(data: GenerateRequest, request: Request) -> GenerateResponse:
    """Persist reviewed text and queue one bounded AI generation job."""

    caller = client_key(request)
    rate_limiter.check(caller, LimitPolicy("generate", settings.rate_limit_generate_per_minute, 60))
    rate_limiter.check(caller, LimitPolicy("ai-calls", settings.rate_limit_ai_calls_per_hour, 3600))

    raw_text = HtmlTextExtractor.sanitize_text(data.raw_text)
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is empty.")
    if len(raw_text) > settings.max_raw_text_chars:
        raw_text = raw_text[: settings.max_raw_text_chars]

    existing_id = repository.get_existing_completed_product_by_url(data.source_url)
    if existing_id:
        return GenerateResponse(
            success=True,
            message="Product already generated in DB, skipping AI",
            product_id=existing_id,
            vendor=data.vendor,
            text_length=len(raw_text),
        )

    product = RawProductData(vendor=data.vendor, source_url=data.source_url, raw_page_text=raw_text)
    product_id = repository.save_raw_product(product)
    generate_ai_task.delay(product_id)
    return GenerateResponse(
        success=True,
        message="Product queued for AI generation",
        product_id=product_id,
        vendor=data.vendor,
        text_length=len(raw_text),
    )


@router.get("/status/{product_id}", response_model=StatusResponse)
def get_status(product_id: str) -> StatusResponse:
    """Return current generation status and generated data when available."""

    ai_data = repository.get_ai_product(product_id)
    if ai_data:
        return StatusResponse(status=ProductStatus.COMPLETE, data=ai_data)

    raw_doc = repository.get_raw_document(product_id)
    if raw_doc:
        status = ProductStatus(raw_doc.get("status", ProductStatus.PROCESSING.value))
        return StatusResponse(status=status, error=raw_doc.get("error_message"))

    raise HTTPException(status_code=404, detail="Product not found")


@router.post("/publish/{product_id}")
def publish_product(product_id: str, request: Request) -> dict:
    """Publish a completed AI product to Zoho or return a dry-run payload."""

    rate_limiter.check(
        client_key(request),
        LimitPolicy("publish", settings.rate_limit_publish_per_minute, 60),
    )
    ai_data = repository.get_ai_product(product_id)
    if not ai_data:
        raise HTTPException(status_code=404, detail="AI product not ready or not found")
    result = publisher.publish(ai_data)
    return {"success": True, "result": result}
