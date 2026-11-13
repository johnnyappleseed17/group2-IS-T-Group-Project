from django.core.management.base import BaseCommand

from tasks.reminders import send_task_reminders


class Command(BaseCommand):
    help = "Email managers and employees 3 days before, 2 days before, on the due date, and when a task is overdue."

    def handle(self, *args, **options):
        sent = send_task_reminders()
        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent} reminder(s) to managers and employees for 3 days, 2 days, the due date, and overdue."
            )
        )
