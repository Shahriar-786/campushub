from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedUUIDModel


class FacilityTicket(TimeStampedUUIDModel):
    class QueueType(models.TextChoices):
        UTILITY = "UTILITY", "Utility / Maintenance"
        IT = "IT", "IT Equipment / Network"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        NEEDS_INFORMATION = "NEEDS_INFORMATION", "Needs Information"
        TRIAGED = "TRIAGED", "Triaged"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"
        ESCALATED = "ESCALATED", "Escalated"
        REOPENED = "REOPENED", "Reopened"
        REJECTED = "REJECTED", "Rejected"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="facility_tickets"
    )
    queue_type = models.CharField(max_length=20, choices=QueueType.choices, default=QueueType.UTILITY)
    category = models.CharField(max_length=80)
    location = models.CharField(max_length=160)
    description = models.TextField()
    priority = models.CharField(max_length=15, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_facility_tickets",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"TKT-{str(self.id)[:8]} ({self.queue_type} | {self.status})"


class WorkLog(TimeStampedUUIDModel):
    ticket = models.ForeignKey(FacilityTicket, on_delete=models.CASCADE, related_name="work_logs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.TextField()

    class Meta:
        ordering = ["created_at"]


class TicketTransition(TimeStampedUUIDModel):
    ticket = models.ForeignKey(FacilityTicket, on_delete=models.CASCADE, related_name="transitions")
    from_state = models.CharField(max_length=25)
    to_state = models.CharField(max_length=25)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]
