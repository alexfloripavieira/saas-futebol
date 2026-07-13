"""Contração segura das cópias públicas legadas por Tenant."""

from dataclasses import dataclass
import hashlib
import json

from django.db import transaction

from futebol.models import GlobalSportsDataBatch, SportsDataSource


RETIRABLE_PUBLIC_CONTRACTS = {
    'football-data-org': {
        'kind': SportsDataSource.Kind.FOOTBALL_DATA_ORG,
        'license_id': 'football-data-org-terms',
        'adapter_version': '1.0',
        'schema_version': 'football-data-v4',
    },
    'statsbomb-open': {
        'kind': SportsDataSource.Kind.STATSBOMB_OPEN,
        'license_id': 'statsbomb-open-data',
        'adapter_version': '1.0',
        'schema_version': 'statsbomb-open-v1.1',
    },
}


@dataclass(frozen=True)
class LegacyPublicCopiesReport:
    sources: int
    batches: int
    records: int
    skipped_artifact_batches: int
    skipped_unverified_batches: int


def _contract_matches(source, contract):
    return all(getattr(source, field) == value for field, value in contract.items())


def _record_signature(record):
    document = {
        'capability': record.capability,
        'provider_record_id': record.provider_record_id,
        'payload': record.payload,
        'raw_payload': record.raw_payload,
        'source_url': record.source_url,
        'content_hash': record.content_hash,
    }
    return hashlib.sha256(json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()


def _has_identical_native_global_copy(source, batch):
    global_batches = GlobalSportsDataBatch.objects.filter(
        source__code=source.code,
        dataset_id=batch.dataset_id,
        content_hash=batch.content_hash,
        status=GlobalSportsDataBatch.Status.COMPLETED,
        sync_runs__status='completed',
    ).distinct()
    legacy_signatures = sorted(_record_signature(record) for record in batch.records.all())
    for global_batch in global_batches:
        global_signatures = sorted(
            _record_signature(record) for record in global_batch.records.all()
        )
        if legacy_signatures == global_signatures:
            return True
    return False


def inspect_legacy_public_copies(*, tenant):
    sources = []
    batches = []
    records = 0
    skipped = 0
    unverified = 0
    for source in SportsDataSource.objects.filter(
        tenant=tenant, code__in=RETIRABLE_PUBLIC_CONTRACTS,
    ):
        if not _contract_matches(source, RETIRABLE_PUBLIC_CONTRACTS[source.code]):
            continue
        candidates = source.import_batches.filter(artifacts__isnull=True).distinct()
        removable_ids = []
        for batch in candidates:
            has_native_global_copy = _has_identical_native_global_copy(source, batch)
            if has_native_global_copy:
                removable_ids.append(batch.pk)
            else:
                unverified += 1
        removable = source.import_batches.filter(pk__in=removable_ids)
        skipped += source.import_batches.filter(artifacts__isnull=False).distinct().count()
        sources.append(source)
        batches.extend(removable)
        records += sum(batch.records.count() for batch in removable)
    return sources, batches, LegacyPublicCopiesReport(
        sources=len(sources),
        batches=len(batches),
        records=records,
        skipped_artifact_batches=skipped,
        skipped_unverified_batches=unverified,
    )


@transaction.atomic
def retire_legacy_public_copies(*, tenant):
    sources, batches, report = inspect_legacy_public_copies(tenant=tenant)
    for batch in batches:
        batch.delete()
    for source in sources:
        if not source.import_batches.exists():
            source.delete()
    return report
