from django.urls import path

from apps.lost_found import views

app_name = "lost_found"

urlpatterns = [
    path("", views.report_list_view, name="list"),
    path("<uuid:pk>/", views.report_detail_view, name="detail"),
]
