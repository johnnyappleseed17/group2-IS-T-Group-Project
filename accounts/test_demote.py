from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile

User = get_user_model()
PASSWORD = "notpassword-123"


def make_user(username, role=UserProfile.Role.EMPLOYEE):
    user = User.objects.create_user(username=username, password=PASSWORD, email="")
    profile = user.profile  # created automatically when the user is saved
    profile.role = role
    profile.save()
    return user


class DemoteManagerTests(TestCase):
    def setUp(self):
        self.boss = make_user("boss", role=UserProfile.Role.MANAGER)
        self.other = make_user("other", role=UserProfile.Role.MANAGER)
        self.worker = make_user("worker")

    def url(self, user):
        return reverse("demote_manager", args=[user.profile.pk])

    def test_manager_page_lists_current_managers(self):
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(reverse("pending_managers"))
        self.assertContains(response, "Current managers")
        self.assertContains(response, "other")

    def test_manager_can_remove_another_manager(self):
        self.client.login(username="boss", password=PASSWORD)
        self.client.post(self.url(self.other))
        self.other.profile.refresh_from_db()
        self.assertEqual(self.other.profile.role, UserProfile.Role.EMPLOYEE)

    def test_cannot_remove_yourself(self):
        self.client.login(username="boss", password=PASSWORD)
        self.client.post(self.url(self.boss))
        self.boss.profile.refresh_from_db()
        self.assertEqual(self.boss.profile.role, UserProfile.Role.MANAGER)

    def test_employee_cannot_remove_a_manager(self):
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.post(self.url(self.other))
        self.assertEqual(response.status_code, 403)
        self.other.profile.refresh_from_db()
        self.assertEqual(self.other.profile.role, UserProfile.Role.MANAGER)

    def test_get_request_is_not_allowed(self):
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(self.url(self.other))
        self.assertEqual(response.status_code, 405)

    def test_logged_out_user_is_sent_to_login(self):
        response = self.client.post(self.url(self.other))
        self.assertEqual(response.status_code, 302)
        self.other.profile.refresh_from_db()
        self.assertEqual(self.other.profile.role, UserProfile.Role.MANAGER)