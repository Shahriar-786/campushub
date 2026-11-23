from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import RoleCode, User
from apps.facilities.models import FacilityTicket
from apps.facilities.services import transition_ticket


@login_required
def ticket_list_view(request):
    if request.method == "POST":
        if not request.user.has_role(RoleCode.STUDENT, RoleCode.LIBRARY_STAFF, RoleCode.LIBRARY_SUPERVISOR):
            raise PermissionDenied("Not authorized to submit facility tickets.")
        FacilityTicket.objects.create(
            reporter=request.user,
            queue_type=request.POST.get("queue_type", FacilityTicket.QueueType.UTILITY),
            category=request.POST["category"].strip(),
            location=request.POST["location"].strip(),
            description=request.POST["description"].strip(),
            priority=request.POST.get("priority", FacilityTicket.Priority.MEDIUM),
        )
        messages.success(request, "Facility/equipment issue ticket submitted.")
        return redirect("facilities:list")

    if request.user.has_role(RoleCode.MANAGEMENT_OFFICER):
        tickets = FacilityTicket.objects.select_related("reporter", "assigned_to").all()[:50]
    elif request.user.has_role(RoleCode.IT_STAFF):
        tickets = FacilityTicket.objects.filter(queue_type=FacilityTicket.QueueType.IT)[:50]
    elif request.user.has_role(RoleCode.UTILITY_STAFF):
        tickets = FacilityTicket.objects.filter(queue_type=FacilityTicket.QueueType.UTILITY)[:50]
    else:
        tickets = FacilityTicket.objects.filter(reporter=request.user)[:50]

    return render(request, "facilities/list.html", {"tickets": tickets})


@login_required
def ticket_detail_view(request, pk):
    ticket = get_object_or_404(
        FacilityTicket.objects.select_related("reporter", "assigned_to").prefetch_related("work_logs__actor", "transitions"),
        pk=pk,
    )
    is_owner = ticket.reporter_id == request.user.id
    is_queue_staff = (
        (ticket.queue_type == FacilityTicket.QueueType.IT and request.user.has_role(RoleCode.IT_STAFF))
        or (ticket.queue_type == FacilityTicket.QueueType.UTILITY and request.user.has_role(RoleCode.UTILITY_STAFF))
        or request.user.has_role(RoleCode.MANAGEMENT_OFFICER)
    )
    if not (is_owner or is_queue_staff):
        raise PermissionDenied("You cannot view another user's ticket.")

    if request.method == "POST":
        try:
            assignee_id = request.POST.get("assignee_id")
            assignee = User.objects.filter(pk=assignee_id).first() if assignee_id else None
            transition_ticket(
                actor=request.user,
                ticket=ticket,
                new_status=request.POST["new_status"],
                note=request.POST.get("note", ""),
                assignee=assignee,
            )
            messages.success(request, f"Ticket updated to {ticket.get_status_display()}.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        return redirect("facilities:detail", pk=ticket.pk)

    staff_candidates = User.objects.filter(
        user_roles__role__code__in=[RoleCode.UTILITY_STAFF, RoleCode.IT_STAFF], user_roles__is_active=True
    ).distinct()
    return render(
        request,
        "facilities/detail.html",
        {"ticket": ticket, "is_queue_staff": is_queue_staff, "staff_candidates": staff_candidates},
    )
