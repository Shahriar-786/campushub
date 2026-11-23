from datetime import date, time

import pytest

from apps.accounts.models import Role, RoleCode, User, UserRole
from apps.library.models import BookingPolicyVersion, LibrarySeat, LibrarySession, LibraryZone


@pytest.fixture
def seed_roles(db):
    roles = {}
    for code, label in RoleCode.choices:
        roles[code], _ = Role.objects.get_or_create(code=code, defaults={"name": label})
    return roles


@pytest.fixture
def make_user(db, seed_roles):
    def _factory(inst_id: str, role_code: str):
        user = User.objects.create_user(
            institutional_id=inst_id,
            email=f"{inst_id.lower()}@test.campushub.local",
            full_name=f"Test {inst_id}",
            password="StrongPassword@2026",
        )
        UserRole.objects.create(user=user, role=seed_roles[role_code], is_active=True)
        return user

    return _factory


@pytest.fixture
def library_setup(db):
    BookingPolicyVersion.get_active()
    zone = LibraryZone.objects.create(code="Z-TEST", name="Test Zone")
    seats = [LibrarySeat.objects.create(zone=zone, seat_code=f"S{i:02d}") for i in range(1, 5)]
    op_date = date(2026, 12, 1)
    sessions = [
        LibrarySession.objects.create(
            session_date=op_date,
            session_index=i,
            label=f"Session {i}",
            start_time=time(8 + i * 2, 0),
            end_time=time(10 + i * 2, 0),
        )
        for i in range(1, 5)
    ]
    return {"zone": zone, "seats": seats, "sessions": sessions, "date": op_date}
