"""
config/settings/prod.py
------------------------
Production settings.  All secrets must be supplied via environment variables.

Usage:
    export DJANGO_SETTINGS_MODULE=config.settings.prod
    gunicorn config.wsgi:application
"""

from .base import *  # noqa: F401, F403

DEBUG = False

# Set in .env or hosting environment
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405

# Security hardening
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Production email — configure SMTP in .env
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405

# Celery uses real Redis broker in production
CELERY_TASK_ALWAYS_EAGER = False

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])  # noqa: F405
