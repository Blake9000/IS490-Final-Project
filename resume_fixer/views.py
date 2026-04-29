from django.shortcuts import render

skills = [
    {'name': 'Python', 'score': 68, 'slug': 'python'},
    {'name': 'React / TypeScript', 'score': 61, 'slug': 'react'},
    {'name': 'AWS / Cloud', 'score': 54, 'slug': 'aws'},
    {'name': 'SQL / PostgreSQL', 'score': 49, 'slug': 'sql'},
    {'name': 'Docker / Kubernetes', 'score': 42, 'slug': 'docker'},
    {'name': 'Machine Learning', 'score': 38, 'slug': 'machine'},
]

insights = [
    {'title': 'Python', 'text': 'appears in 68% of SE postings, up 18% this month.', 'tone': 'green'},
    {'title': 'Rust', 'text': 'demand surged 47% YoY. Now in top 10 skills.', 'tone': 'yellow'},
    {'title': 'Remote SE roles', 'text': 'pay 12% more than on-site equivalents.', 'tone': 'blue'},
    {'title': 'Java', 'text': 'mention rate down 9% since Q3. React growing to fill gaps.', 'tone': 'red'},
]

metrics = [
    {'label': 'Top Skill Demand', 'value': 'Python', 'change': '+18% this month', 'direction': 'up'},
    {'label': 'Avg. Salary Range', 'value': '$134K', 'change': '+8K vs last mo.', 'direction': 'up'},
    {'label': 'Open Roles', 'value': '24.1K', 'change': '-3% this week', 'direction': 'down'},
    {'label': 'Your Match Score', 'value': '72%', 'change': 'Upload resume to improve', 'direction': 'neutral'},
]

jobs = [
    {'title': 'Software Engineer', 'company': 'Nimbus Labs', 'location': 'Remote', 'salary': '$128K to $156K', 'match': '87%'},
    {'title': 'Backend Developer', 'company': 'DataForge', 'location': 'San Mateo, CA', 'salary': '$118K to $145K', 'match': '81%'},
    {'title': 'Python Engineer', 'company': 'Northstar AI', 'location': 'Hybrid', 'salary': '$135K to $170K', 'match': '78%'},
]

pages = {
    'analytics': {'title': 'Analytics', 'subtitle': 'Resume and job-market signal tracking', 'active': 'analytics'},
    'search_jobs': {'title': 'Search Jobs', 'subtitle': 'Browse matching openings by role, skill, and location', 'active': 'search_jobs'},
    'saved_jobs': {'title': 'Saved Jobs', 'subtitle': 'Review roles marked for later comparison', 'active': 'saved_jobs'},
    'job_alerts': {'title': 'Job Alerts', 'subtitle': 'Manage notifications for new market matches', 'active': 'job_alerts'},
    'resume': {'title': 'Resume', 'subtitle': 'Upload, parse, and compare resume skill coverage', 'active': 'resume'},
    'skill_gaps': {'title': 'Skill Gaps', 'subtitle': 'Prioritize skills that improve match quality', 'active': 'skill_gaps'},
    'settings': {'title': 'Settings', 'subtitle': 'Configure search preferences and profile details', 'active': 'settings'},
}


def login_page(request):
    return render(request, 'resume_fixer/login.html', {'page_key': 'login'})


def dashboard(request):
    return render(request, 'resume_fixer/dashboard.html', {
        'page_key': 'dashboard',
        'skills': skills,
        'insights': insights,
        'metrics': metrics,
    })


def analytics(request):
    return render_simple_page(request, 'analytics')


def search_jobs(request):
    return render_simple_page(request, 'search_jobs')


def saved_jobs(request):
    return render_simple_page(request, 'saved_jobs')


def job_alerts(request):
    return render_simple_page(request, 'job_alerts')


def resume(request):
    return render_simple_page(request, 'resume')


def skill_gaps(request):
    return render_simple_page(request, 'skill_gaps')


def settings(request):
    return render_simple_page(request, 'settings')


def render_simple_page(request, key):
    page = pages[key]
    return render(request, 'resume_fixer/simple_page.html', {
        'page_key': page['active'],
        'page_title': page['title'],
        'page_subtitle': page['subtitle'],
        'skills': skills,
        'insights': insights[:3],
        'jobs': jobs,
    })
