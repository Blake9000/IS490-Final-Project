from django.contrib import admin
from .models import (
    Company,
    JobPosting,
    JobSkill,
    Resume,
    ResumeJobMatch,
    ResumeSkill,
    SavedJob,
    SavedJobSearch,
    Skill,
    SkillGap,
    SkillTrendSnapshot,
    UserProfile,
    SkillAlias
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'target_role', 'target_location', 'remote_preference')
    list_filter = ('user_type', 'remote_preference')
    search_fields = ('user__username', 'user__email', 'target_role', 'target_location')


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'normalized_name', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'normalized_name')


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'is_primary', 'updated_at')
    list_filter = ('is_primary', 'created_at', 'updated_at')
    search_fields = ('title', 'user__username', 'extracted_text')


@admin.register(ResumeSkill)
class ResumeSkillAdmin(admin.ModelAdmin):
    list_display = ('resume', 'skill', 'confidence', 'years_experience')
    list_filter = ('skill__category',)
    search_fields = ('resume__title', 'skill__name', 'evidence')


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'website')
    search_fields = ('name', 'industry')


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'location', 'remote_type', 'experience_level', 'is_active', 'posted_at')
    list_filter = ('remote_type', 'employment_type', 'experience_level', 'is_active', 'source_name')
    search_fields = ('title', 'company__name', 'description', 'location')


@admin.register(JobSkill)
class JobSkillAdmin(admin.ModelAdmin):
    list_display = ('job_posting', 'skill', 'importance', 'confidence')
    list_filter = ('importance', 'skill__category')
    search_fields = ('job_posting__title', 'skill__name', 'evidence')


@admin.register(SavedJobSearch)
class SavedJobSearchAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'query', 'location', 'remote_only', 'is_alert_enabled')
    list_filter = ('remote_only', 'is_alert_enabled')
    search_fields = ('name', 'user__username', 'query', 'location')


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ('user', 'job_posting', 'created_at')
    search_fields = ('user__username', 'job_posting__title', 'notes')


@admin.register(ResumeJobMatch)
class ResumeJobMatchAdmin(admin.ModelAdmin):
    list_display = ('resume', 'job_posting', 'user', 'match_score', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('resume__title', 'job_posting__title', 'summary')


@admin.register(SkillGap)
class SkillGapAdmin(admin.ModelAdmin):
    list_display = ('match', 'skill', 'priority')
    list_filter = ('priority', 'skill__category')
    search_fields = ('skill__name', 'explanation')


@admin.register(SkillTrendSnapshot)
class SkillTrendSnapshotAdmin(admin.ModelAdmin):
    list_display = ('skill', 'role_title', 'location', 'posting_count', 'demand_percentage', 'period_start', 'period_end')
    list_filter = ('period_start', 'period_end', 'skill__category')
    search_fields = ('skill__name', 'role_title', 'location')

@admin.register(SkillAlias)
class SkillAliasAdmin(admin.ModelAdmin):
    list_display = ('alias', 'skill', 'source')
    list_filter = ('source',)
    search_fields = ('alias', 'normalized_alias', 'skill__name')