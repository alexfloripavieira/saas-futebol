"""Catálogo e adaptadores autorizados de dados esportivos.

Credenciais são recebidas pelo chamador (env/vault) e nunca persistidas. Fontes
de laboratório e fontes dependentes de contrato são provisionadas inativas para
que a interface deixe claros os limites de uso.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import urllib.request
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from futebol.models import (
    ExternalSystem,
    GlobalSportsDataBatch,
    GlobalSportsDataRecord,
    GlobalSportsDataSource,
    GlobalSportsSyncRun,
    IntegrationRecord,
    SportsDataImportBatch,
    SportsDataArtifact,
    SportsDataRecord,
    SportsDataSource,
)
from futebol.services.audit import log_audit_event, snapshot_instance
from futebol.services.net import safe_urlopen
from futebol.services.tracking_analytics import (
    build_tracking_analysis, build_tracking_context, parse_tracking_stream,
)
from futebol.services.tactical_engine import detect_tactical_moments


logger = logging.getLogger(__name__)


SKILLCORNER_OPEN_BASE_URL = (
    'https://raw.githubusercontent.com/SkillCorner/opendata/master/data'
)
SKILLCORNER_OPEN_MAX_MATCHES = 3
SKILLCORNER_TRACKING_MEDIA_URL = (
    'https://media.githubusercontent.com/media/SkillCorner/opendata/master/data'
)
SKILLCORNER_TRACKING_MAX_BYTES = 150 * 1024 * 1024


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
        'adapter_version': '1.0', 'schema_version': 'statsbomb-open-v1.1',
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
        'adapter_version': '1.0', 'schema_version': 'skillcorner-open-2024-25',
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

STATSBOMB_OPEN_BASE_URL = (
    'https://raw.githubusercontent.com/statsbomb/open-data/master/data'
)
STATSBOMB_MAX_MATCHES = 3
STATSBOMB_MAX_EVENTS_PER_MATCH = 5000


GLOBAL_FOOTBALL_DATA_SOURCE = {
    'code': 'football-data-org',
    'name': 'football-data.org',
    'kind': GlobalSportsDataSource.Kind.FOOTBALL_DATA_ORG,
    'capabilities': [
        'fixtures_results', 'standings_form', 'team_squad', 'player_profile',
    ],
    'license_id': 'football-data-org-terms',
    'license_url': 'https://www.football-data.org/about',
    'attribution': 'Dados fornecidos por football-data.org.',
    'quality': 'production_basic',
    'adapter_version': '1.0',
    'schema_version': 'football-data-v4',
}

GLOBAL_OPEN_DATA_SOURCES = {
    'statsbomb-open': {
        'code': 'statsbomb-open',
        'name': 'StatsBomb Open Data',
        'kind': GlobalSportsDataSource.Kind.STATSBOMB_OPEN,
        'capabilities': ['fixtures_results', 'event_stream', 'xg'],
        'license_id': 'statsbomb-open-data',
        'license_url': 'https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf',
        'attribution': 'StatsBomb Open Data — uso restrito ao laboratório autorizado.',
        'quality': 'research_sample',
        'adapter_version': '1.0',
        'schema_version': 'statsbomb-open-v1.1',
        'active': False,
        'operational_status': GlobalSportsDataSource.OperationalStatus.RESEARCH_ONLY,
    },
    'skillcorner-open': {
        'code': 'skillcorner-open',
        'name': 'SkillCorner Open Data',
        'kind': GlobalSportsDataSource.Kind.SKILLCORNER_OPEN,
        'capabilities': ['match_catalog', 'match_metadata', 'tracking_frames'],
        'license_id': 'skillcorner-open-data',
        'license_url': 'https://github.com/SkillCorner/opendata',
        'attribution': 'SkillCorner Open Data — amostra para pesquisa.',
        'quality': 'research_sample',
        'adapter_version': '1.0',
        'schema_version': 'skillcorner-open-2024-25',
        'active': False,
        'operational_status': GlobalSportsDataSource.OperationalStatus.RESEARCH_ONLY,
    },
}


def provision_global_football_data_source():
    values = dict(GLOBAL_FOOTBALL_DATA_SOURCE)
    code = values.pop('code')
    source, _created = GlobalSportsDataSource.objects.update_or_create(
        code=code,
        defaults=values,
    )
    return source


def _provision_global_open_data_source(code):
    values = dict(GLOBAL_OPEN_DATA_SOURCES[code])
    source_code = values.pop('code')
    source, _created = GlobalSportsDataSource.objects.update_or_create(
        code=source_code,
        defaults=values,
    )
    return source


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


def _get_public_json(url):
    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/json',
            'User-Agent': 'SaaSFutebol-ResearchConnector/1.0',
        },
    )
    with safe_urlopen(request, timeout=30) as response:
        try:
            return json.loads(response.read().decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError('A fonte pública retornou JSON inválido.') from exc


def _normalize_skillcorner_match(match):
    match_id = str(match['id'])
    home_team = match.get('home_team') or {}
    away_team = match.get('away_team') or {}
    return {
        'capability': 'match_catalog',
        'provider_record_id': f'match:{match_id}',
        'observed_at': parse_datetime(match.get('date_time') or ''),
        'source_url': f'{SKILLCORNER_OPEN_BASE_URL}/matches.json',
        'payload': {
            'provider_match_id': match_id,
            'scheduled_at': match.get('date_time'),
            'status': match.get('status'),
            'home_team_id': str(home_team.get('id') or ''),
            'home_team': home_team.get('short_name', ''),
            'away_team_id': str(away_team.get('id') or ''),
            'away_team': away_team.get('short_name', ''),
            'competition_id': str(match.get('competition_id') or ''),
            'season_id': str(match.get('season_id') or ''),
        },
        'raw_payload': match,
    }


def _normalize_skillcorner_metadata(metadata):
    match_id = str(metadata['id'])
    home_team = metadata.get('home_team') or {}
    away_team = metadata.get('away_team') or {}
    competition_edition = metadata.get('competition_edition') or {}
    competition = competition_edition.get('competition') or {}
    return {
        'capability': 'match_metadata',
        'provider_record_id': f'match-metadata:{match_id}',
        'observed_at': parse_datetime(metadata.get('date_time') or ''),
        'source_url': (
            f'{SKILLCORNER_OPEN_BASE_URL}/matches/{match_id}/{match_id}_match.json'
        ),
        'payload': {
            'provider_match_id': match_id,
            'home_team': home_team.get('short_name', ''),
            'away_team': away_team.get('short_name', ''),
            'home_score': metadata.get('home_team_score'),
            'away_score': metadata.get('away_team_score'),
            'competition': competition.get('name', ''),
            'area': competition.get('area', ''),
            'players_count': len(metadata.get('players') or []),
            'pitch_size': metadata.get('pitch_size') or {},
            'match_periods': metadata.get('match_periods') or [],
        },
        'raw_payload': metadata,
    }


def _begin_global_open_sync(*, source, dataset_id, trigger):
    return GlobalSportsSyncRun.objects.create(
        source=source,
        dataset_id=dataset_id,
        trigger=(trigger or 'scheduler')[:32],
        started_at=timezone.now(),
    )


@transaction.atomic
def _persist_global_open_dataset(
    *, source, run, dataset_id, dataset_version, raw_document, records, manifest,
):
    """Persiste uma versão global de pesquisa com idempotência e freshness.

    O hash identifica conteúdo; ``published_at`` identifica a observação mais
    recente. Assim, uma sequência A → B → A volta a apontar corretamente para A
    sem duplicar a versão ou seus registros.
    """
    now = timezone.now()
    raw = json.dumps(
        raw_document, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    ).encode('utf-8')
    content_hash = hashlib.sha256(raw).hexdigest()
    batch = GlobalSportsDataBatch.objects.filter(
        source=source,
        dataset_id=dataset_id,
        content_hash=content_hash,
        status=GlobalSportsDataBatch.Status.COMPLETED,
    ).first()
    if batch is None:
        batch = GlobalSportsDataBatch.objects.create(
            source=source,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            content_hash=content_hash,
            status=GlobalSportsDataBatch.Status.PROCESSING,
            manifest=manifest,
            license_id=source.license_id,
            attribution=source.attribution,
            quality=source.quality,
        )
        for record in records:
            canonical_raw = json.dumps(
                record['raw_payload'],
                sort_keys=True,
                separators=(',', ':'),
                ensure_ascii=False,
            ).encode('utf-8')
            provider_updated_at = record.get('observed_at')
            GlobalSportsDataRecord.objects.create(
                source=source,
                batch=batch,
                capability=record['capability'],
                provider_record_id=record['provider_record_id'],
                provider_updated_at=provider_updated_at,
                observed_at=now,
                ingested_at=now,
                expires_at=now + timedelta(days=7),
                payload=record['payload'],
                raw_payload=record['raw_payload'],
                source_url=record['source_url'],
                content_hash=hashlib.sha256(canonical_raw).hexdigest(),
            )
        batch.status = GlobalSportsDataBatch.Status.COMPLETED
        batch.record_count = len(records)
    else:
        batch.records.update(expires_at=now + timedelta(days=7))
    batch.published_at = now
    batch.save(update_fields=[
        'status', 'record_count', 'published_at', 'updated_at',
    ])

    source.active = False
    source.operational_status = GlobalSportsDataSource.OperationalStatus.RESEARCH_ONLY
    source.last_checked_at = now
    source.last_success_at = now
    source.last_error = ''
    source.save(update_fields=[
        'active', 'operational_status', 'last_checked_at', 'last_success_at',
        'last_error', 'updated_at',
    ])
    run.batch = batch
    run.status = GlobalSportsSyncRun.Status.COMPLETED
    run.finished_at = now
    run.error = ''
    run.save(update_fields=[
        'batch', 'status', 'finished_at', 'error', 'updated_at',
    ])
    return run


def _fail_global_open_sync(*, source, run):
    _record_platform_sync_failure(source=source, run=run)


def sync_platform_skillcorner_open(*, max_matches=1, trigger='scheduler'):
    """Rechecagem global do catálogo e metadados públicos da SkillCorner."""
    if not isinstance(max_matches, int) or not 1 <= max_matches <= SKILLCORNER_OPEN_MAX_MATCHES:
        raise ValidationError(
            f'A amostra deve conter entre 1 e {SKILLCORNER_OPEN_MAX_MATCHES} partidas.'
        )
    source = _provision_global_open_data_source('skillcorner-open')
    dataset_id = 'skillcorner-open-controlled-sample'
    run = _begin_global_open_sync(source=source, dataset_id=dataset_id, trigger=trigger)
    try:
        catalog_url = f'{SKILLCORNER_OPEN_BASE_URL}/matches.json'
        catalog = _get_public_json(catalog_url)
        if not isinstance(catalog, list) or not catalog:
            raise ValidationError('O catálogo público da SkillCorner está vazio ou inválido.')
        metadata_items = []
        for match in catalog[:max_matches]:
            match_id = str(match.get('id') or '')
            if not match_id.isdigit():
                raise ValidationError('O catálogo da SkillCorner contém partida inválida.')
            metadata_items.append(_get_public_json(
                f'{SKILLCORNER_OPEN_BASE_URL}/matches/{match_id}/{match_id}_match.json'
            ))
        records = [_normalize_skillcorner_match(match) for match in catalog]
        records.extend(_normalize_skillcorner_metadata(item) for item in metadata_items)
        return _persist_global_open_dataset(
            source=source,
            run=run,
            dataset_id=dataset_id,
            dataset_version=timezone.now().date().isoformat(),
            raw_document={'catalog': catalog, 'metadata': metadata_items},
            records=records,
            manifest={
                'provider': 'SkillCorner Open Data',
                'repository': 'https://github.com/SkillCorner/opendata',
                'catalog_match_count': len(catalog),
                'selected_metadata_count': max_matches,
                'capabilities': ['match_catalog', 'match_metadata'],
                'excluded_large_files': [
                    'tracking_extrapolated', 'dynamic_events', 'phases_of_play',
                    'aggregates',
                ],
                'usage_scope': 'research_only',
                'limits': {'max_matches': max_matches},
            },
        )
    except Exception:
        _fail_global_open_sync(source=source, run=run)
        raise


def sync_skillcorner_open(*, tenant, imported_by, max_matches=1):
    """Sincroniza somente catálogo e metadados pequenos da amostra pública.

    Arquivos de tracking, eventos dinâmicos e agregados não são baixados por
    este adaptador. A fonte permanece ``research_sample`` e ``research_only``.
    """
    raise ValidationError(
        'A ingestão pública por Tenant foi desativada; use '
        'sync_platform_sports_provider na infraestrutura da plataforma.'
    )
    if not isinstance(max_matches, int) or not 1 <= max_matches <= SKILLCORNER_OPEN_MAX_MATCHES:
        raise ValidationError(
            f'A amostra deve conter entre 1 e {SKILLCORNER_OPEN_MAX_MATCHES} partidas.'
        )
    source = next(
        item for item in provision_provider_catalog(tenant=tenant)
        if item.code == 'skillcorner-open'
    )
    catalog_url = f'{SKILLCORNER_OPEN_BASE_URL}/matches.json'
    catalog = _get_public_json(catalog_url)
    if not isinstance(catalog, list) or not catalog:
        raise ValidationError('O catálogo público da SkillCorner está vazio ou inválido.')

    selected = catalog[:max_matches]
    metadata_items = []
    for match in selected:
        match_id = str(match.get('id') or '')
        if not match_id.isdigit():
            raise ValidationError('O catálogo da SkillCorner contém partida inválida.')
        metadata_items.append(_get_public_json(
            f'{SKILLCORNER_OPEN_BASE_URL}/matches/{match_id}/{match_id}_match.json'
        ))
    records = [_normalize_skillcorner_match(match) for match in catalog]
    records.extend(_normalize_skillcorner_metadata(item) for item in metadata_items)
    return _persist_skillcorner_open_sync(
        tenant=tenant,
        imported_by=imported_by,
        source=source,
        catalog=catalog,
        metadata_items=metadata_items,
        records=records,
        max_matches=max_matches,
    )


def sync_skillcorner_tracking(*, tenant, imported_by, match_id):
    """Baixa e publica um artefato privado de tracking, de forma incremental."""
    match_id = str(match_id or '')
    if not match_id.isdigit():
        raise ValidationError('A partida de tracking informada é inválida.')
    source = next(
        item for item in provision_provider_catalog(tenant=tenant)
        if item.code == 'skillcorner-open'
    )
    url = (
        f'{SKILLCORNER_TRACKING_MEDIA_URL}/matches/{match_id}/'
        f'{match_id}_tracking_extrapolated.jsonl'
    )
    request = urllib.request.Request(url, headers={
        'Accept': 'application/x-ndjson',
        'User-Agent': 'SaaSFutebol-ResearchConnector/1.0',
    })
    temporary_path = ''
    saved_name = ''
    saved_storage = None
    try:
        with safe_urlopen(request, timeout=60) as response, tempfile.NamedTemporaryFile(
            suffix='.jsonl', delete=False,
        ) as temporary:
            temporary_path = temporary.name
            digest = hashlib.sha256()
            byte_size = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                byte_size += len(chunk)
                if byte_size > SKILLCORNER_TRACKING_MAX_BYTES:
                    raise ValidationError('O tracking excede o limite de 150 MB por partida.')
                digest.update(chunk)
                temporary.write(chunk)
        content_hash = digest.hexdigest()
        existing = SportsDataArtifact.objects.filter(
            tenant=tenant, batch__source=source, capability='tracking_frames',
            provider_object_id=f'match:{match_id}', content_hash=content_hash,
            status=SportsDataArtifact.Status.READY,
        ).select_related('batch').first()
        if existing:
            return existing.batch
        metadata_record = SportsDataRecord.objects.filter(
            tenant=tenant, source=source, capability='match_metadata',
            payload__provider_match_id=match_id,
        ).order_by('-created_at').first()
        player_teams = {}
        tracking_context = {}
        if metadata_record:
            tracking_context = build_tracking_context(metadata_record.raw_payload)
            for player in metadata_record.raw_payload.get('players') or []:
                player_id = str(player.get('id') or player.get('player_id') or '')
                team = player.get('team') or {}
                team_id = str(player.get('team_id') or team.get('id') or '')
                if player_id and team_id:
                    player_teams[player_id] = team_id
        with open(temporary_path, 'rb') as stream:
            analysis = build_tracking_analysis(parse_tracking_stream(
                stream, player_teams=player_teams,
            ), context=tracking_context)
        analyses_by_team = {}
        for team_id in sorted(set(player_teams.values())):
            with open(temporary_path, 'rb') as stream:
                analyses_by_team[team_id] = build_tracking_analysis(
                    parse_tracking_stream(stream, player_teams=player_teams),
                    team_id=team_id, context=tracking_context,
                )
        if not analysis['frame_count']:
            raise ValidationError('O tracking não contém frames válidos.')

        with transaction.atomic():
            batch = SportsDataImportBatch.objects.create(
                tenant=tenant, source=source,
                dataset_id=f'skillcorner-tracking-{match_id}',
                dataset_version=content_hash[:12], content_hash=content_hash,
                status=SportsDataImportBatch.Status.PROCESSING,
                record_count=0,
                manifest={
                    'provider': 'SkillCorner Open Data', 'provider_match_id': match_id,
                    'capabilities': ['tracking_frames'], 'artifact_count': 1,
                    'frame_count': analysis['frame_count'],
                    'analyzable_frame_count': analysis['analyzable_frame_count'],
                    'usage_scope': 'research_only',
                    'source_url': url,
                },
                license_id=source.license_id, attribution=source.attribution,
                quality='research_sample', imported_by=imported_by,
            )
            artifact = SportsDataArtifact(
                tenant=tenant, batch=batch, capability='tracking_frames',
                provider_object_id=f'match:{match_id}',
                artifact_version=content_hash[:12], schema_version='skillcorner-jsonl-v1',
                format='jsonl', compression='none', content_hash=content_hash,
                byte_size=byte_size, item_count=analysis['frame_count'],
                metadata={
                    'analysis': analysis, 'analyses_by_team': analyses_by_team,
                    'tracking_context': tracking_context, 'tactical_engine': {},
                    'preview_scope': 'primeiros 240 frames',
                },
                status=SportsDataArtifact.Status.READY,
            )
            with open(temporary_path, 'rb') as stream:
                artifact.file.save(f'{match_id}_tracking.jsonl', File(stream), save=False)
            saved_name = artifact.file.name
            saved_storage = artifact.file.storage
            artifact.save()
            engine_context = detect_tactical_moments(
                analysis['preview'],
                team_directions=tracking_context.get('directions_by_period'),
                source_context={
                    'source_code': source.code, 'batch_id': batch.pk,
                    'artifact_id': artifact.pk, 'content_hash': content_hash,
                    'schema_version': artifact.schema_version,
                    'quality': 'research_sample',
                    'license_id': source.license_id, 'attribution': source.attribution,
                    'usage_scope': 'research_only', 'operational_use_allowed': False,
                    'detected_position_ratio': round(analysis['coverage'] / 100, 3),
                },
            )
            artifact.metadata = {**artifact.metadata, 'tactical_engine': engine_context}
            artifact.save(update_fields=['metadata', 'updated_at'])
            batch.status = SportsDataImportBatch.Status.COMPLETED
            batch.imported_at = timezone.now()
            batch.save(update_fields=['status', 'imported_at', 'updated_at'])
            log_audit_event(
                tenant=tenant, actor=imported_by, action='import', obj=batch,
                after_state=snapshot_instance(batch),
            )
            external_system, _ = ExternalSystem.objects.get_or_create(
                tenant=tenant, name='SkillCorner Open Data',
                defaults={
                    'kind': ExternalSystem.Kind.IMPORT,
                    'base_url': 'https://github.com/SkillCorner/opendata',
                    'active': True,
                },
            )
            IntegrationRecord.objects.create(
                tenant=tenant, external_system=external_system,
                correlation_id=f'skillcorner-tracking:{content_hash}',
                external_object_id=f'match-{match_id}',
                payload={
                    'batch_id': batch.pk, 'artifact_id': artifact.pk,
                    'content_hash': content_hash, 'frame_count': analysis['frame_count'],
                    'usage_scope': 'research_only',
                },
                status='processed', processed_at=timezone.now(),
            )
        return batch
    except Exception:
        if saved_name and saved_storage:
            saved_storage.delete(saved_name)
        _record_skillcorner_tracking_failure(
            tenant=tenant, source=source, match_id=match_id,
        )
        raise
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


@transaction.atomic
def _record_skillcorner_tracking_failure(*, tenant, source, match_id):
    source.last_error = 'Falha ao importar ou validar tracking público.'
    source.save(update_fields=['last_error', 'updated_at'])
    external_system, _ = ExternalSystem.objects.get_or_create(
        tenant=tenant, name='SkillCorner Open Data',
        defaults={
            'kind': ExternalSystem.Kind.IMPORT,
            'base_url': 'https://github.com/SkillCorner/opendata', 'active': True,
        },
    )
    IntegrationRecord.objects.create(
        tenant=tenant, external_system=external_system,
        correlation_id=f'skillcorner-tracking:error:{uuid4()}',
        external_object_id=f'match-{match_id}',
        payload={'provider': 'SkillCorner Open Data', 'usage_scope': 'research_only'},
        status='error', processed_at=timezone.now(),
        error_message='Falha ao importar ou validar tracking público.',
    )


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


def _normalize_team_squad(team):
    team_id = str(team.get('id') or '')
    source_url = f'https://api.football-data.org/v4/teams/{team_id}'
    squad = team.get('squad') or []
    records = [{
        'capability': 'team_squad',
        'provider_record_id': f'team:{team_id}:squad',
        'source_url': source_url,
        'payload': {
            'provider_team_id': team_id,
            'team': team.get('name', ''),
            'short_name': team.get('shortName', ''),
            'tla': team.get('tla', ''),
            'crest': team.get('crest', ''),
            'player_ids': [str(player.get('id') or '') for player in squad],
            'player_count': len(squad),
        },
        'raw_payload': team,
    }]
    for player in squad:
        player_id = str(player.get('id') or '')
        if not player_id:
            continue
        records.append({
            'capability': 'player_profile',
            'provider_record_id': f'player:{player_id}',
            'source_url': source_url,
            'payload': {
                'provider_player_id': player_id,
                'provider_team_id': team_id,
                'team': team.get('name', ''),
                'name': player.get('name', ''),
                'position': player.get('position', ''),
                'date_of_birth': player.get('dateOfBirth'),
                'nationality': player.get('nationality', ''),
            },
            'raw_payload': player,
        })
    return records


def _fixture_team_ids(matches_payload, max_teams, explicit_team_ids=()):
    if max_teams == 0:
        return []
    team_ids = list(explicit_team_ids)
    if len(team_ids) == max_teams:
        return team_ids
    matches = list(matches_payload.get('matches', []))
    upcoming_statuses = {'SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED'}
    upcoming = [match for match in matches if match.get('status') in upcoming_statuses]
    matches = sorted(
        upcoming or matches,
        key=lambda match: match.get('utcDate') or '',
    )
    for match in matches:
        for side in ('homeTeam', 'awayTeam'):
            team_id = str((match.get(side) or {}).get('id') or '')
            if team_id and team_id not in team_ids:
                team_ids.append(team_id)
                if len(team_ids) == max_teams:
                    return team_ids
    return team_ids


def _validate_explicit_team_ids(team_ids, max_teams):
    normalized = []
    for raw_team_id in team_ids or ():
        team_id = str(raw_team_id or '').strip()
        if not team_id.isdigit():
            raise ValidationError('Os IDs explícitos de equipes devem ser numéricos.')
        if team_id not in normalized:
            normalized.append(team_id)
    if len(normalized) > max_teams:
        raise ValidationError(
            'A quantidade de equipes explícitas não pode exceder o limite do ciclo.'
        )
    return tuple(normalized)


def sync_platform_football_data(
    *, api_key, competition_code='BSA', max_teams=0, team_ids=(), trigger='scheduler',
):
    """Atualiza a Base Esportiva Global sem depender de Tenant ou usuário."""
    if not (api_key or '').strip():
        raise ValidationError('Configure a credencial do football-data.org no ambiente.')
    competition_code = (competition_code or '').strip().upper()
    if not competition_code.isalnum() or len(competition_code) > 12:
        raise ValidationError('Código de competição inválido.')
    if not isinstance(max_teams, int) or not 0 <= max_teams <= 20:
        raise ValidationError('O limite de equipes por ciclo deve estar entre 0 e 20.')
    team_ids = _validate_explicit_team_ids(team_ids, max_teams)
    source = provision_global_football_data_source()
    dataset_id = f'competition-{competition_code.lower()}'
    started_at = timezone.now()
    run = GlobalSportsSyncRun.objects.create(
        source=source,
        dataset_id=dataset_id,
        trigger=(trigger or 'scheduler')[:32],
        started_at=started_at,
    )
    base = f'https://api.football-data.org/v4/competitions/{competition_code}'
    try:
        matches_payload, matches_rate = _get_json(f'{base}/matches', api_key=api_key)
        standings_payload, standings_rate = _get_json(f'{base}/standings', api_key=api_key)
        records = _normalize_matches(matches_payload) + _normalize_standings(
            standings_payload, competition_code,
        )
        run = _persist_platform_football_data(
            source=source,
            run=run,
            competition_code=competition_code,
            matches_payload=matches_payload,
            standings_payload=standings_payload,
            records=records,
            rate_limit={'matches': matches_rate, 'standings': standings_rate},
        )
    except Exception:
        _record_platform_sync_failure(source=source, run=run)
        raise

    teams_rate = []
    team_failures = []
    for team_id in _fixture_team_ids(matches_payload, max_teams, team_ids):
        team_run = _begin_global_open_sync(
            source=source,
            dataset_id=f'team-{team_id}-squad',
            trigger=trigger,
        )
        try:
            team, rate_limit = _get_json(
                f'https://api.football-data.org/v4/teams/{team_id}', api_key=api_key,
            )
            teams_rate.append({'team_id': team_id, **rate_limit})
            _persist_platform_team_squad(
                source=source,
                run=team_run,
                team=team,
                records=_normalize_team_squad(team),
                rate_limit=rate_limit,
            )
            requests_available = rate_limit.get('requests_available')
            if requests_available is not None:
                try:
                    if int(requests_available) <= 1:
                        break
                except (TypeError, ValueError):
                    logger.warning('Header X-RequestsAvailable inválido: %r', requests_available)
        except Exception:
            _record_platform_sync_failure(source=source, run=team_run)
            logger.exception('Falha ao atualizar o elenco global da equipe %s.', team_id)
            team_failures.append(team_id)
    run.rate_limit = {
        **run.rate_limit,
        'teams': teams_rate,
        'team_failures': team_failures,
    }
    run.save(update_fields=['rate_limit', 'updated_at'])
    if team_failures:
        raise ValidationError(
            'A competição foi atualizada, mas falhou a atualização dos elencos: '
            + ', '.join(team_failures)
        )
    try:
        from futebol.services.coach_workspace import refresh_all_materialized_provider_matches
        refresh_all_materialized_provider_matches()
    except Exception:
        logger.exception(
            'A Base Esportiva Global foi atualizada, mas uma projeção de Tenant falhou.'
        )
    return run


@transaction.atomic
def _persist_platform_football_data(
    *, source, run, competition_code, matches_payload, standings_payload,
    records, rate_limit,
):
    now = timezone.now()
    raw = json.dumps(
        {
            'matches': matches_payload,
            'standings': standings_payload,
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')
    content_hash = hashlib.sha256(raw).hexdigest()
    dataset_id = f'competition-{competition_code.lower()}'
    batch = GlobalSportsDataBatch.objects.filter(
        source=source,
        dataset_id=dataset_id,
        content_hash=content_hash,
        status=GlobalSportsDataBatch.Status.COMPLETED,
    ).first()
    if batch is None:
        batch = GlobalSportsDataBatch.objects.create(
            source=source,
            dataset_id=dataset_id,
            dataset_version=now.date().isoformat(),
            content_hash=content_hash,
            status=GlobalSportsDataBatch.Status.PROCESSING,
            manifest={
                'provider': 'football-data.org',
                'competition': competition_code,
                'capabilities': ['fixtures_results', 'standings_form'],
            },
            license_id=source.license_id,
            attribution=source.attribution,
            quality=source.quality,
        )
        for record in records:
            canonical_raw = json.dumps(
                record['raw_payload'],
                sort_keys=True,
                separators=(',', ':'),
                ensure_ascii=False,
            ).encode('utf-8')
            GlobalSportsDataRecord.objects.create(
                source=source,
                batch=batch,
                capability=record['capability'],
                provider_record_id=record['provider_record_id'],
                provider_updated_at=parse_datetime(
                    str(record['raw_payload'].get('lastUpdated') or '')
                ),
                observed_at=now,
                ingested_at=now,
                expires_at=now + timedelta(hours=24),
                payload=record['payload'],
                raw_payload=record['raw_payload'],
                source_url=record['source_url'],
                content_hash=hashlib.sha256(canonical_raw).hexdigest(),
            )
        batch.status = GlobalSportsDataBatch.Status.COMPLETED
        batch.record_count = len(records)
        batch.published_at = now
        batch.save(update_fields=[
            'status', 'record_count', 'published_at', 'updated_at',
        ])
    else:
        batch.records.update(expires_at=now + timedelta(hours=24))
        batch.published_at = now
        batch.save(update_fields=['published_at', 'updated_at'])

    source.active = True
    source.operational_status = GlobalSportsDataSource.OperationalStatus.ACTIVE
    source.last_checked_at = now
    source.last_success_at = now
    source.last_error = ''
    source.save(update_fields=[
        'active', 'operational_status', 'last_checked_at', 'last_success_at',
        'last_error', 'updated_at',
    ])
    run.batch = batch
    run.status = GlobalSportsSyncRun.Status.COMPLETED
    run.finished_at = now
    run.rate_limit = rate_limit
    run.error = ''
    run.save(update_fields=[
        'batch', 'status', 'finished_at', 'rate_limit', 'error', 'updated_at',
    ])
    return run


@transaction.atomic
def _persist_platform_team_squad(*, source, run, team, records, rate_limit):
    """Atualiza somente o dataset do elenco efetivamente observado."""
    now = timezone.now()
    team_id = str(team.get('id') or '')
    if not team_id:
        raise ValidationError('A equipe retornada pelo provider não possui identificador.')
    dataset_id = f'team-{team_id}-squad'
    raw = json.dumps(
        team, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    ).encode('utf-8')
    content_hash = hashlib.sha256(raw).hexdigest()
    batch = GlobalSportsDataBatch.objects.filter(
        source=source,
        dataset_id=dataset_id,
        content_hash=content_hash,
        status=GlobalSportsDataBatch.Status.COMPLETED,
    ).first()
    if batch is None:
        batch = GlobalSportsDataBatch.objects.create(
            source=source,
            dataset_id=dataset_id,
            dataset_version=(team.get('lastUpdated') or now.isoformat())[:80],
            content_hash=content_hash,
            status=GlobalSportsDataBatch.Status.PROCESSING,
            manifest={
                'provider': 'football-data.org',
                'provider_team_id': team_id,
                'team': team.get('name', ''),
                'capabilities': ['team_squad', 'player_profile'],
            },
            license_id=source.license_id,
            attribution=source.attribution,
            quality=source.quality,
        )
        for record in records:
            canonical_raw = json.dumps(
                record['raw_payload'],
                sort_keys=True,
                separators=(',', ':'),
                ensure_ascii=False,
            ).encode('utf-8')
            GlobalSportsDataRecord.objects.create(
                source=source,
                batch=batch,
                capability=record['capability'],
                provider_record_id=record['provider_record_id'],
                provider_updated_at=parse_datetime(str(team.get('lastUpdated') or '')),
                observed_at=now,
                ingested_at=now,
                expires_at=now + timedelta(hours=24),
                payload=record['payload'],
                raw_payload=record['raw_payload'],
                source_url=record['source_url'],
                content_hash=hashlib.sha256(canonical_raw).hexdigest(),
            )
        batch.status = GlobalSportsDataBatch.Status.COMPLETED
        batch.record_count = len(records)
    else:
        batch.records.update(expires_at=now + timedelta(hours=24))
    batch.published_at = now
    batch.save(update_fields=[
        'status', 'record_count', 'published_at', 'updated_at',
    ])

    source.active = True
    source.operational_status = GlobalSportsDataSource.OperationalStatus.ACTIVE
    source.last_checked_at = now
    source.last_success_at = now
    source.last_error = ''
    source.save(update_fields=[
        'active', 'operational_status', 'last_checked_at', 'last_success_at',
        'last_error', 'updated_at',
    ])
    run.batch = batch
    run.status = GlobalSportsSyncRun.Status.COMPLETED
    run.finished_at = now
    run.rate_limit = rate_limit
    run.error = ''
    run.save(update_fields=[
        'batch', 'status', 'finished_at', 'rate_limit', 'error', 'updated_at',
    ])
    return run


@transaction.atomic
def _record_platform_sync_failure(*, source, run):
    now = timezone.now()
    message = 'Falha de comunicação ou validação do provider.'
    source.operational_status = GlobalSportsDataSource.OperationalStatus.DEGRADED
    source.last_checked_at = now
    source.last_error = message
    source.save(update_fields=[
        'operational_status', 'last_checked_at', 'last_error', 'updated_at',
    ])
    run.status = GlobalSportsSyncRun.Status.FAILED
    run.finished_at = now
    run.error = message
    run.save(update_fields=['status', 'finished_at', 'error', 'updated_at'])


def sync_football_data_org(*, tenant, imported_by, api_key, competition_code='BSA'):
    raise ValidationError(
        'A ingestão pública por Tenant foi desativada; use '
        'sync_platform_sports_provider na infraestrutura da plataforma.'
    )
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
    batch = _persist_football_data_sync(
        tenant=tenant,
        imported_by=imported_by,
        source=source,
        competition_code=competition_code,
        matches_payload=matches_payload,
        standings_payload=standings_payload,
        records=records,
        rate_limit={'matches': matches_rate, 'standings': standings_rate},
    )
    from futebol.services.coach_workspace import refresh_materialized_provider_matches
    refresh_materialized_provider_matches(tenant=tenant)
    return batch


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
        now = timezone.now()
        existing.records.update(observed_at=now, expires_at=now + timedelta(hours=24))
        existing.imported_at = now
        existing.save(update_fields=['imported_at', 'updated_at'])
        source.active = True
        source.operational_status = SportsDataSource.OperationalStatus.ACTIVE
        source.last_sync_at = now
        source.last_error = ''
        source.save(update_fields=[
            'active', 'operational_status', 'last_sync_at', 'last_error', 'updated_at',
        ])
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


@transaction.atomic
def _persist_skillcorner_open_sync(
    *, tenant, imported_by, source, catalog, metadata_items, records, max_matches,
):
    raw = json.dumps(
        {'catalog': catalog, 'metadata': metadata_items},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    ).encode('utf-8')
    content_hash = hashlib.sha256(raw).hexdigest()
    dataset_id = 'a-league-2024-25-controlled-sample'
    existing = SportsDataImportBatch.objects.filter(
        tenant=tenant,
        source=source,
        dataset_id=dataset_id,
        content_hash=content_hash,
        status=SportsDataImportBatch.Status.COMPLETED,
    ).first()
    if existing:
        now = timezone.now()
        existing.imported_at = now
        existing.save(update_fields=['imported_at', 'updated_at'])
        source.last_sync_at = now
        source.last_error = ''
        source.operational_status = SportsDataSource.OperationalStatus.RESEARCH_ONLY
        source.save(update_fields=[
            'last_sync_at', 'last_error', 'operational_status', 'updated_at',
        ])
        return existing

    now = timezone.now()
    batch = SportsDataImportBatch.objects.create(
        tenant=tenant,
        source=source,
        dataset_id=dataset_id,
        dataset_version='2024-25',
        content_hash=content_hash,
        status=SportsDataImportBatch.Status.PROCESSING,
        manifest={
            'provider': 'SkillCorner Open Data',
            'repository': 'https://github.com/SkillCorner/opendata',
            'catalog_url': f'{SKILLCORNER_OPEN_BASE_URL}/matches.json',
            'selected_metadata_count': max_matches,
            'catalog_match_count': len(catalog),
            'capabilities': ['match_catalog', 'match_metadata'],
            'excluded_large_files': [
                'tracking_extrapolated', 'dynamic_events', 'phases_of_play', 'aggregates',
            ],
            'usage_scope': 'research_only',
        },
        license_id=source.license_id,
        attribution=source.attribution,
        quality='research_sample',
        imported_by=imported_by,
    )
    for record in records:
        canonical_raw = json.dumps(
            record['raw_payload'], sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        ).encode('utf-8')
        SportsDataRecord.objects.create(
            tenant=tenant,
            source=source,
            batch=batch,
            capability=record['capability'],
            provider_record_id=record['provider_record_id'],
            observed_at=record['observed_at'],
            payload=record['payload'],
            raw_payload=record['raw_payload'],
            source_url=record['source_url'],
            content_hash=hashlib.sha256(canonical_raw).hexdigest(),
            expires_at=None,
        )
    batch.status = SportsDataImportBatch.Status.COMPLETED
    batch.record_count = len(records)
    batch.imported_at = now
    batch.save(update_fields=['status', 'record_count', 'imported_at', 'updated_at'])

    # Uma sincronização bem-sucedida não transforma dado de amostra em fonte produtiva.
    source.active = False
    source.operational_status = SportsDataSource.OperationalStatus.RESEARCH_ONLY
    source.last_sync_at = now
    source.last_error = ''
    source.save(update_fields=[
        'active', 'operational_status', 'last_sync_at', 'last_error', 'updated_at',
    ])
    external_system, _ = ExternalSystem.objects.get_or_create(
        tenant=tenant,
        name='SkillCorner Open Data',
        defaults={
            'kind': ExternalSystem.Kind.IMPORT,
            'base_url': 'https://github.com/SkillCorner/opendata',
            'active': True,
        },
    )
    IntegrationRecord.objects.get_or_create(
        tenant=tenant,
        external_system=external_system,
        correlation_id=f'skillcorner-open:{content_hash}',
        defaults={
            'external_object_id': dataset_id,
            'payload': {
                'batch_id': batch.pk,
                'record_count': batch.record_count,
                'content_hash': content_hash,
                'quality': 'research_sample',
                'usage_scope': 'research_only',
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


def _validate_statsbomb_sample(*, competition_id, season_id, max_matches, max_events):
    identifiers = (str(competition_id).strip(), str(season_id).strip())
    if any(not value.isdigit() for value in identifiers):
        raise ValidationError('Competição e temporada do StatsBomb devem ser IDs numéricos.')
    if not 1 <= max_matches <= STATSBOMB_MAX_MATCHES:
        raise ValidationError(
            f'A amostra aceita entre 1 e {STATSBOMB_MAX_MATCHES} partidas.'
        )
    if not 1 <= max_events <= STATSBOMB_MAX_EVENTS_PER_MATCH:
        raise ValidationError(
            f'A amostra aceita entre 1 e {STATSBOMB_MAX_EVENTS_PER_MATCH} eventos por partida.'
        )
    return identifiers


def _normalize_statsbomb_match(match, matches_url):
    match_id = str(match['match_id'])
    return {
        'capability': 'fixtures_results',
        'provider_record_id': f'match:{match_id}',
        'source_url': matches_url,
        'payload': {
            'provider_match_id': match_id,
            'scheduled_at': ' '.join(filter(None, [match.get('match_date'), match.get('kick_off')])),
            'status': 'FINISHED',
            'home_team_id': str(match.get('home_team', {}).get('home_team_id') or ''),
            'home_team': match.get('home_team', {}).get('home_team_name', ''),
            'away_team_id': str(match.get('away_team', {}).get('away_team_id') or ''),
            'away_team': match.get('away_team', {}).get('away_team_name', ''),
            'score': {
                'home': match.get('home_score'),
                'away': match.get('away_score'),
            },
        },
        'raw_payload': match,
    }


def _normalize_statsbomb_event(event, match_id):
    event_id = str(event['id'])
    event_type = event.get('type', {})
    player = event.get('player', {})
    team = event.get('team', {})
    pass_data = event.get('pass') or {}
    shot_data = event.get('shot') or {}
    return {
        'capability': 'event_stream',
        'provider_record_id': f'event:{match_id}:{event_id}',
        'source_url': f'{STATSBOMB_OPEN_BASE_URL}/events/{match_id}.json',
        'payload': {
            'provider_match_id': str(match_id),
            'provider_event_id': event_id,
            'index': event.get('index'),
            'period': event.get('period'),
            'timestamp': event.get('timestamp'),
            'event_type_id': str(event_type.get('id') or ''),
            'event_type': event_type.get('name', ''),
            'team_id': str(team.get('id') or ''),
            'team': team.get('name', ''),
            'player_id': str(player.get('id') or ''),
            'player': player.get('name', ''),
            'location': event.get('location', []),
            'duration': event.get('duration'),
            'possession': event.get('possession'),
            'pass': {
                'end_location': pass_data.get('end_location', []),
                'recipient_id': str((pass_data.get('recipient') or {}).get('id') or ''),
                'recipient': (pass_data.get('recipient') or {}).get('name', ''),
                'outcome': (pass_data.get('outcome') or {}).get('name', ''),
            } if pass_data else {},
            'shot': {
                'end_location': shot_data.get('end_location', []),
                'xg': shot_data.get('statsbomb_xg'),
                'outcome': (shot_data.get('outcome') or {}).get('name', ''),
                'body_part': (shot_data.get('body_part') or {}).get('name', ''),
                'technique': (shot_data.get('technique') or {}).get('name', ''),
            } if shot_data else {},
        },
        'raw_payload': event,
    }


def sync_platform_statsbomb_open(
    *, competition_id, season_id, max_matches=1, max_events=200,
    trigger='scheduler',
):
    """Rechecagem global e limitada da amostra oficial StatsBomb Open Data."""
    competition_id, season_id = _validate_statsbomb_sample(
        competition_id=competition_id,
        season_id=season_id,
        max_matches=max_matches,
        max_events=max_events,
    )
    source = _provision_global_open_data_source('statsbomb-open')
    dataset_id = f'competition-{competition_id}-season-{season_id}-sample'
    run = _begin_global_open_sync(source=source, dataset_id=dataset_id, trigger=trigger)
    try:
        matches_url = (
            f'{STATSBOMB_OPEN_BASE_URL}/matches/{competition_id}/{season_id}.json'
        )
        matches_payload = _get_public_json(matches_url)
        if not isinstance(matches_payload, list):
            raise ValidationError('A lista de partidas do StatsBomb é inválida.')
        selected_matches = matches_payload[:max_matches]
        records = []
        raw_events = {}
        for match in selected_matches:
            match_id = str(match.get('match_id') or '')
            if not match_id.isdigit():
                raise ValidationError('Partida do StatsBomb sem identificador válido.')
            records.append(_normalize_statsbomb_match(match, matches_url))
            events = _get_public_json(
                f'{STATSBOMB_OPEN_BASE_URL}/events/{match_id}.json'
            )
            if not isinstance(events, list):
                raise ValidationError('A lista de eventos do StatsBomb é inválida.')
            raw_events[match_id] = events[:max_events]
            records.extend(
                _normalize_statsbomb_event(event, match_id)
                for event in raw_events[match_id]
            )
        limits = {
            'max_matches': max_matches,
            'max_events_per_match': max_events,
        }
        return _persist_global_open_dataset(
            source=source,
            run=run,
            dataset_id=dataset_id,
            dataset_version=timezone.now().date().isoformat(),
            raw_document={'matches': selected_matches, 'events': raw_events},
            records=records,
            manifest={
                'provider': 'StatsBomb Open Data',
                'competition_id': competition_id,
                'season_id': season_id,
                'capabilities': ['fixtures_results', 'event_stream'],
                'limits': limits,
                'research_only': True,
                'repository': 'https://github.com/statsbomb/open-data',
            },
        )
    except Exception:
        _fail_global_open_sync(source=source, run=run)
        raise


def sync_statsbomb_open(
    *, tenant, imported_by, competition_id, season_id, max_matches=1, max_events=200
):
    """Importa uma amostra pequena do repositório oficial, exclusivamente para P&D."""
    raise ValidationError(
        'A ingestão pública por Tenant foi desativada; use '
        'sync_platform_sports_provider na infraestrutura da plataforma.'
    )
    competition_id, season_id = _validate_statsbomb_sample(
        competition_id=competition_id,
        season_id=season_id,
        max_matches=max_matches,
        max_events=max_events,
    )
    source = next(
        item for item in provision_provider_catalog(tenant=tenant)
        if item.code == 'statsbomb-open'
    )
    matches_url = (
        f'{STATSBOMB_OPEN_BASE_URL}/matches/{competition_id}/{season_id}.json'
    )
    matches_payload = _get_public_json(matches_url)
    if not isinstance(matches_payload, list):
        raise ValidationError('A lista de partidas do StatsBomb é inválida.')
    selected_matches = matches_payload[:max_matches]
    records = []
    raw_events = {}
    for match in selected_matches:
        match_id = str(match.get('match_id') or '')
        if not match_id.isdigit():
            raise ValidationError('Partida do StatsBomb sem identificador válido.')
        records.append(_normalize_statsbomb_match(match, matches_url))
        events = _get_public_json(f'{STATSBOMB_OPEN_BASE_URL}/events/{match_id}.json')
        if not isinstance(events, list):
            raise ValidationError('A lista de eventos do StatsBomb é inválida.')
        raw_events[match_id] = events[:max_events]
        records.extend(
            _normalize_statsbomb_event(event, match_id)
            for event in raw_events[match_id]
        )
    return _persist_statsbomb_open_sync(
        tenant=tenant,
        imported_by=imported_by,
        source=source,
        competition_id=competition_id,
        season_id=season_id,
        selected_matches=selected_matches,
        raw_events=raw_events,
        records=records,
        limits={'max_matches': max_matches, 'max_events_per_match': max_events},
    )


@transaction.atomic
def _persist_statsbomb_open_sync(
    *, tenant, imported_by, source, competition_id, season_id, selected_matches,
    raw_events, records, limits,
):
    raw_document = {'matches': selected_matches, 'events': raw_events}
    raw = json.dumps(
        raw_document, sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode('utf-8')
    content_hash = hashlib.sha256(raw).hexdigest()
    dataset_id = f'competition-{competition_id}-season-{season_id}-sample'
    existing = SportsDataImportBatch.objects.filter(
        tenant=tenant, source=source, dataset_id=dataset_id,
        content_hash=content_hash, status=SportsDataImportBatch.Status.COMPLETED,
    ).first()
    if existing:
        now = timezone.now()
        existing.imported_at = now
        existing.save(update_fields=['imported_at', 'updated_at'])
        source.last_sync_at = now
        source.last_error = ''
        source.operational_status = SportsDataSource.OperationalStatus.RESEARCH_ONLY
        source.save(update_fields=[
            'last_sync_at', 'last_error', 'operational_status', 'updated_at',
        ])
        return existing

    now = timezone.now()
    batch = SportsDataImportBatch.objects.create(
        tenant=tenant, source=source, dataset_id=dataset_id,
        dataset_version=content_hash[:12], content_hash=content_hash,
        status=SportsDataImportBatch.Status.PROCESSING,
        manifest={
            'provider': 'StatsBomb Open Data',
            'competition_id': competition_id,
            'season_id': season_id,
            'capabilities': ['fixtures_results', 'event_stream'],
            'limits': limits,
            'research_only': True,
            'repository': 'https://github.com/statsbomb/open-data',
        },
        license_id=source.license_id, attribution=source.attribution,
        quality='research_sample', imported_by=imported_by,
    )
    for record in records:
        record_raw = json.dumps(
            record['raw_payload'], sort_keys=True, separators=(',', ':'), ensure_ascii=False
        ).encode('utf-8')
        SportsDataRecord.objects.create(
            tenant=tenant, source=source, batch=batch,
            capability=record['capability'],
            provider_record_id=record['provider_record_id'], observed_at=now,
            payload=record['payload'], raw_payload=record['raw_payload'],
            source_url=record['source_url'],
            content_hash=hashlib.sha256(record_raw).hexdigest(),
        )
    batch.status = SportsDataImportBatch.Status.COMPLETED
    batch.record_count = len(records)
    batch.imported_at = now
    batch.save(update_fields=['status', 'record_count', 'imported_at', 'updated_at'])
    # A sincronização nunca promove uma amostra aberta a fonte de produção.
    source.active = False
    source.operational_status = SportsDataSource.OperationalStatus.RESEARCH_ONLY
    source.last_sync_at = now
    source.last_error = ''
    source.save(update_fields=[
        'active', 'operational_status', 'last_sync_at', 'last_error', 'updated_at',
    ])
    external_system, _ = ExternalSystem.objects.get_or_create(
        tenant=tenant, name='StatsBomb Open Data',
        defaults={
            'kind': ExternalSystem.Kind.IMPORT,
            'base_url': 'https://github.com/statsbomb/open-data',
            'active': True,
        },
    )
    IntegrationRecord.objects.get_or_create(
        tenant=tenant, external_system=external_system,
        correlation_id=f'statsbomb-open:{content_hash}',
        defaults={
            'external_object_id': dataset_id,
            'payload': {
                'batch_id': batch.pk, 'competition_id': competition_id,
                'season_id': season_id, 'record_count': batch.record_count,
                'content_hash': content_hash, 'research_only': True,
            },
            'status': 'processed', 'processed_at': now,
        },
    )
    log_audit_event(
        tenant=tenant, actor=imported_by, action='import', obj=batch,
        after_state=snapshot_instance(batch),
    )
    return batch
