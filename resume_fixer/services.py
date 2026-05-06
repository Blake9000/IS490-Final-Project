import re
import json
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from collections import Counter
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from threading import Lock

from django.conf import settings
from django.db import OperationalError
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

# ── Sentence-transformer model (loaded once, reused across requests) ─────────
# We use a module-level singleton so the model is only loaded into memory once
# when the Django process starts, not on every request. Loading takes ~2 seconds
# the first time; after that every encode() call is under 50ms on CPU.

_embedding_model = None


def get_embedding_model():
    """
    Returns the sentence-transformer model, loading it on first call.
    Uses all-MiniLM-L6-v2: 80MB, runs on CPU, 384-dimensional embeddings.
    If the model is unavailable (e.g. no internet on first run), returns None
    and the system falls back to skill-overlap scoring only.
    """
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return _embedding_model
    except Exception:
        return None


def embed_text(text):
    """
    Encodes a string into a 384-dimensional embedding vector.
    Returns a plain Python list so it can be stored in Django's JSONField.
    Returns an empty list if the model is unavailable or the text is empty.
    """
    if not text or not text.strip():
        return []
    model = get_embedding_model()
    if model is None:
        return []
    try:
        vector = model.encode(text.strip(), convert_to_numpy=True)
        return vector.tolist()
    except Exception:
        return []


def cosine_similarity(vec_a, vec_b):
    """
    Computes cosine similarity between two plain Python lists.
    Returns a float between 0.0 and 1.0. Returns 0.0 if either vector is empty.
    We implement this manually so we don't need numpy as a hard dependency in
    views — it's only needed inside the embedding model itself.
    """
    if not vec_a or not vec_b:
        return 0.0
    if len(vec_a) != len(vec_b):
        return 0.0
    try:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = sum(a * a for a in vec_a) ** 0.5
        mag_b = sum(b * b for b in vec_b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
    except Exception:
        return 0.0


# ── Skill ontology ────────────────────────────────────────────────────────────

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


# ── Utilities ─────────────────────────────────────────────────────────────────

_ADZUNA_FETCH_ATTEMPTED = False
_USAJOBS_FETCH_ATTEMPTED = False
_JOB_SOURCE_IMPORT_LOCK = Lock()


@contextmanager
def job_source_import_guard():
    acquired = _JOB_SOURCE_IMPORT_LOCK.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            _JOB_SOURCE_IMPORT_LOCK.release()


def normalize_name(value):
    return re.sub(r'\s+', ' ', value.strip().lower())


def slugify_skill(value):
    value = normalize_name(value)
    value = re.sub(r'[^a-z0-9]+', '-', value)
    return value.strip('-') or 'skill'


def get_working_user(request):
    return request.user


# ── Seeding ───────────────────────────────────────────────────────────────────

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


def parse_adzuna_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone=datetime_timezone.utc)
    return parsed


def strip_html(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', value or '')).strip()


def adzuna_location_text(location):
    area = (location or {}).get('area') or []
    if area:
        return ', '.join(area[1:] or area)
    return (location or {}).get('display_name', '')


def infer_remote_type(job_text, location):
    haystack = normalize_name(f'{job_text} {location}')
    if 'remote' in haystack or 'work from home' in haystack:
        return JobPosting.RemoteType.REMOTE
    if 'hybrid' in haystack:
        return JobPosting.RemoteType.HYBRID
    if location:
        return JobPosting.RemoteType.ON_SITE
    return JobPosting.RemoteType.UNKNOWN


def infer_employment_type(row):
    contract_time = normalize_name(row.get('contract_time') or '')
    contract_type = normalize_name(row.get('contract_type') or '')
    if contract_type == 'contract':
        return JobPosting.EmploymentType.CONTRACT
    if contract_time == 'full_time':
        return JobPosting.EmploymentType.FULL_TIME
    if contract_time == 'part_time':
        return JobPosting.EmploymentType.PART_TIME
    return JobPosting.EmploymentType.UNKNOWN


def infer_experience_level(title, description):
    haystack = normalize_name(f'{title} {description}')
    if re.search(r'\b(intern|internship|junior|entry level|entry-level|graduate)\b', haystack):
        return JobPosting.ExperienceLevel.ENTRY
    if re.search(r'\b(senior|sr\.?|principal|staff)\b', haystack):
        return JobPosting.ExperienceLevel.SENIOR
    if re.search(r'\b(lead|manager|director)\b', haystack):
        return JobPosting.ExperienceLevel.LEAD
    if re.search(r'\b(mid|mid-level|mid level)\b', haystack):
        return JobPosting.ExperienceLevel.MID
    return JobPosting.ExperienceLevel.UNKNOWN


def clean_salary(value):
    if value in (None, ''):
        return None
    try:
        return max(0, int(Decimal(str(value))))
    except Exception:
        return None


def fetch_adzuna_jobs(what=None, where=None, page=1, results_per_page=None):
    if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
        return []

    params = {
        'app_id': settings.ADZUNA_APP_ID,
        'app_key': settings.ADZUNA_APP_KEY,
        'results_per_page': results_per_page or settings.ADZUNA_RESULTS_PER_PAGE,
        'content-type': 'application/json',
    }
    if what:
        params['what'] = what
    if where:
        params['where'] = where

    country = settings.ADZUNA_COUNTRY.lower()
    url = f'https://api.adzuna.com/v1/api/jobs/{country}/search/{page}?{urllib.parse.urlencode(params)}'
    request = urllib.request.Request(url, headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = response.read().decode('utf-8')
    except (urllib.error.URLError, TimeoutError, ValueError):
        return []

    try:
        data = json.loads(payload)
    except ValueError:
        return []
    return data.get('results') or []


def import_adzuna_jobs(what=None, where=None, limit=None):
    rows = fetch_adzuna_jobs(
        what=what or settings.ADZUNA_DEFAULT_QUERY,
        where=where if where is not None else settings.ADZUNA_DEFAULT_LOCATION,
        results_per_page=limit or settings.ADZUNA_RESULTS_PER_PAGE,
    )
    imported = []
    for row in rows:
        external_id = str(row.get('id') or '').strip()
        title = (row.get('title') or '').strip()
        if not external_id or not title:
            continue

        company_name = ((row.get('company') or {}).get('display_name') or 'Unknown Company').strip()
        company, _ = Company.objects.get_or_create(name=company_name)
        description = strip_html(row.get('description'))
        location = adzuna_location_text(row.get('location'))
        job_text = f'{title} {description}'
        job, _ = JobPosting.objects.update_or_create(
            source_name='Adzuna',
            external_id=external_id,
            defaults={
                'company': company,
                'title': title,
                'location': location,
                'remote_type': infer_remote_type(job_text, location),
                'employment_type': infer_employment_type(row),
                'experience_level': infer_experience_level(title, description),
                'salary_min': clean_salary(row.get('salary_min')),
                'salary_max': clean_salary(row.get('salary_max')),
                'salary_currency': 'USD',
                'source_url': row.get('redirect_url') or '',
                'description': description or title,
                'posted_at': parse_adzuna_datetime(row.get('created')),
                'scraped_at': timezone.now(),
                'raw_data': row,
                'is_active': True,
            },
        )
        extract_job_skills(job)
        update_matches_for_job(job)
        imported.append(job)
    if imported:
        refresh_trend_snapshots()
    return imported


def ensure_adzuna_jobs():
    global _ADZUNA_FETCH_ATTEMPTED
    if JobPosting.objects.filter(source_name='Adzuna', is_active=True).exists():
        return 0
    if _ADZUNA_FETCH_ATTEMPTED:
        return 0
    _ADZUNA_FETCH_ATTEMPTED = True
    with job_source_import_guard() as can_import:
        if not can_import:
            return 0
        return len(import_adzuna_jobs())


def usajobs_text(value):
    if isinstance(value, list):
        return '\n'.join(usajobs_text(item) for item in value if item)
    if isinstance(value, dict):
        return '\n'.join(usajobs_text(item) for item in value.values() if item)
    return strip_html(str(value or ''))


def usajobs_descriptor_text(descriptor):
    user_area = descriptor.get('UserArea') or {}
    details = user_area.get('Details') or {}
    parts = [
        descriptor.get('PositionTitle'),
        descriptor.get('OrganizationName'),
        descriptor.get('QualificationSummary'),
        details.get('JobSummary'),
        details.get('Duties'),
        details.get('MajorDuties'),
        details.get('Qualifications'),
        details.get('Requirements'),
        details.get('Evaluations'),
        details.get('Education'),
        details.get('HowToApply'),
    ]
    return '\n\n'.join(part for part in (usajobs_text(item) for item in parts) if part)


def usajobs_location_text(descriptor):
    display = descriptor.get('PositionLocationDisplay')
    if display:
        return display
    locations = descriptor.get('PositionLocation') or []
    names = []
    for location in locations:
        name = location.get('LocationName') if isinstance(location, dict) else ''
        if name:
            names.append(name)
    return ', '.join(names)


def usajobs_salary_range(descriptor):
    remuneration = descriptor.get('PositionRemuneration') or []
    if not remuneration:
        return None, None
    row = remuneration[0] or {}
    return clean_salary(row.get('MinimumRange')), clean_salary(row.get('MaximumRange'))


def usajobs_employment_type(descriptor):
    schedules = descriptor.get('PositionSchedule') or []
    schedule_name = ''
    if schedules and isinstance(schedules[0], dict):
        schedule_name = schedules[0].get('Name') or ''
    haystack = normalize_name(schedule_name)
    if 'part' in haystack:
        return JobPosting.EmploymentType.PART_TIME
    if 'full' in haystack:
        return JobPosting.EmploymentType.FULL_TIME
    if 'temporary' in haystack:
        return JobPosting.EmploymentType.TEMPORARY
    return JobPosting.EmploymentType.UNKNOWN


def fetch_usajobs_jobs(keyword=None, location=None, page=1, results_per_page=None):
    if not settings.USAJOBS_API_KEY:
        return []

    params = {
        'Keyword': keyword or settings.USAJOBS_DEFAULT_KEYWORD,
        'ResultsPerPage': results_per_page or settings.USAJOBS_RESULTS_PER_PAGE,
        'Page': page,
        'Fields': 'Full',
        'WhoMayApply': 'public',
    }
    if location:
        params['LocationName'] = location

    url = f'https://data.usajobs.gov/api/Search?{urllib.parse.urlencode(params)}'
    request = urllib.request.Request(
        url,
        headers={
            'Host': 'data.usajobs.gov',
            'User-Agent': settings.USAJOBS_USER_AGENT,
            'Authorization-Key': settings.USAJOBS_API_KEY,
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = response.read().decode('utf-8')
    except (urllib.error.URLError, TimeoutError, ValueError):
        return []

    try:
        data = json.loads(payload)
    except ValueError:
        return []
    return (data.get('SearchResult') or {}).get('SearchResultItems') or []


def import_usajobs_jobs(keyword=None, location=None, limit=None):
    rows = fetch_usajobs_jobs(
        keyword=keyword or settings.USAJOBS_DEFAULT_KEYWORD,
        location=location if location is not None else settings.USAJOBS_DEFAULT_LOCATION,
        results_per_page=limit or settings.USAJOBS_RESULTS_PER_PAGE,
    )
    imported = []
    for row in rows:
        descriptor = row.get('MatchedObjectDescriptor') or {}
        external_id = str(descriptor.get('PositionID') or '').strip()
        title = (descriptor.get('PositionTitle') or '').strip()
        if not external_id or not title:
            continue

        company_name = (descriptor.get('OrganizationName') or 'U.S. Federal Government').strip()
        company, _ = Company.objects.get_or_create(name=company_name)
        description = usajobs_descriptor_text(descriptor)
        location_text = usajobs_location_text(descriptor)
        salary_min, salary_max = usajobs_salary_range(descriptor)
        source_url = descriptor.get('PositionURI') or ''
        apply_urls = descriptor.get('ApplyURI') or []
        if not source_url and apply_urls:
            source_url = apply_urls[0]

        job, _ = JobPosting.objects.update_or_create(
            source_name='USAJOBS',
            external_id=external_id,
            defaults={
                'company': company,
                'title': title,
                'location': location_text,
                'remote_type': infer_remote_type(description, location_text),
                'employment_type': usajobs_employment_type(descriptor),
                'experience_level': infer_experience_level(title, description),
                'salary_min': salary_min,
                'salary_max': salary_max,
                'salary_currency': 'USD',
                'source_url': source_url,
                'description': description or title,
                'posted_at': parse_adzuna_datetime(descriptor.get('PublicationStartDate')),
                'scraped_at': timezone.now(),
                'raw_data': row,
                'is_active': True,
            },
        )
        extract_job_skills(job)
        update_matches_for_job(job)
        imported.append(job)
    if imported:
        refresh_trend_snapshots()
    return imported


def ensure_usajobs_jobs():
    global _USAJOBS_FETCH_ATTEMPTED
    if JobPosting.objects.filter(source_name='USAJOBS', is_active=True).exists():
        return 0
    if _USAJOBS_FETCH_ATTEMPTED:
        return 0
    _USAJOBS_FETCH_ATTEMPTED = True
    with job_source_import_guard() as can_import:
        if not can_import:
            return 0
        return len(import_usajobs_jobs())


def ensure_external_job_sources():
    global _USAJOBS_FETCH_ATTEMPTED, _ADZUNA_FETCH_ATTEMPTED
    needs_usajobs = not JobPosting.objects.filter(source_name='USAJOBS', is_active=True).exists()
    needs_adzuna = not JobPosting.objects.filter(source_name='Adzuna', is_active=True).exists()
    if not needs_usajobs and not needs_adzuna:
        return {'usajobs_count': 0, 'adzuna_count': 0}

    with job_source_import_guard() as can_import:
        if not can_import:
            return {'busy': True, 'usajobs_count': 0, 'adzuna_count': 0}

        usajobs_count = 0
        adzuna_count = 0
        if needs_usajobs and not _USAJOBS_FETCH_ATTEMPTED:
            _USAJOBS_FETCH_ATTEMPTED = True
            usajobs_count = len(import_usajobs_jobs())
        if needs_adzuna and not _ADZUNA_FETCH_ATTEMPTED:
            _ADZUNA_FETCH_ATTEMPTED = True
            adzuna_count = len(import_adzuna_jobs())
    return {'busy': False, 'usajobs_count': usajobs_count, 'adzuna_count': adzuna_count}


def refresh_external_job_sources():
    with job_source_import_guard() as can_import:
        if not can_import:
            return {'busy': True, 'usajobs_count': 0, 'adzuna_count': 0}
        try:
            usajobs_count = len(import_usajobs_jobs())
            adzuna_count = len(import_adzuna_jobs())
        except OperationalError:
            return {'database_locked': True, 'usajobs_count': 0, 'adzuna_count': 0}
    return {
        'busy': False,
        'database_locked': False,
        'usajobs_count': usajobs_count,
        'adzuna_count': adzuna_count,
    }


# ── Text extraction ───────────────────────────────────────────────────────────

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


# ── Skill extraction ──────────────────────────────────────────────────────────

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
    """
    Extracts skills from a resume using the ontology pipeline, then generates
    and stores a sentence-transformer embedding of the full resume text.
    The embedding is stored in resume.parsed_data so it persists without a
    schema change.
    """
    ResumeSkill.objects.filter(resume=resume).delete()
    extracted = extract_skills_from_text(resume.extracted_text)
    for skill, aliases in extracted:
        ResumeSkill.objects.create(
            resume=resume,
            skill=skill,
            confidence=Decimal('100.00'),
            evidence=', '.join(sorted(set(aliases))),
        )

    # Generate and store the semantic embedding for this resume.
    # We store it in parsed_data under the key 'embedding' so we don't
    # need a migration. The embedding is a 384-dimensional float list.
    embedding = embed_text(resume.extracted_text)
    if embedding:
        resume.parsed_data = resume.parsed_data or {}
        resume.parsed_data['embedding'] = embedding
        resume.save(update_fields=['parsed_data', 'updated_at'])

    return extracted


def extract_job_skills(job):
    """
    Extracts skills from a job posting and stores a sentence-transformer
    embedding of the title plus description in the job's embedding JSONField.
    """
    JobSkill.objects.filter(job_posting=job).delete()
    full_text = f'{job.title}\n{job.description}'
    extracted = extract_skills_from_text(full_text)
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

    # Generate and store the semantic embedding for this job posting.
    # The JobPosting model already has an embedding JSONField for exactly this.
    embedding = embed_text(full_text)
    if embedding:
        job.embedding = embedding
        job.save(update_fields=['embedding', 'updated_at'])

    return extracted


# ── Match scoring ─────────────────────────────────────────────────────────────

# Blending weights for the final score.
# 70% comes from the weighted skill overlap (explicit, interpretable).
# 30% comes from semantic similarity (catches synonyms and paraphrasing).
# We weight skill overlap higher because it is more directly actionable:
# the user can see exactly which skills to add. The semantic score acts as
# a boost for resumes that describe skills in different words.
SKILL_WEIGHT = 0.70
SEMANTIC_WEIGHT = 0.30


def calculate_match(resume, job):
    """
    Computes a blended match score between a resume and a job posting.

    The score has two components:

    1. Weighted skill overlap (70% of final score):
       Each job skill gets a weight based on importance (required=1.5,
       preferred=1.2, mentioned=1.0). The overlap score is the sum of
       weights for matched skills divided by total weight, times 100.

    2. Semantic similarity (30% of final score):
       Cosine similarity between the sentence-transformer embedding of
       the full resume text and the full job description text, scaled to
       0-100. This catches cases where the resume uses different words
       to describe the same skills, like 'built REST services' matching
       'API development experience required'.

    If no embedding is available for either document (e.g. model not
    loaded), the full weight falls back to skill overlap alone.
    """
    resume_skill_ids = set(resume.resume_skills.values_list('skill_id', flat=True))
    job_skills = list(job.job_skills.select_related('skill'))

    # -- Skill overlap score --
    if not job_skills:
        skill_score = Decimal('0.00')
        strengths = []
        missing = []
    else:
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

        skill_score = (
            Decimal('0.00') if total_weight == 0
            else (matched_weight / total_weight * Decimal('100')).quantize(Decimal('0.01'))
        )

    # -- Semantic similarity score --
    resume_embedding = (resume.parsed_data or {}).get('embedding', [])
    job_embedding = job.embedding or []
    raw_similarity = cosine_similarity(resume_embedding, job_embedding)
    semantic_score = Decimal(str(round(raw_similarity * 100, 2)))

    # -- Blended final score --
    # If we have a valid semantic score (model loaded, both docs embedded),
    # blend at 70/30. Otherwise fall back to skill overlap only.
    if resume_embedding and job_embedding:
        blended = (
            Decimal(str(SKILL_WEIGHT)) * skill_score +
            Decimal(str(SEMANTIC_WEIGHT)) * semantic_score
        ).quantize(Decimal('0.01'))
    else:
        blended = skill_score

    return blended, sorted(strengths), sorted(missing)


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
            'recommendations': (
                ['Add evidence for missing high-demand skills before applying.']
                if missing else
                ['Resume covers the extracted job skills.']
            ),
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


# ── Remaining helpers (unchanged) ────────────────────────────────────────────

def latest_resume_for_user(user):
    return Resume.objects.filter(user=user).order_by('-is_primary', '-updated_at').first()


def filter_jobs(query='', location='', remote_type='', experience_level='', skill=''):
    qs = (
        JobPosting.objects
        .select_related('company')
        .prefetch_related('job_skills__skill')
        .filter(is_active=True)
    )
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
    counts = (
        JobSkill.objects
        .filter(job_posting__is_active=True)
        .values('skill__id', 'skill__name', 'skill__normalized_name')
        .annotate(posting_count=Count('job_posting', distinct=True))
        .order_by('-posting_count', 'skill__normalized_name')[:limit]
    )
    rows = []
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
        {'label': 'Best Match Score', 'value': match_text, 'change': 'Semantic + skill overlap blend', 'direction': 'up' if match else 'neutral'},
    ]


def refresh_trend_snapshots():
    today = timezone.localdate()
    start = today - timedelta(days=30)
    total_jobs = JobPosting.objects.filter(is_active=True).count()
    rows = top_skill_rows(10)
    for row in rows:
        skill = Skill.objects.get(pk=row['id'])
        jobs = (
            JobPosting.objects
            .filter(job_skills__skill=skill, is_active=True, salary_min__isnull=False, salary_max__isnull=False)
            .distinct()
        )
        salaries = [((job.salary_min or 0) + (job.salary_max or 0)) // 2 for job in jobs]
        average_salary = round(sum(salaries) / len(salaries)) if salaries else None
        demand_percentage = (
            Decimal('0.00') if total_jobs == 0
            else Decimal(str(row['count'] / total_jobs * 100)).quantize(Decimal('0.01'))
        )
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
