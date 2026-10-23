from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_safe, require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from accounts.models import UserProfile

from .forms import TaskForm
from .models import Task, TaskAssignment


def _require_approved_manager(user):
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("An approved manager account is required.")

    if profile.role != UserProfile.Role.MANAGER or not profile.is_approved:
        raise PermissionDenied("An approved manager account is required.")


@login_required
@require_safe
def my_created_tasks(request):
    _require_approved_manager(request.user)
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


@login_required
@require_http_methods(["GET", "POST"])
def task_create(request):
    _require_approved_manager(request.user)
    form = TaskForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            form.save_m2m()
        messages.success(request, "Task created.")
        return redirect("tasks:my_created_tasks")
    return render(request, "tasks/task_form.html", {"form": form, "task": None})


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def task_update(request, task_id):
    _require_approved_manager(request.user)
    tasks = Task.objects.filter(created_by=request.user)
    if request.method == "POST":
        tasks = tasks.select_for_update()
    task = get_object_or_404(tasks, pk=task_id)
    form = TaskForm(request.POST if request.method == "POST" else None, instance=task)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task updated.")
        return redirect("tasks:my_created_tasks")
    return render(request, "tasks/task_form.html", {"form": form, "task": task})


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def task_delete(request, task_id):
    _require_approved_manager(request.user)
    tasks = Task.objects.filter(created_by=request.user)
    if request.method == "POST":
        tasks = tasks.select_for_update()
    task = get_object_or_404(tasks, pk=task_id)
    has_assignments = task.assignments.exists()
    if request.method == "POST" and not has_assignments:
        task.delete()
        messages.success(request, "Task deleted.")
        return redirect("tasks:my_created_tasks")
    return render(
        request,
        "tasks/task_confirm_delete.html",
        {"task": task, "has_assignments": has_assignments},
        status=409 if request.method == "POST" else 200,
    )


@login_required
@require_safe
def my_accepted_tasks(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("An approved account is required.")

    if profile.role != UserProfile.Role.EMPLOYEE or not profile.is_approved:
        raise PermissionDenied("An approved account is required.")

    tasks = (
        Task.objects.filter(assignments__assignee=request.user)
        .prefetch_related("categories", "assignments")
        .order_by("due_date", "pk")
    )
    page_obj = Paginator(tasks, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "tasks/my_accepted_tasks.html",
        {"tasks": page_obj.object_list, "page_obj": page_obj},
    )

@login_required
@require_POST
@transaction.atomic
def accept_task(request, task_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("An approved account is required.")

    if profile.role != UserProfile.Role.EMPLOYEE or not profile.is_approved:
        raise PermissionDenied("An approved account is required.")
    task = get_object_or_404(Task.objects.select_for_update(), pk=task_id)

    if task.is_archived or task.completed_at or task.is_finished:
        messages.error(request, "This task is no longer available.")
    elif TaskAssignment.objects.filter(task=task, assignee=request.user).exists():
        messages.info(request, "You have already accepted this task.")
    elif task.is_full:
        messages.error(request, "This task has no spots left.")
    else:
        TaskAssignment.objects.create(task=task, assignee=request.user)
        messages.success(request, "You accepted the task.")
    return redirect("tasks:my_accepted_tasks")

