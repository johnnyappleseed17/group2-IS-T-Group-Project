from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ManagerApplication, UserProfile

User = get_user_model()
PASSWORD = "notpassword-123"


def make_user(username, role=UserProfile.Role.EMPLOYEE):
    user = User.objects.create_user(username=username, password=PASSWORD, email="")
    profile = user.profile  # created automatically when the user is saved
    profile.role = role
    profile.save()
    return user


class ApplyManagerTests(TestCase):
    def setUp(self):
        self.worker = make_user("worker")
        self.url = reverse("apply_manager")

    def apply(self, reason="I run the team already."):
        return self.client.post(self.url, {"reason": reason})

    def test_employee_sees_the_form(self):
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Send application")

    def test_sending_an_application_creates_a_pending_one(self):
        self.client.login(username="worker", password=PASSWORD)
        self.apply()
        application = ManagerApplication.objects.get(user=self.worker)
        self.assertEqual(application.status, ManagerApplication.Status.PENDING)
        self.assertEqual(application.reason, "I run the team already.")

    def test_pending_application_hides_the_form(self):
        self.client.login(username="worker", password=PASSWORD)
        self.apply()
        response = self.client.get(self.url)
        self.assertContains(response, "pending")
        self.assertNotContains(response, "Send application")

    def test_cannot_send_a_second_application_while_one_is_pending(self):
        self.client.login(username="worker", password=PASSWORD)
        self.apply("first")
        self.apply("second")
        self.assertEqual(ManagerApplication.objects.filter(user=self.worker).count(), 1)

    def test_declined_note_is_shown_and_they_can_apply_again(self):
        ManagerApplication.objects.create(
            user=self.worker,
            reason="old",
            status=ManagerApplication.Status.DECLINED,
            reviewed_at=timezone.now(),
            review_note="Try again next month",
        )
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertContains(response, "Try again next month")
        self.apply("new reason")
        self.assertEqual(ManagerApplication.objects.filter(user=self.worker).count(), 2)

    def test_manager_is_sent_to_the_dashboard(self):
        make_user("boss", role=UserProfile.Role.MANAGER)
        self.client.login(username="boss", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_logged_out_visitor_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)