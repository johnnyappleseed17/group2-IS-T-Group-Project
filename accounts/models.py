from django.conf import settings
from django.db import models


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