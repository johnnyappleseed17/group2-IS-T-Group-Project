from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile

User = get_user_model()
PASSWORD = "notpassword-123"


def make_user(username, role=UserProfile.Role.EMPLOYEE, requested=False):
    user = User.objects.create_user(username=username, password=PASSWORD, email="")
    profile = user.profile # this is created by post_save
    profile.role = role
    profile.manager_requested = requested
    profile.save()
    return user

class SignUpTests(TestCase):
    def signup(self, **extra):
        data = {
            "username": "newbie",
            "first_name": "New",
            "last_name": "Person",
            "email": "newbie@example.com",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(extra)
        return self.client.post(reverse("register"), data)

    def test_box_ticked_creates_pending_employee(self):
        self.signup(want_manager="on")
        profile = User.objects.get(username="newbie").profile
        self.assertEqual(profile.role, UserProfile.Role.EMPLOYEE)
        self.assertTrue(profile.manager_requested)

    def test_box_unticked_is_plain_employee(self):
        self.signup()
        profile = User.objects.get(username="newbie").profile
        self.assertEqual(profile.role, UserProfile.Role.EMPLOYEE)
        self.assertFalse(profile.manager_requested)


class ApprovalTests(TestCase):
    def setUp(self):
        self.manager = make_user("boss", role=UserProfile.Role.MANAGER)
        self.applicant = make_user("applicant", requested=True)

    def test_manager_sees_pending_list(self):
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(reverse("pending_managers"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "applicant")

    def test_employee_cannot_see_pending_list(self):
        self.client.login(username="applicant", password=PASSWORD)
        response = self.client.get(reverse("pending_managers"))
        self.assertEqual(response.status_code, 403)

    def test_approve_promotes_to_manager(self):
        self.client.login(username="boss", password=PASSWORD)
        self.client.post(reverse("approve_manager", args=[self.applicant.profile.pk]))
        self.applicant.profile.refresh_from_db()
        self.assertEqual(self.applicant.profile.role, UserProfile.Role.MANAGER)
        self.assertFalse(self.applicant.profile.manager_requested)

    def test_decline_keeps_employee(self):
        self.client.login(username="boss", password=PASSWORD)
        self.client.post(reverse("decline_manager", args=[self.applicant.profile.pk]))
        self.applicant.profile.refresh_from_db()
        self.assertEqual(self.applicant.profile.role, UserProfile.Role.EMPLOYEE)
        self.assertFalse(self.applicant.profile.manager_requested)

    def test_employee_cannot_approve_themselves(self):
        self.client.login(username="applicant", password=PASSWORD)
        response = self.client.post(
            reverse("approve_manager", args=[self.applicant.profile.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.applicant.profile.refresh_from_db()
        self.assertEqual(self.applicant.profile.role, UserProfile.Role.EMPLOYEE)

    def test_approve_requires_post(self):
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(
            reverse("approve_manager", args=[self.applicant.profile.pk])
        )
        self.assertEqual(response.status_code, 405)


class NavbarBadgeTests(TestCase):
    def test_manager_badge(self):
        make_user("boss", role=UserProfile.Role.MANAGER)
        self.client.login(username="boss", password=PASSWORD)
        self.assertContains(self.client.get(reverse("dashboard")), "MANAGER")

    def test_pending_badge(self):
        make_user("applicant", requested=True)
        self.client.login(username="applicant", password=PASSWORD)
        self.assertContains(
            self.client.get(reverse("dashboard")), "Manager request pending"
        )
