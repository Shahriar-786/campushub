from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.models import RoleCode, User
from apps.audit.models import AuditEvent
from apps.facilities.models import FacilityTicket
from apps.forecasting.models import ForecastRun
from apps.lost_found.models import LostFoundReport
from apps.reservations.models import AttendeeSessionAllocation, Reservation


@login_required
def home_view(request):
    roles = request.user.active_role_codes
    context = {
        "roles": sorted(roles),
        "metrics": {
            "active_reservations": Reservation.objects.filter(status=Reservation.Status.CONFIRMED).count(),
            "open_tickets": FacilityTicket.objects.exclude(
                status__in=[FacilityTicket.Status.RESOLVED, FacilityTicket.Status.CLOSED, FacilityTicket.Status.REJECTED]
            ).count(),
            "active_lf_reports": LostFoundReport.objects.exclude(
                status__in=[LostFoundReport.Status.CLOSED, LostFoundReport.Status.REJECTED]
            ).count(),
            "forecast_runs": ForecastRun.objects.count(),
        },
        "my_allocations": AttendeeSessionAllocation.objects.filter(attendee=request.user)[:5]
        if RoleCode.STUDENT in roles
        else [],
        "recent_audits": AuditEvent.objects.all()[:8]
        if roles.intersection({RoleCode.SYSTEM_ADMIN, RoleCode.IT_STAFF})
        else [],
        "total_users": User.objects.count() if RoleCode.SYSTEM_ADMIN in roles else None,
    }
    return render(request, "dashboards/home.html", context)
