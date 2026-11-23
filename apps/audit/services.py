from apps.audit.models import AuditEvent
from apps.core.middleware import get_correlation_id


def log_audit_event(
    *,
    actor,
    action: str,
    target_type: str,
    target_id: str,
    before_state: dict | None = None,
    after_state: dict | None = None,
    reason: str = "",
    source: str = "web",
) -> AuditEvent:
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        before_state=before_state or {},
        after_state=after_state or {},
        reason=reason,
        correlation_id=get_correlation_id(),
        source=source,
    )
