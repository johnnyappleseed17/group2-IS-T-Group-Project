from django import forms
from django.contrib.auth.forms import PasswordResetForm


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
