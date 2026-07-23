"""
config/settings/dev.py
-----------------------
Development settings.  Extends base.py with developer-friendly overrides.

Usage:
    export DJANGO_SETTINGS_MODULE=config.settings.dev
    python manage.py runserver
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Allow all origins in development for HTMX / DRF browsable API
CORS_ALLOW_ALL_ORIGINS = True

# Use Django's console email backend so sent emails appear in the terminal
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Celery runs tasks synchronously in dev — no Redis/worker needed
CELERY_TASK_ALWAYS_EAGER = True

# Optional: log all SQL queries to the console
# LOGGING = {
#     "version": 1,
#     "handlers": {"console": {"class": "logging.StreamHandler"}},
#     "loggers": {"django.db.backends": {"handlers": ["console"], "level": "DEBUG"}},
# }
