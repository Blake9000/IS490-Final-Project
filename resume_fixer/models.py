from django.conf import settings
from django.db import models


def resume_upload_path(instance, filename):
    user_id = instance.user_id or 'unassigned'
    return f'resumes/user_{user_id}/{filename}'


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserProfile(TimeStampedModel):
    class UserType(models.TextChoices):
        JOB_SEEKER = 'job_seeker', 'Job Seeker'
        RECRUITER = 'recruiter', 'Recruiter'
        HIRING_TEAM = 'hiring_team', 'Hiring Team'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resume_profile')
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.JOB_SEEKER)
    target_role = models.CharField(max_length=150, blank=True)
    target_location = models.CharField(max_length=150, blank=True)
    remote_preference = models.BooleanField(default=False)
    minimum_salary = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} profile'


class Skill(TimeStampedModel):
    class Category(models.TextChoices):
        LANGUAGE = 'language', 'Programming Language'
        FRAMEWORK = 'framework', 'Framework'
        DATABASE = 'database', 'Database'
        CLOUD = 'cloud', 'Cloud'
        TOOL = 'tool', 'Tool'
        SOFT_SKILL = 'soft_skill', 'Soft Skill'
        CERTIFICATION = 'certification', 'Certification'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=255, unique=True)
    normalized_name = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=25, choices=Category.choices, default=Category.OTHER)

    class Meta:
        ordering = ['normalized_name']

    def __str__(self):
        return self.name

class SkillAlias(TimeStampedModel):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='aliases')
    alias = models.CharField(max_length=255)
    normalized_alias = models.CharField(max_length=255, unique=True, db_index=True)
    source = models.CharField(max_length=50, default='manual')

    class Meta:
        ordering = ['normalized_alias']
        indexes = [models.Index(fields=['normalized_alias'])]

    def __str__(self):
        return f'{self.alias} -> {self.skill.name}'


class Resume(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resumes')
    title = models.CharField(max_length=150)
    file = models.FileField(upload_to=resume_upload_path, blank=True)
    extracted_text = models.TextField(blank=True)
    parsed_data = models.JSONField(default=dict, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} - {self.user.username}'


class ResumeSkill(TimeStampedModel):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='resume_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='resume_skills')
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    years_experience = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    evidence = models.TextField(blank=True)

    class Meta:
        unique_together = ('resume', 'skill')
        ordering = ['skill__normalized_name']

    def __str__(self):
        return f'{self.resume.title}: {self.skill.name}'


class Company(TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name


class JobPosting(TimeStampedModel):
    class RemoteType(models.TextChoices):
        ON_SITE = 'on_site', 'On Site'
        HYBRID = 'hybrid', 'Hybrid'
        REMOTE = 'remote', 'Remote'
        UNKNOWN = 'unknown', 'Unknown'

    class EmploymentType(models.TextChoices):
        FULL_TIME = 'full_time', 'Full Time'
        PART_TIME = 'part_time', 'Part Time'
        CONTRACT = 'contract', 'Contract'
        INTERNSHIP = 'internship', 'Internship'
        TEMPORARY = 'temporary', 'Temporary'
        UNKNOWN = 'unknown', 'Unknown'

    class ExperienceLevel(models.TextChoices):
        ENTRY = 'entry', 'Entry Level'
        MID = 'mid', 'Mid Level'
        SENIOR = 'senior', 'Senior Level'
        LEAD = 'lead', 'Lead'
        UNKNOWN = 'unknown', 'Unknown'

    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='job_postings')
    external_id = models.CharField(max_length=255, blank=True)
    source_name = models.CharField(max_length=100, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200, blank=True)
    remote_type = models.CharField(max_length=20, choices=RemoteType.choices, default=RemoteType.UNKNOWN)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, default=EmploymentType.UNKNOWN)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices, default=ExperienceLevel.UNKNOWN)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=10, default='USD')
    posted_at = models.DateTimeField(null=True, blank=True)
    scraped_at = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    embedding = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-posted_at', '-created_at']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['location']),
            models.Index(fields=['remote_type']),
            models.Index(fields=['experience_level']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['source_name', 'external_id'],
                condition=~models.Q(external_id=''),
                name='unique_job_source_external_id',
            )
        ]

    def __str__(self):
        company_name = self.company.name if self.company else 'Unknown Company'
        return f'{self.title} at {company_name}'


class JobSkill(TimeStampedModel):
    class Importance(models.TextChoices):
        REQUIRED = 'required', 'Required'
        PREFERRED = 'preferred', 'Preferred'
        MENTIONED = 'mentioned', 'Mentioned'

    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='job_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='job_skills')
    importance = models.CharField(max_length=20, choices=Importance.choices, default=Importance.MENTIONED)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    evidence = models.TextField(blank=True)

    class Meta:
        unique_together = ('job_posting', 'skill')
        ordering = ['importance', 'skill__normalized_name']

    def __str__(self):
        return f'{self.job_posting.title}: {self.skill.name}'


class SavedJobSearch(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_job_searches')
    name = models.CharField(max_length=150)
    query = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=150, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    min_salary = models.PositiveIntegerField(null=True, blank=True)
    remote_only = models.BooleanField(default=False)
    is_alert_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SavedJob(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_jobs')
    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='saved_by_users')
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('user', 'job_posting')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.job_posting.title}'


class ResumeJobMatch(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resume_job_matches')
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='job_matches')
    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='resume_matches')
    match_score = models.DecimalField(max_digits=5, decimal_places=2)
    summary = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    missing_skills = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = ('resume', 'job_posting')
        ordering = ['-match_score', '-created_at']
        indexes = [models.Index(fields=['match_score'])]

    def __str__(self):
        return f'{self.resume.title} to {self.job_posting.title}: {self.match_score}%'


class SkillGap(TimeStampedModel):
    class Priority(models.TextChoices):
        HIGH = 'high', 'High'
        MEDIUM = 'medium', 'Medium'
        LOW = 'low', 'Low'

    match = models.ForeignKey(ResumeJobMatch, on_delete=models.CASCADE, related_name='skill_gaps')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='skill_gaps')
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    explanation = models.TextField(blank=True)

    class Meta:
        unique_together = ('match', 'skill')
        ordering = ['priority', 'skill__normalized_name']

    def __str__(self):
        return f'{self.skill.name} gap for {self.match}'


class SkillTrendSnapshot(TimeStampedModel):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='trend_snapshots')
    role_title = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=150, blank=True)
    posting_count = models.PositiveIntegerField(default=0)
    demand_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    average_salary = models.PositiveIntegerField(null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()

    class Meta:
        ordering = ['-period_end', 'skill__normalized_name']
        indexes = [
            models.Index(fields=['role_title']),
            models.Index(fields=['location']),
            models.Index(fields=['period_start', 'period_end']),
        ]

    def __str__(self):
        return f'{self.skill.name} trend: {self.period_start} to {self.period_end}'
