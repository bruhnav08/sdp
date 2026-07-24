from django.conf import settings
from django.db import models
from common.models import TimeStampedModel
from room_inventory.models import Room


class RoomStatusHistory(TimeStampedModel):
    """
    Audit log entry recording every room status change.
    Contains: Room ID, Previous status, New status, Timestamp, User/staff member, Remarks/reason.
    """

    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="status_history"
    )
    previous_status = models.CharField(max_length=40)
    new_status = models.CharField(max_length=40)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="room_status_changes",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Room Status History"
        verbose_name_plural = "Room Status History Records"

    def __str__(self) -> str:
        user_str = self.changed_by.username if self.changed_by else "System/Unknown"
        return f"Room {self.room.room_number}: {self.previous_status} → {self.new_status} (By {user_str})"
