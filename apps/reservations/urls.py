from django.urls import path

from apps.reservations import views

app_name = "reservations"

urlpatterns = [
    path("my/", views.my_reservations_view, name="my_reservations"),
    path("book/", views.create_booking_view, name="create_booking"),
    path("<uuid:reservation_id>/invite/", views.respond_invite_view, name="respond_invite"),
    path("<uuid:reservation_id>/cancel/", views.cancel_booking_view, name="cancel_booking"),
    path("allocation/<uuid:allocation_id>/checkin/", views.checkin_view, name="checkin"),
    path("staff/operations/", views.staff_operations_view, name="staff_operations"),
]
