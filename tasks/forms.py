from django import forms

from .models import Task


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
