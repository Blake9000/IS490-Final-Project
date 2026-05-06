from django.core.management.base import BaseCommand

from resume_fixer.models import Resume
from resume_fixer.services import (
    extract_resume_skills,
    extract_text_from_stored_file,
    update_matches_for_resume,
)


class Command(BaseCommand):
    help = 'Re-extracts resume text from stored resume files and refreshes extracted skills.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-empty',
            action='store_true',
            help='Only reprocess resumes where extracted_text is blank.',
        )

    def handle(self, *args, **options):
        only_empty = options['only_empty']

        resumes = Resume.objects.select_related('user').all()

        if only_empty:
            resumes = resumes.filter(extracted_text='')

        checked = 0
        updated = 0
        skipped = 0

        for resume in resumes:
            checked += 1

            if not resume.file:
                skipped += 1
                continue

            text = extract_text_from_stored_file(resume.file)

            if not text:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipped resume {resume.pk}: no readable text extracted.'
                    )
                )
                continue

            resume.extracted_text = text
            resume.save(update_fields=['extracted_text', 'updated_at'])

            extract_resume_skills(resume)
            update_matches_for_resume(resume.user, resume)

            updated += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated resume {resume.pk}: extracted {len(text)} characters.'
                )
            )

        self.stdout.write('')
        self.stdout.write(f'Checked: {checked}')
        self.stdout.write(f'Updated: {updated}')
        self.stdout.write(f'Skipped: {skipped}')