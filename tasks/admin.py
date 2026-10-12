from django.contrib import admin

from .models import Category, Task, TaskAssignment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "color")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "due_date", "employees_needed", "created_by", "is_archived", "completed_at")
    list_filter = ("is_archived", "categories")
    search_fields = ("title", "description")


@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = ("task", "assignee", "claimed_at", "completed_at")