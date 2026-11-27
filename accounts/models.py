from django.conf import settings
from django.db import models
from django.db.models import Q


class UserProfile(models.Model):
    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        MANAGER = "manager", "Manager"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    is_approved = models.BooleanField(default=True)
    manager_requested = models.BooleanField(
        default=False,
        help_text="This person asked to become a manager, allow this?",
    )

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

class ManagerApplication(models.Model):
    """An employee's request to become a manager, and what was decided."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="manager_applications",
    )
    reason = models.TextField(help_text="Why do you want to be a manager?")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="manager_applications_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="pending"),
                name="one_pending_application_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_status_display()}"