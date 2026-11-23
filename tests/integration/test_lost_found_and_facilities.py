import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import RoleCode
from apps.facilities.models import FacilityTicket
from apps.facilities.services import transition_ticket
from apps.lost_found.models import LostFoundReport, OwnershipClaim, PotentialMatch
from apps.lost_found.services import decide_claim, record_handover, review_report


@pytest.mark.django_db
def test_lost_found_match_not_ownership_and_handover_required(make_user):
    stu = make_user("DIU-LF-STU", RoleCode.STUDENT)
    reviewer = make_user("DIU-LF-REV", RoleCode.LF_REVIEWER)

    lost = LostFoundReport.objects.create(
        reporter=stu, report_type="LOST", category="Bag", location_hint="Hall", public_description="Blue backpack"
    )
    found = LostFoundReport.objects.create(
        reporter=stu, report_type="FOUND", category="Bag", location_hint="Hall", public_description="Blue backpack"
    )
    match = PotentialMatch.objects.create(lost_report=lost, found_report=found, rationale="Same color/category")
    assert match.is_verified_ownership is False

    review_report(actor=reviewer, report=found, new_status=LostFoundReport.Status.ACTIVE, reason="Complete")
    claim = OwnershipClaim.objects.create(report=found, claimant=stu, evidence_summary="Has key fob inside")

    # Handover before approval must fail
    with pytest.raises(ValidationError):
        record_handover(actor=reviewer, claim=claim, verification_ref="ID-123", outcome_notes="Tried early")

    decide_claim(actor=reviewer, claim=claim, decision=OwnershipClaim.Status.APPROVED, reason="Evidence matched")
    record_handover(actor=reviewer, claim=claim, verification_ref="DIU-ID-CHECKED", outcome_notes="Collected in person")
    found.refresh_from_db()
    assert found.status == LostFoundReport.Status.CLOSED


@pytest.mark.django_db
def test_facility_ticket_lifecycle_and_queue_isolation(make_user):
    stu = make_user("DIU-UT-STU", RoleCode.STUDENT)
    util = make_user("DIU-UT-STF", RoleCode.UTILITY_STAFF)
    it_staff = make_user("DIU-UT-IT", RoleCode.IT_STAFF)

    ticket = FacilityTicket.objects.create(
        reporter=stu, queue_type=FacilityTicket.QueueType.UTILITY, category="AC", location="Room 201", description="Leaking"
    )

    # IT staff cannot mutate a UTILITY ticket
    with pytest.raises(PermissionDenied):
        transition_ticket(actor=it_staff, ticket=ticket, new_status=FacilityTicket.Status.TRIAGED)

    transition_ticket(actor=util, ticket=ticket, new_status=FacilityTicket.Status.ASSIGNED, assignee=util)
    transition_ticket(actor=util, ticket=ticket, new_status=FacilityTicket.Status.IN_PROGRESS, note="Inspecting unit")

    # Resolving without a completion note must fail
    with pytest.raises(ValidationError):
        transition_ticket(actor=util, ticket=ticket, new_status=FacilityTicket.Status.RESOLVED, note="")

    transition_ticket(actor=util, ticket=ticket, new_status=FacilityTicket.Status.RESOLVED, note="Replaced drain pipe")
    assert ticket.status == FacilityTicket.Status.RESOLVED
