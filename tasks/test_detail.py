from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from .models import Category, Task, TaskAssignment

User = get_user_model()
PASSWORD = "notpassword-123"


def make_user(username, role, approved=True):
    user = User.objects.create_user(username=username, password=PASSWORD, email="")
    profile = user.profile
    profile.role = role
    profile.is_approved = approved
    profile.save()
    return user


class TaskDetailTests(TestCase):
    def setUp(self):
        self.manager = make_user("boss", UserProfile.Role.MANAGER)
        self.employee = make_user("worker", UserProfile.Role.EMPLOYEE)
        self.task = Task.objects.create(
            title="Stock the shelves",
            description="Front aisle needs restocking.",
            due_date=timezone.localdate() + timedelta(days=4),
            employees_needed=2,
            created_by=self.manager,
            is_priority=True,
        )
        category = Category.objects.create(name="Store", color="#2E7D32")
        self.task.categories.add(category)
        self.url = reverse("tasks:task_detail", args=[self.task.pk])

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_unapproved_account_is_denied(self):
        pending = make_user("pending", UserProfile.Role.EMPLOYEE, approved=False)
        self.client.login(username="pending", password=PASSWORD)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_detail_page_shows_task_information(self):
        TaskAssignment.objects.create(task=self.task, assignee=self.employee)
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stock the shelves")
        self.assertContains(response, "Front aisle needs restocking.")
        self.assertContains(response, "Priority")
        self.assertContains(response, "Store")
        self.assertContains(response, self.task.due_date.isoformat())
        self.assertContains(response, "1 / 2")
        self.assertContains(response, "Claimed")
        self.assertContains(response, "worker")
        self.assertContains(response, "Edit")
        self.assertContains(response, "Archive")

    def test_employee_can_accept_from_the_detail_page(self):
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertContains(response, "Accept task")
        self.assertNotContains(response, "Edit")

    def test_employee_who_already_accepted_does_not_see_accept(self):
        TaskAssignment.objects.create(task=self.task, assignee=self.employee)
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Accept task")
        self.assertNotContains(response, "Mark done")
        self.assertContains(response, "accepted this task on")
