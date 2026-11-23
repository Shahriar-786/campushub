from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedUUIDModel


class LostFoundReport(TimeStampedUUIDModel):
    class ReportType(models.TextChoices):
        LOST = "LOST", "Lost Item"
        FOUND = "FOUND", "Found Item"

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        NEEDS_INFORMATION = "NEEDS_INFORMATION", "Needs Information"
        ACTIVE = "ACTIVE", "Active"
        RESOLVED = "RESOLVED", "Resolved"
        REJECTED = "REJECTED", "Rejected"
        CLOSED = "CLOSED", "Closed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lf_reports"
    )
    report_type = models.CharField(max_length=10, choices=ReportType.choices)
    category = models.CharField(max_length=80)
    location_hint = models.CharField(max_length=160)
    public_description = models.TextField(help_text="Safe non-secret summary visible in eligible listings")
    private_details = models.TextField(
        blank=True, help_text="Secret distinguishing marks kept hidden from public search"
    )
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.SUBMITTED, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"LF-{str(self.id)[:8]} ({self.report_type} | {self.category})"


class PotentialMatch(TimeStampedUUIDModel):
    """Advisory lead only — explicitly NEVER proof of ownership."""

    lost_report = models.ForeignKey(LostFoundReport, on_delete=models.CASCADE, related_name="lost_matches")
    found_report = models.ForeignKey(LostFoundReport, on_delete=models.CASCADE, related_name="found_matches")
    rationale = models.TextField()
    is_verified_ownership = models.BooleanField(default=False, editable=False)
    suggested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)


class OwnershipClaim(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        NEEDS_INFORMATION = "NEEDS_INFORMATION", "Needs Information"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ESCALATED = "ESCALATED", "Escalated to Security"
        HANDED_OVER = "HANDED_OVER", "Handed Over"

    report = models.ForeignKey(LostFoundReport, on_delete=models.CASCADE, related_name="claims")
    claimant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lf_claims")
    evidence_summary = models.TextField()
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="lf_decisions"
    )
    decision_reason = models.TextField(blank=True)
    assigned_security_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_security_claims",
    )

    class Meta:
        ordering = ["-created_at"]


class ItemHandover(TimeStampedUUIDModel):
    claim = models.OneToOneField(OwnershipClaim, on_delete=models.PROTECT, related_name="handover")
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recipient_verification_ref = models.CharField(max_length=160)
    outcome_notes = models.TextField()
    handed_over_at = models.DateTimeField(auto_now_add=True)


class LostFoundTransition(TimeStampedUUIDModel):
    report = models.ForeignKey(LostFoundReport, on_delete=models.CASCADE, related_name="transitions")
    from_state = models.CharField(max_length=30)
    to_state = models.CharField(max_length=30)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField(blank=True)
