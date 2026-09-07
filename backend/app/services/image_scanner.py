"""
image_scanner.py
Vendor-watermark detector, product-image scraper, and Zoho image uploader.

Pipeline (called from the /images/scan-and-upload route):
1. ImageExtractor   — parses a vendor HTML page for all product image URLs
2. ImageScannerService — downloads each image, runs EasyOCR on the backend
                         (CPU, no GPU needed — works fine on Render),
                         fuzzy-matches against vendor keyword list
3. ZohoImageUploader — for images the user approves, downloads the bytes and
                       POSTs them to Zoho Commerce as multipart/form-data so
                       no vendor CDN links are ever stored in our store.

EasyOCR note
------------
EasyOCR downloads its model weights (~100 MB) on first import. On Render this
happens during the first request; subsequent requests use the cached weights
from the build layer. We initialise the Reader lazily (on first scan call) so
app startup is not blocked.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Watermark keywords ────────────────────────────────────────────────────────

WATERMARK_KEYWORDS: list[str] = [
    "quartz components",
    "quartzcomponents",
    "quartz",
    "robu",
    "robu.in",
    "robu india",
]

    "robu india",
]

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ImageScanResult:
    url: str                      # original vendor URL
    flagged: bool = False         # True  → watermark detected (show red)
    matches: list[str] = field(default_factory=list)   # which keywords matched
    ocr_texts: list[str] = field(default_factory=list) # all text detected by OCR
    error: Optional[str] = None  # non-None → image could not be downloaded/scanned


# ── Pydantic Schemas for Gemini ───────────────────────────────────────────────

class ImageWatermarkScan(BaseModel):
    has_watermark: bool
    matched_keywords: list[str]

class BatchWatermarkResponse(BaseModel):
    results: list[ImageWatermarkScan]


# ── ImageExtractor ─────────────────────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

class ImageExtractor:
    """
    Extract product image URLs from vendor HTML pages.

    Attempts (in order):
    1. JSON-LD Product schema   – most reliable for modern e-commerce
    2. Open Graph og:image      – social/SEO meta tags
    3. <img> tags               – classic DOM images
    4. data-src / data-lazy-src – lazy-loaded images
    """

    @classmethod
    def extract(cls, html: str, base_url: str = "") -> list[str]:
        """Return a deduplicated list of absolute image URLs from vendor HTML."""
        urls: list[str] = []

        urls.extend(cls._from_jsonld(html))
        urls.extend(cls._from_og(html))
        urls.extend(cls._from_img_tags(html, base_url))

        # Deduplicate preserving order, keep only recognised image extensions
        seen: set[str] = set()
        result: list[str] = []
        for u in urls:
            u = u.strip()
            if not u or u in seen:
                continue
            parsed = urlparse(u)
            ext = parsed.path.rsplit(".", 1)[-1].lower()
            if f".{ext}" not in _IMAGE_EXTS and "?" not in u:
                # allow URLs without extensions only when they have a path
                # (some CDNs serve images without .jpg extension)
                if not parsed.path or parsed.path == "/":
                    continue
            seen.add(u)
            result.append(u)
        return result[:20]  # cap at 20 to avoid huge payloads

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _from_jsonld(html: str) -> list[str]:
        import json
        urls: list[str] = []
        blocks = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        )
        for raw in blocks:
            try:
                data = json.loads(raw.strip())
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                t = item.get("@type", "")
                if "Product" not in (t if isinstance(t, list) else [t]):
                    continue
                images = item.get("image", [])
                if isinstance(images, str):
                    images = [images]
                for img in images:
                    if isinstance(img, dict):
                        img = img.get("url", "")
                    if img and img.startswith("http"):
                        urls.append(img)
        return urls

    @staticmethod
    def _from_og(html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for tag in soup.find_all("meta", property=re.compile(r"og:image", re.I)):
            content = tag.get("content", "")
            if content and content.startswith("http"):
                urls.append(content)
        return urls

    @staticmethod
    def _from_img_tags(html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for tag in soup.find_all("img"):
            for attr in ("src", "data-src", "data-lazy-src", "data-original"):
                src = tag.get(attr, "")
                if not src or src.startswith("data:"):
                    continue
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/") and base_url:
                    src = urljoin(base_url, src)
                if src.startswith("http"):
                    urls.append(src)
                    break
        return urls


# ── ImageScannerService ────────────────────────────────────────────────────────

_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; YantronixBot/1.0)",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


class ImageScannerService:
    """
    Download images and run EasyOCR watermark detection on the Render server.
    """

    def scan_all(self, urls: list[str]) -> list[ImageScanResult]:
        """Download images and scan them in a single batch using Gemini."""
        if not urls:
            return []

        # Download all images
        images_data = []
        results: list[ImageScanResult] = []
        
        for url in urls:
            result = ImageScanResult(url=url)
            try:
                resp = requests.get(url, headers=_DOWNLOAD_HEADERS, timeout=15)
                resp.raise_for_status()
                images_data.append((url, resp.content))
            except Exception as exc:
                result.error = f"Download failed: {exc}"
                images_data.append((url, None))
            results.append(result)

        valid_images = [(u, b) for u, b in images_data if b is not None]
        if not valid_images:
            return results

        # Process valid images with Gemini in one batch
        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            
            prompt_parts = [
                f"You are a watermark detection AI. I am providing {len(valid_images)} product images in order. "
                f"For each image, check if it contains any of these specific watermark texts: {', '.join(WATERMARK_KEYWORDS)}. "
                "Look closely at the corners, background, and center of the images for these vendor names. "
                "Reply with a JSON object containing a 'results' array with exactly one entry for each image IN THE EXACT SAME ORDER."
            ]
            
            for _, img_bytes in valid_images:
                prompt_parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt_parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BatchWatermarkResponse,
                    temperature=0.1,
                ),
            )

            if not response.text:
                raise RuntimeError("Empty response from Gemini")
                
            batch_result = BatchWatermarkResponse.model_validate_json(response.text)
            
            if len(batch_result.results) != len(valid_images):
                logger.warning(
                    f"Gemini returned {len(batch_result.results)} results, expected {len(valid_images)}"
                )
            
            # Map results back
            valid_idx = 0
            for i, (url, b) in enumerate(images_data):
                if b is None:
                    continue  # already has error
                if valid_idx < len(batch_result.results):
                    scan = batch_result.results[valid_idx]
                    results[i].flagged = scan.has_watermark
                    results[i].matches = scan.matched_keywords
                    results[i].ocr_texts = [] # Not used by Gemini
                else:
                    results[i].error = "Gemini scan failed: Missing result in batch"
                valid_idx += 1

        except Exception as exc:
            logger.error("Gemini OCR failed: %s", exc)
            for res in results:
                if not res.error:
                    res.error = f"AI scan failed: {exc}"
                    
        return results


# ── ZohoImageUploader ─────────────────────────────────────────────────────────


class ZohoImageUploader:
    """
    Download a vendor image by URL and upload it to Zoho Commerce.

    Zoho endpoint:
        POST /store/api/v1/products/{product_id}/images
        Content-Type: multipart/form-data
        Field name: file

    Returns the uploaded image's `image_id` string from Zoho's response,
    or raises on failure.
    """

    def __init__(self, auth) -> None:  # auth: ZohoAuth
        self._auth = auth

    def upload(self, product_id: str, image_url: str) -> dict:
        """
        Download `image_url` and upload to Zoho for `product_id`.
        Returns the Zoho image response dict (contains image_id, url, etc.)
        """
        from app.core.config import settings

        # 1. Download from vendor
        try:
            resp = requests.get(image_url, headers=_DOWNLOAD_HEADERS, timeout=20)
            resp.raise_for_status()
            image_bytes = resp.content
        except Exception as exc:
            raise ValueError(f"Could not download image {image_url}: {exc}") from exc

        # Guess filename from URL
        path = urlparse(image_url).path
        filename = path.rsplit("/", 1)[-1] or "image.jpg"
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]

        # 2. Upload to Zoho
        api_url = f"{settings.zoho_api_domain}/store/api/v1/products/{product_id}/images"

        # Auth headers WITHOUT Content-Type (requests sets it automatically for multipart)
        headers = self._auth.auth_headers()
        headers.pop("Content-Type", None)

        files = {
            "file": (filename, io.BytesIO(image_bytes), content_type),
        }

        upload_resp = requests.post(api_url, headers=headers, files=files, timeout=30)

        if upload_resp.status_code == 401:
            self._auth.invalidate()
            headers = self._auth.auth_headers()
            headers.pop("Content-Type", None)
            upload_resp = requests.post(api_url, headers=headers, files=files, timeout=30)

        if not upload_resp.ok:
            raise ValueError(
                f"Zoho image upload failed ({upload_resp.status_code}): "
                f"{upload_resp.text[:300]}"
            )

        data = upload_resp.json()
        # Zoho returns {"code": 0, "message": "success", "image": {...}}
        if str(data.get("code", -1)) not in ("0", "200"):
            raise ValueError(f"Zoho image upload error: {data}")

        return data.get("image", data)

    def upload_batch(self, product_id: str, image_urls: list[str]) -> list[dict]:
        """Upload multiple images; skip (log + continue) on per-image failure."""
        results: list[dict] = []
        for url in image_urls:
            try:
                result = self.upload(product_id, url)
                results.append({"url": url, "zoho_image": result, "success": True})
                logger.info("Uploaded image to Zoho: %s → %s", url, result.get("image_id"))
            except Exception as exc:
                logger.warning("Image upload failed for %s: %s", url, exc)
                results.append({"url": url, "error": str(exc), "success": False})
        return results


# ── Module-level singletons ───────────────────────────────────────────────────

image_extractor = ImageExtractor()
image_scanner = ImageScannerService()
