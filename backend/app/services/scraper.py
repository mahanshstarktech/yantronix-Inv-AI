"""Supplier scraping and text-cleaning services."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from urllib.parse import quote_plus

import requests
import cloudscraper
from bs4 import BeautifulSoup
from fastapi import HTTPException
from pydantic import HttpUrl

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    """Fetch supplier pages and return sanitized text plus vendor metadata.

    Fetch strategy (tried in order):
    1. ScraperAPI  — if SCRAPER_API_KEY env var is set. Routes through rotating
                     residential proxies, bypasses Cloudflare ASN blocks.
    2. cloudscraper — handles Cloudflare JS-challenge pages. Works from
                      residential IPs (e.g. local dev) but not from datacenter
                      IPs (Render, Railway, Heroku) which Cloudflare ASN-blocks.
    3. plain requests — fast fallback for sites with no bot protection.
    """

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
        self._cloudscraper = cloudscraper.create_scraper()

    # ── Fetch helpers ──────────────────────────────────────────────────────────

    def _fetch_via_scraper_api(self, url: str) -> requests.Response:
        """Fetch through ScraperAPI's rotating residential proxy pool.

        ScraperAPI handles Cloudflare, JS-rendering, and proxy rotation.
        Requires SCRAPER_API_KEY env var (free tier: 5,000 req/month).
        """
        api_key = settings.scraper_api_key
        proxy_url = f"http://api.scraperapi.com?api_key={api_key}&url={quote_plus(url)}&render=false"
        logger.info("Fetching via ScraperAPI: %s", url)
        return requests.get(proxy_url, timeout=settings.scrape_timeout_seconds)

    def _fetch_via_cloudscraper(self, url: str) -> requests.Response:
        """Fetch via cloudscraper (bypasses Cloudflare JS challenges).

        Works from residential IPs. Datacenter IPs may still be ASN-blocked.
        """
        logger.info("Fetching via cloudscraper: %s", url)
        return self._cloudscraper.get(url, headers=self._HEADERS, timeout=settings.scrape_timeout_seconds)

    def _fetch_via_requests(self, url: str) -> requests.Response:
        """Plain requests fetch — fast for sites with no bot protection."""
        logger.info("Fetching via requests: %s", url)
        return requests.get(url, headers=self._HEADERS, timeout=settings.scrape_timeout_seconds)

    def _fetch(self, url: str) -> requests.Response:
        """Run the fetch strategy chain, returning the first successful response."""

        last_exc: Exception | None = None

        # Strategy 1: ScraperAPI (if configured) — best for Cloudflare/datacenter
        if settings.scraper_api_key:
            try:
                resp = self._fetch_via_scraper_api(url)
                if resp.status_code == 200:
                    logger.info("ScraperAPI succeeded for %s", url)
                    return resp
                logger.warning("ScraperAPI returned %d for %s", resp.status_code, url)
            except requests.exceptions.RequestException as exc:
                logger.warning("ScraperAPI fetch failed: %s", exc)
                last_exc = exc

        # Strategy 2: cloudscraper (good for JS-challenge Cloudflare + residential IP)
        try:
            resp = self._fetch_via_cloudscraper(url)
            if resp.status_code == 200:
                logger.info("cloudscraper succeeded for %s", url)
                return resp
            logger.warning("cloudscraper returned %d for %s", resp.status_code, url)
            # Save the last non-200 response to surface the real status code
            last_bad_status = resp.status_code
        except requests.exceptions.RequestException as exc:
            logger.warning("cloudscraper fetch failed: %s", exc)
            last_exc = exc
            last_bad_status = 0

        # Strategy 3: plain requests (fastest, for unprotected sites)
        try:
            resp = self._fetch_via_requests(url)
            if resp.status_code == 200:
                logger.info("plain requests succeeded for %s", url)
                return resp
            last_bad_status = resp.status_code
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            last_bad_status = 0

        # All strategies failed
        if last_exc and last_bad_status == 0:
            raise HTTPException(status_code=408, detail=f"Request timed out or failed: {last_exc}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch page — site returned {last_bad_status}"
            + (" (Cloudflare-protected; add SCRAPER_API_KEY env var to bypass)" if last_bad_status == 403 and not settings.scraper_api_key else ""),
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def extract(self, url: HttpUrl) -> dict:
        """Fetch a product page and return `{raw_text, vendor, source_url, text_length}`."""

        response = self._fetch(str(url))

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
