from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "role": UserProfile.Role.MANAGER if instance.is_superuser else UserProfile.Role.EMPLOYEE,
                "is_approved": True,
            },
        )