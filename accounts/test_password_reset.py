from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile

User = get_user_model()


class PasswordResetEmailTests(TestCase):
    def test_reset_request_sends_an_email_with_a_link(self):
        User.objects.create_user(
            username="hinti",
            password="notpassword-123",
            email="hinti@example.com",
        )
        response = self.client.post(
            reverse("password_reset"),
            {"email": "hinti@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["hinti@example.com"])
        self.assertIn("Password reset", message.subject)
        self.assertIn("hinti", message.body)
        self.assertIn("/accounts/reset/", message.body)

    def test_unknown_email_does_not_send_a_message(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "missing@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)


class NotificationEmailTests(TestCase):
    def test_signed_in_user_can_save_the_address_that_receives_reminders(self):
        user = User.objects.create_user(username="worker", password="notpassword-123", email="")
        profile = user.profile
        profile.role = UserProfile.Role.EMPLOYEE
        profile.save()
        self.client.login(username="worker", password="notpassword-123")
        response = self.client.post(
            reverse("notification_email"),
            {"email": "worker@example.com"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        user.refresh_from_db()
        self.assertEqual(user.email, "worker@example.com")
