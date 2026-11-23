from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import RoleCode, User
from apps.audit.services import log_audit_event
from apps.library.models import (
    BookingPolicyVersion,
    LibrarySeat,
    LibrarySession,
    SeatClosure,
    ZoneClosure,
)
from apps.notifications.services import enqueue_notification
from apps.reservations.models import (
    AttendeeSessionAllocation,
    CheckIn,
    Reservation,
    ReservationAttendee,
    ReservationTransition,
)

ACTIVE_ALLOCATION_STATES = [
    AttendeeSessionAllocation.AllocationState.CONFIRMED,
    AttendeeSessionAllocation.AllocationState.CHECKED_IN,
]


class ReservationConflictError(ValidationError):
    """Raised when a booking violates capacity, eligibility, or concurrency invariants."""


def _validate_consecutive_sessions(sessions: list[LibrarySession], max_consecutive: int) -> None:
    if not sessions:
        raise ValidationError("At least one session must be selected per attendee.")
    dates = {s.session_date for s in sessions}
    if len(dates) != 1:
        raise ValidationError("All sessions in a reservation must fall on the same operational day.")
    indices = sorted(s.session_index for s in sessions)
    if len(indices) != len(set(indices)):
        raise ValidationError("Duplicate session selected for the same attendee.")
    if len(indices) > max_consecutive:
        raise ValidationError(f"Maximum {max_consecutive} consecutive sessions allowed per booking.")
    for i in range(1, len(indices)):
        if indices[i] != indices[i - 1] + 1:
            raise ValidationError("Selected sessions must be consecutive.")


def _check_closures(seat: LibrarySeat, session: LibrarySession) -> None:
    session_start = timezone.make_aware(datetime.combine(session.session_date, session.start_time))
    session_end = timezone.make_aware(datetime.combine(session.session_date, session.end_time))
    if ZoneClosure.objects.filter(
        zone=seat.zone, is_active=True, start_at__lt=session_end, end_at__gt=session_start
    ).exists():
        raise ReservationConflictError(f"Zone {seat.zone.code} is temporarily closed during {session.label}.")
    if SeatClosure.objects.filter(
        seat=seat, is_active=True, start_at__lt=session_end, end_at__gt=session_start
    ).exists():
        raise ReservationConflictError(f"Seat {seat} is temporarily closed during {session.label}.")


@transaction.atomic
def create_reservation(
    *,
    creator: User,
    attendee_allocations: list[dict],
    booking_type: str = Reservation.BookingType.INDIVIDUAL,
    idempotency_key: str | None = None,
) -> Reservation:
    """
    Implements the Final Engineering Corrections concurrency protocol:
    1. Lock every attendee identity row in ascending stable-key (UUID) order FIRST.
    2. Lock session and seat rows in deterministic ascending UUID order.
    3. Re-read all active attendee allocations across ALL reservation creators.
    4. Revalidate limits, consent, closures, and seat capacity inside the same transaction.
    5. Commit reservation + allocations + audit + outbox atomically.

    attendee_allocations format:
    [
        {"attendee_id": <UUID>, "session_ids": [<UUID>, ...], "seat_id": <UUID>},
        ...
    ]
    """
    if not creator.has_role(RoleCode.STUDENT):
        raise PermissionDenied("Only active Students can create library reservations.")

    if idempotency_key:
        existing = Reservation.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    if not attendee_allocations:
        raise ValidationError("At least one attendee allocation is required.")

    policy = BookingPolicyVersion.get_active()

    # Deterministic ascending lock order prevents deadlocks & phantom races
    attendee_ids = sorted({item["attendee_id"] for item in attendee_allocations})
    session_ids = sorted({sid for item in attendee_allocations for sid in item["session_ids"]})
    seat_ids = sorted({item["seat_id"] for item in attendee_allocations})

    # STEP 1: Lock attendee identity rows in ascending key order FIRST
    locked_users = {
        u.id: u for u in User.objects.select_for_update().filter(id__in=attendee_ids).order_by("id")
    }
    if len(locked_users) != len(attendee_ids):
        raise ValidationError("One or more attendee identities could not be resolved.")

    # STEP 2: Lock session and seat rows in ascending key order
    locked_sessions = {
        s.id: s for s in LibrarySession.objects.select_for_update().filter(id__in=session_ids, is_active=True).order_by("id")
    }
    if len(locked_sessions) != len(session_ids):
        raise ValidationError("One or more selected sessions are invalid or inactive.")

    locked_seats = {
        st.id: st
        for st in LibrarySeat.objects.select_for_update().select_related("zone").filter(id__in=seat_ids, is_active=True).order_by("id")
    }
    if len(locked_seats) != len(seat_ids):
        raise ValidationError("One or more selected seats are invalid or inactive.")

    operational_dates = {s.session_date for s in locked_sessions.values()}
    if len(operational_dates) != 1:
        raise ValidationError("All sessions in a reservation must belong to a single operational day.")
    op_date = next(iter(operational_dates))

    # Determine whether group consent is required (any attendee other than creator)
    other_attendees = [uid for uid in attendee_ids if uid != creator.id]
    needs_consent = bool(other_attendees) and policy.consent_required_for_invitees

    # STEP 3 & 4: Re-read active allocations across ALL creators and validate every attendee
    seen_seat_sessions: set[tuple] = set()
    for item in attendee_allocations:
        attendee = locked_users[item["attendee_id"]]
        if not attendee.is_active or not attendee.has_role(RoleCode.STUDENT):
            raise ValidationError(f"Attendee {attendee.institutional_id} is not an active eligible student.")

        att_sessions = [locked_sessions[sid] for sid in item["session_ids"]]
        _validate_consecutive_sessions(att_sessions, policy.max_consecutive_sessions)

        # Anti-proxy & anti-reciprocal (A<->B) check across ALL reservation creators
        existing_day_allocs = AttendeeSessionAllocation.objects.filter(
            attendee=attendee,
            session__session_date=op_date,
            allocation_state__in=ACTIVE_ALLOCATION_STATES,
        )
        if policy.one_booking_per_day and existing_day_allocs.exists():
            raise ReservationConflictError(
                f"{attendee.institutional_id} already has a confirmed booking on {op_date} (daily limit reached)."
            )

        seat = locked_seats[item["seat_id"]]
        for sess in att_sessions:
            _check_closures(seat, sess)
            if (seat.id, sess.id) in seen_seat_sessions:
                raise ReservationConflictError(f"Seat {seat} is assigned twice for session {sess.label}.")
            seen_seat_sessions.add((seat.id, sess.id))

            if AttendeeSessionAllocation.objects.filter(
                seat=seat, session=sess, allocation_state__in=ACTIVE_ALLOCATION_STATES
            ).exists():
                raise ReservationConflictError(f"Seat {seat} is already taken for {sess.label}.")

            if AttendeeSessionAllocation.objects.filter(
                attendee=attendee, session=sess, allocation_state__in=ACTIVE_ALLOCATION_STATES
            ).exists():
                raise ReservationConflictError(
                    f"{attendee.institutional_id} already has an allocation for {sess.label}."
                )

    initial_res_status = (
        Reservation.Status.PENDING_ACCEPTANCE if needs_consent else Reservation.Status.CONFIRMED
    )
    initial_alloc_state = (
        AttendeeSessionAllocation.AllocationState.PENDING
        if needs_consent
        else AttendeeSessionAllocation.AllocationState.CONFIRMED
    )
    expires_at = timezone.now() + timedelta(minutes=policy.invite_expiry_minutes) if needs_consent else None

    try:
        reservation = Reservation.objects.create(
            creator=creator,
            booking_type=booking_type,
            operational_date=op_date,
            status=initial_res_status,
            policy_version=policy,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )

        for item in attendee_allocations:
            attendee = locked_users[item["attendee_id"]]
            inv_state = (
                ReservationAttendee.InvitationState.ACCEPTED
                if attendee.id == creator.id or not needs_consent
                else ReservationAttendee.InvitationState.INVITED
            )
            ReservationAttendee.objects.create(
                reservation=reservation,
                attendee=attendee,
                invitation_state=inv_state,
                responded_at=timezone.now() if inv_state == ReservationAttendee.InvitationState.ACCEPTED else None,
            )

            seat = locked_seats[item["seat_id"]]
            for sid in item["session_ids"]:
                AttendeeSessionAllocation.objects.create(
                    reservation=reservation,
                    attendee=attendee,
                    session=locked_sessions[sid],
                    seat=seat,
                    allocation_state=initial_alloc_state,
                )

            if inv_state == ReservationAttendee.InvitationState.INVITED:
                enqueue_notification(
                    recipient=attendee,
                    event_type="GROUP_INVITE",
                    title="Library Group Booking Invitation",
                    body=f"{creator.full_name} invited you to a library group booking on {op_date}. Please accept or decline.",
                    dedupe_key=f"invite:{reservation.id}:{attendee.id}",
                )

        ReservationTransition.objects.create(
            reservation=reservation,
            from_state=Reservation.Status.DRAFT,
            to_state=initial_res_status,
            actor=creator,
            reason="Reservation submitted",
        )
        log_audit_event(
            actor=creator,
            action="RESERVATION_CREATED",
            target_type="Reservation",
            target_id=str(reservation.id),
            after_state={"status": initial_res_status, "booking_type": booking_type, "date": str(op_date)},
        )
        return reservation
    except IntegrityError as exc:
        raise ReservationConflictError("Seat or attendee allocation conflict detected by database constraint.") from exc


@transaction.atomic
def respond_to_invitation(*, actor: User, reservation_id, accept: bool) -> Reservation:
    reservation = Reservation.objects.select_for_update().get(pk=reservation_id)
    if reservation.status != Reservation.Status.PENDING_ACCEPTANCE:
        raise ValidationError("This reservation is no longer awaiting consent.")

    if reservation.expires_at and timezone.now() > reservation.expires_at:
        reservation.status = Reservation.Status.EXPIRED
        reservation.save(update_fields=["status", "updated_at"])
        reservation.allocations.update(allocation_state=AttendeeSessionAllocation.AllocationState.EXPIRED)
        reservation.attendees.filter(
            invitation_state=ReservationAttendee.InvitationState.INVITED
        ).update(invitation_state=ReservationAttendee.InvitationState.EXPIRED)
        raise ValidationError("Invitation has expired.")

    membership = ReservationAttendee.objects.select_for_update().filter(
        reservation=reservation, attendee=actor
    ).first()
    if not membership:
        raise PermissionDenied("You are not an invited attendee on this reservation.")

    if not accept:
        membership.invitation_state = ReservationAttendee.InvitationState.DECLINED
        membership.responded_at = timezone.now()
        membership.save(update_fields=["invitation_state", "responded_at", "updated_at"])
        if reservation.policy_version.all_or_nothing_group:
            reservation.status = Reservation.Status.REJECTED
            reservation.save(update_fields=["status", "updated_at"])
            reservation.allocations.update(allocation_state=AttendeeSessionAllocation.AllocationState.CANCELLED)
            ReservationTransition.objects.create(
                reservation=reservation,
                from_state=Reservation.Status.PENDING_ACCEPTANCE,
                to_state=Reservation.Status.REJECTED,
                actor=actor,
                reason="Invited attendee declined (all-or-nothing policy)",
            )
        log_audit_event(
            actor=actor,
            action="INVITATION_DECLINED",
            target_type="Reservation",
            target_id=str(reservation.id),
            after_state={"status": reservation.status},
        )
        return reservation

    membership.invitation_state = ReservationAttendee.InvitationState.ACCEPTED
    membership.responded_at = timezone.now()
    membership.save(update_fields=["invitation_state", "responded_at", "updated_at"])

    # If all attendees have accepted, run the exact sorted-lock confirmation protocol
    still_pending = reservation.attendees.filter(
        invitation_state=ReservationAttendee.InvitationState.INVITED
    ).exists()
    if not still_pending:
        allocs = list(reservation.allocations.select_related("attendee", "session", "seat__zone"))
        attendee_ids = sorted({a.attendee_id for a in allocs})
        session_ids = sorted({a.session_id for a in allocs})
        seat_ids = sorted({a.seat_id for a in allocs})

        list(User.objects.select_for_update().filter(id__in=attendee_ids).order_by("id"))
        list(LibrarySession.objects.select_for_update().filter(id__in=session_ids).order_by("id"))
        list(LibrarySeat.objects.select_for_update().filter(id__in=seat_ids).order_by("id"))

        policy = reservation.policy_version
        for a in allocs:
            _check_closures(a.seat, a.session)
            if policy.one_booking_per_day and AttendeeSessionAllocation.objects.filter(
                attendee=a.attendee,
                session__session_date=reservation.operational_date,
                allocation_state__in=ACTIVE_ALLOCATION_STATES,
            ).exists():
                raise ReservationConflictError(
                    f"{a.attendee.institutional_id} is no longer eligible on {reservation.operational_date}."
                )
            if AttendeeSessionAllocation.objects.filter(
                seat=a.seat, session=a.session, allocation_state__in=ACTIVE_ALLOCATION_STATES
            ).exists():
                raise ReservationConflictError(f"Seat {a.seat} was taken while awaiting group consent.")

        reservation.status = Reservation.Status.CONFIRMED
        reservation.save(update_fields=["status", "updated_at"])
        reservation.allocations.update(allocation_state=AttendeeSessionAllocation.AllocationState.CONFIRMED)
        ReservationTransition.objects.create(
            reservation=reservation,
            from_state=Reservation.Status.PENDING_ACCEPTANCE,
            to_state=Reservation.Status.CONFIRMED,
            actor=actor,
            reason="All attendees accepted; confirmed atomically",
        )
        log_audit_event(
            actor=actor,
            action="RESERVATION_CONFIRMED",
            target_type="Reservation",
            target_id=str(reservation.id),
            after_state={"status": Reservation.Status.CONFIRMED},
        )
    return reservation


@transaction.atomic
def cancel_reservation(*, actor: User, reservation_id, reason: str = "Cancelled by user") -> Reservation:
    reservation = Reservation.objects.select_for_update().get(pk=reservation_id)
    if reservation.creator_id != actor.id and not actor.has_role(RoleCode.LIBRARY_SUPERVISOR):
        raise PermissionDenied("Only the reservation creator or a Library Supervisor can cancel.")
    if reservation.status not in (Reservation.Status.PENDING_ACCEPTANCE, Reservation.Status.CONFIRMED):
        raise ValidationError("Only pending or confirmed reservations can be cancelled.")

    old_status = reservation.status
    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=["status", "updated_at"])
    reservation.allocations.exclude(
        allocation_state=AttendeeSessionAllocation.AllocationState.CHECKED_IN
    ).update(allocation_state=AttendeeSessionAllocation.AllocationState.CANCELLED)

    ReservationTransition.objects.create(
        reservation=reservation,
        from_state=old_status,
        to_state=Reservation.Status.CANCELLED,
        actor=actor,
        reason=reason,
    )
    log_audit_event(
        actor=actor,
        action="RESERVATION_CANCELLED",
        target_type="Reservation",
        target_id=str(reservation.id),
        before_state={"status": old_status},
        after_state={"status": Reservation.Status.CANCELLED},
        reason=reason,
    )
    return reservation


@transaction.atomic
def record_checkin(*, actor: User, allocation_id, method: str = "SELF_BUTTON") -> CheckIn:
    alloc = AttendeeSessionAllocation.objects.select_for_update().select_related("attendee", "session").get(pk=allocation_id)
    is_staff = actor.has_role(RoleCode.LIBRARY_STAFF, RoleCode.LIBRARY_SUPERVISOR)
    if alloc.attendee_id != actor.id and not is_staff:
        raise PermissionDenied("You cannot check in another student's allocation.")
    if alloc.allocation_state != AttendeeSessionAllocation.AllocationState.CONFIRMED:
        raise ValidationError("Only CONFIRMED allocations can be checked in.")

    alloc.allocation_state = AttendeeSessionAllocation.AllocationState.CHECKED_IN
    alloc.save(update_fields=["allocation_state", "updated_at"])
    checkin = CheckIn.objects.create(allocation=alloc, recorded_by=actor, method=method)
    log_audit_event(
        actor=actor,
        action="ATTENDEE_CHECKED_IN",
        target_type="AttendeeSessionAllocation",
        target_id=str(alloc.id),
        after_state={"allocation_state": alloc.allocation_state, "method": method},
    )
    return checkin


@transaction.atomic
def release_no_shows(*, now=None, actor: User | None = None) -> int:
    """Transactionally rechecks state and releases unclaimed allocations past grace period."""
    current_time = now or timezone.now()
    policy = BookingPolicyVersion.get_active()
    released_count = 0

    candidates = (
        AttendeeSessionAllocation.objects.select_for_update()
        .select_related("session", "attendee")
        .filter(allocation_state=AttendeeSessionAllocation.AllocationState.CONFIRMED)
    )
    for alloc in candidates:
        session_start = timezone.make_aware(
            datetime.combine(alloc.session.session_date, alloc.session.start_time)
        )
        deadline = session_start + timedelta(minutes=policy.checkin_grace_minutes)
        if current_time > deadline:
            # Never release a checked-in allocation (guarded by filter + lock)
            alloc.allocation_state = AttendeeSessionAllocation.AllocationState.RELEASED
            alloc.save(update_fields=["allocation_state", "updated_at"])
            released_count += 1
            log_audit_event(
                actor=actor,
                action="NO_SHOW_SEAT_RELEASED",
                target_type="AttendeeSessionAllocation",
                target_id=str(alloc.id),
                before_state={"allocation_state": "CONFIRMED"},
                after_state={"allocation_state": "RELEASED"},
                reason=f"No check-in within {policy.checkin_grace_minutes}m grace period",
                source="system_job" if actor is None else "web",
            )
            enqueue_notification(
                recipient=alloc.attendee,
                event_type="NO_SHOW_RELEASED",
                title="Unclaimed Library Seat Released",
                body=f"Your seat {alloc.seat} for {alloc.session.label} was released after the grace period.",
                dedupe_key=f"noshow:{alloc.id}",
            )
    return released_count


@transaction.atomic
def apply_supervisor_override(*, actor: User, allocation_id, new_state: str, reason: str) -> AttendeeSessionAllocation:
    if not actor.has_role(RoleCode.LIBRARY_SUPERVISOR):
        raise PermissionDenied("Only Library Supervisor can apply reservation overrides.")
    if not reason or not reason.strip():
        raise ValidationError("A written reason is mandatory for every supervisor override.")

    alloc = AttendeeSessionAllocation.objects.select_for_update().get(pk=allocation_id)
    before_state = {"allocation_state": alloc.allocation_state}
    alloc.allocation_state = new_state
    alloc.save(update_fields=["allocation_state", "updated_at"])
    log_audit_event(
        actor=actor,
        action="SUPERVISOR_OVERRIDE",
        target_type="AttendeeSessionAllocation",
        target_id=str(alloc.id),
        before_state=before_state,
        after_state={"allocation_state": new_state},
        reason=reason.strip(),
    )
    return alloc
