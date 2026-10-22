from django.shortcuts import render
from tasks.models import Task
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required

def dashboard(request):
    role = request.user.profile.role
    if role == 'manager':
        return render(request,'accounts/manager_dash.html', context={'role':role})
    elif role == 'employee':
        tasks = (
            Task.objects.filter(is_archived=False, completed_at__isnull=True)
            .exclude(assignments__assignee=request.user)
            .prefetch_related("categories", "assignments")
            .order_by("due_date", "pk")
        )
        tasks = [task for task in tasks if task.is_full != True]
        page_obj = Paginator(tasks, 10).get_page(request.GET.get("page"))
        return render(
            request,
            "accounts/employee_dash.html",
            {"tasks": page_obj.object_list, "page_obj": page_obj},
        )

