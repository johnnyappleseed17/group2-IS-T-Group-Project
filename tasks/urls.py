from django.urls import path

from . import category_views, views
from .history_views import task_history
app_name = "tasks"

urlpatterns = [
    path("mine/", views.my_created_tasks, name="my_created_tasks"),
    path("create/", views.task_create, name="task_create"),
    path("<int:task_id>/edit/", views.task_update, name="task_update"),
    path("<int:task_id>/archive/", views.task_archive, name="task_archive"),
    path("<int:task_id>/restore/", views.task_restore, name="task_restore"),
    path("accepted/", views.my_accepted_tasks, name="my_accepted_tasks"),
    path("<int:task_id>/accept/", views.accept_task, name="accept_task"),
    path("<int:task_id>/done/", views.mark_done, name="mark_done"),
    path("categories/", category_views.category_list, name="category_list"),
    path("categories/create/", category_views.category_create, name="category_create"),
    path("categories/<int:category_id>/edit/", category_views.category_update, name="category_update"),
    path("categories/<int:category_id>/delete/", category_views.category_delete, name="category_delete"),
    path('<int:pk>/detail/', views.TaskDetailView.as_view(), name='task_detail'),
    path("history/", task_history, name="task_history"),
]
