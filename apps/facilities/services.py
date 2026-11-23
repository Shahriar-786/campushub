from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import RoleCode, User
from apps.audit.services import log_audit_event
from apps.facilities.models import FacilityTicket, TicketTransition, WorkLog

ALLOWED_TRANSITIONS = {
    FacilityTicket.Status.SUBMITTED: {
        FacilityTicket.Status.UNDER_REVIEW,
        FacilityTicket.Status.TRIAGED,
        FacilityTicket.Status.ASSIGNED,
        FacilityTicket.Status.NEEDS_INFORMATION,
        FacilityTicket.Status.REJECTED,
    },
    FacilityTicket.Status.UNDER_REVIEW: {
        FacilityTicket.Status.TRIAGED,
        FacilityTicket.Status.ASSIGNED,
        FacilityTicket.Status.NEEDS_INFORMATION,
        FacilityTicket.Status.REJECTED,
    },
    FacilityTicket.Status.NEEDS_INFORMATION: {
        FacilityTicket.Status.UNDER_REVIEW,
        FacilityTicket.Status.TRIAGED,
        FacilityTicket.Status.ASSIGNED,
    },
    FacilityTicket.Status.TRIAGED: {FacilityTicket.Status.ASSIGNED, FacilityTicket.Status.ESCALATED},
    FacilityTicket.Status.ASSIGNED: {
        FacilityTicket.Status.IN_PROGRESS,
        FacilityTicket.Status.ESCALATED,
        FacilityTicket.Status.NEEDS_INFORMATION,
    },
    FacilityTicket.Status.IN_PROGRESS: {
        FacilityTicket.Status.RESOLVED,
        FacilityTicket.Status.ESCALATED,
        FacilityTicket.Status.NEEDS_INFORMATION,
    },
    FacilityTicket.Status.ESCALATED: {FacilityTicket.Status.ASSIGNED, FacilityTicket.Status.IN_PROGRESS},
    FacilityTicket.Status.RESOLVED: {FacilityTicket.Status.CLOSED, FacilityTicket.Status.REOPENED},
    FacilityTicket.Status.REOPENED: {FacilityTicket.Status.ASSIGNED, FacilityTicket.Status.IN_PROGRESS},
}


def _can_manage_ticket(actor: User, ticket: FacilityTicket) -> bool:
    if actor.has_role(RoleCode.MANAGEMENT_OFFICER):
        return True
    if ticket.queue_type == FacilityTicket.QueueType.IT and actor.has_role(RoleCode.IT_STAFF):
        return True
    if ticket.queue_type == FacilityTicket.QueueType.UTILITY and actor.has_role(RoleCode.UTILITY_STAFF):
        return True
    return False


@transaction.atomic
def transition_ticket(
    *,
    actor: User,
    ticket: FacilityTicket,
    new_status: str,
    note: str = "",
    assignee: User | None = None,
) -> FacilityTicket:
    if not _can_manage_ticket(actor, ticket):
        raise PermissionDenied("You are not authorized to update this facility ticket queue.")

    allowed = ALLOWED_TRANSITIONS.get(ticket.status, set())
    if new_status not in allowed:
        raise ValidationError(f"Transition from {ticket.status} to {new_status} is not permitted.")

    if new_status == FacilityTicket.Status.RESOLVED and not note.strip():
        raise ValidationError("A completion note is mandatory when marking a ticket RESOLVED.")
    if new_status == FacilityTicket.Status.REOPENED and not note.strip():
        raise ValidationError("A reason is mandatory when reopening a resolved ticket.")

    old = ticket.status
    ticket.status = new_status
    if assignee is not None:
        ticket.assigned_to = assignee
    ticket.save()

    if note.strip():
        WorkLog.objects.create(ticket=ticket, actor=actor, note=note.strip())

    TicketTransition.objects.create(
        ticket=ticket, from_state=old, to_state=new_status, actor=actor, reason=note.strip()
    )
    log_audit_event(
        actor=actor,
        action="FACILITY_TICKET_TRANSITION",
        target_type="FacilityTicket",
        target_id=str(ticket.id),
        before_state={"status": old},
        after_state={"status": new_status},
        reason=note.strip(),
    )
    return ticket
