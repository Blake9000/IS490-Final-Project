import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .models import JobPosting, ResumeJobMatch, Skill, SkillTrendSnapshot
from .services import (
    common_missing_skills,
    get_working_user,
    latest_resume_for_user,
    refresh_trend_snapshots,
    salary_display,
    seed_reference_data,
    top_skill_rows,
)


@require_GET
def api_skills(request):
    """
    GET /api/skills/
    Returns top in-demand skills as JSON based on active job postings.
    Optionally filter by ?limit=N (default 10, max 20).
    No auth required so this can be used as a public read-only endpoint.
    """
    seed_reference_data()
    try:
        limit = min(int(request.GET.get('limit', 10)), 20)
    except ValueError:
        limit = 10

    rows = top_skill_rows(limit)
    total_jobs = JobPosting.objects.filter(is_active=True).count()

    return JsonResponse({
        'total_active_jobs': total_jobs,
        'skill_count': len(rows),
        'skills': [
            {
                'name': row['name'],
                'demand_percentage': row['score'],
                'posting_count': row['count'],
                'slug': row['slug'],
            }
            for row in rows
        ],
    })


@require_GET
def api_job_list(request):
    """
    GET /api/jobs/
    Returns active job postings as JSON.
    Supports ?q=, ?remote_type=, ?experience_level= query params.
    """
    from .services import filter_jobs
    seed_reference_data()

    query = request.GET.get('q', '').strip()
    remote_type = request.GET.get('remote_type', '').strip()
    experience_level = request.GET.get('experience_level', '').strip()
    skill = request.GET.get('skill', '').strip()

    jobs = filter_jobs(query=query, remote_type=remote_type, experience_level=experience_level, skill=skill)[:25]

    return JsonResponse({
        'count': jobs.count() if hasattr(jobs, 'count') else len(jobs),
        'jobs': [
            {
                'id': job.id,
                'title': job.title,
                'company': job.company.name if job.company else None,
                'location': job.location,
                'remote_type': job.remote_type,
                'experience_level': job.experience_level,
                'salary': salary_display(job),
                'posted_at': job.posted_at.isoformat() if job.posted_at else None,
            }
            for job in jobs
        ],
    })


@require_GET
def api_trend_snapshots(request):
    """
    GET /api/trends/
    Returns the latest skill trend snapshots as JSON.
    """
    seed_reference_data()
    refresh_trend_snapshots()

    snapshots = SkillTrendSnapshot.objects.select_related('skill').order_by('-demand_percentage')[:12]

    return JsonResponse({
        'snapshots': [
            {
                'skill': snap.skill.name,
                'category': snap.skill.category,
                'demand_percentage': float(snap.demand_percentage),
                'posting_count': snap.posting_count,
                'average_salary': snap.average_salary,
                'period_start': snap.period_start.isoformat(),
                'period_end': snap.period_end.isoformat(),
            }
            for snap in snapshots
        ]
    })


@login_required(login_url='login')
@require_GET
def export_match_results_csv(request):
    """
    GET /export/matches/
    Downloads the current user's resume-job match results as a CSV file.
    """
    user = get_working_user(request)
    resume = latest_resume_for_user(user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="match_results.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Job Title',
        'Company',
        'Location',
        'Remote Type',
        'Experience Level',
        'Salary',
        'Match Score (%)',
        'Matched Skills',
        'Missing Skills',
        'Summary',
    ])

    matches = ResumeJobMatch.objects.select_related(
        'job_posting', 'job_posting__company', 'resume'
    ).filter(user=user).order_by('-match_score')

    if resume:
        matches = matches.filter(resume=resume)

    for match in matches:
        job = match.job_posting
        writer.writerow([
            job.title,
            job.company.name if job.company else '',
            job.location,
            job.get_remote_type_display(),
            job.get_experience_level_display(),
            salary_display(job),
            match.match_score,
            ', '.join(match.strengths or []),
            ', '.join(match.missing_skills or []),
            match.summary,
        ])

    return response


@login_required(login_url='login')
@require_GET
def export_skill_gaps_csv(request):
    """
    GET /export/skill-gaps/
    Downloads the current user's skill gaps as a CSV file.
    """
    user = get_working_user(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="skill_gaps.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Skill',
        'Skill Category',
        'Priority',
        'Job Title',
        'Company',
        'Match Score (%)',
        'Explanation',
    ])

    from .models import SkillGap
    gaps = SkillGap.objects.select_related(
        'skill', 'match__job_posting', 'match__job_posting__company', 'match__resume'
    ).filter(match__user=user).order_by('priority', 'skill__name')

    for gap in gaps:
        job = gap.match.job_posting
        writer.writerow([
            gap.skill.name,
            gap.skill.get_category_display(),
            gap.get_priority_display(),
            job.title,
            job.company.name if job.company else '',
            gap.match.match_score,
            gap.explanation,
        ])

    return response