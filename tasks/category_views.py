from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from .forms import CategoryForm
from .models import Category
from .views import _require_approved_manager


@login_required
@require_safe
def category_list(request):
    _require_approved_manager(request.user)
    categories = Category.objects.annotate(task_count=Count("tasks"))
    return render(request, "tasks/category_list.html", {"categories": categories})


@login_required
@require_http_methods(["GET", "POST"])
def category_create(request):
    _require_approved_manager(request.user)
    form = CategoryForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category created.")
        return redirect("tasks:category_list")
    return render(request, "tasks/category_form.html", {"form": form, "category": None})


@login_required
@require_http_methods(["GET", "POST"])
def category_update(request, category_id):
    _require_approved_manager(request.user)
    category = get_object_or_404(Category, pk=category_id)
    form = CategoryForm(request.POST if request.method == "POST" else None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category updated.")
        return redirect("tasks:category_list")
    return render(request, "tasks/category_form.html", {"form": form, "category": category})


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def category_delete(request, category_id):
    _require_approved_manager(request.user)
    category = get_object_or_404(Category, pk=category_id)
    if request.method == "POST":
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted.')
        return redirect("tasks:category_list")
    return render(
        request,
        "tasks/category_confirm_delete.html",
        {"category": category, "task_count": category.tasks.count()},
    )