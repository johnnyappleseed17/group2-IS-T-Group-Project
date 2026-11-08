from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile

from .forms import CategoryForm
from .models import Category, Task

User = get_user_model()
PASSWORD = "notpassword-123"


def make_manager(username):
    user = User.objects.create_user(username, password=PASSWORD, email="")
    user.profile.role = UserProfile.Role.MANAGER
    user.profile.save()
    return user


class CategoryTextColorTests(TestCase):
    def test_dark_color_gets_white_text(self):
        self.assertEqual(Category(name="a", color="#1976D2").text_color, "#ffffff")

    def test_light_color_gets_dark_text(self):
        self.assertEqual(Category(name="a", color="#FBC02D").text_color, "#212529")

    def test_no_color_gives_no_text_color(self):
        self.assertEqual(Category(name="a", color="").text_color, "")


class CategoryTaskChecklistTests(TestCase):
    def setUp(self):
        self.boss = make_manager("boss")
        self.rival = make_manager("rival")
        due = timezone.localdate() + timedelta(days=4)

        def task(owner, title, **extra):
            return Task.objects.create(
                title=title, description="d", due_date=due, created_by=owner, **extra
            )

        self.mine_a = task(self.boss, "Mine A")
        self.mine_b = task(self.boss, "Mine B")
        self.archived = task(self.boss, "Old one", is_archived=True)
        self.theirs = task(self.rival, "Their task")
        self.category = Category.objects.create(name="Kitchen")
        self.client.force_login(self.boss)

    def test_form_only_offers_own_unarchived_tasks(self):
        form = CategoryForm(user=self.boss)
        offered = set(form.fields["tasks"].queryset)
        self.assertEqual(offered, {self.mine_a, self.mine_b})

    def test_create_with_tasks_adds_the_category(self):
        self.client.post(
            reverse("tasks:category_create"),
            {"name": "Bar", "color": "#112233", "tasks": [self.mine_a.pk, self.mine_b.pk]},
        )
        bar = Category.objects.get(name="Bar")
        self.assertEqual(set(bar.tasks.all()), {self.mine_a, self.mine_b})

    def test_edit_prechecks_tasks_already_in_the_category(self):
        self.mine_a.categories.add(self.category)
        response = self.client.get(reverse("tasks:category_update", args=[self.category.pk]))
        self.assertEqual(list(response.context["form"].fields["tasks"].initial), [self.mine_a])

    def test_unchecking_removes_only_my_tasks_from_the_category(self):
        self.mine_a.categories.add(self.category)
        self.mine_b.categories.add(self.category)
        self.theirs.categories.add(self.category)
        self.archived.categories.add(self.category)
        self.client.post(
            reverse("tasks:category_update", args=[self.category.pk]),
            {"name": "Kitchen", "color": "", "tasks": [self.mine_a.pk]},
        )
        self.assertEqual(
            set(self.category.tasks.all()), {self.mine_a, self.theirs, self.archived}
        )

    def test_cannot_add_another_managers_task(self):
        response = self.client.post(
            reverse("tasks:category_update", args=[self.category.pk]),
            {"name": "Kitchen", "color": "", "tasks": [self.theirs.pk]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.theirs.categories.filter(pk=self.category.pk).exists())

    def test_edit_page_mentions_other_managers_tasks(self):
        self.theirs.categories.add(self.category)
        response = self.client.get(reverse("tasks:category_update", args=[self.category.pk]))
        self.assertContains(response, "by other managers")

    def test_save_and_add_another_returns_to_a_blank_form(self):
        response = self.client.post(
            reverse("tasks:category_create"),
            {"name": "Bar", "color": "", "add_another": "1"},
        )
        self.assertRedirects(response, reverse("tasks:category_create"))
        self.assertTrue(Category.objects.filter(name="Bar").exists())

    def test_normal_save_goes_to_the_list(self):
        response = self.client.post(
            reverse("tasks:category_create"), {"name": "Bar", "color": ""}
        )
        self.assertRedirects(response, reverse("tasks:category_list"))

    def test_page_knows_existing_names_and_used_colors(self):
        Category.objects.create(name="Cleaning", color="#2E7D32")
        response = self.client.get(reverse("tasks:category_create"))
        self.assertIn("Cleaning", response.context["existing_names"])
        self.assertIn(
            {"name": "Cleaning", "color": "#2E7D32"}, response.context["used_colors"]
        )

    def test_editing_a_category_does_not_list_itself_as_taken(self):
        response = self.client.get(reverse("tasks:category_update", args=[self.category.pk]))
        self.assertNotIn("Kitchen", response.context["existing_names"])

    def test_list_page_uses_edit_link_and_pills(self):
        Category.objects.create(name="Cleaning", color="#2E7D32")
        response = self.client.get(reverse("tasks:category_list"))
        self.assertContains(response, ">Edit</a>")
        self.assertNotContains(response, ">Rename</a>")
        self.assertContains(response, "category-pill")