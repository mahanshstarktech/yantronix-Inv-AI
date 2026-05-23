import os
from celery import Celery
from dotenv import load_dotenv

# Celery worker is a completely separate process from FastAPI.
# It must load .env itself — it does NOT inherit FastAPI's load_dotenv().
load_dotenv()

celery_app = Celery(
    "yantronix",
    broker  = "redis://localhost:6379/0",
    backend = "redis://localhost:6379/0",
    include = ["tasks"],   # tells the worker where to find tasks — without this,
                           # the worker boots but never discovers generate_ai_task
)