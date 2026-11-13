from datetime import timedelta
from io import StringIO
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from .models import DeadlineReminder, Task, TaskAssignment
from .reminders import (
    send_deadline_reminders,
    send_due_date_reminders,
    send_due_reminders,
    send_reminders_before,
    send_task_reminders,
)

User = get_user_model()


def make_user(username, role, email):
    user = User.objects.create_user(username=username, password="notpassword-123", email=email)
    profile = user.profile
    profile.role = role
    profile.save()
    return user


class DeadlineReminderTests(TestCase):
    def setUp(self):
        self.manager = make_user("boss", UserProfile.Role.MANAGER, "boss@example.com")
        self.employee = make_user("worker", UserProfile.Role.EMPLOYEE, "worker@example.com")
        self.today = timezone.localdate()

    def make_task(self, days, finished=False):
        task = Task.objects.create(
            title="Stock the shelves",
            description="Front aisle needs restocking.",
            due_date=self.today + timedelta(days=days),
            employees_needed=1,
            created_by=self.manager,
            completed_at=timezone.now() if finished else None,
        )
        TaskAssignment.objects.create(task=task, assignee=self.employee)
        return task

    def test_due_soon_task_emails_the_manager_and_assignee(self):
        self.make_task(days=2)
        sent = send_deadline_reminders(self.today)
        self.assertEqual(sent, 2)
        recipients = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(recipients, ["boss@example.com", "worker@example.com"])
        self.assertIn("is due", mail.outbox[0].subject)
        self.assertIn("Stock the shelves", mail.outbox[0].body)
        bodies = {message.to[0]: message.body for message in mail.outbox}
        self.assertIn("sent to worker@example.com", bodies["worker@example.com"])
        self.assertIn("sent to boss@example.com", bodies["boss@example.com"])

    def test_the_same_reminder_is_not_sent_twice(self):
        self.make_task(days=1)
        send_deadline_reminders(self.today)
        mail.outbox.clear()
        sent = send_deadline_reminders(self.today)
        self.assertEqual(sent, 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(DeadlineReminder.objects.count(), 2)

    def test_a_distant_task_does_not_send_email(self):
        self.make_task(days=10)
        self.assertEqual(send_deadline_reminders(self.today), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_overdue_task_uses_the_overdue_subject(self):
        self.make_task(days=-1)
        send_deadline_reminders(self.today)
        self.assertTrue(all("Overdue" in message.subject for message in mail.outbox))

    def test_finished_task_does_not_send_email(self):
        self.make_task(days=-1, finished=True)
        self.assertEqual(send_deadline_reminders(self.today), 0)

    def test_a_person_without_an_email_is_skipped(self):
        self.employee.email = ""
        self.employee.save(update_fields=["email"])
        self.manager.email = ""
        self.manager.save(update_fields=["email"])
        self.make_task(days=1)
        self.assertEqual(send_deadline_reminders(self.today), 0)

    def test_every_valid_address_on_the_task_receives_one_email(self):
        task = self.make_task(days=1)
        task.employees_needed = 3
        task.save(update_fields=["employees_needed"])
        helper = make_user("helper", UserProfile.Role.EMPLOYEE, "  Helper@Example.com ")
        same_address = make_user("alias", UserProfile.Role.EMPLOYEE, "worker@example.com")
        invalid = make_user("bad", UserProfile.Role.EMPLOYEE, "not-an-email")
        TaskAssignment.objects.create(task=task, assignee=helper)
        TaskAssignment.objects.create(task=task, assignee=same_address)
        TaskAssignment.objects.create(task=task, assignee=invalid)
        sent = send_deadline_reminders(self.today)
        recipients = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(sent, 3)
        self.assertEqual(recipients, ["Helper@example.com", "boss@example.com", "worker@example.com"])

    def test_a_failed_delivery_does_not_block_the_other_addresses(self):
        self.make_task(days=1)
        real_send = mail.send_mail

        def flaky_send(*args, **kwargs):
            if kwargs.get("recipient_list") == ["boss@example.com"]:
                raise SMTPException("mailbox rejected")
            return real_send(*args, **kwargs)

        with patch("tasks.reminders.send_mail", side_effect=flaky_send):
            sent = send_deadline_reminders(self.today)
        self.assertEqual(sent, 1)
        self.assertEqual(mail.outbox[0].to, ["worker@example.com"])

    def test_due_today_command_emails_only_tasks_due_today(self):
        self.make_task(days=0)
        self.make_task(days=1)
        sent = send_due_reminders(self.today)
        self.assertEqual(sent, 2)
        self.assertTrue(all(message.subject.startswith("Due today:") for message in mail.outbox))

    def test_due_today_command_does_not_repeat(self):
        self.make_task(days=0)
        send_due_reminders(self.today)
        mail.outbox.clear()
        self.assertEqual(send_due_reminders(self.today), 0)

    def test_each_advance_day_emails_only_tasks_due_that_many_days_out(self):
        self.make_task(days=1)
        self.make_task(days=2)
        self.make_task(days=3)
        self.assertEqual(send_reminders_before(1, self.today), 2)
        self.assertEqual(send_reminders_before(2, self.today), 2)
        self.assertEqual(send_reminders_before(3, self.today), 2)
        subjects = sorted(message.subject for message in mail.outbox)
        self.assertEqual(subjects.count("Due tomorrow: Stock the shelves"), 2)
        self.assertEqual(subjects.count("Due in 2 days: Stock the shelves"), 2)
        self.assertEqual(subjects.count("Due in 3 days: Stock the shelves"), 2)

    def test_advance_commands_report_their_counts(self):
        self.make_task(days=1)
        self.make_task(days=2)
        self.make_task(days=3)
        checks = (
            ("send_reminder_1_day_before", "Sent 2 reminder(s) for tasks due in 1 day."),
            ("send_reminder_2_days_before", "Sent 2 reminder(s) for tasks due in 2 days."),
            ("send_reminder_3_days_before", "Sent 2 reminder(s) for tasks due in 3 days."),
        )
        for command, expected in checks:
            output = StringIO()
            call_command(command, stdout=output)
            self.assertIn(expected, output.getvalue())

    def test_due_today_management_command_reports_the_count(self):
        self.make_task(days=0)
        output = StringIO()
        call_command("send_due_reminders", stdout=output)
        self.assertIn("Sent 2 due-today reminder(s).", output.getvalue())

    def test_management_command_reports_how_many_emails_were_sent(self):
        self.make_task(days=2)
        output = StringIO()
        call_command("send_deadline_reminders", stdout=output)
        self.assertIn("Sent 2 deadline reminder(s).", output.getvalue())

    def test_three_days_two_days_due_date_and_overdue_go_to_managers_and_employees(self):
        make_user("lead", UserProfile.Role.MANAGER, "lead@example.com")
        make_user("outsider", UserProfile.Role.EMPLOYEE, "outsider@example.com")
        pending = make_user("pending", UserProfile.Role.MANAGER, "pending@example.com")
        pending.profile.is_approved = False
        pending.profile.save()
        self.make_task(days=3)
        self.make_task(days=2)
        self.make_task(days=0)
        self.make_task(days=-2)
        self.make_task(days=1)
        output = StringIO()
        call_command("send_task_reminders", stdout=output)
        self.assertIn(
            "Sent 12 reminder(s) to managers and employees for 3 days, 2 days, the due date, and overdue.",
            output.getvalue(),
        )
        addresses = {message.to[0] for message in mail.outbox}
        self.assertEqual(addresses, {"boss@example.com", "lead@example.com", "worker@example.com"})
        subjects = [message.subject for message in mail.outbox]
        self.assertEqual(sum(subject.startswith("Due in 3 days:") for subject in subjects), 3)
        self.assertEqual(sum(subject.startswith("Due in 2 days:") for subject in subjects), 3)
        self.assertEqual(sum(subject.startswith("Due today:") for subject in subjects), 3)
        self.assertEqual(sum(subject.startswith("Overdue:") for subject in subjects), 3)
        self.assertEqual(send_task_reminders(self.today), 0)

    def test_due_date_reminder_states_the_calendar_date(self):
        task = self.make_task(days=10)
        due = task.due_date.isoformat()
        self.assertEqual(send_due_date_reminders(task), 2)
        self.assertEqual(send_due_date_reminders(task), 0)
        recipients = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(recipients, ["boss@example.com", "worker@example.com"])
        for message in mail.outbox:
            self.assertIn(f"is due {due}", message.subject)
            self.assertIn(f"Due date: {due}", message.body)

    def test_creating_and_accepting_a_task_emails_the_due_date(self):
        self.client.login(username="boss", password="notpassword-123")
        due = (self.today + timedelta(days=12)).isoformat()
        response = self.client.post(
            reverse("tasks:task_create"),
            {
                "title": "Wipe the counters",
                "description": "Front counter",
                "due_date": due,
                "employees_needed": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mail.outbox[0].to, ["boss@example.com"])
        self.assertIn(f"Due date: {due}", mail.outbox[0].body)
        mail.outbox.clear()
        task = Task.objects.get(title="Wipe the counters")
        self.client.login(username="worker", password="notpassword-123")
        response = self.client.post(reverse("tasks:accept_task", args=[task.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual([message.to[0] for message in mail.outbox], ["worker@example.com"])
        self.assertIn(f"Due date: {due}", mail.outbox[0].body)

    def test_a_new_due_date_is_sent_again(self):
        task = self.make_task(days=4)
        send_due_date_reminders(task)
        mail.outbox.clear()
        task.due_date = self.today + timedelta(days=9)
        task.save(update_fields=["due_date"])
        due = task.due_date.isoformat()
        self.assertEqual(send_due_date_reminders(task), 2)
        self.assertTrue(all(f"Due date: {due}" in message.body for message in mail.outbox))
