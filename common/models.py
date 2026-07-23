"""
common/models.py
----------------
Shared abstract base models used by every app in the project.

Usage:
    from common.models import TimeStampedModel

    class MyModel(TimeStampedModel):
        ...
"""

from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base class that provides ``created_at`` and ``updated_at``
    timestamp fields.  Every concrete model in the project should inherit
    from this class so that audit timestamps are consistent everywhere.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
