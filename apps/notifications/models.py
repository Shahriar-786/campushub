from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedUUIDModel


class NotificationOutbox(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    event_type = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    body = models.TextField()
    dedupe_key = models.CharField(max_length=160, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


class NotificationAttempt(TimeStampedUUIDModel):
    outbox = models.ForeignKey(NotificationOutbox, on_delete=models.CASCADE, related_name="attempts")
    channel = models.CharField(max_length=30, default="in_app")
    succeeded = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
