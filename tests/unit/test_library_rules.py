import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import RoleCode
from apps.reservations.models import AttendeeSessionAllocation, Reservation
from apps.reservations.services import (
    apply_supervisor_override,
    create_reservation,
    record_checkin,
    release_no_shows,
    respond_to_invitation,
)


@pytest.mark.django_db
def test_three_consecutive_sessions_rejected(make_user, library_setup):
    student = make_user("DIU-T-001", RoleCode.STUDENT)
    sessions = library_setup["sessions"]
    seat = library_setup["seats"][0]

    with pytest.raises(ValidationError):
        create_reservation(
            creator=student,
            attendee_allocations=[
                {"attendee_id": student.id, "seat_id": seat.id, "session_ids": [s.id for s in sessions[:3]]}
            ],
        )


@pytest.mark.django_db
def test_no_second_booking_same_operational_day(make_user, library_setup):
    student = make_user("DIU-T-002", RoleCode.STUDENT)
    sessions = library_setup["sessions"]
    seat = library_setup["seats"][0]

    res = create_reservation(
        creator=student,
        attendee_allocations=[{"attendee_id": student.id, "seat_id": seat.id, "session_ids": [sessions[0].id]}],
    )
    assert res.status == Reservation.Status.CONFIRMED

    with pytest.raises(ValidationError):
        create_reservation(
            creator=student,
            attendee_allocations=[{"attendee_id": student.id, "seat_id": seat.id, "session_ids": [sessions[2].id]}],
        )


@pytest.mark.django_db
def test_reciprocal_group_booking_blocked_and_per_attendee_sessions(make_user, library_setup):
    stu_a = make_user("DIU-T-003", RoleCode.STUDENT)
    stu_b = make_user("DIU-T-004", RoleCode.STUDENT)
    sessions = library_setup["sessions"]
    seats = library_setup["seats"]

    # Group booking where A attends S1+S2 and B attends only S2
    res = create_reservation(
        creator=stu_a,
        booking_type=Reservation.BookingType.GROUP,
        attendee_allocations=[
            {"attendee_id": stu_a.id, "seat_id": seats[0].id, "session_ids": [sessions[0].id, sessions[1].id]},
            {"attendee_id": stu_b.id, "seat_id": seats[1].id, "session_ids": [sessions[1].id]},
        ],
    )
    assert res.status == Reservation.Status.PENDING_ACCEPTANCE

    # Invitee B accepts -> confirmed atomically
    res = respond_to_invitation(actor=stu_b, reservation_id=res.id, accept=True)
    assert res.status == Reservation.Status.CONFIRMED
    assert AttendeeSessionAllocation.objects.filter(attendee=stu_b, allocation_state="CONFIRMED").count() == 1

    # Reciprocal bypass attempt: B tries to book A for S3 -> MUST be rejected
    with pytest.raises(ValidationError):
        create_reservation(
            creator=stu_b,
            booking_type=Reservation.BookingType.GROUP,
            attendee_allocations=[
                {"attendee_id": stu_a.id, "seat_id": seats[2].id, "session_ids": [sessions[2].id]}
            ],
        )


@pytest.mark.django_db
def test_declined_invitation_rejects_all_or_nothing_group(make_user, library_setup):
    stu_a = make_user("DIU-T-005", RoleCode.STUDENT)
    stu_b = make_user("DIU-T-006", RoleCode.STUDENT)
    sessions = library_setup["sessions"]
    seats = library_setup["seats"]

    res = create_reservation(
        creator=stu_a,
        booking_type=Reservation.BookingType.GROUP,
        attendee_allocations=[
            {"attendee_id": stu_a.id, "seat_id": seats[0].id, "session_ids": [sessions[0].id]},
            {"attendee_id": stu_b.id, "seat_id": seats[1].id, "session_ids": [sessions[0].id]},
        ],
    )
    res = respond_to_invitation(actor=stu_b, reservation_id=res.id, accept=False)
    assert res.status == Reservation.Status.REJECTED


@pytest.mark.django_db
def test_checkin_prevents_no_show_release_and_override_requires_supervisor(make_user, library_setup):
    student = make_user("DIU-T-007", RoleCode.STUDENT)
    staff = make_user("DIU-T-LIB", RoleCode.LIBRARY_STAFF)
    supervisor = make_user("DIU-T-SUP", RoleCode.LIBRARY_SUPERVISOR)
    sessions = library_setup["sessions"]
    seat = library_setup["seats"][0]

    res = create_reservation(
        creator=student,
        attendee_allocations=[{"attendee_id": student.id, "seat_id": seat.id, "session_ids": [sessions[0].id]}],
    )
    alloc = res.allocations.first()
    record_checkin(actor=student, allocation_id=alloc.id)
    assert release_no_shows() == 0

    with pytest.raises(PermissionDenied):
        apply_supervisor_override(actor=staff, allocation_id=alloc.id, new_state="CANCELLED", reason="test")

    updated = apply_supervisor_override(
        actor=supervisor, allocation_id=alloc.id, new_state="COMPLETED", reason="Verified manual checkout"
    )
    assert updated.allocation_state == "COMPLETED"
