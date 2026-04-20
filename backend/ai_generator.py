import json
import re
import ollama
from prompts import build_ai_prompt

def generate_ai_content(product):
    prompt = build_ai_prompt(product)

    response = ollama.chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional electronics product data extractor and "
                    "e-commerce listing generator. You generate complete, structured, "
                    "SEO-optimized product listings in strict JSON format only. "
                    "Do NOT include any explanation, markdown, or text outside the JSON object."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    text = response['message']['content']
    text = re.sub(r"```json|```", "", text).strip()

    # ✅ Add this — pull out the JSON block even if there's text before it
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            return {"raw_output": text}

    return {"raw_output": text}