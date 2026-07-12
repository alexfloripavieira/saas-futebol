"""Catálogo e adaptadores autorizados de dados esportivos.

Credenciais são recebidas pelo chamador (env/vault) e nunca persistidas. Fontes
de laboratório e fontes dependentes de contrato são provisionadas inativas para
que a interface deixe claros os limites de uso.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from futebol.models import (
    ExternalSystem,
    IntegrationRecord,
    SportsDataImportBatch,
    SportsDataRecord,
    SportsDataSource,
)
from futebol.services.audit import log_audit_event, snapshot_instance
from futebol.services.net import safe_urlopen


PROVIDER_CATALOG = (
    {
        'code': 'club-internal', 'name': 'Dados internos do clube',
        'kind': SportsDataSource.Kind.CLUB_INTERNAL,
        'capabilities': ['availability', 'physical_load', 'lineups_events'],
        'license_id': 'club-controlled', 'license_url': '',
        'attribution': 'Dados fornecidos e controlados pelo clube.',
        'quality': 'production_primary', 'active': True,
        'operational_status': SportsDataSource.OperationalStatus.ACTIVE,
    },
    {
        'code': 'football-data-org', 'name': 'football-data.org',
        'kind': SportsDataSource.Kind.FOOTBALL_DATA_ORG,
        'capabilities': ['fixtures_results', 'standings_form'],
        'license_id': 'football-data-org-terms',
        'license_url': 'https://www.football-data.org/about',
        'attribution': 'Dados fornecidos por football-data.org.',
        'quality': 'production_basic', 'active': False,
        'operational_status': SportsDataSource.OperationalStatus.DRAFT,
        'adapter_version': '1.0', 'schema_version': 'football-data-v4',
    },
    {
        'code': 'statsbomb-open', 'name': 'StatsBomb Open Data',
        'kind': SportsDataSource.Kind.STATSBOMB_OPEN,
        'capabilities': ['lineups_events', 'event_stream', 'xg'],
        'license_id': 'statsbomb-open-data',
        'license_url': 'https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf',
        'attribution': 'StatsBomb Open Data — uso restrito ao laboratório autorizado.',
        'quality': 'research_sample', 'active': False,
        'operational_status': SportsDataSource.OperationalStatus.RESEARCH_ONLY,
    },
    {
        'code': 'skillcorner-open', 'name': 'SkillCorner Open Data',
        'kind': SportsDataSource.Kind.SKILLCORNER_OPEN,
        'capabilities': ['tracking_frames', 'physical_metrics'],
        'license_id': 'skillcorner-open-data',
        'license_url': 'https://github.com/SkillCorner/opendata',
        'attribution': 'SkillCorner Open Data — amostra para pesquisa.',
        'quality': 'research_sample', 'active': False,
        'operational_status': SportsDataSource.OperationalStatus.RESEARCH_ONLY,
    },
    {
        'code': 'hudl-wyscout', 'name': 'Hudl Wyscout',
        'kind': SportsDataSource.Kind.LICENSED_PROVIDER,
        'capabilities': ['lineups_events', 'event_stream', 'video', 'scouting'],
        'license_id': 'contract-required', 'license_url': 'https://www.hudl.com/products/wyscout',
        'attribution': 'Uso condicionado a contrato comercial.',
        'quality': 'contract_required', 'active': False,
        'operational_status': SportsDataSource.OperationalStatus.CONTRACT_REQUIRED,
    },
    {
        'code': 'opta', 'name': 'Opta / Stats Perform',
        'kind': SportsDataSource.Kind.LICENSED_PROVIDER,
        'capabilities': ['fixtures_results', 'event_stream', 'tracking_frames'],
        'license_id': 'contract-required', 'license_url': 'https://www.statsperform.com/opta/',
        'attribution': 'Uso condicionado a contrato comercial.',
        'quality': 'contract_required', 'active': False,
        'operational_status': SportsDataSource.OperationalStatus.CONTRACT_REQUIRED,
    },
    {
        'code': 'fmdb-pro', 'name': 'Football Manager FMDB Pro',
        'kind': SportsDataSource.Kind.LICENSED_PROVIDER,
        'capabilities': ['scouting', 'contracts', 'player_attributes'],
        'license_id': 'custom-saas-contract-required',
        'license_url': 'https://www.footballmanager.com/',
        'attribution': 'Exige autorização explícita da Sports Interactive para uso em SaaS.',
        'quality': 'contract_required', 'active': False,
        'operational_status': SportsDataSource.OperationalStatus.CONTRACT_REQUIRED,
    },
)


def provision_provider_catalog(*, tenant):
    sources = []
    for item in PROVIDER_CATALOG:
        values = dict(item)
        code = values.pop('code')
        source, created = SportsDataSource.objects.get_or_create(
            tenant=tenant, code=code, defaults=values
        )
        if not created:
            # Atualiza o contrato declarado pelo código sem reativar, revogar ou
            # apagar o estado operacional escolhido pelo tenant.
            mutable_metadata = {
                key: value for key, value in values.items()
                if key not in {'active', 'operational_status', 'last_sync_at', 'last_error'}
            }
            for key, value in mutable_metadata.items():
                setattr(source, key, value)
            source.save(update_fields=[*mutable_metadata, 'updated_at'])
        sources.append(source)
    return sources


def _get_json(url, *, api_key):
    request = urllib.request.Request(
        url,
        headers={'X-Auth-Token': api_key, 'Accept': 'application/json'},
    )
    with safe_urlopen(request, timeout=30) as response:
        try:
            payload = json.loads(response.read().decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError('O provider retornou JSON inválido.') from exc
        headers = getattr(response, 'headers', {})
        return payload, {
            'requests_available': headers.get('X-RequestsAvailable'),
            'reset_seconds': headers.get('X-RequestCounter-Reset'),
            'api_version': headers.get('X-API-Version'),
        }


def _normalize_matches(payload):
    records = []
    for match in payload.get('matches', []):
        match_id = str(match['id'])
        records.append({
            'capability': 'fixtures_results',
            'provider_record_id': f'match:{match_id}',
            'observed_at': match.get('utcDate'),
            'source_url': f'https://api.football-data.org/v4/matches/{match_id}',
            'payload': {
                'provider_match_id': match_id,
                'scheduled_at': match.get('utcDate'),
                'status': match.get('status'),
                'home_team_id': str(match.get('homeTeam', {}).get('id') or ''),
                'home_team': match.get('homeTeam', {}).get('name', ''),
                'away_team_id': str(match.get('awayTeam', {}).get('id') or ''),
                'away_team': match.get('awayTeam', {}).get('name', ''),
                'score': match.get('score', {}).get('fullTime', {}),
            },
            'raw_payload': match,
        })
    return records


def _normalize_standings(payload, competition_code):
    records = []
    for standing in payload.get('standings', []):
        if standing.get('type') != 'TOTAL':
            continue
        for row in standing.get('table', []):
            team = row.get('team', {})
            team_id = str(team.get('id') or '')
            records.append({
                'capability': 'standings_form',
                'provider_record_id': f'standing:{competition_code}:{team_id}',
                'source_url': f'https://api.football-data.org/v4/competitions/{competition_code}/standings',
                'payload': {
                    'competition_code': competition_code,
                    'team_id': team_id,
                    'team': team.get('name', ''),
                    'position': row.get('position'),
                    'played_games': row.get('playedGames'),
                    'points': row.get('points'),
                    'form': row.get('form') or '',
                },
                'raw_payload': row,
            })
    return records


def sync_football_data_org(*, tenant, imported_by, api_key, competition_code='BSA'):
    if not (api_key or '').strip():
        raise ValidationError('Configure a credencial do football-data.org no ambiente.')
    competition_code = (competition_code or '').strip().upper()
    if not competition_code.isalnum() or len(competition_code) > 12:
        raise ValidationError('Código de competição inválido.')

    source = next(
        item for item in provision_provider_catalog(tenant=tenant)
        if item.code == 'football-data-org'
    )
    base = f'https://api.football-data.org/v4/competitions/{competition_code}'
    try:
        matches_payload, matches_rate = _get_json(f'{base}/matches', api_key=api_key)
        standings_payload, standings_rate = _get_json(f'{base}/standings', api_key=api_key)
    except Exception:
        _record_provider_failure(
            tenant=tenant, source=source, competition_code=competition_code
        )
        raise
    records = _normalize_matches(matches_payload) + _normalize_standings(
        standings_payload, competition_code
    )
    return _persist_football_data_sync(
        tenant=tenant,
        imported_by=imported_by,
        source=source,
        competition_code=competition_code,
        matches_payload=matches_payload,
        standings_payload=standings_payload,
        records=records,
        rate_limit={'matches': matches_rate, 'standings': standings_rate},
    )


@transaction.atomic
def _record_provider_failure(*, tenant, source, competition_code):
    now = timezone.now()
    source.operational_status = SportsDataSource.OperationalStatus.DEGRADED
    source.last_error = 'Falha de comunicação ou validação do provider.'
    source.save(update_fields=['operational_status', 'last_error', 'updated_at'])
    external_system, _ = ExternalSystem.objects.get_or_create(
        tenant=tenant,
        name='football-data.org',
        defaults={
            'kind': ExternalSystem.Kind.IMPORT,
            'base_url': 'https://api.football-data.org/v4/',
            'active': True,
        },
    )
    IntegrationRecord.objects.create(
        tenant=tenant,
        external_system=external_system,
        correlation_id=f'football-data:error:{uuid4()}',
        external_object_id=f'competition-{competition_code.lower()}',
        payload={'competition': competition_code, 'provider': 'football-data.org'},
        status='error',
        processed_at=now,
        error_message='Falha de comunicação ou validação do provider.',
    )


@transaction.atomic
def _persist_football_data_sync(
    *, tenant, imported_by, source, competition_code, matches_payload,
    standings_payload, records, rate_limit,
):
    raw = json.dumps(
        {'matches': matches_payload, 'standings': standings_payload},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    ).encode('utf-8')
    content_hash = hashlib.sha256(raw).hexdigest()
    dataset_version = timezone.now().date().isoformat()
    existing = SportsDataImportBatch.objects.filter(
        tenant=tenant, source=source, dataset_id=f'competition-{competition_code.lower()}',
        content_hash=content_hash, status=SportsDataImportBatch.Status.COMPLETED,
    ).first()
    if existing:
        return existing

    now = timezone.now()
    batch = SportsDataImportBatch.objects.create(
        tenant=tenant, source=source,
        dataset_id=f'competition-{competition_code.lower()}',
        dataset_version=dataset_version, content_hash=content_hash,
        status=SportsDataImportBatch.Status.PROCESSING,
        manifest={'provider': 'football-data.org', 'competition': competition_code,
                  'capabilities': ['fixtures_results', 'standings_form'],
                  'rate_limit': rate_limit},
        license_id=source.license_id, attribution=source.attribution,
        quality=source.quality, imported_by=imported_by,
    )
    for record in records:
        record_raw = json.dumps(record, sort_keys=True, separators=(',', ':')).encode()
        SportsDataRecord.objects.create(
            tenant=tenant, source=source, batch=batch,
            capability=record['capability'],
            provider_record_id=record['provider_record_id'],
            observed_at=now,
            payload=record['payload'], raw_payload=record['raw_payload'],
            source_url=record['source_url'],
            content_hash=hashlib.sha256(record_raw).hexdigest(),
            expires_at=now + timedelta(hours=24),
        )
    batch.status = SportsDataImportBatch.Status.COMPLETED
    batch.record_count = len(records)
    batch.imported_at = now
    batch.save(update_fields=['status', 'record_count', 'imported_at', 'updated_at'])
    source.active = True
    source.operational_status = SportsDataSource.OperationalStatus.ACTIVE
    source.last_sync_at = now
    source.last_error = ''
    source.save(
        update_fields=['active', 'operational_status', 'last_sync_at', 'last_error', 'updated_at']
    )
    external_system, _ = ExternalSystem.objects.get_or_create(
        tenant=tenant,
        name='football-data.org',
        defaults={
            'kind': ExternalSystem.Kind.IMPORT,
            'base_url': 'https://api.football-data.org/v4/',
            'active': True,
        },
    )
    IntegrationRecord.objects.get_or_create(
        tenant=tenant,
        external_system=external_system,
        correlation_id=f'football-data:{content_hash}',
        defaults={
            'external_object_id': batch.dataset_id,
            'payload': {
                'batch_id': batch.pk,
                'competition': competition_code,
                'record_count': batch.record_count,
                'content_hash': content_hash,
            },
            'status': 'processed',
            'processed_at': now,
        },
    )
    log_audit_event(
        tenant=tenant, actor=imported_by, action='import', obj=batch,
        after_state=snapshot_instance(batch),
    )
    return batch
