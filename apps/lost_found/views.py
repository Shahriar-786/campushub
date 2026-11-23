from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import RoleCode, User
from apps.lost_found.models import LostFoundReport, OwnershipClaim
from apps.lost_found.services import decide_claim, record_handover, review_report


@login_required
def report_list_view(request):
    if request.method == "POST":
        if not request.user.has_role(RoleCode.STUDENT, RoleCode.LF_REVIEWER):
            raise PermissionDenied("Not allowed to submit lost/found reports.")
        LostFoundReport.objects.create(
            reporter=request.user,
            report_type=request.POST["report_type"],
            category=request.POST["category"].strip(),
            location_hint=request.POST["location_hint"].strip(),
            public_description=request.POST["public_description"].strip(),
            private_details=request.POST.get("private_details", "").strip(),
        )
        messages.success(request, "Report submitted for reviewer screening.")
        return redirect("lost_found:list")

    if request.user.has_role(RoleCode.LF_REVIEWER):
        reports = LostFoundReport.objects.select_related("reporter").all()[:50]
    elif request.user.has_role(RoleCode.SECURITY_OFFICER):
        # Security Officer sees ONLY cases with claims assigned to them
        reports = LostFoundReport.objects.filter(
            claims__assigned_security_officer=request.user
        ).distinct()[:50]
    else:
        # Students see their own reports + active FOUND items (without private_details in template)
        own = LostFoundReport.objects.filter(reporter=request.user)
        active_found = LostFoundReport.objects.filter(
            report_type=LostFoundReport.ReportType.FOUND, status=LostFoundReport.Status.ACTIVE
        )
        reports = (own | active_found).distinct()[:50]

    return render(request, "lost_found/list.html", {"reports": reports})


@login_required
def report_detail_view(request, pk):
    report = get_object_or_404(LostFoundReport.objects.prefetch_related("claims__claimant"), pk=pk)
    is_reviewer = request.user.has_role(RoleCode.LF_REVIEWER)
    is_assigned_sec = (
        request.user.has_role(RoleCode.SECURITY_OFFICER)
        and report.claims.filter(assigned_security_officer=request.user).exists()
    )
    is_owner = report.reporter_id == request.user.id
    is_public_active_found = (
        report.report_type == LostFoundReport.ReportType.FOUND and report.status == LostFoundReport.Status.ACTIVE
    )
    if not (is_reviewer or is_assigned_sec or is_owner or is_public_active_found):
        raise PermissionDenied("You do not have access to this Lost and Found case.")

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "review":
                review_report(
                    actor=request.user,
                    report=report,
                    new_status=request.POST["status"],
                    reason=request.POST.get("reason", "Screened"),
                )
                messages.success(request, "Report review saved.")
            elif action == "submit_claim":
                OwnershipClaim.objects.create(
                    report=report,
                    claimant=request.user,
                    evidence_summary=request.POST["evidence_summary"].strip(),
                )
                messages.success(request, "Ownership claim submitted for verification.")
            elif action == "decide_claim":
                claim = get_object_or_404(OwnershipClaim, pk=request.POST["claim_id"], report=report)
                sec_id = request.POST.get("security_officer_id")
                sec_user = User.objects.filter(pk=sec_id).first() if sec_id else None
                decide_claim(
                    actor=request.user,
                    claim=claim,
                    decision=request.POST["decision"],
                    reason=request.POST.get("reason", ""),
                    security_officer=sec_user,
                )
                messages.success(request, "Claim decision recorded.")
            elif action == "handover":
                claim = get_object_or_404(OwnershipClaim, pk=request.POST["claim_id"], report=report)
                record_handover(
                    actor=request.user,
                    claim=claim,
                    verification_ref=request.POST["verification_ref"],
                    outcome_notes=request.POST["outcome_notes"],
                )
                messages.success(request, "Handover recorded and case closed.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        return redirect("lost_found:detail", pk=report.pk)

    security_officers = User.objects.filter(user_roles__role__code=RoleCode.SECURITY_OFFICER, user_roles__is_active=True)
    return render(
        request,
        "lost_found/detail.html",
        {
            "report": report,
            "can_view_private": is_reviewer or is_assigned_sec or is_owner,
            "security_officers": security_officers,
        },
    )
