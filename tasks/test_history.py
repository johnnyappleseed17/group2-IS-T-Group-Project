from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from .models import Task, TaskAssignment

User = get_user_model()
PASSWORD = "notpassword-123"


def make_user(username, role):
    user = User.objects.create_user(username=username, password=PASSWORD, email="")
    profile = user.profile
    profile.role = role
    profile.save()
    return user


class TaskHistoryTests(TestCase):
    def setUp(self):
        self.manager = make_user("boss", UserProfile.Role.MANAGER)
        self.employee = make_user("worker", UserProfile.Role.EMPLOYEE)
        self.other = make_user("other", UserProfile.Role.EMPLOYEE)
        self.due = timezone.localdate() + timedelta(days=5)

    def make_task(self, title):
        return Task.objects.create(
            title=title, description="desc", due_date=self.due, created_by=self.manager
        )

    def test_employee_sees_only_finished_tasks(self):
        done = self.make_task("Finished job")
        open_task = self.make_task("Still open job")
        TaskAssignment.objects.create(
            task=done, assignee=self.employee, completed_at=timezone.now()
        )
        TaskAssignment.objects.create(task=open_task, assignee=self.employee)
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(reverse("tasks:task_history"))
        titles = [a.task.title for a in response.context["assignments"]]
        self.assertEqual(titles, ["Finished job"])

    def test_employee_does_not_see_other_peoples_history(self):
        task = self.make_task("Their job")
        TaskAssignment.objects.create(
            task=task, assignee=self.other, completed_at=timezone.now()
        )
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(reverse("tasks:task_history"))
        self.assertEqual(list(response.context["assignments"]), [])

    def test_task_completed_by_manager_counts_as_history(self):
        task = self.make_task("Closed job")
        task.completed_at = timezone.now()
        task.save()
        TaskAssignment.objects.create(task=task, assignee=self.employee)
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(reverse("tasks:task_history"))
        titles = [a.task.title for a in response.context["assignments"]]
        self.assertEqual(titles, ["Closed job"])

    def test_empty_history_shows_message(self):
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(reverse("tasks:task_history"))
        self.assertContains(response, "You haven't completed any tasks yet.")

    def test_manager_history_uses_the_archive_page(self):
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(reverse("tasks:task_history"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tasks/archived_tasks.html")
        self.assertEqual(list(response.context["tasks"]), [])

    def test_login_required(self):
        response = self.client.get(reverse("tasks:task_history"))
        self.assertEqual(response.status_code, 302)