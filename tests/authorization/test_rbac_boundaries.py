import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.accounts.models import RoleCode
from apps.audit.models import AuditEvent


@pytest.mark.django_db
def test_student_denied_admin_and_staff_routes(client, make_user):
    student = make_user("DIU-AUTH-001", RoleCode.STUDENT)
    client.force_login(student)

    for url_name in ("accounts:user_management", "reservations:staff_operations", "library:manage_closures", "audit:list"):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 403


@pytest.mark.django_db
def test_audit_events_are_append_only(make_user):
    admin = make_user("DIU-AUTH-ADM", RoleCode.SYSTEM_ADMIN)
    ev = AuditEvent.objects.create(actor=admin, action="TEST_EVENT", target_type="System", target_id="1")
    with pytest.raises(PermissionDenied):
        ev.action = "TAMPERED"
        ev.save()
    with pytest.raises(PermissionDenied):
        ev.delete()
