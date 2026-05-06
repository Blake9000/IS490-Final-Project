import csv
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from resume_fixer.models import Skill, SkillAlias
from resume_fixer.services import normalize_name, seed_reference_data


ESCO_API_BASE_URL = 'https://ec.europa.eu/esco/api'
ESCO_SELECTED_VERSION = 'latest'
ESCO_SKILLS_SCHEME_URI = 'http://data.europa.eu/esco/concept-scheme/skills'

def first_value(row, keys):
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    for key in keys:
        value = normalized.get(key.lower())
        if value:
            return str(value).strip()
    return ''


def split_labels(value):
    if not value:
        return []

    cleaned = str(value).replace('\r\n', '\n').replace('\r', '\n')
    parts = re.split(r'\n+|;|\|', cleaned)
    labels = []

    for part in parts:
        label = re.sub(r'\s+', ' ', part).strip(' .,"\'')
        if label and label not in labels:
            labels.append(label)

    return labels


def skill_category_from_esco(row):
    skill_type = first_value(row, ['skillType', 'skill type', 'skill_type', 'type']).lower()
    scheme = first_value(row, ['inScheme', 'in scheme', 'conceptType', 'concept type']).lower()

    if 'transversal' in skill_type or 'transversal' in scheme:
        return Skill.Category.SOFT_SKILL
    if 'language' in skill_type or 'language' in scheme:
        return Skill.Category.SOFT_SKILL
    if 'knowledge' in skill_type or 'knowledge' in scheme:
        return Skill.Category.OTHER
    return Skill.Category.OTHER


def upsert_skill_with_aliases(name, category, aliases, source):
    name = re.sub(r'\s+', ' ', str(name or '')).strip()
    if not name:
        return False, 0

    normalized_name = normalize_name(name)
    skill, created = Skill.objects.get_or_create(
        normalized_name=normalized_name,
        defaults={'name': name[:255], 'category': category},
    )

    changed = False

    if not created:
        updates = []

        if skill.name != name[:255]:
            skill.name = name[:255]
            updates.append('name')

        if skill.category == Skill.Category.OTHER and category != Skill.Category.OTHER:
            skill.category = category
            updates.append('category')

        if updates:
            updates.append('updated_at')
            skill.save(update_fields=updates)
            changed = True

    alias_count = 0

    for alias in [name, *aliases]:
        alias = re.sub(r'\s+', ' ', str(alias or '')).strip()
        normalized_alias = normalize_name(alias)

        if not alias or len(normalized_alias) < 2:
            continue

        if len(alias) > 255 or len(normalized_alias) > 255:
            continue

        _, alias_created = SkillAlias.objects.get_or_create(
            normalized_alias=normalized_alias,
            defaults={
                'skill': skill,
                'alias': alias,
                'source': source,
            },
        )

        if alias_created:
            alias_count += 1

    return created or changed, alias_count


def csv_rows_from_path(path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as handle:
        yield from csv.DictReader(handle)


def csv_rows_from_zip(path, member_name=''):
    with zipfile.ZipFile(path) as archive:
        candidates = [name for name in archive.namelist() if name.lower().endswith('.csv')]

        if member_name:
            candidates = [name for name in candidates if Path(name).name.lower() == member_name.lower()]
        else:
            preferred = [name for name in candidates if Path(name).name.lower() == 'skills_en.csv']
            candidates = preferred or [name for name in candidates if 'skills' in Path(name).name.lower()]

        if not candidates:
            raise CommandError('No ESCO skills CSV was found inside the zip file.')

        with archive.open(candidates[0], 'r') as raw_handle:
            text = (line.decode('utf-8-sig') for line in raw_handle)
            yield from csv.DictReader(text)


def get_embedded_items(data):
    embedded = data.get('_embedded') or {}

    if isinstance(embedded, dict):
        for value in embedded.values():
            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                nested_embedded = value.get('_embedded') or {}
                for nested_value in nested_embedded.values():
                    if isinstance(nested_value, list):
                        return nested_value

    return []


def rows_from_esco_api(limit=100, max_pages=200):
    offset = 0
    pages = 0

    while pages < max_pages:
        params = urllib.parse.urlencode({
            'isInScheme': ESCO_SKILLS_SCHEME_URI,
            'language': 'en',
            'offset': offset,
            'limit': limit,
            'selectedVersion': ESCO_SELECTED_VERSION,
            'viewObsolete': 'false',
        })

        url = f'{ESCO_API_BASE_URL}/resource/skill?{params}'

        request = urllib.request.Request(
            url,
            headers={
                'Accept': 'application/json,application/json;charset=UTF-8',
                'Accept-Language': 'en',
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            error_body = ''

            try:
                error_body = exc.read().decode('utf-8', errors='ignore')
            except Exception:
                pass

            raise CommandError(
                f'ESCO API returned HTTP {exc.code}. URL was: {url}. Response: {error_body[:500]}'
            ) from exc
        except urllib.error.URLError as exc:
            raise CommandError(f'Could not reach ESCO API: {exc}. Use the CSV import option instead.') from exc

        data = json.loads(payload)
        values = get_embedded_items(data)

        if not values:
            break

        for item in values:
            yield item

        pages += 1
        offset += 1



def row_to_skill(row):
    preferred = first_value(row, ['preferredLabel', 'preferred label', 'title', 'label', 'name'])

    if not preferred:
        preferred = first_value(row, ['preferredTerm', 'preferred term'])

    alt_labels = []
    alt_labels.extend(split_labels(first_value(row, ['altLabels', 'alt labels', 'nonPreferredLabels', 'alternativeLabels'])))
    alt_labels.extend(split_labels(first_value(row, ['hiddenLabels', 'hidden labels'])))

    return preferred, skill_category_from_esco(row), alt_labels


def text_from_multilingual_value(value):
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        english = value.get('en')

        if isinstance(english, list):
            return str(english[0]).strip() if english else ''

        if english:
            return str(english).strip()

        for item in value.values():
            if isinstance(item, list) and item:
                return str(item[0]).strip()
            if item:
                return str(item).strip()

    if isinstance(value, list) and value:
        return str(value[0]).strip()

    return ''


def list_from_multilingual_value(value):
    labels = []

    if isinstance(value, str):
        labels.extend(split_labels(value))

    elif isinstance(value, list):
        labels.extend(str(item).strip() for item in value if item)

    elif isinstance(value, dict):
        english = value.get('en')

        if isinstance(english, list):
            labels.extend(str(item).strip() for item in english if item)
        elif english:
            labels.append(str(english).strip())

        if not labels:
            for item in value.values():
                if isinstance(item, list):
                    labels.extend(str(v).strip() for v in item if v)
                elif item:
                    labels.append(str(item).strip())

    return [label for label in labels if label]


def api_item_to_skill(item):
    preferred = (
        text_from_multilingual_value(item.get('preferredLabel'))
        or text_from_multilingual_value(item.get('title'))
        or text_from_multilingual_value(item.get('label'))
    )

    links = item.get('_links') or {}
    self_link = links.get('self') or {}

    if not preferred and isinstance(self_link, dict):
        preferred = text_from_multilingual_value(self_link.get('title'))

    alt_labels = []
    alt_labels.extend(list_from_multilingual_value(item.get('alternativeLabel')))
    alt_labels.extend(list_from_multilingual_value(item.get('altLabels')))
    alt_labels.extend(list_from_multilingual_value(item.get('hiddenLabel')))

    skill_type_raw = str(item.get('skillType') or item.get('skillTypeLabel') or '').lower()

    if 'transversal' in skill_type_raw:
        category = Skill.Category.SOFT_SKILL
    else:
        category = Skill.Category.OTHER

    return preferred, category, alt_labels

class Command(BaseCommand):
    help = 'Imports ESCO skills into the local Skill and SkillAlias tables.'

    def add_arguments(self, parser):
        parser.add_argument('--csv', dest='csv_path', help='Path to skills_en.csv from the ESCO download package.')
        parser.add_argument('--zip', dest='zip_path', help='Path to an ESCO download zip containing skills_en.csv.')
        parser.add_argument('--zip-member', default='', help='Optional CSV filename inside the zip. Defaults to skills_en.csv.')
        parser.add_argument('--api', action='store_true', help='Try importing skills from the ESCO web-service API.')
        parser.add_argument('--clear-esco-aliases', action='store_true', help='Delete existing ESCO aliases before import.')

    def handle(self, *args, **options):
        seed_reference_data()

        selected = sum(1 for key in ('csv_path', 'zip_path') if options.get(key)) + int(options['api'])

        if selected != 1:
            raise CommandError('Choose exactly one import source: --csv, --zip, or --api.')

        if options['clear_esco_aliases']:
            deleted, _ = SkillAlias.objects.filter(source='esco').delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing ESCO alias row(s).'))

        if options['csv_path']:
            rows = csv_rows_from_path(options['csv_path'])
            converter = row_to_skill
        elif options['zip_path']:
            rows = csv_rows_from_zip(options['zip_path'], options['zip_member'])
            converter = row_to_skill
        else:
            rows = rows_from_esco_api()
            converter = api_item_to_skill

        checked = 0
        skills_changed = 0
        aliases_created = 0
        skipped = 0

        with transaction.atomic():
            for row in rows:
                checked += 1
                name, category, aliases = converter(row)

                if not name:
                    skipped += 1
                    continue

                changed, alias_count = upsert_skill_with_aliases(name, category, aliases, source='esco')

                if changed:
                    skills_changed += 1

                aliases_created += alias_count

        self.stdout.write(self.style.SUCCESS(f'Checked {checked} ESCO row(s).'))
        self.stdout.write(self.style.SUCCESS(f'Created or updated {skills_changed} skill row(s).'))
        self.stdout.write(self.style.SUCCESS(f'Created {aliases_created} alias row(s).'))
        self.stdout.write(self.style.SUCCESS(f'Skipped {skipped} row(s).'))