import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import (
    Company,
    JobPosting,
    JobSkill,
    Resume,
    ResumeJobMatch,
    ResumeSkill,
    Skill,
    SkillGap,
    SkillTrendSnapshot,
)


SKILL_DEFINITIONS = [
    ('Python', Skill.Category.LANGUAGE, ['python', 'django', 'flask', 'pandas', 'numpy']),
    ('JavaScript', Skill.Category.LANGUAGE, ['javascript', 'js', 'node.js', 'nodejs']),
    ('TypeScript', Skill.Category.LANGUAGE, ['typescript', 'ts']),
    ('React', Skill.Category.FRAMEWORK, ['react', 'react.js', 'reactjs']),
    ('Django', Skill.Category.FRAMEWORK, ['django']),
    ('Flask', Skill.Category.FRAMEWORK, ['flask']),
    ('SQL', Skill.Category.DATABASE, ['sql', 'postgresql', 'postgres', 'mysql', 'sqlite', 'database']),
    ('MongoDB', Skill.Category.DATABASE, ['mongodb', 'mongo']),
    ('AWS', Skill.Category.CLOUD, ['aws', 'amazon web services', 'ec2', 's3', 'lambda']),
    ('Azure', Skill.Category.CLOUD, ['azure', 'microsoft azure']),
    ('Docker', Skill.Category.TOOL, ['docker', 'container', 'containers']),
    ('Kubernetes', Skill.Category.TOOL, ['kubernetes', 'k8s']),
    ('Git', Skill.Category.TOOL, ['git', 'github', 'gitlab']),
    ('Linux', Skill.Category.TOOL, ['linux', 'ubuntu', 'bash', 'shell scripting']),
    ('REST APIs', Skill.Category.FRAMEWORK, ['rest', 'rest api', 'restful', 'api development']),
    ('Machine Learning', Skill.Category.OTHER, ['machine learning', 'ml', 'scikit-learn', 'tensorflow', 'pytorch']),
    ('Data Analysis', Skill.Category.OTHER, ['data analysis', 'analytics', 'data visualization', 'tableau', 'power bi']),
    ('Cybersecurity', Skill.Category.OTHER, ['cybersecurity', 'security', 'siem', 'incident response']),
    ('Communication', Skill.Category.SOFT_SKILL, ['communication', 'communicate', 'stakeholder']),
    ('Project Management', Skill.Category.SOFT_SKILL, ['project management', 'agile', 'scrum', 'kanban']),
]


SAMPLE_JOBS = [
    {
        'company': 'Nimbus Labs',
        'title': 'Software Engineer',
        'location': 'Remote',
        'remote_type': JobPosting.RemoteType.REMOTE,
        'employment_type': JobPosting.EmploymentType.FULL_TIME,
        'experience_level': JobPosting.ExperienceLevel.ENTRY,
        'salary_min': 92000,
        'salary_max': 128000,
        'description': 'Build web applications with Python, Django, SQL, REST APIs, Git, and Docker. Communication with product stakeholders is important.',
        'source_name': 'Seed Data',
        'external_id': 'seed-nimbus-software-engineer',
    },
    {
        'company': 'DataForge',
        'title': 'Backend Developer',
        'location': 'San Mateo, CA',
        'remote_type': JobPosting.RemoteType.HYBRID,
        'employment_type': JobPosting.EmploymentType.FULL_TIME,
        'experience_level': JobPosting.ExperienceLevel.MID,
        'salary_min': 112000,
        'salary_max': 148000,
        'description': 'Backend role focused on Python, Flask, PostgreSQL, REST APIs, Docker, Linux, and AWS services.',
        'source_name': 'Seed Data',
        'external_id': 'seed-dataforge-backend-developer',
    },
    {
        'company': 'Northstar Analytics',
        'title': 'Data Analyst',
        'location': 'Chicago, IL',
        'remote_type': JobPosting.RemoteType.HYBRID,
        'employment_type': JobPosting.EmploymentType.FULL_TIME,
        'experience_level': JobPosting.ExperienceLevel.ENTRY,
        'salary_min': 78000,
        'salary_max': 102000,
        'description': 'Analyze product and market data using SQL, Python, pandas, data visualization, communication, and project management skills.',
        'source_name': 'Seed Data',
        'external_id': 'seed-northstar-data-analyst',
    },
    {
        'company': 'SecurePath',
        'title': 'Security Systems Administrator',
        'location': 'Champaign, IL',
        'remote_type': JobPosting.RemoteType.ON_SITE,
        'employment_type': JobPosting.EmploymentType.FULL_TIME,
        'experience_level': JobPosting.ExperienceLevel.MID,
        'salary_min': 85000,
        'salary_max': 115000,
        'description': 'Maintain Linux servers, cybersecurity controls, Git-based configuration changes, SQL-backed systems, and stakeholder communication.',
        'source_name': 'Seed Data',
        'external_id': 'seed-securepath-security-admin',
    },
]


def normalize_name(value):
    return re.sub(r'\s+', ' ', value.strip().lower())


def slugify_skill(value):
    value = normalize_name(value)
    value = re.sub(r'[^a-z0-9]+', '-', value)
    return value.strip('-') or 'skill'


def get_working_user(request):
    return request.user


def seed_reference_data():
    for name, category, aliases in SKILL_DEFINITIONS:
        Skill.objects.get_or_create(
            normalized_name=normalize_name(name),
            defaults={'name': name, 'category': category},
        )

    if JobPosting.objects.exists():
        return

    for row in SAMPLE_JOBS:
        company, _ = Company.objects.get_or_create(name=row['company'])
        job, _ = JobPosting.objects.get_or_create(
            source_name=row['source_name'],
            external_id=row['external_id'],
            defaults={
                'company': company,
                'title': row['title'],
                'location': row['location'],
                'remote_type': row['remote_type'],
                'employment_type': row['employment_type'],
                'experience_level': row['experience_level'],
                'salary_min': row['salary_min'],
                'salary_max': row['salary_max'],
                'description': row['description'],
                'posted_at': timezone.now(),
                'scraped_at': timezone.now(),
                'is_active': True,
            },
        )
        extract_job_skills(job)

    refresh_trend_snapshots()


def extract_text_from_upload(uploaded_file):
    if not uploaded_file:
        return ''
    name = uploaded_file.name.lower()
    if not name.endswith(('.txt', '.md', '.csv')):
        return ''
    position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read()
        if isinstance(raw, str):
            return raw
        return raw.decode('utf-8', errors='ignore')
    finally:
        uploaded_file.seek(position)


def extract_skills_from_text(text):
    seed_reference_data()
    found = []
    haystack = normalize_name(text or '')
    if not haystack:
        return found

    for name, category, aliases in SKILL_DEFINITIONS:
        matched_aliases = []
        for alias in aliases:
            pattern = r'(?<![a-z0-9])' + re.escape(alias.lower()) + r'(?![a-z0-9])'
            if re.search(pattern, haystack):
                matched_aliases.append(alias)
        if matched_aliases:
            skill, _ = Skill.objects.get_or_create(
                normalized_name=normalize_name(name),
                defaults={'name': name, 'category': category},
            )
            found.append((skill, matched_aliases))
    return found


def extract_resume_skills(resume):
    ResumeSkill.objects.filter(resume=resume).delete()
    extracted = extract_skills_from_text(resume.extracted_text)
    for skill, aliases in extracted:
        ResumeSkill.objects.create(
            resume=resume,
            skill=skill,
            confidence=Decimal('100.00'),
            evidence=', '.join(sorted(set(aliases))),
        )
    return extracted


def extract_job_skills(job):
    JobSkill.objects.filter(job_posting=job).delete()
    extracted = extract_skills_from_text(f'{job.title}\n{job.description}')
    required_words = normalize_name(job.description)
    for skill, aliases in extracted:
        importance = JobSkill.Importance.MENTIONED
        for alias in aliases:
            alias_pattern = re.escape(alias.lower())
            if re.search(r'(required|must have|must know|required skills?).{0,90}' + alias_pattern, required_words):
                importance = JobSkill.Importance.REQUIRED
                break
            if re.search(r'(preferred|nice to have|bonus).{0,90}' + alias_pattern, required_words):
                importance = JobSkill.Importance.PREFERRED
        JobSkill.objects.create(
            job_posting=job,
            skill=skill,
            importance=importance,
            confidence=Decimal('100.00'),
            evidence=', '.join(sorted(set(aliases))),
        )
    return extracted


def calculate_match(resume, job):
    resume_skill_ids = set(resume.resume_skills.values_list('skill_id', flat=True))
    job_skills = list(job.job_skills.select_related('skill'))
    if not job_skills:
        return Decimal('0.00'), [], [skill.name for skill in Skill.objects.none()]

    total_weight = Decimal('0.00')
    matched_weight = Decimal('0.00')
    strengths = []
    missing = []

    for job_skill in job_skills:
        if job_skill.importance == JobSkill.Importance.REQUIRED:
            weight = Decimal('1.50')
        elif job_skill.importance == JobSkill.Importance.PREFERRED:
            weight = Decimal('1.20')
        else:
            weight = Decimal('1.00')
        total_weight += weight
        if job_skill.skill_id in resume_skill_ids:
            matched_weight += weight
            strengths.append(job_skill.skill.name)
        else:
            missing.append(job_skill.skill.name)

    score = Decimal('0.00') if total_weight == 0 else (matched_weight / total_weight * Decimal('100')).quantize(Decimal('0.01'))
    return score, sorted(strengths), sorted(missing)


def update_match_for_resume_and_job(user, resume, job):
    score, strengths, missing = calculate_match(resume, job)
    summary = f'{len(strengths)} matching skill(s), {len(missing)} missing skill(s).'
    match, _ = ResumeJobMatch.objects.update_or_create(
        resume=resume,
        job_posting=job,
        defaults={
            'user': user,
            'match_score': score,
            'summary': summary,
            'strengths': strengths,
            'missing_skills': missing,
            'recommendations': ['Add evidence for missing high-demand skills before applying.'] if missing else ['Resume covers the extracted job skills.'],
        },
    )
    SkillGap.objects.filter(match=match).exclude(skill__name__in=missing).delete()
    for skill_name in missing:
        skill = Skill.objects.filter(name=skill_name).first()
        if skill:
            SkillGap.objects.update_or_create(
                match=match,
                skill=skill,
                defaults={
                    'priority': SkillGap.Priority.HIGH if score < 60 else SkillGap.Priority.MEDIUM,
                    'explanation': f'{skill.name} appears in the job posting but was not found in this resume.',
                },
            )
    return match


def update_matches_for_resume(user, resume):
    matches = []
    for job in JobPosting.objects.filter(is_active=True).prefetch_related('job_skills'):
        matches.append(update_match_for_resume_and_job(user, resume, job))
    return matches


def update_matches_for_job(job):
    for resume in Resume.objects.all():
        update_match_for_resume_and_job(resume.user, resume, job)


def latest_resume_for_user(user):
    return Resume.objects.filter(user=user).order_by('-is_primary', '-updated_at').first()


def filter_jobs(query='', location='', remote_type='', experience_level='', skill=''):
    qs = JobPosting.objects.select_related('company').prefetch_related('job_skills__skill').filter(is_active=True)
    if query:
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(company__name__icontains=query) |
            Q(job_skills__skill__name__icontains=query)
        )
    if location:
        qs = qs.filter(location__icontains=location)
    if remote_type:
        qs = qs.filter(remote_type=remote_type)
    if experience_level:
        qs = qs.filter(experience_level=experience_level)
    if skill:
        qs = qs.filter(job_skills__skill__name__icontains=skill)
    return qs.distinct()


def top_skill_rows(limit=8):
    total_jobs = JobPosting.objects.filter(is_active=True).count()
    rows = []
    counts = (
        JobSkill.objects
        .filter(job_posting__is_active=True)
        .values('skill__id', 'skill__name', 'skill__normalized_name')
        .annotate(posting_count=Count('job_posting', distinct=True))
        .order_by('-posting_count', 'skill__normalized_name')[:limit]
    )
    for item in counts:
        count = item['posting_count']
        percent = 0 if total_jobs == 0 else round(count / total_jobs * 100)
        rows.append({
            'id': item['skill__id'],
            'name': item['skill__name'],
            'score': percent,
            'slug': slugify_skill(item['skill__name']),
            'count': count,
        })
    return rows


def dashboard_metrics(user):
    resume = latest_resume_for_user(user)
    total_jobs = JobPosting.objects.filter(is_active=True).count()
    saved_count = user.saved_jobs.count()
    top_skill = top_skill_rows(1)
    top_skill_name = top_skill[0]['name'] if top_skill else 'None'
    salaries = []
    for job in JobPosting.objects.filter(is_active=True, salary_min__isnull=False, salary_max__isnull=False):
        salaries.append((job.salary_min + job.salary_max) // 2)
    avg_salary_text = 'N/A' if not salaries else f'${round(sum(salaries) / len(salaries) / 1000)}K'
    match = None
    if resume:
        match = ResumeJobMatch.objects.filter(resume=resume).order_by('-match_score').first()
    match_text = f'{match.match_score}%' if match else 'Upload'
    return [
        {'label': 'Top Skill Demand', 'value': top_skill_name, 'change': f'{total_jobs} active posting(s)', 'direction': 'up'},
        {'label': 'Avg. Salary Range', 'value': avg_salary_text, 'change': 'Based on stored postings', 'direction': 'neutral'},
        {'label': 'Open Roles', 'value': total_jobs, 'change': f'{saved_count} saved by you', 'direction': 'neutral'},
        {'label': 'Best Match Score', 'value': match_text, 'change': 'Deterministic skill overlap', 'direction': 'up' if match else 'neutral'},
    ]


def refresh_trend_snapshots():
    today = timezone.localdate()
    start = today - timedelta(days=30)
    total_jobs = JobPosting.objects.filter(is_active=True).count()
    rows = top_skill_rows(10)
    for row in rows:
        skill = Skill.objects.get(pk=row['id'])
        jobs = JobPosting.objects.filter(job_skills__skill=skill, is_active=True, salary_min__isnull=False, salary_max__isnull=False).distinct()
        salaries = [((job.salary_min or 0) + (job.salary_max or 0)) // 2 for job in jobs]
        average_salary = round(sum(salaries) / len(salaries)) if salaries else None
        demand_percentage = Decimal('0.00') if total_jobs == 0 else Decimal(str(row['count'] / total_jobs * 100)).quantize(Decimal('0.01'))
        SkillTrendSnapshot.objects.update_or_create(
            skill=skill,
            role_title='',
            location='',
            period_start=start,
            period_end=today,
            defaults={
                'posting_count': row['count'],
                'demand_percentage': demand_percentage,
                'average_salary': average_salary,
            },
        )


def common_missing_skills(user, limit=8):
    names = []
    for match in ResumeJobMatch.objects.filter(user=user):
        names.extend(match.missing_skills or [])
    counts = Counter(names)
    return [{'name': name, 'count': count} for name, count in counts.most_common(limit)]


def salary_display(job):
    if job.salary_min and job.salary_max:
        return f'${job.salary_min:,} to ${job.salary_max:,}'
    if job.salary_min:
        return f'${job.salary_min:,}+'
    if job.salary_max:
        return f'Up to ${job.salary_max:,}'
    return 'Salary not listed'
