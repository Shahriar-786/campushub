from apps.notifications.models import NotificationOutbox


def enqueue_notification(*, recipient, event_type: str, title: str, body: str, dedupe_key: str) -> NotificationOutbox:
    """Transactional outbox insert: safely deduplicated and committed with domain state."""
    obj, _ = NotificationOutbox.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "recipient": recipient,
            "event_type": event_type,
            "title": title,
            "body": body,
            "status": NotificationOutbox.Status.SENT,
        },
    )
    return obj
