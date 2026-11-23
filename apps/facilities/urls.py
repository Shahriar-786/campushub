from django.urls import path

from apps.facilities import views

app_name = "facilities"

urlpatterns = [
    path("", views.ticket_list_view, name="list"),
    path("<uuid:pk>/", views.ticket_detail_view, name="detail"),
]
