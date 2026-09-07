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
from rapidfuzz import fuzz

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

# Fuzzy similarity threshold (0–100).  82 catches typo/OCR near-misses while
# avoiding false positives from product text that legitimately mentions quartz.
FUZZ_THRESHOLD = 82

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ImageScanResult:
    url: str                      # original vendor URL
    flagged: bool = False         # True  → watermark detected (show red)
    matches: list[str] = field(default_factory=list)   # which keywords matched
    ocr_texts: list[str] = field(default_factory=list) # all text detected by OCR
    error: Optional[str] = None  # non-None → image could not be downloaded/scanned


# ── Lazy EasyOCR reader ───────────────────────────────────────────────────────

_reader = None  # initialised on first use

def _get_reader():
    """Return the EasyOCR Reader singleton, creating it on first call."""
    global _reader
    if _reader is None:
        try:
            import easyocr  # type: ignore
            logger.info("Initialising EasyOCR Reader (first call — may take ~10–20 s)…")
            _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            logger.info("EasyOCR Reader ready.")
        except Exception as exc:
            logger.error("Failed to initialise EasyOCR: %s", exc)
            raise RuntimeError(f"EasyOCR unavailable: {exc}") from exc
    return _reader


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

    def scan_url(self, url: str) -> ImageScanResult:
        """Download one image, OCR it, return a flagged/clean result."""
        result = ImageScanResult(url=url)
        try:
            resp = requests.get(url, headers=_DOWNLOAD_HEADERS, timeout=15)
            resp.raise_for_status()
            image_bytes = resp.content
        except Exception as exc:
            result.error = f"Download failed: {exc}"
            return result

        try:
            reader = _get_reader()
            # EasyOCR accepts bytes directly
            ocr_output = reader.readtext(image_bytes, detail=1)
        except Exception as exc:
            result.error = f"OCR failed: {exc}"
            return result

        texts: list[str] = []
        matched_keywords: list[str] = []

        for (_bbox, text, _conf) in ocr_output:
            cleaned = text.strip().lower()
            if not cleaned:
                continue
            texts.append(text)
            for keyword in WATERMARK_KEYWORDS:
                score = fuzz.partial_ratio(cleaned, keyword)
                if score >= FUZZ_THRESHOLD:
                    if keyword not in matched_keywords:
                        matched_keywords.append(keyword)
                    logger.debug("Watermark match: '%s' ~ '%s' (score=%d)", text, keyword, score)

        result.ocr_texts = texts
        result.matches = matched_keywords
        result.flagged = len(matched_keywords) > 0
        return result

    def scan_all(self, urls: list[str]) -> list[ImageScanResult]:
        """Scan a list of image URLs sequentially. Returns results in same order."""
        results: list[ImageScanResult] = []
        for url in urls:
            logger.info("Scanning image: %s", url)
            results.append(self.scan_url(url))
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
