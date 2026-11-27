from django.contrib import messages
from django.shortcuts import redirect, render
from tasks.models import Task
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ProfileForm, ManagerApplicationForm
from .forms import NotificationEmailForm
from .models import ManagerApplication, UserProfile

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
            .order_by("-is_priority", "due_date", "pk")
        )
        tasks = [task for task in tasks if not task.is_full and not task.is_finished]
        page_obj = Paginator(tasks, 10).get_page(request.GET.get("page"))
        return render(
            request,
            "accounts/employee_dash.html",
            {"tasks": page_obj.object_list, "page_obj": page_obj},
        )

@login_required
def notification_email(request):
    """Save the address that receives this person's deadline reminders."""
    form = NotificationEmailForm(
        request.POST or None,
        initial={"email": request.user.email},
    )
    if request.method == "POST" and form.is_valid():
        request.user.email = form.cleaned_data["email"]
        request.user.save(update_fields=["email"])
        messages.success(request, "Deadline reminders will be sent to this email address.")
        return redirect("dashboard")
    return render(request, "accounts/notification_email.html", {"form": form})


@login_required
@require_GET
def calendar_events(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        raise PermissionDenied

    if not profile.is_approved:
        raise PermissionDenied

    # Load names with the tasks so showing a preview needs no extra request.
    calendar_tasks = Task.objects.filter(is_archived=False).prefetch_related(
        "categories", "assignments__assignee"
    )
    available_ids = set()
    if profile.role == UserProfile.Role.MANAGER:
        tasks = calendar_tasks.filter(created_by=request.user)
    elif profile.role == UserProfile.Role.EMPLOYEE:
        mine = list(
            calendar_tasks.filter(
                assignments__assignee=request.user,
                assignments__completed_at__isnull=True,
            )
            .distinct()
        )
        available = [
            task
            for task in calendar_tasks.filter(completed_at__isnull=True)
            .exclude(assignments__assignee=request.user)
            if not task.is_full and not task.is_finished
        ]
        available_ids = {task.pk for task in available}
        tasks = mine + available
    else:
        raise PermissionDenied

    events = []
    for task in tasks:
        category = task.categories.first()
        assignees = sorted(
            assignment.assignee.get_username() for assignment in task.assignments.all()
        )
        events.append({
            "id": task.pk,
            "title": ("\u2605 " if task.is_priority else "") + task.title,
            "start": task.due_date.isoformat(),
            "allDay": True,
            "extendedProps": {"assignees": assignees},
            "color": category.color if category and category.color else "#3788d8",
            "classNames": ["event-available"] if task.pk in available_ids else [],
            "url": reverse("tasks:task_detail", args=[task.pk]),
        })
    return JsonResponse(events, safe=False)


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    form = ProfileForm(request.POST if request.method == "POST" else None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(
        request,
        "accounts/profile.html",
        {"form": form, "user_profile": getattr(request.user, "profile", None)},
    )


@login_required
@require_POST
def send_password_reset(request):
    """Email a password reset link to the address saved on this account."""
    form = PasswordResetForm(data={"email": request.user.email})
    if not form.is_valid():
        messages.error(request, "Save a valid email on your profile before requesting a reset.")
        return redirect("profile")
    form.save(
        request=request,
        use_https=request.is_secure(),
        email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
    )
    messages.success(request, "A password reset link was sent to your email address.")
    return redirect("profile")
@login_required
def apply_manager(request):
    """Employees apply to become a manager and see what happened to their last application."""
    if request.user.profile.role == UserProfile.Role.MANAGER:
        messages.info(request, "You are already a manager.")
        return redirect("dashboard")

    applications = request.user.manager_applications
    pending = applications.filter(status=ManagerApplication.Status.PENDING).first()
    last_decision = applications.exclude(status=ManagerApplication.Status.PENDING).first()

    if request.method == "POST" and pending is None:
        form = ManagerApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.save()
            messages.success(request, "Your application was sent to the managers.")
            return redirect("apply_manager")
    else:
        form = ManagerApplicationForm()

    return render(
        request,
        "accounts/apply_manager.html",
        {"form": form, "pending": pending, "last_decision": last_decision},
    )