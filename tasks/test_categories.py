from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile

from .models import Category, Task

User = get_user_model()


class CategoryManagementTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("cat_manager", password="pw12345!")
        self.manager.profile.role = UserProfile.Role.MANAGER
        self.manager.profile.save()
        self.employee = User.objects.create_user("cat_employee", password="pw12345!")

        self.kitchen = Category.objects.create(name="Kitchen")
        self.cleaning = Category.objects.create(name="Cleaning", color="#2E7D32")

        self.task = Task.objects.create(
            title="Clean the fryer",
            description="Deep clean",
            due_date=timezone.localdate() + timedelta(days=5),
            created_by=self.manager,
        )
        self.task.categories.add(self.kitchen)

        self.list_url = reverse("tasks:category_list")
        self.create_url = reverse("tasks:category_create")
        self.edit_url = reverse("tasks:category_update", args=[self.kitchen.pk])
        self.delete_url = reverse("tasks:category_delete", args=[self.kitchen.pk])
        self.client.force_login(self.manager)

    def test_manager_sees_categories_with_task_counts(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, "Kitchen")
        self.assertContains(response, "Cleaning")
        counts = {c.name: c.task_count for c in response.context["categories"]}
        self.assertEqual(counts["Kitchen"], 1)
        self.assertEqual(counts["Cleaning"], 0)

    def test_employee_is_blocked_from_every_category_page(self):
        self.client.force_login(self.employee)
        for url in (self.list_url, self.create_url, self.edit_url, self.delete_url):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.client.post(self.create_url, {"name": "Sneaky", "color": ""})
        self.assertFalse(Category.objects.filter(name="Sneaky").exists())
        self.client.post(self.delete_url)
        self.assertTrue(Category.objects.filter(pk=self.kitchen.pk).exists())

    def test_unapproved_manager_is_blocked(self):
        self.manager.profile.is_approved = False
        self.manager.profile.save()
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_logged_out_visitor_is_sent_to_login(self):
        self.client.logout()
        for url in (self.list_url, self.create_url, self.edit_url, self.delete_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response["Location"])

    def test_manager_can_create_a_category(self):
        response = self.client.post(self.create_url, {"name": "Bar", "color": "#112233"})
        self.assertRedirects(response, self.list_url)
        self.assertEqual(Category.objects.get(name="Bar").color, "#112233")

    def test_color_is_optional(self):
        self.client.post(self.create_url, {"name": "Bar", "color": ""})
        self.assertEqual(Category.objects.get(name="Bar").color, "")

    def test_blank_name_is_rejected(self):
        response = self.client.post(self.create_url, {"name": "   ", "color": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.count(), 2)

    def test_duplicate_name_is_rejected_ignoring_capitals(self):
        response = self.client.post(self.create_url, {"name": "kitchen", "color": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A category with this name already exists.")
        self.assertEqual(Category.objects.count(), 2)

    def test_bad_color_is_rejected(self):
        response = self.client.post(self.create_url, {"name": "Bar", "color": "green"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a color like #2E7D32")
        self.assertFalse(Category.objects.filter(name="Bar").exists())

    def test_manager_can_rename_a_category(self):
        response = self.client.post(self.edit_url, {"name": "Kitchen staff", "color": ""})
        self.assertRedirects(response, self.list_url)
        self.kitchen.refresh_from_db()
        self.assertEqual(self.kitchen.name, "Kitchen staff")

    def test_saving_a_category_with_its_own_name_is_allowed(self):
        response = self.client.post(self.edit_url, {"name": "Kitchen", "color": "#445566"})
        self.assertRedirects(response, self.list_url)
        self.kitchen.refresh_from_db()
        self.assertEqual(self.kitchen.color, "#445566")

    def test_renaming_to_another_existing_name_is_rejected(self):
        response = self.client.post(self.edit_url, {"name": "cleaning", "color": ""})
        self.assertEqual(response.status_code, 200)
        self.kitchen.refresh_from_db()
        self.assertEqual(self.kitchen.name, "Kitchen")

    def test_delete_page_warns_but_does_not_delete(self):
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["task_count"], 1)
        self.assertTrue(Category.objects.filter(pk=self.kitchen.pk).exists())

    def test_deleting_a_category_keeps_its_tasks(self):
        response = self.client.post(self.delete_url)
        self.assertRedirects(response, self.list_url)
        self.assertFalse(Category.objects.filter(pk=self.kitchen.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertEqual(self.task.categories.count(), 0)

    def test_unknown_category_returns_404(self):
        response = self.client.get(reverse("tasks:category_update", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_manager_dashboard_links_to_categories_but_employee_does_not(self):
        self.assertContains(self.client.get(reverse("dashboard")), f'href="{self.list_url}"')
        self.client.force_login(self.employee)
        self.assertNotContains(self.client.get(reverse("dashboard")), f'href="{self.list_url}"')