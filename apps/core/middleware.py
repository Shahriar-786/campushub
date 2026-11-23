import threading
import uuid

_local = threading.local()


def get_correlation_id() -> str:
    return getattr(_local, "correlation_id", "")


class RequestCorrelationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        _local.correlation_id = cid
        request.correlation_id = cid
        response = self.get_response(request)
        response["X-Correlation-ID"] = cid
        return response
