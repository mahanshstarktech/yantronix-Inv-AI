"""Supplier scraping and text-cleaning services."""

from __future__ import annotations

import re
import unicodedata

import requests
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
        """Remove page chrome and extract visible text with normalized whitespace."""

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(cls._NOISE_TAGS):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

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

    def extract(self, url: HttpUrl) -> dict:
        """Fetch a product page and return `{raw_text, vendor, source_url, text_length}`."""

        try:
            response = requests.get(str(url), headers=self._HEADERS, timeout=settings.scrape_timeout_seconds)
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
