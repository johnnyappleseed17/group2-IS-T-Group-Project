from django import forms
from django.core.validators import RegexValidator

from .models import Category, Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "due_date", "employees_needed", "categories"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "due_date": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}
            ),
            "employees_needed": forms.NumberInput(
                attrs={"min": 1, "class": "form-control"}
            ),
            "categories": forms.SelectMultiple(attrs={"class": "form-select"}),
        }
        help_texts = {
            "employees_needed": "Total number of people needed for this task.",
            "categories": "Optional. Hold Ctrl (Windows) or Command (Mac) to select multiple categories.",
        }

    def clean_employees_needed(self):
        employees_needed = self.cleaned_data["employees_needed"]
        if self.instance.pk:
            assigned_count = self.instance.assignments.count()
            if employees_needed < assigned_count:
                raise forms.ValidationError(
                    "This task already has %(count)s assigned people. The number needed cannot be lower.",
                    params={"count": assigned_count},
                )
        return employees_needed


class CategoryForm(forms.ModelForm):
    color = forms.CharField(
        required=False,
        max_length=7,
        validators=[
            RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Enter a color like #2E7D32, or leave it blank.")
        ],
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "#2E7D32"}),
        help_text="Optional hex color for the calendar.",
    )

    class Meta:
        model = Category
        fields = ["name", "color"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicates = Category.objects.filter(name__iexact=name)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError("A category with this name already exists.")
        return name