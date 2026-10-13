from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# A task counts as "due soon" (yellow) when it is due within this many days.
DUE_SOON_DAYS = 3


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

    # ---- Helpers: worked out when needed, not stored in the database ----

    @property
    def claimed_count(self):
        """How many people have claimed this task."""
        return self.assignments.count()

    @property
    def spots_left(self):
        """How many more people the task still needs (never below 0)."""
        return max(self.employees_needed - self.claimed_count, 0)

    @property
    def is_full(self):
        return self.spots_left == 0

    @property
    def is_finished(self):
        """Finished if someone marked the whole task complete, or if everyone
        who claimed it has marked their part done."""
        if self.completed_at is not None:
            return True
        claims = self.assignments.all()
        return claims.exists() and not claims.filter(completed_at__isnull=True).exists()

    @property
    def status(self):
        """'finished', 'claimed' (at least one person), or 'unclaimed'."""
        if self.is_finished:
            return "finished"
        if self.claimed_count > 0:
            return "claimed"
        return "unclaimed"

    @property
    def is_overdue(self):
        return not self.is_finished and self.due_date < timezone.localdate()

    @property
    def due_color(self):
        """'red' = overdue, 'yellow' = due soon, 'green' = plenty of time,
        'done' = finished (no deadline color needed)."""
        if self.is_finished:
            return "done"
        today = timezone.localdate()
        if self.due_date < today:
            return "red"
        if self.due_date <= today + timedelta(days=DUE_SOON_DAYS):
            return "yellow"
        return "green"


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