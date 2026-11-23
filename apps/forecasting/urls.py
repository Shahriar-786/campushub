from django.urls import path

from apps.forecasting import views

app_name = "forecasting"

urlpatterns = [
    path("", views.forecast_dashboard_view, name="dashboard"),
]
