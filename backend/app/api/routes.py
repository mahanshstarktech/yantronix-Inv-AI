"""HTTP routes for the product-listing workflow."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request
from pydantic import HttpUrl
from bson import ObjectId
from app.core.config import settings
from app.core.rate_limiter import LimitPolicy, client_key, rate_limiter
from app.models.product import (
    CategorySuggestRequest,
    CategorySuggestResponse,
    CategoryTreeResponse,
    ExtractRequest,
    ExtractResponse,
    GenerateRequest,
    GenerateResponse,
    ImageScanRequest,
    ImageScanResponse,
    ImageScanResultModel,
    ProductStatus,
    PublishRequest,
    RawProductData,
    StatusResponse,
)
from app.repositories.product_repository import repository
from app.services.scraper import HtmlTextExtractor, scraper_service
from app.services.publisher import publisher
from app.services.image_scanner import image_scanner, ZohoImageUploader
from app.services.zoho_categories import zoho_category_service
from app.services.zoho_brands import zoho_brand_service
from app.services.zoho_custom_fields import zoho_custom_field_service
from app.services.category_suggester import get_category_suggester
from app.workers.tasks import generate_ai_task

router = APIRouter()


# ── Scraping ──────────────────────────────────────────────────────────────────

@router.post("/extract", response_model=ExtractResponse)
def extract_website(data: ExtractRequest, request: Request) -> ExtractResponse:
    """Fetch a supplier URL and return sanitized text + product image URLs."""

    rate_limiter.check(
        client_key(request),
        LimitPolicy("extract", settings.rate_limit_extract_per_minute, 60),
    )
    result = scraper_service.extract(data.url)
    return ExtractResponse(**result)


# ── Image Scanning ───────────────────────────────────────────────────────────

@router.post("/images/scan", response_model=ImageScanResponse)
def scan_images(data: ImageScanRequest, request: Request) -> ImageScanResponse:
    """Run EasyOCR watermark detection on a list of image URLs.

    Downloads each image on the server (Render) and scans it with EasyOCR.
    Returns per-image flagged/clean results so the frontend can display a
    colour-coded review grid. Flagged images have red borders; clean images
    have green borders. The user can toggle any image before approving.

    Note: EasyOCR model weights (~100 MB) are loaded on first call.
    Subsequent calls are fast. Expect ~1–3 seconds per image on Render CPU.
    """
    rate_limiter.check(
        client_key(request),
        LimitPolicy("extract", settings.rate_limit_extract_per_minute, 60),
    )

    if len(data.urls) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 images per scan.")

    raw_results = image_scanner.scan_all(data.urls)
    results = [
        ImageScanResultModel(
            url=r.url,
            flagged=r.flagged,
            matches=r.matches,
            ocr_texts=r.ocr_texts,
            error=r.error,
        )
        for r in raw_results
    ]
    flagged = sum(1 for r in results if r.flagged)
    return ImageScanResponse(
        results=results,
        total=len(results),
        flagged_count=flagged,
        clean_count=len(results) - flagged,
    )


# ── AI Generation ─────────────────────────────────────────────────────────────

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


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=CategoryTreeResponse)
def get_categories(refresh: bool = False) -> CategoryTreeResponse:
    """Fetch the full Zoho Commerce category tree (cached 10 min).

    Pass ?refresh=true to force a cache bust.
    Returns both a tree (for the hierarchical dropdown) and a flat list
    (for AI suggestion matching).
    """
    try:
        return zoho_category_service.get_categories(force_refresh=refresh)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/categories/suggest", response_model=CategorySuggestResponse)
def suggest_category(data: CategorySuggestRequest, request: Request) -> CategorySuggestResponse:
    """Use Gemini to suggest the best Zoho category for a product.

    Accepts the product's title, tags, and keywords alongside the flat
    categories list and returns the AI-picked category_id, name, confidence,
    and reasoning string.
    """
    rate_limiter.check(
        client_key(request),
        LimitPolicy("ai-calls", settings.rate_limit_ai_calls_per_hour, 3600),
    )
    try:
        return get_category_suggester().suggest(data)
    except Exception as exc:
        # Non-fatal — return empty suggestion so the UI can still show the dropdown
        return CategorySuggestResponse(reasoning=f"Suggestion failed: {str(exc)[:100]}")


# ── Brands ────────────────────────────────────────────────────────────────────

@router.get("/brands")
def get_brands(refresh: bool = False) -> dict:
    """Fetch all Zoho Commerce brands (cached 10 min)."""
    try:
        brands = zoho_brand_service.get_brands(force_refresh=refresh)
        return {"brands": brands, "total": len(brands)}
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/zoho-custom-fields")
def get_zoho_custom_fields(refresh: bool = False) -> dict:
    """Fetch all Zoho Commerce product custom field definitions.

    Call this once to find the customfield_id values for 'Company Division'
    and 'Ref Link', then paste them into your .env file as:
      ZOHO_CF_COMPANY_DIVISION_ID=<id>
      ZOHO_CF_REF_LINK_ID=<id>
    """
    try:
        fields = zoho_custom_field_service.get_custom_fields(force_refresh=refresh)
        return {
            "fields": fields,
            "total": len(fields),
            "configured": {
                "ZOHO_CF_COMPANY_DIVISION_ID": settings.zoho_cf_company_division_id or "NOT SET",
                "ZOHO_CF_REF_LINK_ID": settings.zoho_cf_ref_link_id or "NOT SET",
            },
            "tip": "Copy the customfield_id values above into your .env file, then restart the backend.",
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ── Publishing ────────────────────────────────────────────────────────────────

@router.post("/publish/{product_id}")
def publish_product(
    product_id: str,
    request: Request,
    body: PublishRequest = Body(default_factory=PublishRequest),
) -> dict:
    """Publish a completed AI product to Zoho or return a dry-run payload.

    Optionally accepts a JSON body:
        {"category_id": "123456789", "approved_image_urls": ["https://..."]}

    After the product is created in Zoho, any approved_image_urls are
    downloaded from the vendor and re-uploaded to Zoho via multipart upload
    so no vendor CDN links appear in the store.
    """

    import datetime
    
    rate_limiter.check(
        client_key(request),
        LimitPolicy("publish", settings.rate_limit_publish_per_minute, 60),
    )
    ai_data = repository.get_ai_product(product_id)
    if not ai_data:
        raise HTTPException(status_code=404, detail="AI product not ready or not found")

    raw_doc = repository.raw_products.find_one({"_id": ObjectId(product_id)})
    if not raw_doc:
        raise HTTPException(status_code=404, detail="Raw product not found")
        
    source_url = raw_doc.get("source_url", "")
    
    # Brand matching: pull AI-extracted brand and find best Zoho match
    ai_brand_name = ai_data.get("brand", "")
    try:
        matched_brand = zoho_brand_service.find_best_match(ai_brand_name)
        
        # If celery worker just created the brand, it might not be in our FastAPI process cache yet.
        # So if we get Generic but ai_brand_name is specific, invalidate cache and retry.
        if matched_brand.get("name") == "Generic" and ai_brand_name and ai_brand_name.lower() != "generic":
            zoho_brand_service.invalidate_cache()
            matched_brand = zoho_brand_service.find_best_match(ai_brand_name)

        brand_name = matched_brand.get("name", "Generic")
        brand_id = matched_brand.get("brand_id", "")
    except Exception:
        brand_name = "Generic"
        brand_id = ""
    
    # Calculate Year string like "2627"
    now = datetime.datetime.now()
    year1 = str(now.year)[-2:]
    year2 = str(now.year + 1)[-2:]
    year_str = f"{year1}{year2}"
    
    max_retries = 5
    result = None
    for attempt in range(max_retries):
        if attempt == 0:
            sku_str = ai_data.get("sku")
            if not sku_str:
                seq = repository.get_next_sku_sequence(f"sku_seq_{now.year}")
                sku_str = f"YTX{year_str}{seq:04d}"
        else:
            seq = repository.get_next_sku_sequence(f"sku_seq_{now.year}")
            sku_str = f"YTX{year_str}{seq:04d}"

        try:
            result = publisher.publish(
                ai_data, 
                category_id=body.category_id, 
                source_url=source_url, 
                generated_sku=sku_str,
                brand_name=brand_name,
                brand_id=brand_id,
            )
            break  # Success!
        except Exception as exc:
            error_msg = str(exc)
            # If Zoho complains about the SKU already existing, and we have retries left, loop again
            if attempt < max_retries - 1 and "SKU" in error_msg and "already exists" in error_msg:
                continue
            raise HTTPException(status_code=400, detail=f"Failed to publish to Zoho: {error_msg}")

    # ── Upload approved images to Zoho (download from vendor + re-upload) ───────────
    image_upload_results: list[dict] = []
    zoho_product_id = result.get("zoho_product_id", "") if result else ""

    if body.approved_image_urls and zoho_product_id and not settings.test_mode:
        try:
            from app.zoho import ZohoAuth
            auth = ZohoAuth()
            uploader = ZohoImageUploader(auth)
            image_upload_results = uploader.upload_batch(zoho_product_id, body.approved_image_urls)
            import logging as _logging
            _logging.getLogger(__name__).info(
                "Uploaded %d/%d images to Zoho product %s",
                sum(1 for r in image_upload_results if r.get("success")),
                len(image_upload_results),
                zoho_product_id,
            )
        except Exception as exc:
            # Image upload failure must NOT fail the overall publish — log and continue
            import logging as _logging
            _logging.getLogger(__name__).warning("Image upload batch failed: %s", exc)
    elif body.approved_image_urls and settings.test_mode:
        image_upload_results = [
            {"url": u, "success": True, "zoho_image": {"image_id": f"TEST-IMG-{i}"}, "test_mode": True}
            for i, u in enumerate(body.approved_image_urls)
        ]

    # Save audit trail (best-effort — never fail the request because of this)
    repository.save_publish_result(
        raw_product_id=product_id,
        result=result,
        category_id=body.category_id,
        test_mode=settings.test_mode,
    )

    return {
        "success": True,
        "zoho_product_id": zoho_product_id,
        "zoho_id": zoho_product_id,  # kept for frontend compat
        "category_id": body.category_id,
        "result": result,
        "image_uploads": image_upload_results,
    }


# ── Health & Utilities ────────────────────────────────────────────────────────

@router.get("/health")
def health_check() -> dict:
    """Return connectivity status for MongoDB, Redis, and Zoho OAuth."""

    import redis as redis_lib
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError

    checks: dict = {}

    # MongoDB
    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        checks["mongodb"] = "ok"
    except Exception as exc:
        checks["mongodb"] = f"error: {str(exc)[:80]}"

    # Redis
    try:
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=1)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {str(exc)[:80]}"

    # Zoho OAuth (token refresh test)
    try:
        from app.zoho import ZohoAuth
        auth = ZohoAuth()
        auth.get_access_token()
        checks["zoho_oauth"] = "ok"
    except Exception as exc:
        checks["zoho_oauth"] = f"error: {str(exc)[:80]}"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


@router.get("/products")
def list_products(limit: int = 50) -> dict:
    """List all AI-generated products (newest first) for a future dashboard."""

    products = repository.get_all_products(limit=min(limit, 200))
    return {"products": products, "total": len(products)}
