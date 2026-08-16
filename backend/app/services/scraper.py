"""Supplier scraping and text-cleaning services."""

from __future__ import annotations

import json
import re
import unicodedata

import requests
import cloudscraper
from bs4 import BeautifulSoup
from fastapi import HTTPException
from pydantic import HttpUrl

from app.core.config import settings


class VendorDetector:
    """Detect supported supplier vendors from product URLs."""

    @staticmethod
    def detect(url: HttpUrl) -> str:
        """Return the canonical vendor key or raise HTTP 400 for unsupported hosts."""

        host = str(url.host)
        if "quartzcomponents.com" in host:
            return "quartz"
        if "robu.in" in host:
            return "robu"
        return "custom"


class HtmlTextExtractor:
    """Convert noisy HTML pages into safe plain text for human/AI review."""

    _NOISE_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg", "form"]

    @classmethod
    def html_to_text(cls, html: str) -> str:
        """Remove page chrome and extract visible text with normalized whitespace.

        For JS-rendered pages (like Robu.in's Next.js frontend) that return
        an almost empty HTML body, this falls back to parsing structured
        JSON-LD Product schema blocks embedded by the server at render time.
        """
        # --- Primary: try JSON-LD Product schema first (works for Next.js / SSR sites) ---
        jsonld_text = cls._extract_jsonld_product_text(html)
        if jsonld_text and len(jsonld_text) >= 100:
            return jsonld_text

        # --- Fallback: standard DOM text extraction ---
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(cls._NOISE_TAGS):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @staticmethod
    def _extract_jsonld_product_text(html: str) -> str:
        """Extract rich product text from JSON-LD schema.org/Product blocks.

        Many modern e-commerce sites (especially Next.js / Nuxt / headless)
        inject structured data server-side even though the visible DOM is
        empty until JavaScript hydrates. This gives us product data without
        needing a headless browser.
        """
        blocks = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        )

        for raw_block in blocks:
            try:
                data = json.loads(raw_block.strip())
            except (json.JSONDecodeError, ValueError):
                continue

            # Handle both a single object and a @graph array
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                schema_type = item.get("@type", "")
                if isinstance(schema_type, list):
                    is_product = "Product" in schema_type
                else:
                    is_product = schema_type == "Product"

                if not is_product:
                    continue

                # We found a Product schema — extract all useful fields
                lines: list[str] = []

                name = item.get("name", "")
                if name:
                    lines.append(f"Product Name: {name}")

                brand = item.get("brand", {})
                brand_name = brand.get("name", "") if isinstance(brand, dict) else str(brand)
                if brand_name:
                    lines.append(f"Brand: {brand_name}")

                sku = item.get("sku", "") or item.get("productID", "")
                if sku:
                    lines.append(f"SKU / Product ID: {sku}")

                gtin = item.get("gtin", "") or item.get("gtin13", "") or item.get("gtin8", "")
                if gtin:
                    lines.append(f"GTIN/Barcode: {gtin}")

                description = item.get("description", "")
                if description:
                    lines.append(f"Description: {description}")

                # Price / offer info
                offers = item.get("offers", {})
                if isinstance(offers, dict):
                    price = offers.get("price", "")
                    currency = offers.get("priceCurrency", "INR")
                    availability = offers.get("availability", "")
                    if price:
                        lines.append(f"Selling Price: {price} {currency}")
                    if availability:
                        avail_label = availability.split("/")[-1]  # e.g. "InStock"
                        lines.append(f"Availability: {avail_label}")

                    # MRP / list price
                    price_spec = offers.get("priceSpecification", {})
                    if isinstance(price_spec, dict):
                        mrp = price_spec.get("price", "")
                        if mrp:
                            lines.append(f"MRP / List Price: {mrp} {currency}")
                elif isinstance(offers, list):
                    for offer in offers:
                        price = offer.get("price", "")
                        currency = offer.get("priceCurrency", "INR")
                        if price:
                            lines.append(f"Selling Price: {price} {currency}")
                            break

                # Category breadcrumbs (sometimes in the Product schema)
                category = item.get("category", "")
                if category:
                    lines.append(f"Category: {category}")

                # Images
                images = item.get("image", [])
                if isinstance(images, str):
                    images = [images]
                if images:
                    lines.append(f"Product Images: {', '.join(images[:5])}")

                # Weight / dimensions
                weight = item.get("weight", {})
                if isinstance(weight, dict):
                    w_val = weight.get("value", "")
                    w_unit = weight.get("unitCode", "")
                    if w_val:
                        lines.append(f"Weight: {w_val} {w_unit}")

                # Ratings
                rating = item.get("aggregateRating", {})
                if isinstance(rating, dict):
                    rv = rating.get("ratingValue", "")
                    rc = rating.get("reviewCount", "")
                    if rv:
                        lines.append(f"Rating: {rv}/5 ({rc} reviews)")

                # Reviews (top 3 for context)
                reviews = item.get("review", [])
                if isinstance(reviews, list):
                    for review in reviews[:3]:
                        body = review.get("reviewBody", "").strip()
                        if body and len(body) > 5:
                            lines.append(f"Customer Review: {body}")

                if lines:
                    return "\n".join(lines)

        return ""

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Remove invalid/control characters while preserving readable newlines."""

        text = text.replace("\x00", "").replace("\ufffd", "")
        text = text.encode("utf-8", errors="ignore").decode("utf-8")
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class ScraperService:
    """Fetch supplier pages and return sanitized text plus vendor metadata."""

    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, detector: VendorDetector | None = None, extractor: HtmlTextExtractor | None = None) -> None:
        self._detector = detector or VendorDetector()
        self._extractor = extractor or HtmlTextExtractor()
        # cloudscraper handles Cloudflare JS-challenge / 403 bot protection
        self._scraper = cloudscraper.create_scraper()

    def extract(self, url: HttpUrl) -> dict:
        """Fetch a product page and return `{raw_text, vendor, source_url, text_length}`."""

        try:
            response = self._scraper.get(str(url), headers=self._HEADERS, timeout=settings.scrape_timeout_seconds)
        except requests.exceptions.RequestException as exc:
            raise HTTPException(status_code=408, detail=f"Request timed out or failed: {exc}") from exc

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to fetch page — site returned {response.status_code}")

        raw_text = self._extractor.sanitize_text(self._extractor.html_to_text(response.text))
        if len(raw_text) < settings.min_scraped_text_chars:
            raise HTTPException(
                status_code=422,
                detail="Page returned too little text - it may be behind a login or JS-rendered.",
            )

        vendor = self._detector.detect(url)
        return {
            "raw_text": raw_text,
            "vendor": vendor,
            "source_url": str(url),
            "text_length": len(raw_text),
        }


scraper_service = ScraperService()
