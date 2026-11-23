import uuid

from django.db import models


class TimeStampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SystemSetting(TimeStampedUUIDModel):
    key = models.CharField(max_length=100, unique=True)
    value_json = models.JSONField(default=dict)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} (v{self.version})"
