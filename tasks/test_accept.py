from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile

from .models import Task, TaskAssignment

User = get_user_model()


class AcceptTaskTests(TestCase):
    def setUp(self):
        # A manager who posts the task (the signal gives every new user a profile).
        self.manager = User.objects.create_user("manager1", password="pw12345!")
        self.manager.profile.role = UserProfile.Role.MANAGER
        self.manager.profile.save()

        # Two ordinary employees.
        self.alice = User.objects.create_user("alice", password="pw12345!")
        self.bob = User.objects.create_user("bob", password="pw12345!")

        # One open task that needs a single person.
        self.task = Task.objects.create(
            title="Clean the fryer",
            description="Deep clean",
            due_date=timezone.localdate() + timedelta(days=10),
            employees_needed=1,
            created_by=self.manager,
        )
        self.url = reverse("tasks:accept_task", args=[self.task.id])

    def messages_for(self, response):
        # The notes the page would show, as plain text.
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_employee_can_accept_an_open_task(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("tasks:my_accepted_tasks"))
        self.assertTrue(
            TaskAssignment.objects.filter(task=self.task, assignee=self.alice).exists()
        )
        self.assertIn("You accepted the task.", self.messages_for(response))

    def test_accepting_twice_is_refused_with_a_message(self):
        TaskAssignment.objects.create(task=self.task, assignee=self.alice)
        self.client.force_login(self.alice)
        response = self.client.post(self.url)
        self.assertEqual(
            TaskAssignment.objects.filter(task=self.task, assignee=self.alice).count(), 1
        )
        self.assertIn("You have already accepted this task.", self.messages_for(response))

    def test_full_task_is_refused(self):
        TaskAssignment.objects.create(task=self.task, assignee=self.bob)  # takes the only spot
        self.client.force_login(self.alice)
        response = self.client.post(self.url)
        self.assertFalse(
            TaskAssignment.objects.filter(task=self.task, assignee=self.alice).exists()
        )
        self.assertIn("This task has no spots left.", self.messages_for(response))

    def test_task_with_two_spots_can_be_taken_by_two_people(self):
        self.task.employees_needed = 2
        self.task.save()
        for user in (self.alice, self.bob):
            self.client.force_login(user)
            self.client.post(self.url)
        self.assertEqual(self.task.assignments.count(), 2)

    def test_archived_task_is_refused(self):
        self.task.is_archived = True
        self.task.save()
        self.client.force_login(self.alice)
        response = self.client.post(self.url)
        self.assertEqual(self.task.assignments.count(), 0)
        self.assertIn("This task is no longer available.", self.messages_for(response))

    def test_finished_task_is_refused(self):
        self.task.completed_at = timezone.now()
        self.task.save()
        self.client.force_login(self.alice)
        response = self.client.post(self.url)
        self.assertEqual(self.task.assignments.count(), 0)
        self.assertIn("This task is no longer available.", self.messages_for(response))

    def test_manager_is_blocked(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.task.assignments.count(), 0)

    def test_unapproved_employee_is_blocked(self):
        self.alice.profile.is_approved = False
        self.alice.profile.save()
        self.client.force_login(self.alice)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.task.assignments.count(), 0)

    def test_logged_out_visitor_is_sent_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertEqual(self.task.assignments.count(), 0)

    def test_plain_page_visit_is_rejected(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class DashboardLoginTests(TestCase):
    def test_logged_out_visitor_is_sent_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])