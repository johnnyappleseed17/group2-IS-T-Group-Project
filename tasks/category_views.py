from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from .forms import CategoryForm
from .models import Category
from .views import _require_approved_manager


def _form_context(form, category):
    others = Category.objects.exclude(pk=category.pk) if category else Category.objects.all()
    return {
        "form": form,
        "category": category,
        "existing_names": list(others.values_list("name", flat=True)),
        "used_colors": [
            {"name": other.name, "color": other.color} for other in others.exclude(color="")
        ],
    }


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
    form = CategoryForm(request.POST if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category created.")
        if "add_another" in request.POST:
            return redirect("tasks:category_create")
        return redirect("tasks:category_list")
    return render(request, "tasks/category_form.html", _form_context(form, None))


@login_required
@require_http_methods(["GET", "POST"])
def category_update(request, category_id):
    _require_approved_manager(request.user)
    category = get_object_or_404(Category, pk=category_id)
    form = CategoryForm(
        request.POST if request.method == "POST" else None,
        instance=category,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category updated.")
        return redirect("tasks:category_list")
    return render(request, "tasks/category_form.html", _form_context(form, category))


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