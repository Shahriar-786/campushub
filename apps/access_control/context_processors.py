from apps.accounts.models import RoleCode


def user_roles_context(request):
    if request.user.is_authenticated:
        roles = request.user.active_role_codes
    else:
        roles = set()
    return {
        "active_roles": roles,
        "RoleCode": RoleCode,
    }
