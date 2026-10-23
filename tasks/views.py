from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.views.decorators.http import require_safe, require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from accounts.models import UserProfile

from .models import Task, TaskAssignment


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
def accept_task(request, task_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("An approved account is required.")

    if profile.role != UserProfile.Role.EMPLOYEE or not profile.is_approved:
        raise PermissionDenied("An approved account is required.")

    try:
        with transaction.atomic():
            task = get_object_or_404(Task.objects.select_for_update(), pk=task_id)

            if task.is_archived or task.is_finished:
                messages.error(request, "This task is no longer available.")
            elif TaskAssignment.objects.filter(task=task, assignee=request.user).exists():
                messages.info(request, "You have already accepted this task.")
            elif task.is_full:
                messages.error(request, "This task has no spots left.")
            else:
                TaskAssignment.objects.create(task=task, assignee=request.user)
                messages.success(request, "You accepted the task.")
    except IntegrityError:
        messages.info(request, "You have already accepted this task.")

    return redirect("tasks:my_accepted_tasks")