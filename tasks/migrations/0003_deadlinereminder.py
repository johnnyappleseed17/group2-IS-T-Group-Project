from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tasks", "0002_task_is_priority"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeadlineReminder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("due_soon", "Due soon"), ("overdue", "Overdue")], max_length=20)),
                ("due_date", models.DateField()),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deadline_reminders", to=settings.AUTH_USER_MODEL)),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deadline_reminders", to="tasks.task")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("task", "recipient", "kind", "due_date"), name="unique_deadline_reminder"),
                ],
            },
        ),
    ]
