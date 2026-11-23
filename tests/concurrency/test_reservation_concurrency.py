import threading
from datetime import datetime, timedelta

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.accounts.models import RoleCode
from apps.library.models import SeatClosure
from apps.reservations.models import AttendeeSessionAllocation, Reservation
from apps.reservations.services import ReservationConflictError, create_reservation


@pytest.mark.django_db(transaction=True)
def test_idempotent_retry_creates_single_reservation(make_user, library_setup):
    student = make_user("DIU-C-001", RoleCode.STUDENT)
    sess = library_setup["sessions"][0]
    seat = library_setup["seats"][0]

    r1 = create_reservation(
        creator=student,
        attendee_allocations=[{"attendee_id": student.id, "seat_id": seat.id, "session_ids": [sess.id]}],
        idempotency_key="idem-key-123",
    )
    r2 = create_reservation(
        creator=student,
        attendee_allocations=[{"attendee_id": student.id, "seat_id": seat.id, "session_ids": [sess.id]}],
        idempotency_key="idem-key-123",
    )
    assert r1.id == r2.id
    assert Reservation.objects.filter(idempotency_key="idem-key-123").count() == 1


@pytest.mark.django_db(transaction=True)
def test_simultaneous_last_seat_contention(make_user, library_setup):
    stu1 = make_user("DIU-C-002", RoleCode.STUDENT)
    stu2 = make_user("DIU-C-003", RoleCode.STUDENT)
    sess = library_setup["sessions"][0]
    seat = library_setup["seats"][0]

    results = []
    barrier = threading.Barrier(2)

    def worker(user):
        close_old_connections()
        barrier.wait()
        try:
            res = create_reservation(
                creator=user,
                attendee_allocations=[{"attendee_id": user.id, "seat_id": seat.id, "session_ids": [sess.id]}],
            )
            results.append(("ok", res.id))
        except Exception as exc:
            results.append(("err", type(exc).__name__))
        finally:
            close_old_connections()

    t1 = threading.Thread(target=worker, args=(stu1,))
    t2 = threading.Thread(target=worker, args=(stu2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [r for r in results if r[0] == "ok"]
    assert len(successes) == 1
    assert AttendeeSessionAllocation.objects.filter(seat=seat, session=sess, allocation_state="CONFIRMED").count() == 1


@pytest.mark.django_db
def test_seat_closure_blocks_booking(make_user, library_setup):
    student = make_user("DIU-C-004", RoleCode.STUDENT)
    staff = make_user("DIU-C-LIB", RoleCode.LIBRARY_STAFF)
    sess = library_setup["sessions"][0]
    seat = library_setup["seats"][0]

    start = timezone.make_aware(datetime.combine(sess.session_date, sess.start_time)) - timedelta(minutes=10)
    end = timezone.make_aware(datetime.combine(sess.session_date, sess.end_time)) + timedelta(minutes=10)
    SeatClosure.objects.create(seat=seat, start_at=start, end_at=end, reason="Broken desk", created_by=staff)

    with pytest.raises(ReservationConflictError):
        create_reservation(
            creator=student,
            attendee_allocations=[{"attendee_id": student.id, "seat_id": seat.id, "session_ids": [sess.id]}],
        )
