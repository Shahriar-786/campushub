from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.notifications.models import NotificationOutbox


@login_required
def notification_list_view(request):
    items = NotificationOutbox.objects.filter(recipient=request.user)[:50]
    return render(request, "notifications/list.html", {"notifications": items})


@login_required
@require_POST
def mark_read_view(request, pk):
    item = get_object_or_404(NotificationOutbox, pk=pk, recipient=request.user)
    item.is_read = True
    item.save(update_fields=["is_read", "updated_at"])
    return redirect("notifications:list")
