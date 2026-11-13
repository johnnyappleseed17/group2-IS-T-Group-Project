from django.core.management.base import BaseCommand

from tasks.reminders import send_due_reminders


class Command(BaseCommand):
    help = "Email managers and employees on the day a task is due."

    def handle(self, *args, **options):
        sent = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} due-today reminder(s)."))
