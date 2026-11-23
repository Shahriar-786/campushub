from functools import wraps

from django.core.exceptions import PermissionDenied


def require_roles(*allowed_roles: str):
    """Deny-by-default server-side role guard."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            if not request.user.has_role(*allowed_roles):
                raise PermissionDenied("Insufficient role permissions for this resource.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
