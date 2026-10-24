from django.urls import path

from . import category_views, views

app_name = "tasks"

urlpatterns = [
    path("mine/", views.my_created_tasks, name="my_created_tasks"),
    path("create/", views.task_create, name="task_create"),
    path("<int:task_id>/edit/", views.task_update, name="task_update"),
    path("<int:task_id>/delete/", views.task_delete, name="task_delete"),
    path("accepted/", views.my_accepted_tasks, name="my_accepted_tasks"),
    path("<int:task_id>/accept/", views.accept_task, name="accept_task"),
    path("categories/", category_views.category_list, name="category_list"),
    path("categories/create/", category_views.category_create, name="category_create"),
    path("categories/<int:category_id>/edit/", category_views.category_update, name="category_update"),
    path("categories/<int:category_id>/delete/", category_views.category_delete, name="category_delete"),
]