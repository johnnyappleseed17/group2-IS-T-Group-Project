from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserProfile

from .models import Task, TaskAssignment
from .reminders import send_due_reminders

User = get_user_model()
PASSWORD = "notpassword-123"


def make_user(username, role, email=""):
    user = User.objects.create_user(username=username, password=PASSWORD, email=email)
    profile = user.profile  # created automatically when the user is saved
    profile.role = role
    profile.save()
    return user


class ReminderOptOutTests(TestCase):
    def setUp(self):
        self.boss = make_user("boss", UserProfile.Role.MANAGER, "boss@example.com")
        self.worker = make_user("worker", UserProfile.Role.EMPLOYEE, "worker@example.com")
        self.task = Task.objects.create(
            title="Water the plants",
            description="Front office",
            due_date=timezone.localdate(),
            created_by=self.boss,
        )
        TaskAssignment.objects.create(task=self.task, assignee=self.worker)

    def turn_off(self, user):
        user.profile.email_reminders = False
        user.profile.save()

    def test_everyone_gets_a_reminder_by_default(self):
        self.assertEqual(send_due_reminders(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_manager_who_turned_reminders_off_is_skipped(self):
        self.turn_off(self.boss)
        self.assertEqual(send_due_reminders(), 1)
        self.assertEqual(mail.outbox[0].to, ["worker@example.com"])

    def test_employee_who_turned_reminders_off_is_skipped(self):
        self.turn_off(self.worker)
        self.assertEqual(send_due_reminders(), 1)
        self.assertEqual(mail.outbox[0].to, ["boss@example.com"])