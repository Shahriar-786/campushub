from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.access_control.decorators import require_roles
from apps.accounts.models import Role, RoleCode, User
from apps.accounts.services import assign_role, revoke_role, set_account_active
from apps.audit.services import log_audit_event


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboards:home")

    if request.method == "POST":
        institutional_id = request.POST.get("institutional_id", "").strip().upper()
        password = request.POST.get("password", "")
        user = authenticate(request, institutional_id=institutional_id, password=password)
        if user is not None and user.is_active:
            login(request, user)
            request.session.cycle_key()
            log_audit_event(
                actor=user,
                action="USER_LOGIN",
                target_type="User",
                target_id=str(user.pk),
                after_state={"roles": sorted(user.active_role_codes)},
            )
            return redirect(request.GET.get("next") or "dashboards:home")
        messages.error(request, "Invalid institutional ID or password.")

    return render(request, "accounts/login.html")


@login_required
@require_http_methods(["POST"])
def logout_view(request):
    log_audit_event(
        actor=request.user,
        action="USER_LOGOUT",
        target_type="User",
        target_id=str(request.user.pk),
    )
    logout(request)
    return redirect("accounts:login")


@login_required
@require_roles(RoleCode.SYSTEM_ADMIN)
def user_management_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        target = get_object_or_404(User, pk=request.POST.get("user_id"))
        reason = request.POST.get("reason", "Administrative update").strip() or "Administrative update"
        try:
            if action == "assign_role":
                assign_role(
                    actor=request.user,
                    target_user=target,
                    role_code=request.POST.get("role_code", ""),
                    reason=reason,
                )
                messages.success(request, f"Assigned role to {target.institutional_id}.")
            elif action == "revoke_role":
                revoke_role(
                    actor=request.user,
                    target_user=target,
                    role_code=request.POST.get("role_code", ""),
                    reason=reason,
                )
                messages.success(request, f"Revoked role from {target.institutional_id}.")
            elif action == "toggle_active":
                set_account_active(
                    actor=request.user,
                    target_user=target,
                    is_active=not target.is_active,
                    reason=reason,
                )
                messages.success(request, f"Updated active status for {target.institutional_id}.")
        except (ValidationError, Role.DoesNotExist) as exc:
            messages.error(request, str(exc))
        return redirect("accounts:user_management")

    users = User.objects.prefetch_related("user_roles__role").all()
    roles = Role.objects.all()
    return render(request, "accounts/user_management.html", {"users": users, "roles": roles})
