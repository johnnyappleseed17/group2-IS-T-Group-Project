"""Approving people who asked to become managers."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from .models import UserProfile


def _require_approved_manager(user):
    # Only managers who are already approved get to handle these requests.
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("You are not approved by a manager")
    if profile.role != UserProfile.Role.MANAGER or not profile.is_approved:
        raise PermissionDenied("You are not approved by a manager")


def _requests():
    # The people who ticked the request box and are still employees.
    return UserProfile.objects.filter(
        manager_requested=True, role=UserProfile.Role.EMPLOYEE
    ).select_related("user")


@login_required
@require_safe
def pending_managers(request):
    """The list page: who is asking to become a manager."""
    _require_approved_manager(request.user)
    return render(
        request,
        "accounts/pending_managers.html",
        {"profiles": _requests().order_by("user__date_joined", "pk")},
    )


@login_required
@require_POST
@transaction.atomic
def approve_manager(request, profile_id):
    """Yes: the person becomes a manager."""
    _require_approved_manager(request.user)
    profile = get_object_or_404(_requests().select_for_update(), pk=profile_id)
    profile.role = UserProfile.Role.MANAGER
    profile.manager_requested = False
    profile.is_approved = True
    profile.save()
    messages.success(request, f"{profile.user.username} is now a manager.")
    return redirect("pending_managers")


@login_required
@require_POST
@transaction.atomic
def decline_manager(request, profile_id):
    """No: the request is cleared and the person stays an employee."""
    _require_approved_manager(request.user)
    profile = get_object_or_404(_requests().select_for_update(), pk=profile_id)
    profile.manager_requested = False
    profile.save(update_fields=["manager_requested"])
    messages.success(request, f"{profile.user.username}'s request was declined.")
    return redirect("pending_managers")