from django.core.management.base import BaseCommand

from tasks.reminders import send_reminders_before


class Command(BaseCommand):
    help = "Email creators and assignees when a task is due tomorrow."

    def handle(self, *args, **options):
        sent = send_reminders_before(1)
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder(s) for tasks due in 1 day."))
