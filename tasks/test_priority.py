from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from .models import Task

User = get_user_model()
PASSWORD = "notpassword-123"


def make_user(username, role):
    user = User.objects.create_user(username=username, password=PASSWORD, email="")
    profile = user.profile
    profile.role = role
    profile.save()
    return user


def make_task(user, title, days, priority=False):
    return Task.objects.create(
        title=title,
        description="desc",
        due_date=timezone.localdate() + timedelta(days=days),
        created_by=user,
        is_priority=priority,
    )


class PriorityTests(TestCase):
    def setUp(self):
        self.manager = make_user("boss", UserProfile.Role.MANAGER)
        self.employee = make_user("worker", UserProfile.Role.EMPLOYEE)

    def test_tasks_are_not_priority_by_default(self):
        task = make_task(self.manager, "Plain", 5)
        self.assertFalse(task.is_priority)

    def test_manager_can_create_priority_task(self):
        self.client.login(username="boss", password=PASSWORD)
        self.client.post(
            reverse("tasks:task_create"),
            {
                "title": "Urgent",
                "description": "Do it now",
                "due_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
                "employees_needed": 1,
                "is_priority": "on",
            },
        )
        self.assertTrue(Task.objects.get(title="Urgent").is_priority)

    def test_created_list_shows_priority_badge(self):
        make_task(self.manager, "Urgent", 5, priority=True)
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(reverse("tasks:my_created_tasks"))
        self.assertContains(response, "Priority")

    def test_created_list_puts_priority_first(self):
        make_task(self.manager, "Soon normal", 1)
        make_task(self.manager, "Later priority", 10, priority=True)
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(reverse("tasks:my_created_tasks"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertEqual(titles, ["Later priority", "Soon normal"])

    def test_employee_dashboard_puts_priority_first(self):
        make_task(self.manager, "Soon normal", 1)
        make_task(self.manager, "Later priority", 10, priority=True)
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(reverse("dashboard"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertEqual(titles, ["Later priority", "Soon normal"])

    def test_accepted_list_puts_priority_first(self):
        normal = make_task(self.manager, "Soon normal", 1)
        urgent = make_task(self.manager, "Later priority", 10, priority=True)
        self.client.login(username="worker", password=PASSWORD)
        self.client.post(reverse("tasks:accept_task", args=[normal.pk]))
        self.client.post(reverse("tasks:accept_task", args=[urgent.pk]))
        response = self.client.get(reverse("tasks:my_accepted_tasks"))
        titles = [t.title for t in response.context["tasks"]]
        self.assertEqual(titles, ["Later priority", "Soon normal"])