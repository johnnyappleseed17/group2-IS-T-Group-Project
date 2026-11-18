from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sam", password="pw", email="sam@example.com")
        self.url = reverse("profile")

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_page_loads_for_logged_in_user(self):
        self.client.login(username="sam", password="pw")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sam")

    def test_user_can_update_name_and_email(self):
        self.client.login(username="sam", password="pw")
        response = self.client.post(
            self.url,
            {"first_name": "Sam", "last_name": "Lee", "email": "new@example.com"},
        )
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Sam")
        self.assertEqual(self.user.email, "new@example.com")

    def test_email_is_required(self):
        self.client.login(username="sam", password="pw")
        response = self.client.post(self.url, {"first_name": "Sam", "last_name": "Lee", "email": ""})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "sam@example.com")