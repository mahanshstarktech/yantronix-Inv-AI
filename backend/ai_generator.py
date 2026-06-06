"""Compatibility wrapper for the Gemini product generator service."""

from app.services.ai_service import AIGenerationError, AIUsageLimiter, GeminiProductGenerator, get_product_generator


def generate_ai_content(product: dict) -> dict:
    """Generate an AI product listing and return a plain dictionary."""

    return get_product_generator().generate(product).as_mongo()


__all__ = ["AIGenerationError", "AIUsageLimiter", "GeminiProductGenerator", "generate_ai_content"]
