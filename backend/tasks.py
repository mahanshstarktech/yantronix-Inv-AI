"""Compatibility module for `celery -A tasks worker`.

The production task implementation lives in `app.workers.tasks`.
"""

from app.workers.tasks import generate_ai_task
from celery_app import celery_app

# Celery CLI discovers an application named `celery` when using `celery -A tasks worker`.
celery = celery_app

__all__ = ["celery", "celery_app", "generate_ai_task"]
