from django.core.management.base import BaseCommand

from resume_fixer.models import JobPosting, Resume
from resume_fixer.services import (
    extract_job_skills,
    extract_resume_skills,
    seed_reference_data,
    update_matches_for_job,
    update_matches_for_resume,
)


class Command(BaseCommand):
    help = 'Refreshes extracted skills and match scores using the current skill catalog.'

    def handle(self, *args, **options):
        seed_reference_data()

        resumes = Resume.objects.select_related('user').all()
        jobs = JobPosting.objects.all()

        resume_count = 0
        job_count = 0

        for resume in resumes:
            extract_resume_skills(resume)
            update_matches_for_resume(resume.user, resume)
            resume_count += 1

        for job in jobs:
            extract_job_skills(job)
            update_matches_for_job(job)
            job_count += 1

        self.stdout.write(self.style.SUCCESS(f'Refreshed {resume_count} resume(s).'))
        self.stdout.write(self.style.SUCCESS(f'Refreshed {job_count} job posting(s).'))