from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Role, RoleCode, User, UserRole
from apps.facilities.models import FacilityTicket
from apps.forecasting.models import ForecastRun
from apps.forecasting.services import run_synthetic_forecast_pipeline
from apps.library.models import BookingPolicyVersion, LibrarySeat, LibrarySession, LibraryZone
from apps.lost_found.models import LostFoundReport

DEMO_USERS = [
    ("DIU-STU-001", "student1@demo.campushub.local", "Arafat Rahman (Student A)", RoleCode.STUDENT),
    ("DIU-STU-002", "student2@demo.campushub.local", "Nusrat Jahan (Student B)", RoleCode.STUDENT),
    ("DIU-LIB-001", "libstaff@demo.campushub.local", "Kamrul Hasan (Library Staff)", RoleCode.LIBRARY_STAFF),
    ("DIU-SUP-001", "libsup@demo.campushub.local", "Farhana Akter (Library Supervisor)", RoleCode.LIBRARY_SUPERVISOR),
    ("DIU-LFR-001", "lfrev@demo.campushub.local", "Mahmudul Islam (L&F Reviewer)", RoleCode.LF_REVIEWER),
    ("DIU-SEC-001", "security@demo.campushub.local", "Tariqul Alam (Security Officer)", RoleCode.SECURITY_OFFICER),
    ("DIU-IT-001", "itstaff@demo.campushub.local", "Sabbir Ahmed (IT Staff)", RoleCode.IT_STAFF),
    ("DIU-UTL-001", "utility@demo.campushub.local", "Rafiqul Islam (Utility Staff)", RoleCode.UTILITY_STAFF),
    ("DIU-MGT-001", "mgmt@demo.campushub.local", "Dr. Nadia Karim (Management Officer)", RoleCode.MANAGEMENT_OFFICER),
    ("DIU-ADM-001", "admin@demo.campushub.local", "System Administrator", RoleCode.SYSTEM_ADMIN),
]


class Command(BaseCommand):
    help = "Seeds synthetic prototype data and demo accounts for all 9 operational roles."

    def handle(self, *args, **options):
        for code, label in RoleCode.choices:
            Role.objects.get_or_create(code=code, defaults={"name": label})

        created_users = {}
        for inst_id, email, full_name, role_code in DEMO_USERS:
            user, created = User.objects.get_or_create(
                institutional_id=inst_id,
                defaults={"email": email, "full_name": full_name, "is_staff": role_code == RoleCode.SYSTEM_ADMIN},
            )
            if created:
                user.set_password("CampusHub@2026")
                user.save()
            role = Role.objects.get(code=role_code)
            UserRole.objects.get_or_create(user=user, role=role, is_active=True, defaults={"reason": "Demo seed"})
            created_users[inst_id] = user

        BookingPolicyVersion.get_active()

        zone_a, _ = LibraryZone.objects.get_or_create(
            code="ZONE-A", defaults={"name": "Quiet Reading Hall", "floor": "Floor 2"}
        )
        zone_b, _ = LibraryZone.objects.get_or_create(
            code="ZONE-B", defaults={"name": "Collaborative Study Wing", "floor": "Floor 3"}
        )
        for zone in (zone_a, zone_b):
            for num in range(1, 7):
                LibrarySeat.objects.get_or_create(zone=zone, seat_code=f"S{num:02d}")

        today = timezone.localdate()
        session_slots = [
            (1, "Morning 1", time(9, 0), time(11, 0)),
            (2, "Midday 2", time(11, 0), time(13, 0)),
            (3, "Afternoon 3", time(14, 0), time(16, 0)),
            (4, "Late Afternoon 4", time(16, 0), time(18, 0)),
        ]
        for day_offset in range(7):
            d = today + timedelta(days=day_offset)
            for idx, label, st, et in session_slots:
                LibrarySession.objects.get_or_create(
                    session_date=d,
                    session_index=idx,
                    defaults={"label": label, "start_time": st, "end_time": et},
                )

        if not LostFoundReport.objects.exists():
            LostFoundReport.objects.create(
                reporter=created_users["DIU-STU-001"],
                report_type=LostFoundReport.ReportType.FOUND,
                category="Electronics",
                location_hint="Library Floor 2, near Zone A",
                public_description="Black scientific calculator found on reading table.",
                private_details="Sticker on back reads 'EEE-Batch-61' with initials AR.",
                status=LostFoundReport.Status.ACTIVE,
            )

        if not FacilityTicket.objects.exists():
            FacilityTicket.objects.create(
                reporter=created_users["DIU-STU-001"],
                queue_type=FacilityTicket.QueueType.UTILITY,
                category="Air Conditioning",
                location="Library Floor 2 — Quiet Reading Hall",
                description="AC unit near seats S01–S03 is leaking water.",
                priority=FacilityTicket.Priority.HIGH,
            )
            FacilityTicket.objects.create(
                reporter=created_users["DIU-STU-002"],
                queue_type=FacilityTicket.QueueType.IT,
                category="Campus Wi-Fi",
                location="Library Floor 3 — Collaborative Study Wing",
                description="Access point disconnects intermittently during midday sessions.",
                priority=FacilityTicket.Priority.MEDIUM,
            )

        if not ForecastRun.objects.exists():
            run_synthetic_forecast_pipeline(horizon_days=7)

        self.stdout.write(self.style.SUCCESS("CampusHub synthetic demo data seeded for all 9 roles."))
