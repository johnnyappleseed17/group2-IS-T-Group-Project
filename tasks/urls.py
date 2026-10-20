from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("mine/", views.my_created_tasks, name="my_created_tasks"),
]
