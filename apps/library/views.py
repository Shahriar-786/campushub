from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.access_control.decorators import require_roles
from apps.accounts.models import RoleCode
from apps.audit.services import log_audit_event
from apps.forecasting.models import ForecastValue
from apps.library.models import (
    BookingPolicyVersion,
    LibrarySeat,
    LibrarySession,
    LibraryZone,
    SeatClosure,
    ZoneClosure,
)
from apps.reservations.models import AttendeeSessionAllocation


@login_required
def availability_view(request):
    selected_date_str = request.GET.get("date")
    try:
        selected_date = date.fromisoformat(selected_date_str) if selected_date_str else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    zones = LibraryZone.objects.filter(is_active=True).prefetch_related("seats")
    sessions = LibrarySession.objects.filter(session_date=selected_date, is_active=True)
    policy = BookingPolicyVersion.get_active()

    taken_pairs = set(
        AttendeeSessionAllocation.objects.filter(
            session__session_date=selected_date,
            allocation_state__in=[
                AttendeeSessionAllocation.AllocationState.CONFIRMED,
                AttendeeSessionAllocation.AllocationState.CHECKED_IN,
            ],
        ).values_list("seat_id", "session_id")
    )

    now = timezone.now()
    closed_zone_ids = set(
        ZoneClosure.objects.filter(is_active=True, start_at__lte=now, end_at__gte=now).values_list("zone_id", flat=True)
    )
    closed_seat_ids = set(
        SeatClosure.objects.filter(is_active=True, start_at__lte=now, end_at__gte=now).values_list("seat_id", flat=True)
    )

    # Forecast is loaded separately as an advisory estimate, never mixed into live seat counts
    forecasts = ForecastValue.objects.filter(target_date=selected_date).select_related("zone", "run__model_version")[:12]

    availability_rows = []
    for zone in zones:
        zone_seats = [s for s in zone.seats.all() if s.is_active]
        session_cards = []
        for sess in sessions:
            available_seats = [
                s
                for s in zone_seats
                if (zone.id not in closed_zone_ids)
                and (s.id not in closed_seat_ids)
                and ((s.id, sess.id) not in taken_pairs)
            ]
            session_cards.append(
                {
                    "session": sess,
                    "total_capacity": len(zone_seats),
                    "available_count": len(available_seats),
                    "available_seats": available_seats,
                    "is_closed": zone.id in closed_zone_ids,
                }
            )
        availability_rows.append({"zone": zone, "sessions": session_cards})

    return render(
        request,
        "library/availability.html",
        {
            "selected_date": selected_date,
            "availability_rows": availability_rows,
            "policy": policy,
            "forecasts": forecasts,
        },
    )


@login_required
@require_roles(RoleCode.LIBRARY_STAFF, RoleCode.LIBRARY_SUPERVISOR)
def manage_closures_view(request):
    if request.method == "POST":
        closure_type = request.POST.get("closure_type", "zone")
        reason = request.POST.get("reason", "").strip()
        start_at = timezone.make_aware(datetime.fromisoformat(request.POST["start_at"]))
        end_at = timezone.make_aware(datetime.fromisoformat(request.POST["end_at"]))
        if not reason or end_at <= start_at:
            messages.error(request, "Provide a valid reason and end time after start time.")
            return redirect("library:manage_closures")

        if closure_type == "zone":
            zone = get_object_or_404(LibraryZone, pk=request.POST["zone_id"])
            closure = ZoneClosure.objects.create(
                zone=zone, start_at=start_at, end_at=end_at, reason=reason, created_by=request.user
            )
            log_audit_event(
                actor=request.user,
                action="ZONE_CLOSURE_CREATED",
                target_type="ZoneClosure",
                target_id=str(closure.pk),
                after_state={"zone": zone.code, "reason": reason},
                reason=reason,
            )
            messages.success(request, f"Zone {zone.code} closed temporarily.")
        else:
            seat = get_object_or_404(LibrarySeat, pk=request.POST["seat_id"])
            closure = SeatClosure.objects.create(
                seat=seat, start_at=start_at, end_at=end_at, reason=reason, created_by=request.user
            )
            log_audit_event(
                actor=request.user,
                action="SEAT_CLOSURE_CREATED",
                target_type="SeatClosure",
                target_id=str(closure.pk),
                after_state={"seat": str(seat), "reason": reason},
                reason=reason,
            )
            messages.success(request, f"Seat {seat} closed temporarily.")
        return redirect("library:manage_closures")

    return render(
        request,
        "library/manage_closures.html",
        {
            "zones": LibraryZone.objects.filter(is_active=True),
            "seats": LibrarySeat.objects.filter(is_active=True).select_related("zone"),
            "zone_closures": ZoneClosure.objects.filter(is_active=True).select_related("zone")[:20],
            "seat_closures": SeatClosure.objects.filter(is_active=True).select_related("seat__zone")[:20],
        },
    )
