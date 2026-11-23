from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedUUIDModel
from apps.library.models import BookingPolicyVersion, LibrarySeat, LibrarySession


class Reservation(TimeStampedUUIDModel):
    class BookingType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        GROUP = "GROUP", "Group"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_ACCEPTANCE = "PENDING_ACCEPTANCE", "Pending Group Consent"
        CONFIRMED = "CONFIRMED", "Confirmed"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"
        REJECTED = "REJECTED", "Rejected"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_reservations"
    )
    booking_type = models.CharField(max_length=20, choices=BookingType.choices, default=BookingType.INDIVIDUAL)
    operational_date = models.DateField(db_index=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    policy_version = models.ForeignKey(BookingPolicyVersion, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"RES-{str(self.id)[:8]} ({self.status})"


class ReservationAttendee(TimeStampedUUIDModel):
    class InvitationState(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", "Not Required"
        INVITED = "INVITED", "Invited"
        ACCEPTED = "ACCEPTED", "Accepted"
        DECLINED = "DECLINED", "Declined"
        EXPIRED = "EXPIRED", "Expired"

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="attendees")
    attendee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservation_memberships"
    )
    invitation_state = models.CharField(
        max_length=20, choices=InvitationState.choices, default=InvitationState.NOT_REQUIRED
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reservation", "attendee"], name="uniq_reservation_attendee"),
        ]


class AttendeeSessionAllocation(TimeStampedUUIDModel):
    class AllocationState(models.TextChoices):
        PENDING = "PENDING", "Pending Consent"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CHECKED_IN = "CHECKED_IN", "Checked In"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No-Show"
        RELEASED = "RELEASED", "Released"
        EXPIRED = "EXPIRED", "Expired"

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="allocations")
    attendee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="session_allocations"
    )
    session = models.ForeignKey(LibrarySession, on_delete=models.PROTECT, related_name="allocations")
    seat = models.ForeignKey(LibrarySeat, on_delete=models.PROTECT, related_name="allocations")
    allocation_state = models.CharField(
        max_length=20, choices=AllocationState.choices, default=AllocationState.PENDING, db_index=True
    )

    class Meta:
        ordering = ["session__session_date", "session__session_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["attendee", "session"],
                condition=models.Q(allocation_state__in=["CONFIRMED", "CHECKED_IN"]),
                name="uniq_active_attendee_session",
            ),
            models.UniqueConstraint(
                fields=["seat", "session"],
                condition=models.Q(allocation_state__in=["CONFIRMED", "CHECKED_IN"]),
                name="uniq_active_seat_session",
            ),
        ]

    def __str__(self):
        return f"{self.attendee.institutional_id} @ {self.seat} ({self.session.label})"


class CheckIn(TimeStampedUUIDModel):
    allocation = models.OneToOneField(AttendeeSessionAllocation, on_delete=models.CASCADE, related_name="checkin")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    method = models.CharField(max_length=30, default="SELF_BUTTON")
    checked_in_at = models.DateTimeField(auto_now_add=True)


class ReservationTransition(TimeStampedUUIDModel):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="transitions")
    from_state = models.CharField(max_length=30)
    to_state = models.CharField(max_length=30)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]
