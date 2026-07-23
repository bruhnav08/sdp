"""
config/celery.py
----------------
Celery application factory.

For Sprint 1 / demo use, set CELERY_TASK_ALWAYS_EAGER=True in your .env
and tasks will execute synchronously — no separate worker process needed.

To run a real Celery worker (when Redis is available):
    celery -A config worker -l info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("hsrs")

# Namespace 'CELERY' means all celery-related settings in settings.py
# must start with CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks from all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
