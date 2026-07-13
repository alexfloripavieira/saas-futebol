from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from futebol.models import (
    GlobalSportsDataBatch,
    GlobalSportsDataRecord,
    GlobalSportsDataSource,
    GlobalSportsSyncRun,
    SportsDataArtifact,
    SportsDataImportBatch,
    SportsDataRecord,
    SportsDataSource,
    Tenant,
)
from futebol.services.sports_data_transition import retire_legacy_public_copies


User = get_user_model()


class SportsDataTransitionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube', slug='clube')
        self.user = User.objects.create_user('operador')

    def _source(self, *, code='football-data-org', adapter='1.0'):
        return SportsDataSource.objects.create(
            tenant=self.tenant,
            code=code,
            name=code,
            kind=(
                SportsDataSource.Kind.FOOTBALL_DATA_ORG
                if code == 'football-data-org'
                else SportsDataSource.Kind.STATSBOMB_OPEN
            ),
            capabilities=['fixtures_results'],
            license_id=(
                'football-data-org-terms'
                if code == 'football-data-org' else 'statsbomb-open-data'
            ),
            attribution='Fonte pública',
            quality='production_basic',
            adapter_version=adapter,
            schema_version=(
                'football-data-v4'
                if code == 'football-data-org' else 'statsbomb-open-v1.1'
            ),
        )

    def _batch(self, source, suffix):
        batch = SportsDataImportBatch.objects.create(
            tenant=self.tenant,
            source=source,
            dataset_id=f'dataset-{suffix}',
            dataset_version='1',
            content_hash=suffix.ljust(64, '0')[:64],
            status=SportsDataImportBatch.Status.COMPLETED,
            record_count=1,
            manifest={'provider': source.code},
            license_id=source.license_id,
            attribution=source.attribution,
            quality=source.quality,
            imported_by=self.user,
            imported_at=timezone.now(),
        )
        SportsDataRecord.objects.create(
            tenant=self.tenant,
            source=source,
            batch=batch,
            capability='fixtures_results',
            provider_record_id=f'match:{suffix}',
            observed_at=timezone.now(),
            payload={'value': suffix},
            content_hash=('r' + suffix).ljust(64, '0')[:64],
        )
        return batch

    def _global_copy(self, legacy_batch):
        source, _ = GlobalSportsDataSource.objects.get_or_create(
            code=legacy_batch.source.code,
            defaults={
                'name': legacy_batch.source.name,
                'kind': legacy_batch.source.kind,
                'capabilities': legacy_batch.source.capabilities,
                'license_id': legacy_batch.source.license_id,
                'attribution': legacy_batch.source.attribution,
                'quality': legacy_batch.source.quality,
                'operational_status': GlobalSportsDataSource.OperationalStatus.ACTIVE,
            },
        )
        batch = GlobalSportsDataBatch.objects.create(
            source=source,
            dataset_id=legacy_batch.dataset_id,
            dataset_version=legacy_batch.dataset_version,
            content_hash=legacy_batch.content_hash,
            status=GlobalSportsDataBatch.Status.COMPLETED,
            record_count=legacy_batch.record_count,
            manifest=legacy_batch.manifest,
            license_id=legacy_batch.license_id,
            attribution=legacy_batch.attribution,
            quality=legacy_batch.quality,
            published_at=timezone.now(),
        )
        GlobalSportsSyncRun.objects.create(
            source=source,
            batch=batch,
            dataset_id=batch.dataset_id,
            status=GlobalSportsSyncRun.Status.COMPLETED,
            started_at=timezone.now(),
            finished_at=timezone.now(),
        )
        for record in legacy_batch.records.all():
            GlobalSportsDataRecord.objects.create(
                source=source,
                batch=batch,
                capability=record.capability,
                provider_record_id=record.provider_record_id,
                observed_at=record.observed_at,
                ingested_at=timezone.now(),
                payload=record.payload,
                raw_payload=record.raw_payload,
                source_url=record.source_url,
                content_hash=record.content_hash,
            )

    def test_remove_copia_publica_exata_e_preserva_fonte_homonima_enriquecida(self):
        trusted = self._source()
        trusted_batch = self._batch(trusted, 'trusted')
        self._global_copy(trusted_batch)
        private_tenant = Tenant.objects.create(name='Outro', slug='outro')
        enriched = SportsDataSource.objects.create(
            tenant=private_tenant,
            code='football-data-org',
            name='Fonte enriquecida pelo clube',
            kind=SportsDataSource.Kind.FOOTBALL_DATA_ORG,
            capabilities=['gps_private'],
            license_id='football-data-org-terms',
            attribution='Clube',
            quality='internal',
            adapter_version='club-custom',
            schema_version='private-v1',
        )

        report = retire_legacy_public_copies(tenant=self.tenant)

        self.assertEqual(report.records, 1)
        self.assertFalse(SportsDataSource.objects.filter(pk=trusted.pk).exists())
        self.assertTrue(SportsDataSource.objects.filter(pk=enriched.pk).exists())

    def test_preserva_lote_publico_sem_copia_global_identica(self):
        source = self._source()
        batch = self._batch(source, 'enriched-payload')

        report = retire_legacy_public_copies(tenant=self.tenant)

        self.assertEqual(report.records, 0)
        self.assertEqual(report.skipped_unverified_batches, 1)
        self.assertTrue(SportsDataImportBatch.objects.filter(pk=batch.pk).exists())

    def test_preserva_enriquecimento_feito_apos_hash_do_lote(self):
        source = self._source()
        batch = self._batch(source, 'same-batch-hash')
        self._global_copy(batch)
        record = batch.records.get()
        record.payload = {'value': 'same-batch-hash', 'gps_private': 97}
        record.save()

        report = retire_legacy_public_copies(tenant=self.tenant)

        self.assertEqual(report.records, 0)
        self.assertEqual(report.skipped_unverified_batches, 1)
        self.assertTrue(SportsDataImportBatch.objects.filter(pk=batch.pk).exists())

    def test_preserva_lote_que_possui_artefato_tenant_scoped(self):
        source = self._source(code='statsbomb-open')
        batch = self._batch(source, 'artifact')
        SportsDataArtifact.objects.create(
            tenant=self.tenant,
            batch=batch,
            capability='tracking_frames',
            provider_object_id='match:1',
            artifact_version='a' * 12,
            schema_version='tracking-v1',
            format='jsonl',
            file=SimpleUploadedFile('tracking.jsonl', b'{"frame": 1}\n'),
            content_hash='a' * 64,
            byte_size=10,
            item_count=1,
            metadata={'usage_scope': 'tenant_private'},
            status=SportsDataArtifact.Status.READY,
        )

        report = retire_legacy_public_copies(tenant=self.tenant)

        self.assertEqual(report.skipped_artifact_batches, 1)
        self.assertTrue(SportsDataImportBatch.objects.filter(pk=batch.pk).exists())
        self.assertTrue(SportsDataSource.objects.filter(pk=source.pk).exists())
