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
    "Do NOT include any explanation, markdown, or text outside the JSON object."
)

def generate_ai_content(product: dict) -> dict:
    prompt = build_ai_prompt(product)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
                max_output_tokens=8192,
            )
        )

        text = response.text
        text = re.sub(r"```json|```", "", text).strip()

        # Pull out the JSON block even if there's stray text around it
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception as e:
                print(f"[ERROR] JSON parse failed: {e}")
                return {"raw_output": text}

        return {"raw_output": text}

    except Exception as e:
        print(f"[ERROR] Gemini API call failed: {e}")
        return {"raw_output": str(e)}
