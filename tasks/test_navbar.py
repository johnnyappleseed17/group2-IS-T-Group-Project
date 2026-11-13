from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile

User = get_user_model()
PASSWORD = "notpassword-123"


class NavbarHighlightTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password=PASSWORD, email="")
        self.boss.profile.role = UserProfile.Role.MANAGER
        self.boss.profile.save()
        self.worker = User.objects.create_user("worker", password=PASSWORD, email="")

    def assert_only_active(self, response, url_name):
        link = 'class="nav-link active" aria-current="page" href="%s"' % reverse(url_name)
        self.assertContains(response, link)
        self.assertContains(response, 'aria-current="page"', count=1)

    def test_manager_created_tasks_link_is_highlighted(self):
        self.client.force_login(self.boss)
        response = self.client.get(reverse("tasks:my_created_tasks"))
        self.assert_only_active(response, "tasks:my_created_tasks")

    def test_employee_accepted_tasks_link_is_highlighted(self):
        self.client.force_login(self.worker)
        response = self.client.get(reverse("tasks:my_accepted_tasks"))
        self.assert_only_active(response, "tasks:my_accepted_tasks")

    def test_employee_dashboard_link_is_highlighted(self):
        self.client.force_login(self.worker)
        response = self.client.get(reverse("dashboard"))
        self.assert_only_active(response, "dashboard")