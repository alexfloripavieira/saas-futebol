from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from futebol.models import Club, Competition, CompetitionEdition, CompetitionPhase, Match, Tenant
from futebol.services.audit import log_audit_event


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[dict] | None = None

    def as_dict(self):
        return {
            'created': self.created,
            'updated': self.updated,
            'skipped': self.skipped,
            'failed': self.failed,
            'errors': self.errors or [],
        }


MODEL_REGISTRY = {
    'club': Club,
    'competition': Competition,
    'edition': CompetitionEdition,
    'phase': CompetitionPhase,
    'match': Match,
}

EXPORT_FIELDS = {
    'club': ['name', 'slug', 'registration_code', 'city', 'state', 'active'],
    'competition': ['name', 'slug', 'scope', 'active'],
    'edition': ['competition_slug', 'slug', 'name', 'season_year', 'status', 'registration_deadline', 'published_at'],
    'phase': ['competition_slug', 'edition_slug', 'code', 'name', 'order', 'status', 'starts_at', 'ends_at'],
    'match': ['reference_code', 'competition_slug', 'edition_slug', 'phase_code', 'home_club_slug', 'away_club_slug', 'scheduled_at', 'venue', 'status', 'home_score', 'away_score'],
}


def _tenant_queryset(tenant: Tenant, model_name: str):
    model = MODEL_REGISTRY[model_name]
    return model.objects.filter(tenant=tenant)


def export_rows(tenant: Tenant, model_name: str):
    model_name = model_name.lower()
    if model_name not in MODEL_REGISTRY:
        raise ValidationError(f'Modelo inválido: {model_name}')
    fields = EXPORT_FIELDS[model_name]
    rows = []
    for obj in _tenant_queryset(tenant, model_name).select_related():
        if model_name == 'club':
            rows.append({f: getattr(obj, f) for f in fields})
        elif model_name == 'competition':
            rows.append({f: getattr(obj, f) for f in fields})
        elif model_name == 'edition':
            rows.append({
                'competition_slug': obj.competition.slug,
                'slug': obj.slug,
                'name': obj.name,
                'season_year': obj.season_year,
                'status': obj.status,
                'registration_deadline': obj.registration_deadline.isoformat() if obj.registration_deadline else '',
                'published_at': obj.published_at.isoformat() if obj.published_at else '',
            })
        elif model_name == 'phase':
            rows.append({
                'competition_slug': obj.edition.competition.slug,
                'edition_slug': obj.edition.slug,
                'code': obj.code,
                'name': obj.name,
                'order': obj.order,
                'status': obj.status,
                'starts_at': obj.starts_at.isoformat() if obj.starts_at else '',
                'ends_at': obj.ends_at.isoformat() if obj.ends_at else '',
            })
        elif model_name == 'match':
            rows.append({
                'reference_code': obj.reference_code,
                'competition_slug': obj.phase.edition.competition.slug,
                'edition_slug': obj.phase.edition.slug,
                'phase_code': obj.phase.code,
                'home_club_slug': obj.home_club.slug,
                'away_club_slug': obj.away_club.slug,
                'scheduled_at': obj.scheduled_at.isoformat(),
                'venue': obj.venue,
                'status': obj.status,
                'home_score': '' if obj.home_score is None else obj.home_score,
                'away_score': '' if obj.away_score is None else obj.away_score,
            })
    return fields, rows


def export_csv(tenant: Tenant, model_name: str) -> str:
    fields, rows = export_rows(tenant, model_name)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    log_audit_event(
        tenant=tenant,
        action='export',
        obj=tenant,
        after_state={'model_name': model_name, 'rows': len(rows)},
    )
    return buffer.getvalue()


def _load_rows_from_payload(raw_payload: str):
    raw_payload = raw_payload.strip()
    if not raw_payload:
        return []
    if raw_payload.lstrip().startswith('['):
        return json.loads(raw_payload)
    reader = csv.DictReader(io.StringIO(raw_payload))
    return list(reader)


def _normalize_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'sim', 'y'}


def _parse_datetime(value):
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise ValidationError(f'Data/hora inválida: {value}')
    return parsed


def _apply_if_changed(obj, defaults: dict):
    changed = False
    for key, value in defaults.items():
        if getattr(obj, key) != value:
            setattr(obj, key, value)
            changed = True
    if changed:
        obj.save()
    return changed


@transaction.atomic
def import_payload(tenant: Tenant, model_name: str, raw_payload: str, conflict_policy: str = 'skip'):
    model_name = model_name.lower()
    if model_name not in MODEL_REGISTRY:
        raise ValidationError(f'Modelo inválido: {model_name}')
    rows = _load_rows_from_payload(raw_payload)
    result = ImportResult(errors=[])

    for index, row in enumerate(rows, start=1):
        try:
            if model_name == 'club':
                obj, status = _upsert_club(tenant, row, conflict_policy)
            elif model_name == 'competition':
                obj, status = _upsert_competition(tenant, row, conflict_policy)
            elif model_name == 'edition':
                obj, status = _upsert_edition(tenant, row, conflict_policy)
            elif model_name == 'phase':
                obj, status = _upsert_phase(tenant, row, conflict_policy)
            elif model_name == 'match':
                obj, status = _upsert_match(tenant, row, conflict_policy)
            else:
                raise ValidationError(f'Modelo inválido: {model_name}')
            if status == 'created':
                result.created += 1
            elif status == 'updated':
                result.updated += 1
            else:
                result.skipped += 1
        except Exception as exc:
            result.failed += 1
            result.errors.append({'row': index, 'error': str(exc), 'data': row})
    log_audit_event(
        tenant=tenant,
        action='import',
        obj=tenant,
        after_state={
            'model_name': model_name,
            'created': result.created,
            'updated': result.updated,
            'skipped': result.skipped,
            'failed': result.failed,
            'error_count': len(result.errors or []),
        },
    )
    return result


def _upsert_club(tenant: Tenant, row: dict, conflict_policy: str):
    defaults = {
        'name': row['name'],
        'registration_code': row.get('registration_code', ''),
        'city': row.get('city', ''),
        'state': row.get('state', ''),
        'active': _normalize_bool(row.get('active', True)),
    }
    obj, created = Club.objects.get_or_create(tenant=tenant, slug=row['slug'], defaults=defaults)
    if created:
        return obj, 'created'
    if conflict_policy == 'skip':
        return obj, 'skipped'
    if conflict_policy == 'overwrite':
        if _apply_if_changed(obj, defaults):
            return obj, 'updated'
        return obj, 'skipped'
    raise ValidationError(f'Conflito ao importar clube {row["slug"]}')


def _upsert_competition(tenant: Tenant, row: dict, conflict_policy: str):
    defaults = {
        'name': row['name'],
        'scope': row.get('scope', Competition.Scope.CHAMPIONSHIP),
        'active': _normalize_bool(row.get('active', True)),
    }
    obj, created = Competition.objects.get_or_create(tenant=tenant, slug=row['slug'], defaults=defaults)
    if created:
        return obj, 'created'
    if conflict_policy == 'skip':
        return obj, 'skipped'
    if conflict_policy == 'overwrite':
        if _apply_if_changed(obj, defaults):
            return obj, 'updated'
        return obj, 'skipped'
    raise ValidationError(f'Conflito ao importar competição {row["slug"]}')


def _upsert_edition(tenant: Tenant, row: dict, conflict_policy: str):
    competition = Competition.objects.get(tenant=tenant, slug=row['competition_slug'])
    defaults = {
        'name': row['name'],
        'season_year': int(row['season_year']),
        'status': row.get('status', CompetitionEdition.Status.DRAFT),
        'registration_deadline': _parse_datetime(row.get('registration_deadline')),
        'published_at': _parse_datetime(row.get('published_at')),
    }
    obj, created = CompetitionEdition.objects.get_or_create(tenant=tenant, competition=competition, slug=row['slug'], defaults=defaults)
    if created:
        return obj, 'created'
    if conflict_policy == 'skip':
        return obj, 'skipped'
    if conflict_policy == 'overwrite':
        if _apply_if_changed(obj, defaults):
            return obj, 'updated'
        return obj, 'skipped'
    raise ValidationError(f'Conflito ao importar edição {row["slug"]}')


def _upsert_phase(tenant: Tenant, row: dict, conflict_policy: str):
    competition = Competition.objects.get(tenant=tenant, slug=row['competition_slug'])
    edition = CompetitionEdition.objects.get(tenant=tenant, competition=competition, slug=row['edition_slug'])
    defaults = {
        'name': row['name'],
        'order': int(row['order']),
        'status': row.get('status', CompetitionPhase.Status.DRAFT),
        'starts_at': _parse_datetime(row.get('starts_at')),
        'ends_at': _parse_datetime(row.get('ends_at')),
    }
    obj, created = CompetitionPhase.objects.get_or_create(tenant=tenant, edition=edition, code=row['code'], defaults=defaults)
    if created:
        return obj, 'created'
    if conflict_policy == 'skip':
        return obj, 'skipped'
    if conflict_policy == 'overwrite':
        if _apply_if_changed(obj, defaults):
            return obj, 'updated'
        return obj, 'skipped'
    raise ValidationError(f'Conflito ao importar fase {row["code"]}')


def _upsert_match(tenant: Tenant, row: dict, conflict_policy: str):
    competition = Competition.objects.get(tenant=tenant, slug=row['competition_slug'])
    edition = CompetitionEdition.objects.get(tenant=tenant, competition=competition, slug=row['edition_slug'])
    phase = CompetitionPhase.objects.get(tenant=tenant, edition=edition, code=row['phase_code'])
    home_club = Club.objects.get(tenant=tenant, slug=row['home_club_slug'])
    away_club = Club.objects.get(tenant=tenant, slug=row['away_club_slug'])
    defaults = {
        'phase': phase,
        'home_club': home_club,
        'away_club': away_club,
        'scheduled_at': _parse_datetime(row['scheduled_at']),
        'venue': row.get('venue', ''),
        'status': row.get('status', Match.Status.SCHEDULED),
        'home_score': int(row['home_score']) if row.get('home_score') not in (None, '') else None,
        'away_score': int(row['away_score']) if row.get('away_score') not in (None, '') else None,
    }
    obj, created = Match.objects.get_or_create(tenant=tenant, reference_code=row['reference_code'], defaults=defaults)
    if created:
        return obj, 'created'
    if conflict_policy == 'skip':
        return obj, 'skipped'
    if conflict_policy == 'overwrite':
        if _apply_if_changed(obj, defaults):
            return obj, 'updated'
        return obj, 'skipped'
    raise ValidationError(f'Conflito ao importar partida {row["reference_code"]}')
