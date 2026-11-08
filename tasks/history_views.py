from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_safe

from accounts.models import UserProfile
from .models import TaskAssignment


@login_required
@require_safe
def task_history(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("You are not on an approved account.")

    if profile.role != UserProfile.Role.EMPLOYEE or not profile.is_approved:
        raise PermissionDenied("You need an approved account.")

    assignments = (
        TaskAssignment.objects.filter(assignee=request.user)
        .filter(Q(completed_at__isnull=False) | Q(task__completed_at__isnull=False))
        .select_related("task")
        .prefetch_related("task__categories")
        .order_by("-claimed_at", "-pk")
    )
    page_obj = Paginator(assignments, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "tasks/task_history.html",
        {"assignments": page_obj.object_list, "page_obj": page_obj},
    )