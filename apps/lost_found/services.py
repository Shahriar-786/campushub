from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import RoleCode, User
from apps.audit.services import log_audit_event
from apps.lost_found.models import (
    ItemHandover,
    LostFoundReport,
    LostFoundTransition,
    OwnershipClaim,
)


@transaction.atomic
def review_report(*, actor: User, report: LostFoundReport, new_status: str, reason: str) -> LostFoundReport:
    if not actor.has_role(RoleCode.LF_REVIEWER):
        raise PermissionDenied("Only Lost and Found Reviewer can screen reports.")
    allowed = {
        LostFoundReport.Status.ACTIVE,
        LostFoundReport.Status.NEEDS_INFORMATION,
        LostFoundReport.Status.REJECTED,
    }
    if new_status not in allowed:
        raise ValidationError("Invalid review outcome.")
    old = report.status
    report.status = new_status
    report.save(update_fields=["status", "updated_at"])
    LostFoundTransition.objects.create(report=report, from_state=old, to_state=new_status, actor=actor, reason=reason)
    log_audit_event(
        actor=actor,
        action="LF_REPORT_REVIEWED",
        target_type="LostFoundReport",
        target_id=str(report.id),
        before_state={"status": old},
        after_state={"status": new_status},
        reason=reason,
    )
    return report


@transaction.atomic
def decide_claim(
    *,
    actor: User,
    claim: OwnershipClaim,
    decision: str,
    reason: str,
    security_officer: User | None = None,
) -> OwnershipClaim:
    if not actor.has_role(RoleCode.LF_REVIEWER):
        raise PermissionDenied("Only authorized Lost and Found Reviewer can decide ownership claims.")
    if decision not in (
        OwnershipClaim.Status.APPROVED,
        OwnershipClaim.Status.REJECTED,
        OwnershipClaim.Status.ESCALATED,
        OwnershipClaim.Status.NEEDS_INFORMATION,
    ):
        raise ValidationError("Invalid claim decision.")
    if decision == OwnershipClaim.Status.ESCALATED and security_officer is None:
        raise ValidationError("Assign a Security Officer when escalating a disputed/suspicious claim.")

    old = claim.status
    claim.status = decision
    claim.decided_by = actor
    claim.decision_reason = reason
    if security_officer is not None:
        claim.assigned_security_officer = security_officer
    claim.save()
    log_audit_event(
        actor=actor,
        action="LF_CLAIM_DECIDED",
        target_type="OwnershipClaim",
        target_id=str(claim.id),
        before_state={"status": old},
        after_state={"status": decision},
        reason=reason,
    )
    return claim


@transaction.atomic
def record_handover(*, actor: User, claim: OwnershipClaim, verification_ref: str, outcome_notes: str) -> ItemHandover:
    is_reviewer = actor.has_role(RoleCode.LF_REVIEWER)
    is_assigned_security = (
        actor.has_role(RoleCode.SECURITY_OFFICER) and claim.assigned_security_officer_id == actor.id
    )
    if not (is_reviewer or is_assigned_security):
        raise PermissionDenied("Not authorized to record handover for this claim.")
    if claim.status != OwnershipClaim.Status.APPROVED:
        raise ValidationError("Handover cannot be recorded before ownership claim is APPROVED.")
    if hasattr(claim, "handover"):
        raise ValidationError("Item handover has already been recorded for this claim.")

    handover = ItemHandover.objects.create(
        claim=claim,
        released_by=actor,
        recipient_verification_ref=verification_ref.strip(),
        outcome_notes=outcome_notes.strip(),
    )
    claim.status = OwnershipClaim.Status.HANDED_OVER
    claim.save(update_fields=["status", "updated_at"])

    report = claim.report
    old_rep_status = report.status
    report.status = LostFoundReport.Status.CLOSED
    report.save(update_fields=["status", "updated_at"])
    LostFoundTransition.objects.create(
        report=report,
        from_state=old_rep_status,
        to_state=LostFoundReport.Status.CLOSED,
        actor=actor,
        reason="Closed after verified handover",
    )
    log_audit_event(
        actor=actor,
        action="LF_ITEM_HANDED_OVER",
        target_type="OwnershipClaim",
        target_id=str(claim.id),
        after_state={"status": "HANDED_OVER", "report_status": "CLOSED"},
        reason=verification_ref,
    )
    return handover
