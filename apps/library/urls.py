from django.urls import path

from apps.library import views

app_name = "library"

urlpatterns = [
    path("availability/", views.availability_view, name="availability"),
    path("closures/", views.manage_closures_view, name="manage_closures"),
]
