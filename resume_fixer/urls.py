from django.urls import path
from . import views
from . import api

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_page, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_account, name='logout'),
    path('analytics/', views.analytics, name='analytics'),
    path('search-jobs/', views.search_jobs, name='search_jobs'),
    path('jobs/refresh/', views.refresh_job_sources, name='refresh_job_sources'),
    path('jobs/<int:pk>/', views.job_detail, name='job_detail'),
    path('jobs/<int:pk>/save/', views.save_job, name='save_job'),
    path('jobs/<int:pk>/unsave/', views.unsave_job, name='unsave_job'),
    path('saved-jobs/', views.saved_jobs, name='saved_jobs'),
    path('job-alerts/', views.job_alerts, name='job_alerts'),
    path('job-alerts/<int:pk>/delete/', views.delete_saved_search, name='delete_saved_search'),
    path('resume/', views.resume, name='resume'),
    path('resume/upload/', views.resume_upload, name='resume_upload'),
    path('resume/<int:pk>/', views.resume_detail, name='resume_detail'),
    path('resume/<int:pk>/file/', views.resume_file, name='resume_file'),
    path('resume/<int:pk>/primary/', views.set_primary_resume, name='set_primary_resume'),
    path('resume/<int:pk>/delete/', views.delete_resume, name='delete_resume'),
    path('skill-gaps/', views.skill_gaps, name='skill_gaps'),
    path('settings/', views.settings, name='settings'),
    path('api/skills/', api.api_skills, name='api_skills'),
    path('api/jobs/', api.api_job_list, name='api_job_list'),
    path('api/trends/', api.api_trend_snapshots, name='api_trend_snapshots'),

    # ── CSV exports (login required) ─────────────────────────────────────
    path('export/matches/', api.export_match_results_csv, name='export_matches_csv'),
    path('export/skill-gaps/', api.export_skill_gaps_csv, name='export_skill_gaps_csv'),
]
