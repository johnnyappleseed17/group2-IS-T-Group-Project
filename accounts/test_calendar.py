from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Category, Task, TaskAssignment

from .models import UserProfile

User = get_user_model()
PASSWORD = "notpassword-123"


class CalendarEventsTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password=PASSWORD, email="")
        self.boss.profile.role = UserProfile.Role.MANAGER
        self.boss.profile.save()
        self.rival = User.objects.create_user("rival", password=PASSWORD, email="")
        self.rival.profile.role = UserProfile.Role.MANAGER
        self.rival.profile.save()
        self.worker = User.objects.create_user("worker", password=PASSWORD, email="")
        self.other = User.objects.create_user("other", password=PASSWORD, email="")
        self.due = timezone.localdate() + timedelta(days=5)

    def make_task(self, title, owner=None, needed=1, **extra):
        return Task.objects.create(
            title=title,
            description="d",
            due_date=self.due,
            employees_needed=needed,
            created_by=owner or self.boss,
            **extra,
        )

    def events_for(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("calendar_events"))
        return {
            event["title"].removeprefix("\u2605 "): event for event in response.json()
        }

    def test_manager_sees_tasks_nobody_has_accepted(self):
        self.make_task("Nobody yet")
        event = self.events_for(self.boss)["Nobody yet"]
        self.assertEqual(event["extendedProps"]["assignees"], [])

    def test_manager_does_not_see_other_managers_tasks(self):
        self.make_task("Rival task", owner=self.rival)
        self.assertNotIn("Rival task", self.events_for(self.boss))

    def test_manager_does_not_see_archived_tasks(self):
        self.make_task("Old task", is_archived=True)
        self.assertNotIn("Old task", self.events_for(self.boss))

    def test_employee_sees_accepted_task_in_solid_color(self):
        task = self.make_task("Mine")
        TaskAssignment.objects.create(task=task, assignee=self.worker)
        self.assertEqual(self.events_for(self.worker)["Mine"]["classNames"], [])

    def test_employee_sees_available_task_faded(self):
        self.make_task("Up for grabs")
        event = self.events_for(self.worker)["Up for grabs"]
        self.assertEqual(event["classNames"], ["event-available"])
        self.assertEqual(event["extendedProps"]["assignees"], [])

    def test_employee_does_not_see_archived_available_or_accepted_tasks(self):
        accepted = self.make_task("Archived accepted task", is_archived=True)
        TaskAssignment.objects.create(task=accepted, assignee=self.worker)
        self.make_task("Archived available task", is_archived=True)
        self.assertEqual(self.events_for(self.worker), {})

    def test_employee_does_not_see_full_tasks(self):
        task = self.make_task("Taken", needed=1)
        TaskAssignment.objects.create(task=task, assignee=self.other)
        self.assertNotIn("Taken", self.events_for(self.worker))

    def test_employee_does_not_see_tasks_they_finished(self):
        task = self.make_task("Finished by me", needed=2)
        TaskAssignment.objects.create(
            task=task, assignee=self.worker, completed_at=timezone.now()
        )
        self.assertNotIn("Finished by me", self.events_for(self.worker))

    def test_priority_tasks_get_a_star(self):
        self.make_task("Urgent", is_priority=True)
        self.client.force_login(self.boss)
        titles = [e["title"] for e in self.client.get(reverse("calendar_events")).json()]
        self.assertIn("\u2605 Urgent", titles)

    def test_preview_assignees_use_usernames_in_sorted_order_for_both_roles(self):
        self.worker.first_name = "Alice"
        self.worker.save(update_fields=["first_name"])
        self.other.first_name = "Zoe"
        self.other.save(update_fields=["first_name"])
        task = self.make_task("Shared work", needed=3)
        # Claim order differs from username order. Completed assignees are still
        # listed on the detail page and should remain in the preview as well.
        TaskAssignment.objects.create(task=task, assignee=self.worker)
        TaskAssignment.objects.create(
            task=task, assignee=self.other, completed_at=timezone.now()
        )
        expected = [self.other.get_username(), self.worker.get_username()]
        for viewer in (self.boss, self.worker):
            with self.subTest(viewer=viewer.username):
                event = self.events_for(viewer)["Shared work"]
                self.assertEqual(event["extendedProps"]["assignees"], expected)
                detail = self.client.get(event["url"])
                self.assertEqual(
                    sorted(str(assignment.assignee) for assignment in detail.context["assignments"]),
                    expected,
                )

    def test_preview_keeps_priority_date_detail_link_and_category_color(self):
        task = self.make_task("Inventory review", is_priority=True)
        category = Category.objects.create(name="Inventory", color="#1267ab")
        task.categories.add(category)
        for viewer in (self.boss, self.worker):
            with self.subTest(viewer=viewer.username):
                event = self.events_for(viewer)["Inventory review"]
                self.assertEqual(event["id"], task.pk)
                self.assertEqual(event["title"], "\u2605 Inventory review")
                self.assertEqual(event["start"], self.due.isoformat())
                self.assertIs(event["allDay"], True)
                self.assertEqual(event["url"], reverse("tasks:task_detail", args=[task.pk]))
                self.assertEqual(event["color"], category.color)
                self.assertEqual(self.client.get(event["url"]).status_code, 200)
