from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile

User = get_user_model()
PASSWORD = "notpassword-123"
NEW_PASSWORD = "a-new-Pass-9876"


def make_user(username, role=UserProfile.Role.EMPLOYEE):
    user = User.objects.create_user(username=username, password=PASSWORD, email="")
    profile = user.profile  # created automatically when the user is saved
    profile.role = role
    profile.save()
    return user


class SettingsPageTests(TestCase):
    def setUp(self):
        self.user = make_user("worker")
        self.url = reverse("account_settings")

    def test_logged_out_visitor_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_page_shows_the_three_sections(self):
        self.client.login(username="worker", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertContains(response, "Account")
        self.assertContains(response, "Email reminders")
        self.assertContains(response, "Change password")

    def test_reminders_are_on_by_default(self):
        self.assertTrue(self.user.profile.email_reminders)

    def test_turning_reminders_off_is_saved(self):
        self.client.login(username="worker", password=PASSWORD)
        self.client.post(self.url, {})  # an unticked box sends nothing
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.email_reminders)

    def test_turning_reminders_back_on_is_saved(self):
        self.user.profile.email_reminders = False
        self.user.profile.save()
        self.client.login(username="worker", password=PASSWORD)
        self.client.post(self.url, {"email_reminders": "on"})
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.email_reminders)


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = make_user("worker")
        self.client.login(username="worker", password=PASSWORD)

    def test_page_uses_the_site_layout(self):
        response = self.client.get(reverse("password_change"))
        self.assertContains(response, "Change password")
        self.assertContains(response, "Task Manager")

    def test_changing_the_password_works(self):
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": PASSWORD,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("password_change_done"))
        self.client.logout()
        self.assertTrue(self.client.login(username="worker", password=NEW_PASSWORD))

    def test_wrong_old_password_is_refused(self):
        self.client.post(
            reverse("password_change"),
            {
                "old_password": "wrong-password-1",
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.client.logout()
        self.assertTrue(self.client.login(username="worker", password=PASSWORD))