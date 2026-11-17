from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Task, TaskAssignment

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
        self.assertIn("Nobody yet", self.events_for(self.boss))

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