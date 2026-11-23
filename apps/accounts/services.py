from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import Role, RoleCode, User, UserRole
from apps.audit.services import log_audit_event


@transaction.atomic
def assign_role(*, actor: User, target_user: User, role_code: str, reason: str) -> UserRole:
    if not actor.has_role(RoleCode.SYSTEM_ADMIN):
        raise PermissionDenied("Only System Administrator can assign roles.")
    if actor.pk == target_user.pk and role_code == RoleCode.SYSTEM_ADMIN:
        raise ValidationError("Self-escalation is not permitted.")
    role = Role.objects.get(code=role_code)
    assignment, created = UserRole.objects.get_or_create(
        user=target_user,
        role=role,
        is_active=True,
        defaults={"assigned_by": actor, "reason": reason},
    )
    log_audit_event(
        actor=actor,
        action="ROLE_ASSIGNED",
        target_type="User",
        target_id=str(target_user.pk),
        after_state={"role": role_code, "created": created},
        reason=reason,
    )
    return assignment


@transaction.atomic
def revoke_role(*, actor: User, target_user: User, role_code: str, reason: str) -> None:
    if not actor.has_role(RoleCode.SYSTEM_ADMIN):
        raise PermissionDenied("Only System Administrator can revoke roles.")
    if role_code == RoleCode.SYSTEM_ADMIN:
        active_admins = UserRole.objects.filter(
            role__code=RoleCode.SYSTEM_ADMIN, is_active=True, user__is_active=True
        ).count()
        if active_admins <= 1:
            raise ValidationError("Cannot revoke the last active System Administrator.")
    updated = UserRole.objects.filter(
        user=target_user, role__code=role_code, is_active=True
    ).update(is_active=False)
    if updated:
        log_audit_event(
            actor=actor,
            action="ROLE_REVOKED",
            target_type="User",
            target_id=str(target_user.pk),
            before_state={"role": role_code},
            after_state={"is_active": False},
            reason=reason,
        )


@transaction.atomic
def set_account_active(*, actor: User, target_user: User, is_active: bool, reason: str) -> User:
    if not actor.has_role(RoleCode.SYSTEM_ADMIN):
        raise PermissionDenied("Only System Administrator can change account status.")
    if not is_active and target_user.has_role(RoleCode.SYSTEM_ADMIN):
        active_admins = UserRole.objects.filter(
            role__code=RoleCode.SYSTEM_ADMIN, is_active=True, user__is_active=True
        ).count()
        if active_admins <= 1:
            raise ValidationError("Cannot deactivate the last active System Administrator.")
    before = {"is_active": target_user.is_active}
    target_user.is_active = is_active
    target_user.save(update_fields=["is_active", "updated_at"])
    log_audit_event(
        actor=actor,
        action="ACCOUNT_STATUS_CHANGED",
        target_type="User",
        target_id=str(target_user.pk),
        before_state=before,
        after_state={"is_active": is_active},
        reason=reason,
    )
    return target_user
