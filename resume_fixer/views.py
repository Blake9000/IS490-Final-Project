from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    AccountRegistrationForm,
    JobPostingForm,
    ResumeUploadForm,
    SavedJobSearchForm,
    StyledAuthenticationForm,
    UserProfileForm,
)
from .models import Company, JobPosting, Resume, ResumeJobMatch, SavedJob, SavedJobSearch, SkillTrendSnapshot, UserProfile
from .services import (
    common_missing_skills,
    dashboard_metrics,
    extract_job_skills,
    extract_resume_skills,
    extract_text_from_upload,
    filter_jobs,
    get_working_user,
    ensure_external_job_sources,
    latest_resume_for_user,
    refresh_trend_snapshots,
    refresh_external_job_sources,
    salary_display,
    seed_reference_data,
    top_skill_rows,
    update_matches_for_job,
    update_matches_for_resume,
)


def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = StyledAuthenticationForm(request, data=request.POST or None)
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.get_user())
        return redirect(next_url or 'dashboard')
    return render(request, 'resume_fixer/login.html', {
        'page_key': 'login',
        'form': form,
        'next': next_url,
    })


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = AccountRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        UserProfile.objects.get_or_create(user=user)
        auth_login(request, user)
        messages.success(request, 'Account created.')
        return redirect('dashboard')
    return render(request, 'resume_fixer/register.html', {
        'page_key': 'register',
        'form': form,
    })


@login_required(login_url='login')
@require_POST
def logout_account(request):
    auth_logout(request)
    return redirect('login')


@login_required(login_url='login')
def dashboard(request):
    seed_reference_data()
    ensure_external_job_sources()
    user = get_working_user(request)
    resume = latest_resume_for_user(user)
    top_matches = ResumeJobMatch.objects.select_related('job_posting', 'job_posting__company', 'resume').filter(user=user).order_by('-match_score')[:5]
    jobs = []
    for match in top_matches:
        jobs.append({
            'id': match.job_posting_id,
            'title': match.job_posting.title,
            'company': match.job_posting.company.name if match.job_posting.company else 'Unknown Company',
            'location': match.job_posting.location or 'Location not listed',
            'salary': salary_display(match.job_posting),
            'match': f'{match.match_score}%',
            'source': match.job_posting.source_name or 'Stored',
        })
    if not jobs:
        usajobs_jobs = JobPosting.objects.select_related('company').filter(source_name='USAJOBS', is_active=True)[:5]
        adzuna_jobs = JobPosting.objects.select_related('company').filter(source_name='Adzuna', is_active=True)[:5]
        fallback_jobs = (
            JobPosting.objects
            .select_related('company')
            .filter(is_active=True)
            .exclude(source_name__in=['USAJOBS', 'Adzuna'])[:5]
        )
        for job in list(usajobs_jobs) + list(adzuna_jobs) + list(fallback_jobs):
            if len(jobs) >= 5:
                break
            jobs.append({
                'id': job.id,
                'title': job.title,
                'company': job.company.name if job.company else 'Unknown Company',
                'location': job.location or 'Location not listed',
                'salary': salary_display(job),
                'match': 'Upload resume',
                'source': job.source_name or 'Stored',
            })

    insights = []
    top_skills = top_skill_rows(4)
    for skill in top_skills:
        insights.append({
            'title': skill['name'],
            'text': f'appears in {skill["count"]} stored posting(s), representing {skill["score"]}% of active jobs.',
            'tone': 'green' if skill['score'] >= 50 else 'blue',
        })
    for missing in common_missing_skills(user, 2):
        insights.append({
            'title': missing['name'],
            'text': f'is missing across {missing["count"]} current match result(s).',
            'tone': 'yellow',
        })
    if not insights:
        insights.append({'title': 'No data yet', 'text': 'Upload a resume or add job postings to generate signals.', 'tone': 'blue'})

    return render(request, 'resume_fixer/dashboard.html', {
        'page_key': 'dashboard',
        'skills': top_skill_rows(8),
        'insights': insights[:5],
        'metrics': dashboard_metrics(user),
        'jobs': jobs,
        'resume': resume,
    })


@login_required(login_url='login')
def analytics(request):
    seed_reference_data()
    ensure_external_job_sources()
    refresh_trend_snapshots()
    user = get_working_user(request)
    trend_rows = SkillTrendSnapshot.objects.select_related('skill').order_by('-demand_percentage', 'skill__normalized_name')[:12]
    match_average = ResumeJobMatch.objects.filter(user=user).aggregate(value=Avg('match_score'))['value']
    resume_count = Resume.objects.filter(user=user).count()
    saved_count = SavedJob.objects.filter(user=user).count()
    job_count = JobPosting.objects.filter(is_active=True).count()
    missing_rows = common_missing_skills(user, 10)

    return render(request, 'resume_fixer/analytics.html', {
        'page_key': 'analytics',
        'page_title': 'Analytics',
        'page_subtitle': 'Stored job data, extracted skills, match scores, and market trend snapshots',
        'trend_rows': trend_rows,
        'missing_rows': missing_rows,
        'metrics': [
            {'label': 'Active Jobs', 'value': job_count, 'change': 'Stored postings', 'direction': 'neutral'},
            {'label': 'Uploaded Resumes', 'value': resume_count, 'change': 'Only your account', 'direction': 'neutral'},
            {'label': 'Saved Jobs', 'value': saved_count, 'change': 'Marked for later review', 'direction': 'neutral'},
            {'label': 'Average Match', 'value': f'{match_average:.2f}%' if match_average is not None else 'N/A', 'change': 'Across your generated matches', 'direction': 'up' if match_average else 'neutral'},
        ],
    })


@login_required(login_url='login')
def search_jobs(request):
    seed_reference_data()
    ensure_external_job_sources()
    user = get_working_user(request)
    job_form = JobPostingForm(prefix='job')
    search_form = SavedJobSearchForm(prefix='search')

    if request.method == 'POST' and request.POST.get('form_type') == 'job':
        job_form = JobPostingForm(request.POST, prefix='job')
        if job_form.is_valid():
            company, _ = Company.objects.get_or_create(name=job_form.cleaned_data['company_name'])
            job = job_form.save(commit=False)
            job.company = company
            job.source_name = 'Manual Entry'
            job.save()
            extract_job_skills(job)
            update_matches_for_job(job)
            messages.success(request, 'Job posting saved and matched against existing resumes.')
            return redirect('job_detail', pk=job.pk)

    if request.method == 'POST' and request.POST.get('form_type') == 'search':
        search_form = SavedJobSearchForm(request.POST, prefix='search')
        if search_form.is_valid():
            saved_search = search_form.save(commit=False)
            saved_search.user = user
            filters = {
                'remote_type': request.GET.get('remote_type', ''),
                'experience_level': request.GET.get('experience_level', ''),
                'skill': request.GET.get('skill', ''),
            }
            saved_search.filters = filters
            saved_search.save()
            messages.success(request, 'Search saved.')
            return redirect('job_alerts')

    query = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    remote_type = request.GET.get('remote_type', '').strip()
    experience_level = request.GET.get('experience_level', '').strip()
    skill = request.GET.get('skill', '').strip()
    jobs = filter_jobs(query, location, remote_type, experience_level, skill)
    paginator = Paginator(jobs, 6)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_query = query_params.urlencode()
    saved_ids = set(SavedJob.objects.filter(user=user).values_list('job_posting_id', flat=True))
    matches = {
        item.job_posting_id: item
        for item in ResumeJobMatch.objects.filter(user=user, job_posting__in=page_obj.object_list).select_related('resume')
    }
    job_cards = []
    for job in page_obj.object_list:
        job_cards.append({
            'job': job,
            'saved': job.id in saved_ids,
            'match': matches.get(job.id),
            'salary': salary_display(job),
        })

    return render(request, 'resume_fixer/search_jobs.html', {
        'page_key': 'search_jobs',
        'page_title': 'Search Jobs',
        'page_subtitle': 'Search stored postings, add new postings, and save roles for later comparison',
        'job_cards': job_cards,
        'page_obj': page_obj,
        'paginator': paginator,
        'page_query': page_query,
        'job_form': job_form,
        'search_form': search_form,
        'filters': {
            'q': query,
            'location': location,
            'remote_type': remote_type,
            'experience_level': experience_level,
            'skill': skill,
        },
        'remote_choices': JobPosting.RemoteType.choices,
        'experience_choices': JobPosting.ExperienceLevel.choices,
    })


@login_required(login_url='login')
@require_POST
def refresh_job_sources(request):
    seed_reference_data()
    result = refresh_external_job_sources()
    if result.get('busy'):
        messages.warning(request, 'A job refresh is already running. Wait a moment, then refresh the page.')
        return redirect(request.POST.get('next') or 'dashboard')
    if result.get('database_locked'):
        messages.warning(request, 'The database is busy finishing another write. Wait a moment, then try Refresh Jobs again.')
        return redirect(request.POST.get('next') or 'dashboard')

    usajobs_count = result['usajobs_count']
    adzuna_count = result['adzuna_count']
    total_count = usajobs_count + adzuna_count
    if total_count:
        messages.success(
            request,
            f'Refreshed {total_count} job posting(s): {usajobs_count} from USAJOBS and {adzuna_count} from Adzuna.',
        )
    else:
        messages.warning(request, 'No jobs were imported. Check API credentials, network access, or source availability.')
    return redirect(request.POST.get('next') or 'dashboard')


@login_required(login_url='login')
def job_detail(request, pk):
    seed_reference_data()
    user = get_working_user(request)
    job = get_object_or_404(JobPosting.objects.select_related('company').prefetch_related('job_skills__skill'), pk=pk)
    saved = SavedJob.objects.filter(user=user, job_posting=job).exists()
    matches = ResumeJobMatch.objects.select_related('resume').filter(user=user, job_posting=job).order_by('-match_score')
    return render(request, 'resume_fixer/job_detail.html', {
        'page_key': 'search_jobs',
        'job': job,
        'saved': saved,
        'matches': matches,
        'salary': salary_display(job),
    })


@login_required(login_url='login')
@require_POST
def save_job(request, pk):
    user = get_working_user(request)
    job = get_object_or_404(JobPosting, pk=pk)
    SavedJob.objects.get_or_create(user=user, job_posting=job)
    messages.success(request, 'Job saved.')
    return redirect(request.POST.get('next') or reverse('job_detail', kwargs={'pk': pk}))


@login_required(login_url='login')
@require_POST
def unsave_job(request, pk):
    user = get_working_user(request)
    SavedJob.objects.filter(user=user, job_posting_id=pk).delete()
    messages.success(request, 'Job removed from saved jobs.')
    return redirect(request.POST.get('next') or 'saved_jobs')


@login_required(login_url='login')
def saved_jobs(request):
    seed_reference_data()
    user = get_working_user(request)
    saved = SavedJob.objects.select_related('job_posting', 'job_posting__company').filter(user=user)
    matches = {
        item.job_posting_id: item
        for item in ResumeJobMatch.objects.filter(user=user, job_posting__in=[item.job_posting for item in saved])
    }
    saved_cards = []
    for item in saved:
        saved_cards.append({
            'saved': item,
            'job': item.job_posting,
            'match': matches.get(item.job_posting_id),
            'salary': salary_display(item.job_posting),
        })
    return render(request, 'resume_fixer/saved_jobs.html', {
        'page_key': 'saved_jobs',
        'page_title': 'Saved Jobs',
        'page_subtitle': 'Review roles marked for later comparison',
        'saved_cards': saved_cards,
    })


@login_required(login_url='login')
def job_alerts(request):
    seed_reference_data()
    user = get_working_user(request)
    searches = SavedJobSearch.objects.filter(user=user)
    return render(request, 'resume_fixer/job_alerts.html', {
        'page_key': 'job_alerts',
        'page_title': 'Job Alerts',
        'page_subtitle': 'Saved search criteria and alert preferences',
        'searches': searches,
    })


@login_required(login_url='login')
@require_POST
def delete_saved_search(request, pk):
    user = get_working_user(request)
    get_object_or_404(SavedJobSearch, pk=pk, user=user).delete()
    messages.success(request, 'Saved search deleted.')
    return redirect('job_alerts')


@login_required(login_url='login')
def resume(request):
    return resume_upload(request)


@login_required(login_url='login')
def resume_upload(request):
    seed_reference_data()
    user = get_working_user(request)
    form = ResumeUploadForm()
    if request.method == 'POST':
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            resume_obj = form.save(commit=False)
            resume_obj.user = user
            uploaded_text = extract_text_from_upload(request.FILES.get('file'))
            if uploaded_text and not resume_obj.extracted_text:
                resume_obj.extracted_text = uploaded_text
            if resume_obj.is_primary:
                Resume.objects.filter(user=user, is_primary=True).update(is_primary=False)
            resume_obj.save()
            extract_resume_skills(resume_obj)
            update_matches_for_resume(user, resume_obj)
            messages.success(request, 'Resume uploaded and matched against stored jobs.')
            return redirect('resume_detail', pk=resume_obj.pk)

    resumes = Resume.objects.filter(user=user).prefetch_related('resume_skills__skill')
    return render(request, 'resume_fixer/resume.html', {
        'page_key': 'resume',
        'page_title': 'Resume',
        'page_subtitle': 'Upload a resume file or paste resume text to extract skills and generate match scores',
        'form': form,
        'resumes': resumes,
    })


@login_required(login_url='login')
def resume_detail(request, pk):
    seed_reference_data()
    user = get_working_user(request)
    resume_obj = get_object_or_404(Resume.objects.prefetch_related('resume_skills__skill'), pk=pk, user=user)
    matches = ResumeJobMatch.objects.select_related('job_posting', 'job_posting__company').filter(user=user, resume=resume_obj).order_by('-match_score')
    return render(request, 'resume_fixer/resume_detail.html', {
        'page_key': 'resume',
        'resume_obj': resume_obj,
        'matches': matches,
    })


@login_required(login_url='login')
def resume_file(request, pk):
    user = get_working_user(request)
    resume_obj = get_object_or_404(Resume, pk=pk, user=user)
    if not resume_obj.file:
        raise Http404
    return FileResponse(resume_obj.file.open('rb'), as_attachment=True, filename=resume_obj.file.name.split('/')[-1])


@login_required(login_url='login')
@require_POST
def set_primary_resume(request, pk):
    user = get_working_user(request)
    resume_obj = get_object_or_404(Resume, pk=pk, user=user)
    Resume.objects.filter(user=user, is_primary=True).update(is_primary=False)
    resume_obj.is_primary = True
    resume_obj.save(update_fields=['is_primary', 'updated_at'])
    messages.success(request, 'Primary resume updated.')
    return redirect('resume')


@login_required(login_url='login')
@require_POST
def delete_resume(request, pk):
    user = get_working_user(request)
    resume_obj = get_object_or_404(Resume, pk=pk, user=user)
    resume_obj.delete()
    messages.success(request, 'Resume deleted.')
    return redirect('resume')


@login_required(login_url='login')
def skill_gaps(request):
    seed_reference_data()
    user = get_working_user(request)
    resume_obj = latest_resume_for_user(user)
    matches = ResumeJobMatch.objects.select_related('job_posting', 'job_posting__company').prefetch_related('skill_gaps__skill').filter(user=user)
    if resume_obj:
        matches = matches.filter(resume=resume_obj)
    return render(request, 'resume_fixer/skill_gaps.html', {
        'page_key': 'skill_gaps',
        'page_title': 'Skill Gaps',
        'page_subtitle': 'Missing skills found by comparing extracted resume skills to stored job descriptions',
        'resume_obj': resume_obj,
        'matches': matches.order_by('-match_score'),
        'missing_rows': common_missing_skills(user, 12),
    })


@login_required(login_url='login')
def settings(request):
    user = get_working_user(request)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    form = UserProfileForm(instance=profile)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved.')
            return redirect('settings')
    return render(request, 'resume_fixer/settings.html', {
        'page_key': 'settings',
        'page_title': 'Settings',
        'page_subtitle': 'Profile preferences used for filtering and saved search defaults',
        'form': form,
        'profile': profile,
    })
