"""Compatibility entrypoint for `uvicorn main:app`.

The application is implemented in `app.main` to keep HTTP bootstrapping separate
from routes, services, models, and repositories.
"""

from app.main import app, create_app
from app.services.scraper import HtmlTextExtractor, VendorDetector

html_to_text = HtmlTextExtractor.html_to_text
sanitize_text = HtmlTextExtractor.sanitize_text
detect_vendors = VendorDetector.detect

__all__ = ["app", "create_app", "html_to_text", "sanitize_text", "detect_vendors"]
