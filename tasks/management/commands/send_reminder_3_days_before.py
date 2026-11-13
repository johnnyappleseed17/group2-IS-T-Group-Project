from django.core.management.base import BaseCommand

from tasks.reminders import send_reminders_before


class Command(BaseCommand):
    help = "Email managers and employees when a task is due in 3 days."

    def handle(self, *args, **options):
        sent = send_reminders_before(3)
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder(s) for tasks due in 3 days."))
