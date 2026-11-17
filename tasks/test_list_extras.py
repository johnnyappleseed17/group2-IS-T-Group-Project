from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile

from .models import Task, TaskAssignment

User = get_user_model()
PASSWORD = "notpassword-123"


class ListExtrasTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password=PASSWORD, email="")
        self.boss.profile.role = UserProfile.Role.MANAGER
        self.boss.profile.save()
        self.worker = User.objects.create_user("worker", password=PASSWORD, email="")
        self.other = User.objects.create_user("other", password=PASSWORD, email="")
        self.today = timezone.localdate()

    def make_task(self, title, days=3, needed=1):
        return Task.objects.create(
            title=title,
            description="d",
            due_date=self.today + timedelta(days=days),
            employees_needed=needed,
            created_by=self.boss,
        )

    def get_created(self, **params):
        self.client.force_login(self.boss)
        return self.client.get(reverse("tasks:my_created_tasks"), params)

    def test_overdue_tag_shows_for_a_late_unfinished_task(self):
        self.make_task("Late job", days=-2)
        self.assertContains(self.get_created(), "badge-overdue")

    def test_no_overdue_tag_for_an_upcoming_task(self):
        self.make_task("Future job", days=3)
        self.assertNotContains(self.get_created(), "badge-overdue")

    def test_no_overdue_tag_once_the_task_is_finished(self):
        task = self.make_task("Late but done", days=-2)
        TaskAssignment.objects.create(
            task=task, assignee=self.worker, completed_at=timezone.now()
        )
        self.assertNotContains(self.get_created(), "badge-overdue")

    def test_progress_bar_shows_the_counts(self):
        task = self.make_task("Team job", needed=3)
        TaskAssignment.objects.create(task=task, assignee=self.worker)
        response = self.get_created()
        self.assertContains(response, "1 / 3")
        self.assertContains(response, 'aria-valuenow="1"')

    def test_full_task_progress_bar_is_green(self):
        task = self.make_task("Solo job", needed=1)
        TaskAssignment.objects.create(task=task, assignee=self.worker)
        self.assertContains(self.get_created(), "progress-bar bg-success")

    def test_hide_finished_hides_a_task_everyone_completed(self):
        task = self.make_task("All done")
        TaskAssignment.objects.create(
            task=task, assignee=self.worker, completed_at=timezone.now()
        )
        self.assertContains(self.get_created(), "All done")
        self.assertNotContains(self.get_created(hide_finished="1"), "All done")

    def test_hide_finished_hides_a_task_marked_complete(self):
        task = self.make_task("Marked complete")
        task.completed_at = timezone.now()
        task.save()
        self.assertNotContains(self.get_created(hide_finished="1"), "Marked complete")

    def test_hide_finished_keeps_open_and_partly_done_tasks(self):
        self.make_task("Nobody yet")
        partly = self.make_task("Half done", needed=2)
        TaskAssignment.objects.create(
            task=partly, assignee=self.worker, completed_at=timezone.now()
        )
        TaskAssignment.objects.create(task=partly, assignee=self.other)
        response = self.get_created(hide_finished="1")
        self.assertContains(response, "Nobody yet")
        self.assertContains(response, "Half done")

    def test_hide_finished_checkbox_is_only_on_created_tasks(self):
        task = self.make_task("Any job")
        TaskAssignment.objects.create(task=task, assignee=self.worker)
        self.assertContains(self.get_created(), 'id="filter-hide-finished"')
        self.client.force_login(self.worker)
        response = self.client.get(reverse("tasks:my_accepted_tasks"))
        self.assertNotContains(response, 'id="filter-hide-finished"')