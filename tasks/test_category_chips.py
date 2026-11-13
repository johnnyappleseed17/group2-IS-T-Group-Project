from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile

from .models import Category, Task, TaskAssignment

User = get_user_model()
PASSWORD = "notpassword-123"


class CategoryChipTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password=PASSWORD, email="")
        self.boss.profile.role = UserProfile.Role.MANAGER
        self.boss.profile.save()
        self.worker = User.objects.create_user("worker", password=PASSWORD, email="")
        self.green = Category.objects.create(name="Kitchen", color="#2E7D32")
        self.plain = Category.objects.create(name="Misc")
        self.task = Task.objects.create(
            title="Clean the fryer",
            description="d",
            due_date=timezone.localdate() + timedelta(days=3),
            created_by=self.boss,
        )
        self.task.categories.add(self.green, self.plain)

    def test_task_form_shows_categories_as_colored_chips(self):
        self.client.force_login(self.boss)
        response = self.client.get(reverse("tasks:task_create"))
        self.assertContains(response, 'class="chip-face"', count=2)
        self.assertContains(response, "--chip-color: #2E7D32")
        self.assertContains(response, "--chip-color: #6c757d")

    def test_task_form_without_categories_links_to_create_one(self):
        Category.objects.all().delete()
        self.client.force_login(self.boss)
        response = self.client.get(reverse("tasks:task_create"))
        self.assertContains(response, "No categories yet.")
        self.assertContains(response, reverse("tasks:category_create"))

    def test_editing_a_task_prechecks_its_chips(self):
        self.client.force_login(self.boss)
        response = self.client.get(reverse("tasks:task_update", args=[self.task.pk]))
        self.assertContains(response, "checked", count=2)

    def test_created_tasks_list_shows_colored_pills(self):
        self.client.force_login(self.boss)
        response = self.client.get(reverse("tasks:my_created_tasks"))
        self.assertContains(response, "background-color: #2E7D32")
        self.assertContains(response, "category-pill is-plain")

    def test_employee_dashboard_shows_pills(self):
        self.client.force_login(self.worker)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "background-color: #2E7D32")

    def test_accepted_tasks_list_shows_pills(self):
        TaskAssignment.objects.create(task=self.task, assignee=self.worker)
        self.client.force_login(self.worker)
        response = self.client.get(reverse("tasks:my_accepted_tasks"))
        self.assertContains(response, "background-color: #2E7D32")

    def test_history_shows_pills(self):
        TaskAssignment.objects.create(
            task=self.task, assignee=self.worker, completed_at=timezone.now()
        )
        self.client.force_login(self.worker)
        response = self.client.get(reverse("tasks:task_history"))
        self.assertContains(response, "background-color: #2E7D32")

    def test_task_without_categories_shows_none(self):
        self.task.categories.clear()
        self.client.force_login(self.boss)
        response = self.client.get(reverse("tasks:my_created_tasks"))
        self.assertContains(response, "None")