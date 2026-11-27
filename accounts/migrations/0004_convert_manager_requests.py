from django.db import migrations


def convert(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    ManagerApplication = apps.get_model("accounts", "ManagerApplication")
    for profile in UserProfile.objects.filter(manager_requested=True, role="employee"):
        ManagerApplication.objects.get_or_create(
            user_id=profile.user_id,
            status="pending",
            defaults={"reason": "Asked to be a manager when signing up."},
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_managerapplication")]
    operations = [migrations.RunPython(convert, migrations.RunPython.noop)]