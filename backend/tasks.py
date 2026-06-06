"""Compatibility module for `celery -A tasks worker`.

The production task implementation lives in `app.workers.tasks`.
"""

from app.workers.tasks import generate_ai_task

__all__ = ["generate_ai_task"]
