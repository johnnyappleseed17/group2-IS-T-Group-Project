from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField()
    want_manager = forms.BooleanField(
        required=False,
        label="I want to be a manager",
        help_text="You will start as an employee. An existing manager has to approve this before you become a manager.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password1", "password2"]

    def save(self, commit=True):
        # Everyone is an employee at first. If the box was ticked, remember the request.
        user = super().save(commit=commit)
        if commit:
            profile = user.profile
            profile.manager_requested = self.cleaned_data["want_manager"]
            profile.save()
        return user