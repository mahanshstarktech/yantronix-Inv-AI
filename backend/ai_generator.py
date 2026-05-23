import json
import re
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import build_ai_prompt

# Load .env BEFORE reading any env var — must come first
load_dotenv()

# ── Guard: fail loudly at startup if the key is missing ─────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. "
        "Add it to your .env file and restart the Celery worker."
    )
 
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "You are a professional electronics product data extractor and "
    "e-commerce listing generator. You generate complete, structured, "
    "SEO-optimized product listings in strict JSON format only. "
    "Do NOT include any explanation, markdown, or text outside the JSON object. "
    "CRITICAL: All string values in the JSON must be on a single line. "
    "Never use literal newline characters inside a JSON string value. "
    "Use the escape sequence \\n if you need a line break inside a string."
)

def _clean_json_text(text: str) -> str:
    """
    Gemini sometimes emits literal newlines inside JSON string values,
    which makes json.loads raise 'Invalid control character'.
    
    Strategy: walk the raw text character by character, and when we are
    inside a JSON string (between unescaped double-quotes) replace any
    literal \n / \r / \t with their escape sequences.
    """
    result = []
    in_string = False
    escape_next = False
 
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
 
        if ch == '\\' and in_string:
            result.append(ch)
            escape_next = True
            continue
 
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
 
        if in_string:
            if ch == '\n':
                result.append('\\n')
            elif ch == '\r':
                result.append('\\r')
            elif ch == '\t':
                result.append('\\t')
            elif ord(ch) < 0x20:          # any other control character
                result.append(' ')
            else:
                result.append(ch)
        else:
            result.append(ch)
 
    return ''.join(result)
 
 
def generate_ai_content(product: dict) -> dict:
    prompt = build_ai_prompt(product)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
                max_output_tokens=65536,
            )
        )

        text = response.text
        text = re.sub(r"```json|```", "", text).strip()

        # Pull out the JSON block even if there's stray text around it
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            raw_json = match.group()
            # First attempt: parse as-is
            try:
                return json.loads(raw_json)
            except json.JSONDecodeError as e:
                print(f"[WARN] First JSON parse failed ({e}), attempting control-char fix...")

            # Second attempt: fix embedded control characters in strings
            try:
                fixed = _clean_json_text(raw_json)
                return json.loads(fixed)
            except json.JSONDecodeError as e2:
                print(f"[ERROR] JSON parse failed after fix: {e2}")
                return {"raw_output": text}

        return {"raw_output": text}

    except Exception as e:
        print(f"[ERROR] Gemini API call failed: {e}")
        return {"raw_output": str(e)}
