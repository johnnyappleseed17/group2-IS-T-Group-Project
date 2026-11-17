from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile

from .models import Category, Task, TaskAssignment

User = get_user_model()
PASSWORD = "notpassword-123"


class TaskFilterTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password=PASSWORD, email="")
        self.boss.profile.role = UserProfile.Role.MANAGER
        self.boss.profile.save()
        self.worker = User.objects.create_user("worker", password=PASSWORD, email="")
        self.kitchen = Category.objects.create(name="Kitchen", color="#2E7D32")
        self.office = Category.objects.create(name="Office")
        due = timezone.localdate() + timedelta(days=3)
        self.fryer = Task.objects.create(
            title="Clean the fryer",
            description="Grease everywhere",
            due_date=due,
            created_by=self.boss,
            is_priority=True,
        )
        self.fryer.categories.add(self.kitchen)
        self.desks = Task.objects.create(
            title="Tidy the desks",
            description="Wipe down every surface",
            due_date=due,
            created_by=self.boss,
        )
        self.desks.categories.add(self.office)

    def get_created(self, **params):
        self.client.force_login(self.boss)
        return self.client.get(reverse("tasks:my_created_tasks"), params)

    def get_accepted(self, **params):
        TaskAssignment.objects.create(task=self.fryer, assignee=self.worker)
        TaskAssignment.objects.create(task=self.desks, assignee=self.worker)
        self.client.force_login(self.worker)
        return self.client.get(reverse("tasks:my_accepted_tasks"), params)

    def test_created_search_matches_title(self):
        response = self.get_created(q="fryer")
        self.assertContains(response, "Clean the fryer")
        self.assertNotContains(response, "Tidy the desks")

    def test_created_search_matches_description(self):
        response = self.get_created(q="surface")
        self.assertContains(response, "Tidy the desks")
        self.assertNotContains(response, "Clean the fryer")

    def test_created_category_filter(self):
        response = self.get_created(category=self.kitchen.pk)
        self.assertContains(response, "Clean the fryer")
        self.assertNotContains(response, "Tidy the desks")

    def test_created_priority_only(self):
        response = self.get_created(priority="1")
        self.assertContains(response, "Clean the fryer")
        self.assertNotContains(response, "Tidy the desks")

    def test_created_no_match_shows_message_and_keeps_bar(self):
        response = self.get_created(q="zzzz")
        self.assertContains(response, "No tasks match your filters")
        self.assertContains(response, 'id="filter-q"')

    def test_created_search_text_stays_in_the_box(self):
        response = self.get_created(q="fryer")
        self.assertContains(response, 'value="fryer"')

    def test_created_bad_category_value_is_ignored(self):
        response = self.get_created(category="abc")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clean the fryer")
        self.assertContains(response, "Tidy the desks")

    def test_page_links_keep_the_filter(self):
        due = timezone.localdate() + timedelta(days=5)
        for number in range(11):
            Task.objects.create(
                title="Filler task %d" % number,
                description="d",
                due_date=due,
                created_by=self.boss,
            )
        response = self.get_created(q="Filler")
        self.assertContains(response, "q=Filler&amp;page=2")

    def test_accepted_search_matches_title(self):
        response = self.get_accepted(q="desks")
        self.assertContains(response, "Tidy the desks")
        self.assertNotContains(response, "Clean the fryer")

    def test_accepted_priority_only(self):
        response = self.get_accepted(priority="1")
        self.assertContains(response, "Clean the fryer")
        self.assertNotContains(response, "Tidy the desks")

    def test_accepted_no_match_shows_message(self):
        response = self.get_accepted(q="zzzz")
        self.assertContains(response, "No tasks match your filters")