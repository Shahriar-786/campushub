from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Readiness probe without exposing internal stack traces or secrets."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "service": "campushub-prototype"})
    except Exception:
        return JsonResponse({"status": "degraded"}, status=503)
