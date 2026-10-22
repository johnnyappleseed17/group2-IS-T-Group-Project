from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("mine/", views.my_created_tasks, name="my_created_tasks"),
    path("accepted/", views.my_accepted_tasks, name="my_accepted_tasks"),
    path("<int:task_id>/accept/", views.accept_task, name="accept_task")
]
