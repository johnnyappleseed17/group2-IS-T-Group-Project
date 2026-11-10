from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
class HomeTest(TestCase):
    def test_home_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')

    def test_home_does_not_redirect_to_login(self):
        response = self.client.get(reverse('index'))
        self.assertNotContains(response, 'http-equiv="refresh"')

    def test_home_has_text(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'Welcome to Task Manager 2.0')
        self.assertContains(response, 'How it works')

    def test_signup_and_login_buttons(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'class="btn btn-primary" href="/register/"')
        self.assertContains(response, 'class="btn btn-outline-secondary" href="/accounts/login/"')

    def test_navbar_home_link(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'href="/">Home</a>')

    def test_logged_in_user_sees_dashboard_button(self):
        User.objects.create_user(username='testuser', password='Testpass123!')
        self.client.login(username='testuser', password='Testpass123!')
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'Go to Dashboard')
        self.assertNotContains(response, 'class="btn btn-primary" href="/register/"')
