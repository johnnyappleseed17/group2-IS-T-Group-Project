from django.shortcuts import render
from tasks.models import Task
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

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

