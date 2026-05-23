from celery_app import celery_app
from ai_generator import generate_ai_content
from database import get_raw_product, save_ai_product
from publish import publish_to_zoho

@celery_app.task
def generate_ai_task(product_id: int):
    print(f"[INFO] Starting AI generation for product_id={product_id}")

    # Step 1: Fetch raw product from DB
    product = get_raw_product(product_id)
    # Guard: don't call Gemini if scraper returned nothing useful
    if not product.get("raw_page_text"):
        print(f"[ERROR] Scraper returned empty raw_page_text for product_id={product_id}.")
        return

    # Step 2: Call Gemini
    ai_content = generate_ai_content(product)

    # Step 3: Guard against unparseable AI output
    if "raw_output" in ai_content:
        print(f"[WARN] Gemini returned unparseable output for product_id={product_id}")
        print(f"[WARN] Raw output:\n{ai_content['raw_output'][:500]}")
        return  # Don't save or publish garbage

    print(f"[INFO] AI generation successful for product_id={product_id}")

    # Step 4: Save to DB
    save_ai_product(product_id, ai_content)
    print(f"[INFO] AI product saved for product_id={product_id}")

    # Step 5: Publish (test mode by default)
    publish_to_zoho(ai_content)