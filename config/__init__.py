"""
config/__init__.py
------------------
Import Celery app so it is initialised when Django starts.
This ensures that @shared_task decorators in any app work correctly.
"""

from .celery import app as celery_app  # noqa: F401

__all__ = ["celery_app"]
