from django.shortcuts import render
from tasks.models import Task
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from accounts.models import UserProfile

from .models import UserProfile

@login_required
def dashboard(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("An approved account is required.")
    if not profile.is_approved or profile.role not in UserProfile.Role.values:
        raise PermissionDenied("An approved account is required.")
    role = profile.role
    if role == 'manager':
        return render(request,'accounts/manager_dash.html', context={'role':role})
    elif role == 'employee':
        tasks = (
            Task.objects.filter(is_archived=False, completed_at__isnull=True)
            .exclude(assignments__assignee=request.user)
            .prefetch_related("categories", "assignments")
            .order_by("due_date", "pk")
        )
        tasks = [task for task in tasks if not task.is_full and not task.is_finished]
        page_obj = Paginator(tasks, 10).get_page(request.GET.get("page"))
        return render(
            request,
            "accounts/employee_dash.html",
            {"tasks": page_obj.object_list, "page_obj": page_obj},
        )

@login_required
@require_GET
def calendar_events(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied

    if not profile.is_approved:
        raise PermissionDenied

    if profile.role == UserProfile.Role.MANAGER:
        tasks = Task.objects.filter(
            created_by=request.user,
            assignments__isnull=False,
        ).distinct()
    elif profile.role == UserProfile.Role.EMPLOYEE:
        tasks = Task.objects.filter(
            assignments__assignee=request.user,
        ).distinct()
    else:
        raise PermissionDenied

    events = [
        {
            "id": task.pk,
            "title": task.title,
            "start": task.due_date.isoformat(),
            "allDay": True,
        }
        for task in tasks
    ]
    return JsonResponse(events, safe=False)