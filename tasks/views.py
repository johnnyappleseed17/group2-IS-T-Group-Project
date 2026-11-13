from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_safe, require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from accounts.models import UserProfile
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.utils import timezone


from .forms import TaskForm
from .models import Task, TaskAssignment
from .reminders import send_due_date_reminders


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
        Task.objects.filter(created_by=request.user, is_archived=False)
        .prefetch_related("categories", "assignments")
        .order_by("-is_priority", "due_date", "pk")
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
            send_due_date_reminders(task)
        messages.success(request, "Task created.")
        return redirect("tasks:my_created_tasks")
    return render(request, "tasks/task_form.html", {"form": form, "task": None})


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def task_update(request, task_id):
    _require_approved_manager(request.user)
    tasks = Task.objects.filter(created_by=request.user, is_archived=False)
    if request.method == "POST":
        tasks = tasks.select_for_update()
    task = get_object_or_404(tasks, pk=task_id)
    form = TaskForm(request.POST if request.method == "POST" else None, instance=task)
    if request.method == "POST" and form.is_valid():
        previous_due = task.due_date
        task = form.save()
        if task.due_date != previous_due:
            send_due_date_reminders(task)
        messages.success(request, "Task updated.")
        return redirect("tasks:my_created_tasks")
    return render(request, "tasks/task_form.html", {"form": form, "task": task})


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def task_archive(request, task_id):
    _require_approved_manager(request.user)
    tasks = Task.objects.filter(created_by=request.user, is_archived=False)
    if request.method == "POST":
        tasks = tasks.select_for_update()
    task = get_object_or_404(tasks, pk=task_id)
    has_assignments = task.assignments.exists()
    if request.method == "POST" and not has_assignments:
        task.is_archived = True
        task.archived_at = timezone.now()
        task.save(update_fields=["is_archived", "archived_at"])
        messages.success(request, "Task archived. You can restore it from Task History.")
        return redirect("tasks:my_created_tasks")
    return render(
        request,
        "tasks/task_confirm_archive.html",
        {"task": task, "has_assignments": has_assignments},
        status=409 if request.method == "POST" else 200,
    )


@login_required
@require_POST
@transaction.atomic
def task_restore(request, task_id):
    _require_approved_manager(request.user)
    task = get_object_or_404(
        Task.objects.select_for_update(),
        pk=task_id,
        created_by=request.user,
        is_archived=True,
    )
    task.is_archived = False
    task.archived_at = None
    task.save(update_fields=["is_archived", "archived_at"])
    messages.success(request, "Task restored. It is back in Created Tasks.")
    return redirect("tasks:task_history")


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
        Task.objects.filter(is_archived=False, assignments__assignee=request.user, assignments__completed_at__isnull=True)
        .prefetch_related("categories", "assignments")
        .order_by("-is_priority", "due_date", "pk")
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
        send_due_date_reminders(task)
        messages.success(request, "You accepted the task.")
    return redirect("tasks:my_accepted_tasks")

class TaskDetailView(LoginRequiredMixin, generic.DetailView):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            profile = None
        if profile is None or not profile.is_approved:
            get_object_or_404(self.get_queryset(), pk=kwargs["pk"])
            raise PermissionDenied("An approved account is required.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        tasks = Task.objects.prefetch_related("categories", "assignments__assignee")
        try:
            profile = self.request.user.profile
        except UserProfile.DoesNotExist:
            return tasks.filter(is_archived=False)

        if profile.role == UserProfile.Role.MANAGER and profile.is_approved:
            return tasks.filter(Q(is_archived=False) | Q(created_by=self.request.user))
        return tasks.filter(is_archived=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignments"] = self.object.assignments.all()
        context["done_assignments"] = self.object.assignments.filter(
            completed_at__isnull=False
        ).select_related("assignee")
        task = context["task"]
        user = self.request.user
        profile = user.profile
        already_accepted = task.assignments.filter(assignee=user).exists()
        context["is_owner"] = (
            profile.role == UserProfile.Role.MANAGER and task.created_by_id == user.id
        )
        context["can_accept"] = (
            profile.role == UserProfile.Role.EMPLOYEE
            and not task.is_archived
            and not task.is_finished
            and not task.is_full
            and not already_accepted
        )
        return context

def mark_done(request, task_id):
    assignment = get_object_or_404(
        TaskAssignment.objects.select_for_update(),
        task_id=task_id,
        assignee=request.user,
    )

    if assignment.completed_at is None:
        assignment.completed_at = timezone.now()
        assignment.save(update_fields=["completed_at"])
        messages.success(request, "Task marked as done.")
    else:
        messages.info(request, "You have already marked this task as done.")

    return redirect("tasks:my_accepted_tasks")

@login_required
@require_POST
@transaction.atomic
def remove_self(request, task_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied("An approved account is required.")

    if profile.role != UserProfile.Role.EMPLOYEE or not profile.is_approved:
        raise PermissionDenied("An approved account is required.")

    assignment = get_object_or_404(
        TaskAssignment.objects.select_for_update(),
        task_id=task_id,
        assignee=request.user,
    )
    assignment.delete()
    messages.success(request, "You have removed yourself from the task.")
    return redirect("tasks:my_accepted_tasks")
