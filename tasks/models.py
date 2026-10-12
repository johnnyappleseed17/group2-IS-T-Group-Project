from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, blank=True, help_text="Optional hex color, like #2E7D32")

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Task(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    employees_needed = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    categories = models.ManyToManyField(Category, blank=True, related_name="tasks")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tasks_posted",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks_completed",
    )

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return self.title


class TaskAssignment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_assignments",
    )
    claimed_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["claimed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "assignee"], name="unique_claim_per_task"
            ),
        ]

    def __str__(self):
        return f"{self.assignee} on {self.task}"