from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from futebol.models import SportsDataImportBatch, SportsDataRecord, SportsDataSource
from futebol.services.audit import log_audit_event, snapshot_instance


SAFE_DATASET_ID = re.compile(r'^[a-z0-9][a-z0-9-]{0,119}$')
MAX_MANIFEST_BYTES = 64 * 1024
MAX_DATA_FILE_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 10_000
ALLOWED_CAPABILITIES = {
    'fixtures_results',
    'standings_form',
    'lineups_events',
    'event_stream',
    'xg',
    'tracking_frames',
    'physical_metrics',
}


def _read_json(path: Path, *, max_bytes: int):
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ValidationError(f'O arquivo {path.name} excede o tamanho permitido.')
    try:
        return json.loads(raw.decode('utf-8')), raw
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f'O arquivo {path.name} não contém JSON UTF-8 válido.') from exc


def _safe_child(root: Path, relative_name: str) -> Path:
    if not relative_name or Path(relative_name).name != relative_name:
        raise ValidationError('O manifesto contém um caminho de arquivo inseguro.')
    unresolved = root / relative_name
    if unresolved.is_symlink():
        raise ValidationError('O manifesto contém um caminho fora da raiz permitida.')
    candidate = unresolved.resolve()
    if candidate.parent != root.resolve():
        raise ValidationError('O manifesto contém um caminho fora da raiz permitida.')
    return candidate


def _validate_record(record, capability):
    if not isinstance(record, dict):
        raise ValidationError(f'Registro inválido na capacidade {capability}.')
    provider_record_id = record.get('provider_record_id')
    payload = record.get('payload')
    if not isinstance(provider_record_id, str) or not provider_record_id.strip():
        raise ValidationError('Todo registro exige provider_record_id textual.')
    if not isinstance(payload, dict):
        raise ValidationError('Todo registro exige payload em objeto JSON.')


def _parse_optional_datetime(record, field_name):
    if field_name not in record or record[field_name] is None:
        return None
    raw_value = record[field_name]
    parsed_value = parse_datetime(raw_value) if isinstance(raw_value, str) else None
    if parsed_value is None:
        raise ValidationError(f'O registro contém {field_name} inválido.')
    return parsed_value


@transaction.atomic
def import_local_sports_dataset(*, tenant, dataset_slug, imported_by, root):
    if not SAFE_DATASET_ID.fullmatch(dataset_slug or ''):
        raise ValidationError('Informe um identificador seguro para o dataset.')
    root = Path(root).resolve()
    unresolved_dataset_dir = root / dataset_slug
    if unresolved_dataset_dir.is_symlink():
        raise ValidationError('Dataset inexistente ou fora da raiz configurada.')
    dataset_dir = unresolved_dataset_dir.resolve()
    if dataset_dir.parent != root or not dataset_dir.is_dir():
        raise ValidationError('Dataset inexistente ou fora da raiz configurada.')

    manifest, manifest_raw = _read_json(
        dataset_dir / 'manifest.json', max_bytes=MAX_MANIFEST_BYTES
    )
    required = {'dataset_id', 'version', 'license_id', 'attribution', 'quality', 'files'}
    if not isinstance(manifest, dict) or not required.issubset(manifest):
        raise ValidationError('Manifesto incompleto para a Fonte de Dados Esportivos.')
    if manifest['dataset_id'] != dataset_slug:
        raise ValidationError('O identificador do manifesto diverge do diretório do dataset.')
    if not isinstance(manifest['files'], dict) or not manifest['files']:
        raise ValidationError('O manifesto precisa declarar ao menos um arquivo de dados.')

    loaded = []
    content_hasher = hashlib.sha256(manifest_raw)
    total_records = 0
    for capability, file_spec in sorted(manifest['files'].items()):
        if capability not in ALLOWED_CAPABILITIES:
            raise ValidationError(f'Capacidade não suportada: {capability}.')
        if not isinstance(file_spec, dict) or not {'path', 'sha256'}.issubset(file_spec):
            raise ValidationError(f'Arquivo incompleto no manifesto: {capability}.')
        data_path = _safe_child(dataset_dir, file_spec['path'])
        records, raw = _read_json(data_path, max_bytes=MAX_DATA_FILE_BYTES)
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != file_spec['sha256']:
            raise ValidationError(f'O hash não confere para {data_path.name}.')
        if not isinstance(records, list):
            raise ValidationError(f'O arquivo {data_path.name} precisa conter uma lista.')
        for record in records:
            _validate_record(record, capability)
        total_records += len(records)
        if total_records > MAX_RECORDS:
            raise ValidationError('O dataset excede o limite de registros por importação.')
        content_hasher.update(capability.encode('utf-8'))
        content_hasher.update(actual_hash.encode('ascii'))
        loaded.append((capability, records))

    source, _created = SportsDataSource.objects.update_or_create(
        tenant=tenant,
        code=dataset_slug,
        defaults={
            'name': manifest.get('name') or dataset_slug,
            'kind': SportsDataSource.Kind.LOCAL_DATASET,
            'capabilities': sorted(manifest['files']),
            'license_id': manifest['license_id'],
            'license_url': manifest.get('license_url', ''),
            'attribution': manifest['attribution'],
            'quality': manifest['quality'],
            'active': True,
        },
    )
    source = SportsDataSource.objects.select_for_update().get(pk=source.pk)
    content_hash = content_hasher.hexdigest()
    existing = SportsDataImportBatch.objects.filter(
        tenant=tenant,
        source=source,
        dataset_id=manifest['dataset_id'],
        dataset_version=str(manifest['version']),
        content_hash=content_hash,
        status=SportsDataImportBatch.Status.COMPLETED,
    ).first()
    if existing:
        return existing

    batch = SportsDataImportBatch.objects.create(
        tenant=tenant,
        source=source,
        dataset_id=manifest['dataset_id'],
        dataset_version=str(manifest['version']),
        content_hash=content_hash,
        status=SportsDataImportBatch.Status.PROCESSING,
        manifest=manifest,
        license_id=manifest['license_id'],
        attribution=manifest['attribution'],
        quality=manifest['quality'],
        imported_by=imported_by,
    )
    for capability, records in loaded:
        for record in records:
            record_hash = hashlib.sha256(
                json.dumps(record, sort_keys=True, separators=(',', ':')).encode('utf-8')
            ).hexdigest()
            observed_at = _parse_optional_datetime(record, 'observed_at')
            expires_at = _parse_optional_datetime(record, 'expires_at')
            if observed_at and expires_at and expires_at < observed_at:
                raise ValidationError('O registro contém expires_at anterior a observed_at.')
            SportsDataRecord.objects.create(
                tenant=tenant,
                source=source,
                batch=batch,
                capability=capability,
                provider_record_id=record['provider_record_id'],
                observed_at=observed_at,
                payload=record['payload'],
                source_url=record.get('source_url', ''),
                content_hash=record_hash,
                expires_at=expires_at,
            )
    batch.status = SportsDataImportBatch.Status.COMPLETED
    batch.record_count = total_records
    batch.imported_at = timezone.now()
    batch.save(update_fields=['status', 'record_count', 'imported_at', 'updated_at'])
    log_audit_event(
        tenant=tenant,
        actor=imported_by,
        action='import',
        obj=batch,
        after_state=snapshot_instance(batch),
    )
    return batch
