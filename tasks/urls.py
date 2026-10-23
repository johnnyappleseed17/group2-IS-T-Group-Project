from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("mine/", views.my_created_tasks, name="my_created_tasks"),
    path("create/", views.task_create, name="task_create"),
    path("<int:task_id>/edit/", views.task_update, name="task_update"),
    path("<int:task_id>/delete/", views.task_delete, name="task_delete"),
    path("accepted/", views.my_accepted_tasks, name="my_accepted_tasks"),
    path("<int:task_id>/accept/", views.accept_task, name="accept_task")
]
