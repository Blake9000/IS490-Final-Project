from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_page, name='login'),
    path('analytics/', views.analytics, name='analytics'),
    path('search-jobs/', views.search_jobs, name='search_jobs'),
    path('saved-jobs/', views.saved_jobs, name='saved_jobs'),
    path('job-alerts/', views.job_alerts, name='job_alerts'),
    path('resume/', views.resume, name='resume'),
    path('skill-gaps/', views.skill_gaps, name='skill_gaps'),
    path('settings/', views.settings, name='settings'),
]
