"""Compatibility wrapper for the prompt builder service."""

from app.core.config import settings
from app.services.prompt_builder import build_ai_prompt as _build_ai_prompt


def build_ai_prompt(product: dict) -> str:
    """Build the canonical bounded AI prompt."""

    return _build_ai_prompt(product, settings.max_raw_text_chars)


__all__ = ["build_ai_prompt"]
