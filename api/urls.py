from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/login/',    views.auth_login,    name='auth-login'),
    path('auth/logout/', views.auth_logout, name='auth-logout'),
    path('auth/register/', views.auth_register, name='auth-register'),

    # Users
    path('users/',      views.users_list,   name='users-list'),
    path('users/<pk>/', views.users_detail, name='users-detail'),

    # Incidents
    path('incidents/',      views.incidents_list,   name='incidents-list'),
    path('incidents/<pk>/', views.incidents_detail, name='incidents-detail'),

    # Alerts
    path('alerts/',      views.alerts_list,   name='alerts-list'),
    path('alerts/<pk>/', views.alerts_detail, name='alerts-detail'),

    # Evacuation Centers
    path('evacuation-centers/',      views.evac_list,   name='evac-list'),
    path('evacuation-centers/<pk>/', views.evac_detail, name='evac-detail'),

    # Residents (ADD = mobile only, EDIT/VIEW = both)
    path('residents/',      views.residents_list,   name='residents-list'),
    path('residents/<pk>/', views.residents_detail, name='residents-detail'),

    # Resources
    path('resources/',      views.resources_list,   name='resources-list'),
    path('resources/<pk>/', views.resources_detail, name='resources-detail'),

    # Activity Log
    path('activity-log/', views.activity_log_list, name='activity-log'),

    # Dashboard summary
    path('dashboard/', views.dashboard_summary, name='dashboard-summary'),
]
