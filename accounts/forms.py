from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from .models import ManagerApplication, UserProfile

class NotificationEmailForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        help_text="Task deadline reminders are sent to this address.",
    )


class UserEmailPasswordResetForm(PasswordResetForm):
    """Send the reset link to the email address typed on the form."""

    email = forms.EmailField(
        label="Email",
        max_length=254,
        help_text="The reset link is sent to this address.",
    )
class ProfileForm(forms.ModelForm):
    email = forms.EmailField(label="Email", max_length=254)

    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name", "email"]

class ManagerApplicationForm(forms.ModelForm):
    class Meta:
        model = ManagerApplication
        fields = ["reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 5, "class": "form-control"})}
        labels = {"reason": "Why do you want to be a manager?"}

class ReminderSettingsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["email_reminders"]
        labels = {"email_reminders": "Send me deadline reminder emails"}
        widgets = {"email_reminders": forms.CheckboxInput(attrs={"class": "form-check-input"})}