import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.access_control.decorators import require_roles
from apps.accounts.models import RoleCode
from apps.forecasting.models import ForecastRun
from apps.forecasting.services import run_synthetic_forecast_pipeline


@login_required
@require_roles(
    RoleCode.STUDENT,
    RoleCode.LIBRARY_STAFF,
    RoleCode.LIBRARY_SUPERVISOR,
    RoleCode.MANAGEMENT_OFFICER,
    RoleCode.SYSTEM_ADMIN,
)
def forecast_dashboard_view(request):
    if request.method == "POST" and request.user.has_role(RoleCode.LIBRARY_SUPERVISOR, RoleCode.SYSTEM_ADMIN):
        run_synthetic_forecast_pipeline(horizon_days=7)
        messages.success(request, "New synthetic demand forecast run completed and published.")
        return redirect("forecasting:dashboard")

    latest_run = ForecastRun.objects.select_related("model_version__dataset").prefetch_related("metrics", "values__zone").first()
    chart_labels, chart_predicted, chart_capacity = [], [], []
    if latest_run:
        for val in latest_run.values.all()[:16]:
            chart_labels.append(f"{val.target_date} S{val.session_index} ({val.zone.code})")
            chart_predicted.append(val.predicted_occupancy)
            chart_capacity.append(val.configured_capacity)

    return render(
        request,
        "forecasting/dashboard.html",
        {
            "latest_run": latest_run,
            "chart_labels_json": json.dumps(chart_labels),
            "chart_predicted_json": json.dumps(chart_predicted),
            "chart_capacity_json": json.dumps(chart_capacity),
        },
    )
