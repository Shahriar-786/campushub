from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.access_control.decorators import require_roles
from apps.accounts.models import RoleCode
from apps.audit.models import AuditEvent


@login_required
@require_roles(RoleCode.SYSTEM_ADMIN, RoleCode.LIBRARY_SUPERVISOR, RoleCode.IT_STAFF, RoleCode.MANAGEMENT_OFFICER)
def audit_log_view(request):
    qs = AuditEvent.objects.select_related("actor")
    if request.user.has_role(RoleCode.LIBRARY_SUPERVISOR) and not request.user.has_role(RoleCode.SYSTEM_ADMIN):
        qs = qs.filter(target_type__in=["Reservation", "AttendeeSessionAllocation", "SeatClosure", "ZoneClosure"])
    events = qs[:100]
    return render(request, "audit/audit_list.html", {"events": events})
