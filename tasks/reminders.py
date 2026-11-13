from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile

from .models import DUE_SOON_DAYS, DeadlineReminder, Task


def send_deadline_reminders(today=None):
    """Email people about tasks that are due soon or overdue.

    A reminder goes to every approved manager and to each employee who
    accepted the task and has not finished, when that person has a valid
    email.
    Each address is emailed once. An invalid address is skipped, and a
    failed delivery does not stop the other addresses. Returns the
    number of emails sent.
    """
    today = today or timezone.localdate()
    soon_limit = today + timedelta(days=DUE_SOON_DAYS)
    tasks = (
        Task.objects.filter(
            is_archived=False,
            completed_at__isnull=True,
            due_date__lte=soon_limit,
        )
        .select_related("created_by")
        .prefetch_related("assignments__assignee")
    )

    sent = 0
    for task in tasks:
        if task.is_finished:
            continue
        kind = (
            DeadlineReminder.Kind.OVERDUE
            if task.due_date < today
            else DeadlineReminder.Kind.DUE_SOON
        )
        sent += _notify(task, kind)
    return sent


REMINDERS_BY_DAYS_BEFORE = {
    3: DeadlineReminder.Kind.IN_3_DAYS,
    2: DeadlineReminder.Kind.IN_2_DAYS,
    1: DeadlineReminder.Kind.IN_1_DAY,
    0: DeadlineReminder.Kind.DUE_TODAY,
}


def send_reminders_before(days_before, today=None):
    """Email people when a task is due in exactly ``days_before`` days.

    Zero means the task is due today. Every approved manager and each
    employee who accepted the task and has not finished receives one
    message at their valid email address. Returns the number of emails
    sent.
    """
    if days_before not in REMINDERS_BY_DAYS_BEFORE:
        raise ValueError("days_before must be 0, 1, 2, or 3.")
    today = today or timezone.localdate()
    kind = REMINDERS_BY_DAYS_BEFORE[days_before]
    tasks = (
        Task.objects.filter(
            is_archived=False,
            completed_at__isnull=True,
            due_date=today + timedelta(days=days_before),
        )
        .select_related("created_by")
        .prefetch_related("assignments__assignee")
    )
    sent = 0
    for task in tasks:
        if task.is_finished:
            continue
        sent += _notify(task, kind)
    return sent


def send_due_reminders(today=None):
    """Email managers and employees on the day a task is due."""
    return send_reminders_before(0, today)


def send_overdue_reminders(today=None):
    """Email managers and employees about tasks whose due date has passed."""
    today = today or timezone.localdate()
    tasks = (
        Task.objects.filter(
            is_archived=False,
            completed_at__isnull=True,
            due_date__lt=today,
        )
        .prefetch_related("assignments__assignee")
    )
    sent = 0
    for task in tasks:
        if task.is_finished:
            continue
        sent += _notify(task, DeadlineReminder.Kind.OVERDUE)
    return sent


def send_task_reminders(today=None):
    """Email managers and employees at 3 days, 2 days, the due date, and overdue.

    Returns the number of emails sent.
    """
    today = today or timezone.localdate()
    return (
        send_reminders_before(3, today)
        + send_reminders_before(2, today)
        + send_due_reminders(today)
        + send_overdue_reminders(today)
    )


def send_due_date_reminders(task):
    """Email each valid address the calendar date this task is due.

    The same address is not told that date again. A later change to the
    due date sends the new date. Returns the number of emails sent.
    """
    return _notify(task, DeadlineReminder.Kind.DUE_DATE)


def _notify(task, kind):
    sent = 0
    for recipient, email in _recipients(task):
        if _already_sent(task, recipient, kind):
            continue
        try:
            send_mail(
                subject=_subject(task, kind),
                message=_message(task, email, kind),
                from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
        except (SMTPException, OSError):
            continue
        DeadlineReminder.objects.create(
            task=task,
            recipient=recipient,
            kind=kind,
            due_date=task.due_date,
        )
        sent += 1
    return sent


def _valid_email(user):
    """Return the user's address when it is a real email, otherwise blank."""
    email = (user.email or "").strip()
    if not email:
        return ""
    try:
        validate_email(email)
    except ValidationError:
        return ""
    return email


def _recipients(task):
    """One entry per valid address for approved managers and assigned employees."""
    from django.contrib.auth import get_user_model

    people = []
    seen = set()
    managers = get_user_model().objects.filter(
        profile__role=UserProfile.Role.MANAGER,
        profile__is_approved=True,
    )
    employees = []
    for assignment in task.assignments.all():
        if assignment.completed_at:
            continue
        assignee = assignment.assignee
        try:
            profile = assignee.profile
        except UserProfile.DoesNotExist:
            continue
        if profile.role == UserProfile.Role.EMPLOYEE and profile.is_approved:
            employees.append(assignee)
    for person in list(managers) + employees:
        email = _valid_email(person)
        key = email.casefold()
        if not email or key in seen:
            continue
        seen.add(key)
        people.append((person, email))
    return people


def _already_sent(task, recipient, kind):
    return DeadlineReminder.objects.filter(
        task=task,
        recipient=recipient,
        kind=kind,
        due_date=task.due_date,
    ).exists()


def _subject(task, kind):
    due = task.due_date.isoformat()
    if kind == DeadlineReminder.Kind.DUE_DATE:
        return f"Due date: {task.title} is due {due}"
    if kind == DeadlineReminder.Kind.OVERDUE:
        return f"Overdue: {task.title} was due {due}"
    if kind == DeadlineReminder.Kind.DUE_TODAY:
        return f"Due today: {task.title}"
    if kind == DeadlineReminder.Kind.IN_1_DAY:
        return f"Due tomorrow: {task.title}"
    if kind == DeadlineReminder.Kind.IN_2_DAYS:
        return f"Due in 2 days: {task.title}"
    if kind == DeadlineReminder.Kind.IN_3_DAYS:
        return f"Due in 3 days: {task.title}"
    return f"Reminder: {task.title} is due {due}"


def _message(task, email, kind):
    due = task.due_date.isoformat()
    if kind == DeadlineReminder.Kind.DUE_DATE:
        timing = f"This task is due on {due}."
    elif kind == DeadlineReminder.Kind.OVERDUE:
        timing = f"This task was due on {due} and is not finished."
    elif kind == DeadlineReminder.Kind.DUE_TODAY:
        timing = f"This task is due today, {due}."
    elif kind == DeadlineReminder.Kind.IN_1_DAY:
        timing = f"This task is due tomorrow, {due}."
    elif kind == DeadlineReminder.Kind.IN_2_DAYS:
        timing = f"This task is due in 2 days, on {due}."
    elif kind == DeadlineReminder.Kind.IN_3_DAYS:
        timing = f"This task is due in 3 days, on {due}."
    else:
        timing = f"This task is due on {due}."
    link = f"{settings.SITE_URL.rstrip('/')}{reverse('tasks:task_detail', args=[task.pk])}"
    return (
        f"{timing}\n\n"
        f"Due date: {due}\n"
        f"Task: {task.title}\n"
        f"{task.description}\n\n"
        f"This reminder was sent to {email}.\n"
        f"Open the task: {link}\n"
    )
