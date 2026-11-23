from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedUUIDModel


class LibraryZone(TimeStampedUUIDModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    floor = models.CharField(max_length=40, default="Floor 1")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class LibrarySeat(TimeStampedUUIDModel):
    zone = models.ForeignKey(LibraryZone, on_delete=models.CASCADE, related_name="seats")
    seat_code = models.CharField(max_length=30)
    has_power_outlet = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["zone__code", "seat_code"]
        constraints = [
            models.UniqueConstraint(fields=["zone", "seat_code"], name="uniq_zone_seat_code"),
        ]

    def __str__(self):
        return f"{self.zone.code}-{self.seat_code}"


class LibrarySession(TimeStampedUUIDModel):
    session_date = models.DateField(db_index=True)
    session_index = models.PositiveSmallIntegerField(help_text="1-based daily session order (1, 2, 3, 4)")
    label = models.CharField(max_length=60)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["session_date", "session_index"]
        constraints = [
            models.UniqueConstraint(fields=["session_date", "session_index"], name="uniq_date_session_index"),
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="chk_session_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.session_date} | {self.label} ({self.start_time:%H:%M}-{self.end_time:%H:%M})"


class ZoneClosure(TimeStampedUUIDModel):
    zone = models.ForeignKey(LibraryZone, on_delete=models.CASCADE, related_name="closures")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_at"]


class SeatClosure(TimeStampedUUIDModel):
    seat = models.ForeignKey(LibrarySeat, on_delete=models.CASCADE, related_name="closures")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_at"]


class BookingPolicyVersion(TimeStampedUUIDModel):
    """Configurable ADR-003 prototype defaults (not hard-coded institutional policy)."""

    version_name = models.CharField(max_length=80, unique=True)
    max_consecutive_sessions = models.PositiveSmallIntegerField(default=2)
    one_booking_per_day = models.BooleanField(default=True)
    all_or_nothing_group = models.BooleanField(default=True)
    consent_required_for_invitees = models.BooleanField(default=True)
    invite_expiry_minutes = models.PositiveSmallIntegerField(default=30)
    checkin_grace_minutes = models.PositiveSmallIntegerField(default=15)
    cancellation_restores_eligibility = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-effective_from"]

    @classmethod
    def get_active(cls) -> "BookingPolicyVersion":
        policy = cls.objects.filter(is_active=True).order_by("-effective_from").first()
        if policy is None:
            policy = cls.objects.create(version_name="ADR-003-Prototype-Default-v1")
        return policy

    def __str__(self):
        return self.version_name
