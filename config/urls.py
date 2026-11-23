from django.contrib import admin
from django.urls import include, path

from apps.core.views import health_check

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
    path("accounts/", include("apps.accounts.urls")),
    path("audit/", include("apps.audit.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("library/", include("apps.library.urls")),
    path("reservations/", include("apps.reservations.urls")),
    path("forecasting/", include("apps.forecasting.urls")),
    path("lost-found/", include("apps.lost_found.urls")),
    path("facilities/", include("apps.facilities.urls")),
    path("", include("apps.dashboards.urls")),
]
