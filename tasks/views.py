from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

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
def available_tasks(request):
    # The numbers of tasks this person has already claimed, fetched in one go.
    my_task_ids = set(
        TaskAssignment.objects.filter(assignee=request.user).values_list("task_id", flat=True)
    )

    # Open tasks only: not archived and not marked complete.
    open_tasks = (
        Task.objects.filter(is_archived=False, completed_at__isnull=True)
        .prefetch_related("categories", "assignments")
        .order_by("due_date", "pk")
    )

    # Keep tasks that still have room, aren't finished, and aren't already mine.
    tasks = [
        task
        for task in open_tasks
        if task.pk not in my_task_ids and not task.is_full and not task.is_finished
    ]
    return render(request, "tasks/available_tasks.html", {"tasks": tasks})


@login_required
@require_POST
def claim_task(request, task_id):
    try:
        # atomic: the checks and the save happen as one unit, so two people
        # pressing Claim on the last spot cannot both get it.
        with transaction.atomic():
            task = get_object_or_404(Task.objects.select_for_update(), pk=task_id)

            if task.is_archived or task.is_finished:
                messages.error(request, "That task is no longer available.")
            elif task.assignments.filter(assignee=request.user).exists():
                messages.info(request, "You have already claimed that task.")
            elif task.is_full:
                messages.error(request, "Sorry, that task is already full.")
            else:
                TaskAssignment.objects.create(task=task, assignee=request.user)
                messages.success(request, f'You claimed "{task.title}".')
    except IntegrityError:
        # The database's own "no double claims" rule caught a duplicate.
        messages.info(request, "You have already claimed that task.")

    return redirect("tasks:available_tasks")