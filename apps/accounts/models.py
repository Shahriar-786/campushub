import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class RoleCode(models.TextChoices):
    STUDENT = "STUDENT", "Student"
    LIBRARY_STAFF = "LIBRARY_STAFF", "Library Staff"
    LIBRARY_SUPERVISOR = "LIBRARY_SUPERVISOR", "Library Supervisor"
    LF_REVIEWER = "LF_REVIEWER", "Lost and Found Reviewer"
    SECURITY_OFFICER = "SECURITY_OFFICER", "Security Officer"
    IT_STAFF = "IT_STAFF", "IT Staff"
    UTILITY_STAFF = "UTILITY_STAFF", "Utility Staff"
    MANAGEMENT_OFFICER = "MANAGEMENT_OFFICER", "Management Officer"
    SYSTEM_ADMIN = "SYSTEM_ADMIN", "System Administrator"


class UserManager(BaseUserManager):
    def create_user(self, institutional_id, email, full_name, password=None, **extra_fields):
        if not institutional_id:
            raise ValueError("institutional_id is required")
        if not email:
            raise ValueError("email is required")
        normalized_id = institutional_id.strip().upper()
        email = self.normalize_email(email)
        user = self.model(
            institutional_id=normalized_id,
            email=email,
            full_name=full_name.strip(),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, institutional_id, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(institutional_id, email, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institutional_id = models.CharField(max_length=40, unique=True, db_index=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "institutional_id"
    REQUIRED_FIELDS = ["email", "full_name"]

    class Meta:
        ordering = ["institutional_id"]

    def save(self, *args, **kwargs):
        self.institutional_id = self.institutional_id.strip().upper()
        super().save(*args, **kwargs)

    @property
    def active_role_codes(self) -> set[str]:
        now = timezone.now()
        qs = self.user_roles.filter(is_active=True).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=now)
        )
        return set(qs.values_list("role__code", flat=True))

    def has_role(self, *codes: str) -> bool:
        return bool(self.active_role_codes.intersection(set(codes)))

    def __str__(self):
        return f"{self.institutional_id} — {self.full_name}"


class Role(models.Model):
    code = models.CharField(max_length=40, choices=RoleCode.choices, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name


class UserRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="roles_granted"
    )
    effective_from = models.DateTimeField(default=timezone.now)
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=models.Q(is_active=True),
                name="uniq_active_user_role",
            )
        ]

    def __str__(self):
        return f"{self.user.institutional_id} -> {self.role.code}"
