"""AI-powered category suggester using Gemini.

Given a product's title, tags, and keywords alongside a list of Zoho category
names, asks Gemini to pick the single best-matching category.  Returns a
structured response with category_id, category_name, confidence, and reasoning
so the frontend can show the user why the AI picked what it picked.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.core.config import settings
from app.models.product import CategorySuggestRequest, CategorySuggestResponse

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are a product categorization expert for an Indian electronics e-commerce store. "
    "You must respond ONLY with a single valid JSON object — no explanation, no markdown. "
    "The JSON must contain exactly these fields: "
    "category_id (string), category_name (string), confidence (float 0.0–1.0), reasoning (string ≤ 80 chars)."
)


class CategorySuggester:
    """Use Gemini to suggest the best Zoho category for a product."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        self._client = genai.Client(api_key=api_key)

    def suggest(self, request: CategorySuggestRequest) -> CategorySuggestResponse:
        """Return the best matching category for the given product data."""

        if not request.categories:
            return CategorySuggestResponse(reasoning="No categories available to match against.")

        # Build a compact categories list for the prompt
        cat_lines = "\n".join(
            f"- id={c['category_id']} name={c['name']}" for c in request.categories
        )

        prompt = (
            f"Product Title: {request.product_title}\n"
            f"Tags: {', '.join(request.tags[:20])}\n"
            f"Keywords: {', '.join(request.seo_keywords[:15])}\n\n"
            f"Available Zoho Commerce Categories:\n{cat_lines}\n\n"
            "Select the SINGLE best matching category from the list above for this product. "
            "If nothing fits well, pick the closest general category. "
            "Respond ONLY with JSON: {\"category_id\": \"...\", \"category_name\": \"...\", "
            "\"confidence\": 0.0, \"reasoning\": \"...\"}."
        )

        try:
            response = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    temperature=0.1,  # low temperature for deterministic classification
                    max_output_tokens=256,
                ),
            )
        except Exception as exc:
            logger.warning("Gemini category suggestion failed: %s", exc)
            return CategorySuggestResponse(reasoning=f"AI call failed: {str(exc)[:100]}")

        return self._parse_response(response.text or "", request.categories)

    def _parse_response(
        self, text: str, categories: List[Dict[str, str]]
    ) -> CategorySuggestResponse:
        """Extract and validate the JSON response from Gemini."""

        cleaned = re.sub(r"```json|```", "", text).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.warning("Category suggestion response contained no JSON: %s", cleaned[:200])
            return CategorySuggestResponse(reasoning="AI returned no JSON.")

        try:
            data: Dict[str, Any] = json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.warning("Category suggestion JSON parse error: %s", exc)
            return CategorySuggestResponse(reasoning="AI returned invalid JSON.")

        category_id = str(data.get("category_id", "")).strip()
        category_name = str(data.get("category_name", "")).strip()
        confidence = float(data.get("confidence", 0.0))
        reasoning = str(data.get("reasoning", ""))[:120]

        # Validate that the returned category_id actually exists in our list
        valid_ids = {c["category_id"] for c in categories}
        if category_id not in valid_ids:
            # Try to find by name as fallback
            for cat in categories:
                if cat["name"].lower() == category_name.lower():
                    category_id = cat["category_id"]
                    break
            else:
                logger.warning("AI suggested unknown category_id=%s, ignoring.", category_id)
                return CategorySuggestResponse(reasoning=f"AI suggested unknown category: {category_name}")

        return CategorySuggestResponse(
            category_id=category_id,
            category_name=category_name,
            confidence=min(max(confidence, 0.0), 1.0),
            reasoning=reasoning,
        )


_suggester: Optional[CategorySuggester] = None


def get_category_suggester() -> CategorySuggester:
    """Return a singleton CategorySuggester instance."""
    global _suggester
    if _suggester is None:
        _suggester = CategorySuggester(settings.gemini_api_key)
    return _suggester
