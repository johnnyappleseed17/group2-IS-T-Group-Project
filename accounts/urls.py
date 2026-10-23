
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views



urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path("calendar-events/", views.calendar_events, name="calendar_events"),
]