"""Reviewing manager applications and removing managers."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from .models import ManagerApplication, UserProfile


def _require_approved_manager(user):
    # Only managers who are already approved get to handle these requests.
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("You are not approved by a manager")
    if profile.role != UserProfile.Role.MANAGER or not profile.is_approved:
        raise PermissionDenied("You are not approved by a manager")


def _applications():
    # Applications that still wait for a decision.
    return ManagerApplication.objects.filter(
        status=ManagerApplication.Status.PENDING
    ).select_related("user")


def _managers():
    # Approved managers, the people who can be removed.
    return UserProfile.objects.filter(
        role=UserProfile.Role.MANAGER, is_approved=True
    ).select_related("user")


def _finish(application, reviewer, status, note=""):
    # Record who decided, when, and the optional note.
    application.status = status
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()
    application.review_note = note
    application.save()


@login_required
@require_safe
def pending_managers(request):
    """The list page: who applied to become a manager, and who the managers are."""
    _require_approved_manager(request.user)
    return render(
        request,
        "accounts/pending_managers.html",
        {
            "applications": _applications().order_by("created_at", "pk"),
            "managers": _managers().order_by("user__username"),
        },
    )


@login_required
@require_POST
@transaction.atomic
def approve_manager(request, application_id):
    """Yes: the applicant becomes a manager."""
    _require_approved_manager(request.user)
    application = get_object_or_404(_applications().select_for_update(), pk=application_id)
    profile = application.user.profile
    profile.role = UserProfile.Role.MANAGER
    profile.manager_requested = False
    profile.is_approved = True
    profile.save()
    _finish(application, request.user, ManagerApplication.Status.APPROVED)
    messages.success(request, f"{application.user.username} is now a manager.")
    return redirect("pending_managers")


@login_required
@require_POST
@transaction.atomic
def decline_manager(request, application_id):
    """No: the applicant stays an employee and sees the note."""
    _require_approved_manager(request.user)
    application = get_object_or_404(_applications().select_for_update(), pk=application_id)
    profile = application.user.profile
    profile.manager_requested = False
    profile.save(update_fields=["manager_requested"])
    note = request.POST.get("note", "").strip()[:300]
    _finish(application, request.user, ManagerApplication.Status.DECLINED, note)
    messages.success(request, f"{application.user.username}'s application was declined.")
    return redirect("pending_managers")


@login_required
@require_POST
@transaction.atomic
def demote_manager(request, profile_id):
    """Remove someone's manager role. They go back to being an employee."""
    _require_approved_manager(request.user)
    profile = get_object_or_404(_managers().select_for_update(), pk=profile_id)
    if profile.user_id == request.user.id:
        messages.error(request, "You can't remove yourself as a manager.")
        return redirect("pending_managers")
    profile.role = UserProfile.Role.EMPLOYEE
    profile.save(update_fields=["role"])
    messages.success(request, f"{profile.user.username} is no longer a manager.")
    return redirect("pending_managers")