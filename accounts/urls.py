from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import approval_views, views


urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path("calendar-events/", views.calendar_events, name="calendar_events"),
    path("approvals/", approval_views.pending_managers, name="pending_managers"),
    path("approvals/<int:profile_id>/approve/", approval_views.approve_manager, name="approve_manager"),
    path("approvals/<int:profile_id>/decline/", approval_views.decline_manager, name="decline_manager"),
]