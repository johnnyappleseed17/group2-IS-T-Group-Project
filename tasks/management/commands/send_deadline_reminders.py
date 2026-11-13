from django.core.management.base import BaseCommand

from tasks.reminders import send_deadline_reminders


class Command(BaseCommand):
    help = "Email managers and employees about tasks that are due soon or overdue."

    def handle(self, *args, **options):
        sent = send_deadline_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} deadline reminder(s)."))
