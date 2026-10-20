from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.http import require_safe

from accounts.models import UserProfile

from .models import Task


@login_required
@require_safe
def my_created_tasks(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("An approved manager account is required.")

    if profile.role != UserProfile.Role.MANAGER or not profile.is_approved:
        raise PermissionDenied("An approved manager account is required.")

    tasks = (
        Task.objects.filter(created_by=request.user)
        .prefetch_related("categories", "assignments")
        .order_by("due_date", "pk")
    )
    page_obj = Paginator(tasks, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "tasks/my_created_tasks.html",
        {"tasks": page_obj.object_list, "page_obj": page_obj},
    )
