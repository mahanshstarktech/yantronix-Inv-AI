"""AI generation service for product listings."""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from google import genai
from google.genai import types

from app.core.config import settings
from app.models.product import AIProduct
from app.services.prompt_builder import build_ai_prompt


SYSTEM_INSTRUCTION = (
    "You are a professional electronics product data extractor and e-commerce listing generator. "
    "You generate complete, structured, SEO-optimized product listings in strict JSON format only. "
    "Do NOT include any explanation, markdown, or text outside the JSON object. "
    "All string values in JSON must be on one line; use \\n escape sequences for line breaks."
)


class AIGenerationError(RuntimeError):
    """Raised when the AI provider call or JSON validation fails."""


class AIUsageLimiter:
    """Guardrail for prompt size before spending tokens on an AI call."""

    def __init__(self, max_raw_text_chars: int) -> None:
        self.max_raw_text_chars = max_raw_text_chars

    def trim_raw_text(self, raw_text: str) -> str:
        """Return text capped to the configured prompt budget."""

        return raw_text[: self.max_raw_text_chars]


class GeminiProductGenerator:
    """Generate and validate product listings using Gemini."""

    def __init__(self, api_key: str, limiter: AIUsageLimiter | None = None) -> None:
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file and restart the worker.")
        self._client = genai.Client(api_key=api_key)
        self._limiter = limiter or AIUsageLimiter(settings.max_raw_text_chars)

    def generate(self, product: Dict[str, Any]) -> AIProduct:
        """Generate an AI product and validate it against the `AIProduct` schema."""

        limited_product = dict(product)
        limited_product["raw_page_text"] = self._limiter.trim_raw_text(product.get("raw_page_text", ""))
        prompt = build_ai_prompt(limited_product, max_raw_text_chars=settings.max_raw_text_chars)

        try:
            response = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=settings.gemini_temperature,
                    max_output_tokens=settings.gemini_max_output_tokens,
                ),
            )
        except Exception as exc:
            raise AIGenerationError(f"Gemini API call failed: {exc}") from exc

        data = self._parse_json(response.text or "")
        try:
            return AIProduct.model_validate(data)
        except Exception as exc:
            raise AIGenerationError(f"AI output did not match the product schema: {exc}") from exc

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse the first JSON object from a model response."""

        cleaned = re.sub(r"```json|```", "", text).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise AIGenerationError(f"AI response did not contain JSON: {cleaned[:500]}")

        raw_json = match.group()
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            try:
                return json.loads(self._escape_control_chars(raw_json))
            except json.JSONDecodeError as exc:
                raise AIGenerationError(f"AI response JSON could not be parsed: {exc}") from exc

    @staticmethod
    def _escape_control_chars(text: str) -> str:
        """Escape literal control characters inside JSON strings."""

        result: list[str] = []
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == "\\" and in_string:
                result.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string and ch == "\n":
                result.append("\\n")
            elif in_string and ch == "\r":
                result.append("\\r")
            elif in_string and ch == "\t":
                result.append("\\t")
            elif in_string and ord(ch) < 0x20:
                result.append(" ")
            else:
                result.append(ch)
        return "".join(result)


def get_product_generator() -> GeminiProductGenerator:
    """Factory used by workers to avoid constructing Gemini at web import time."""

    return GeminiProductGenerator(settings.gemini_api_key)
