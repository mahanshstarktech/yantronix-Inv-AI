import os
import ssl
from celery import Celery
from dotenv import load_dotenv

# Celery worker is a completely separate process from FastAPI.
# It must load .env itself — it does NOT inherit FastAPI's load_dotenv().
load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# If using rediss:// (Upstash/secure Redis), Celery requires explicit SSL config
ssl_kwargs = {}
if redis_url.startswith("rediss://"):
    ssl_kwargs = {"ssl_cert_reqs": ssl.CERT_NONE}

celery_app = Celery(
    "yantronix",
    broker=redis_url,
    backend=redis_url,
    include=["app.workers.tasks"],
    broker_use_ssl=ssl_kwargs if ssl_kwargs else None,
    redis_backend_use_ssl=ssl_kwargs if ssl_kwargs else None,
)