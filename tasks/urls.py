from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("mine/", views.my_created_tasks, name="my_created_tasks"),
    path("available/", views.available_tasks, name="available_tasks"),
    path("<int:task_id>/claim/", views.claim_task, name="claim_task"),
]