from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from .models import Task, TaskAssignment

User = get_user_model()


class MarkDoneTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("boss", password="pw")
        UserProfile.objects.update_or_create(
            user=self.manager, defaults={"role": "manager", "is_approved": True}
        )
        self.worker = User.objects.create_user("worker", password="pw")
        UserProfile.objects.update_or_create(
            user=self.worker, defaults={"role": "employee", "is_approved": True}
        )
        self.task = Task.objects.create(
            title="Sweep", description="x", created_by=self.manager,
            due_date=timezone.now().date(), employees_needed=1,
        )
        self.assignment = TaskAssignment.objects.create(task=self.task, assignee=self.worker)
        self.url = reverse("tasks:mark_done", args=[self.task.pk])

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_get_is_not_allowed(self):
        self.client.login(username="worker", password="pw")
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_post_marks_assignment_done(self):
        self.client.login(username="worker", password="pw")
        self.client.post(self.url)
        self.assignment.refresh_from_db()
        self.assertIsNotNone(self.assignment.completed_at)

    def test_other_user_cannot_mark_it_done(self):
        other = User.objects.create_user("other", password="pw")
        UserProfile.objects.update_or_create(user=other, defaults={"role": "employee", "is_approved": True})
        self.client.login(username="other", password="pw")
        self.assertEqual(self.client.post(self.url).status_code, 404)