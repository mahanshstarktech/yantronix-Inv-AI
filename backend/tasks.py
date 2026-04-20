from celery_app import celery_app
from ai_generator import generate_ai_content
from database import get_raw_product, save_ai_product
from publish import publish_to_zoho

@celery_app.task
def generate_ai_task(product_id):
    product = get_raw_product(product_id)
    ai_content = generate_ai_content(product)
    save_ai_product(product_id, ai_content)
    publish_to_zoho(ai_content)