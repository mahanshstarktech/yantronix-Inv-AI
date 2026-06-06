"""Compatibility wrapper for Zoho publishing services."""

from app.services.publisher import HtmlSanitizer, ZohoPayloadBuilder, ZohoPublisher, publisher


def build_zoho_payload(ai_product: dict) -> dict:
    """Build a Zoho Commerce payload from an AI product dictionary."""

    return ZohoPayloadBuilder().build(ai_product)


def publish_to_zoho(ai_product: dict) -> dict:
    """Publish or dry-run a Zoho Commerce product payload."""

    return publisher.publish(ai_product)


__all__ = ["HtmlSanitizer", "ZohoPayloadBuilder", "ZohoPublisher", "build_zoho_payload", "publish_to_zoho"]
