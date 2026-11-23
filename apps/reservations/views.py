import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.access_control.decorators import require_roles
from apps.accounts.models import RoleCode, User
from apps.library.models import LibrarySeat, LibrarySession
from apps.reservations.models import AttendeeSessionAllocation, Reservation, ReservationAttendee
from apps.reservations.services import (
    apply_supervisor_override,
    cancel_reservation,
    create_reservation,
    record_checkin,
    release_no_shows,
    respond_to_invitation,
)


@login_required
@require_roles(RoleCode.STUDENT)
def my_reservations_view(request):
    my_allocs = (
        AttendeeSessionAllocation.objects.filter(attendee=request.user)
        .select_related("reservation", "session", "seat__zone")
        .order_by("-created_at")[:30]
    )
    pending_invites = (
        ReservationAttendee.objects.filter(
            attendee=request.user,
            invitation_state=ReservationAttendee.InvitationState.INVITED,
            reservation__status=Reservation.Status.PENDING_ACCEPTANCE,
        )
        .select_related("reservation__creator")
    )
    return render(
        request,
        "reservations/my_reservations.html",
        {"allocations": my_allocs, "pending_invites": pending_invites},
    )


@login_required
@require_roles(RoleCode.STUDENT)
def create_booking_view(request):
    if request.method == "POST":
        booking_type = request.POST.get("booking_type", Reservation.BookingType.INDIVIDUAL)
        seat_id = request.POST.get("seat_id")
        session_ids = request.POST.getlist("session_ids")
        idempotency_key = request.POST.get("idempotency_key") or str(uuid.uuid4())

        try:
            seat_uuid = uuid.UUID(seat_id)
            session_uuids = [uuid.UUID(s) for s in session_ids]
            alloc_specs = [{"attendee_id": request.user.id, "seat_id": seat_uuid, "session_ids": session_uuids}]

            if booking_type == Reservation.BookingType.GROUP:
                invitee_code = request.POST.get("invitee_id", "").strip().upper()
                invitee_seat_id = request.POST.get("invitee_seat_id")
                invitee_session_ids = request.POST.getlist("invitee_session_ids") or session_ids
                if invitee_code and invitee_seat_id:
                    invitee = User.objects.get(institutional_id=invitee_code)
                    alloc_specs.append(
                        {
                            "attendee_id": invitee.id,
                            "seat_id": uuid.UUID(invitee_seat_id),
                            "session_ids": [uuid.UUID(s) for s in invitee_session_ids],
                        }
                    )

            res = create_reservation(
                creator=request.user,
                attendee_allocations=alloc_specs,
                booking_type=booking_type,
                idempotency_key=idempotency_key,
            )
            messages.success(request, f"Reservation {res} created with status: {res.get_status_display()}.")
            return redirect("reservations:my_reservations")
        except (ValidationError, PermissionDenied, ValueError, User.DoesNotExist) as exc:
            messages.error(request, str(exc))

    sessions = LibrarySession.objects.filter(is_active=True)[:16]
    seats = LibrarySeat.objects.filter(is_active=True).select_related("zone")
    return render(
        request,
        "reservations/create_booking.html",
        {"sessions": sessions, "seats": seats, "idempotency_key": str(uuid.uuid4())},
    )


@login_required
@require_POST
def respond_invite_view(request, reservation_id):
    accept = request.POST.get("decision") == "accept"
    try:
        res = respond_to_invitation(actor=request.user, reservation_id=reservation_id, accept=accept)
        messages.success(request, f"Response recorded. Reservation status is now {res.get_status_display()}.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, str(exc))
    return redirect("reservations:my_reservations")


@login_required
@require_POST
def cancel_booking_view(request, reservation_id):
    try:
        cancel_reservation(actor=request.user, reservation_id=reservation_id)
        messages.success(request, "Reservation cancelled.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, str(exc))
    return redirect("reservations:my_reservations")


@login_required
@require_POST
def checkin_view(request, allocation_id):
    try:
        record_checkin(actor=request.user, allocation_id=allocation_id)
        messages.success(request, "Check-in recorded.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, str(exc))
    return redirect(request.META.get("HTTP_REFERER") or "reservations:my_reservations")


@login_required
@require_roles(RoleCode.LIBRARY_STAFF, RoleCode.LIBRARY_SUPERVISOR)
def staff_operations_view(request):
    if request.method == "POST":
        op = request.POST.get("operation")
        try:
            if op == "release_no_shows":
                count = release_no_shows(actor=request.user)
                messages.success(request, f"Released {count} unclaimed past-grace seat(s).")
            elif op == "override":
                apply_supervisor_override(
                    actor=request.user,
                    allocation_id=request.POST["allocation_id"],
                    new_state=request.POST["new_state"],
                    reason=request.POST.get("reason", ""),
                )
                messages.success(request, "Supervisor override applied and logged to audit trail.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        return redirect("reservations:staff_operations")

    allocations = (
        AttendeeSessionAllocation.objects.select_related("attendee", "session", "seat__zone", "reservation")
        .order_by("-created_at")[:50]
    )
    return render(request, "reservations/staff_operations.html", {"allocations": allocations})
