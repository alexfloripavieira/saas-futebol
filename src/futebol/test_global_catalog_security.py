from datetime import timedelta
from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from futebol.models import (
    GlobalSportsDataBatch,
    GlobalSportsDataRecord,
    GlobalSportsDataSource,
    GlobalSportsSyncRun,
    SportsDataImportBatch,
    SportsDataRecord,
    SportsDataSource,
    Tenant,
    TenantModuleSubscription,
)
from futebol.services.sports_catalog import (
    capability_entitlement_code,
    latest_records_for,
    source_entitlement_code,
    sources_for,
)


User = get_user_model()


class GlobalCatalogCanonicalSelectionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube assinante', slug='clube-assinante')
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='ia', module_name='IA', enabled=True,
        )
        self.source = GlobalSportsDataSource.objects.create(
            code='provider-canonico', name='Provider canônico', kind='licensed_provider',
            capabilities=['fixtures_results'], license_id='contrato',
            attribution='Provider', quality='licensed_production', active=True,
        )

    def _batch(self, content_hash, published_at, status):
        batch = GlobalSportsDataBatch.objects.create(
            source=self.source, dataset_id='competition-bsa',
            dataset_version=content_hash, content_hash=content_hash * 64,
            status='completed', record_count=1, manifest={'provider': 'test'},
            license_id='contrato',
            attribution='Provider', quality='licensed_production',
            published_at=published_at,
        )
        GlobalSportsDataRecord.objects.create(
            source=self.source, batch=batch, capability='fixtures_results',
            provider_record_id='match:1', observed_at=published_at,
            ingested_at=published_at, expires_at=timezone.now() + timedelta(days=1),
            payload={'status': status}, content_hash=content_hash * 64,
        )
        return batch

    def test_ultima_execucao_a_b_a_torna_lote_a_canonico_novamente(self):
        now = timezone.now()
        batch_a = self._batch('a', now - timedelta(hours=3), 'SCHEDULED')
        batch_b = self._batch('b', now - timedelta(hours=2), 'POSTPONED')
        for index, batch in enumerate((batch_a, batch_b, batch_a), start=1):
            moment = now - timedelta(hours=4 - index)
            GlobalSportsSyncRun.objects.create(
                source=self.source, batch=batch, dataset_id='competition-bsa',
                trigger='scheduler', status='completed', started_at=moment,
                finished_at=moment,
            )

        record = latest_records_for(
            self.tenant, capability='fixtures_results', provider_code=self.source.code,
        ).get(provider_record_id='match:1')

        self.assertEqual(record.batch_id, batch_a.pk)
        self.assertEqual(record.payload['status'], 'SCHEDULED')


class GlobalCatalogEntitlementTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube granular', slug='clube-granular')
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='ia', module_name='IA', enabled=True,
        )
        self.fixtures = GlobalSportsDataSource.objects.create(
            code='fixtures-pro', name='Fixtures Pro', kind='licensed_provider',
            capabilities=['fixtures_results', 'standings_form'], license_id='a',
            attribution='A', quality='licensed_production',
        )
        self.events = GlobalSportsDataSource.objects.create(
            code='events-pro', name='Events Pro', kind='licensed_provider',
            capabilities=['event_stream', 'xg'], license_id='b', attribution='B',
            quality='licensed_production',
        )
        now = timezone.now()
        for source, capability in (
            (self.fixtures, 'fixtures_results'),
            (self.fixtures, 'standings_form'),
            (self.events, 'event_stream'),
            (self.events, 'xg'),
        ):
            batch = GlobalSportsDataBatch.objects.create(
                source=source, dataset_id=f'data-{capability}', dataset_version='1',
                content_hash=(str(source.pk) + capability).ljust(64, '0')[:64],
                status='completed', record_count=1, manifest={'provider': 'test'},
                license_id=source.license_id, attribution=source.attribution,
                quality=source.quality, published_at=now,
            )
            GlobalSportsDataRecord.objects.create(
                source=source, batch=batch, capability=capability,
                provider_record_id=f'{capability}:1', observed_at=now, ingested_at=now,
                payload={'value': 1}, content_hash=capability.ljust(64, '0')[:64],
            )

    def test_fonte_e_capacidade_formam_uniao_sem_vazar_outras_capacidades(self):
        TenantModuleSubscription.objects.bulk_create([
            TenantModuleSubscription(
                tenant=self.tenant,
                module_code=source_entitlement_code(self.fixtures.code),
                module_name='Fixtures Pro', enabled=True,
            ),
            TenantModuleSubscription(
                tenant=self.tenant,
                module_code=capability_entitlement_code('xg'),
                module_name='Métrica xG', enabled=True,
            ),
        ])

        self.assertSetEqual(
            set(sources_for(self.tenant).values_list('code', flat=True)),
            {'fixtures-pro', 'events-pro'},
        )
        self.assertSetEqual(
            set(latest_records_for(self.tenant).values_list('capability', flat=True)),
            {'fixtures_results', 'standings_form', 'xg'},
        )

    def test_entitlement_granular_desabilitado_restringe_todo_o_catalogo(self):
        TenantModuleSubscription.objects.create(
            tenant=self.tenant,
            module_code=source_entitlement_code(self.fixtures.code),
            module_name='Fixtures Pro', enabled=False,
        )

        self.assertFalse(sources_for(self.tenant).exists())
        self.assertFalse(latest_records_for(self.tenant).exists())

    def test_sem_modulo_ia_nao_consulta_mesmo_com_codigo_granular(self):
        TenantModuleSubscription.objects.filter(tenant=self.tenant, module_code='ia').update(
            enabled=False,
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant,
            module_code=source_entitlement_code(self.fixtures.code),
            module_name='Fixtures Pro', enabled=True,
        )

        with self.assertRaises(PermissionDenied):
            sources_for(self.tenant)


class GlobalCatalogBackfillSafetyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('operador-catalogo', password='segredo-forte')

    def _legacy_source(self, tenant):
        return SportsDataSource.objects.create(
            tenant=tenant, code='football-data-org', name='football-data.org',
            kind='football_data_org', capabilities=['fixtures_results', 'standings_form'],
            license_id='football-data-org-terms',
            license_url='https://www.football-data.org/about',
            attribution='Dados fornecidos por football-data.org.',
            quality='production_basic', adapter_version='1.0',
            schema_version='football-data-v4', active=True,
        )

    def _legacy_batch(self, tenant, source, suffix, capability, source_url):
        now = timezone.now()
        batch = SportsDataImportBatch.objects.create(
            tenant=tenant, source=source, dataset_id=f'competition-bsa-{suffix}',
            dataset_version='1', content_hash=suffix.ljust(64, '0')[:64],
            status='completed', record_count=1,
            manifest={
                'provider': 'football-data.org',
                'capabilities': [capability],
            },
            license_id=source.license_id, attribution=source.attribution,
            quality=source.quality, imported_by=self.user, imported_at=now,
        )
        SportsDataRecord.objects.create(
            tenant=tenant, source=source, batch=batch, capability=capability,
            provider_record_id=f'{suffix}:1', observed_at=now,
            payload={'value': 1}, raw_payload={'value': 1},
            source_url=source_url, content_hash=suffix.ljust(64, '0')[:64],
        )

    def test_backfill_nunca_promove_payload_tenant_scoped(self):
        trusted_tenant = Tenant.objects.create(name='Origem confiável', slug='origem-confiavel')
        private_tenant = Tenant.objects.create(name='Clube privado', slug='clube-privado')
        trusted_source = self._legacy_source(trusted_tenant)
        private_source = self._legacy_source(private_tenant)
        self._legacy_batch(
            trusted_tenant, trusted_source, 'trusted', 'fixtures_results',
            'https://api.football-data.org/v4/matches/1',
        )
        self._legacy_batch(
            private_tenant, private_source, 'private', 'gps_private',
            'https://clube.example/gps/1',
        )

        migration = import_module('futebol.migrations.0032_backfill_global_sports_catalog')
        migration.backfill_global_catalog(apps, None)

        self.assertFalse(
            GlobalSportsDataRecord.objects.filter(provider_record_id='trusted:1').exists()
        )
        self.assertFalse(
            GlobalSportsDataRecord.objects.filter(provider_record_id='private:1').exists()
        )

        global_source = GlobalSportsDataSource.objects.create(
            code='football-data-org', name='football-data.org',
            kind=GlobalSportsDataSource.Kind.FOOTBALL_DATA_ORG,
            capabilities=['fixtures_results'],
            license_id='football-data-org-terms',
            attribution='Dados fornecidos por football-data.org.',
            quality='production_basic', adapter_version='1.0',
            schema_version='football-data-v4',
        )
        now = timezone.now()
        unsafe_batch = GlobalSportsDataBatch.objects.create(
            source=global_source, dataset_id='competition-private-gps',
            dataset_version='1', content_hash='u' * 64, status='completed',
            record_count=1,
            manifest={'provider': 'football-data.org', 'capabilities': ['gps_private']},
            license_id=global_source.license_id,
            attribution=global_source.attribution, quality=global_source.quality,
            published_at=now,
        )
        GlobalSportsDataRecord.objects.create(
            source=global_source, batch=unsafe_batch, capability='gps_private',
            provider_record_id='private-global:1', observed_at=now, ingested_at=now,
            payload={'carga': 99}, raw_payload={'carga': 99},
            source_url='https://clube.example/gps/1', content_hash='v' * 64,
        )

        cleanup = import_module(
            'futebol.migrations.0033_remove_unsafe_global_sports_backfill'
        )
        cleanup.remove_unsafe_backfill(apps, None)

        self.assertFalse(
            GlobalSportsDataRecord.objects.filter(provider_record_id='trusted:1').exists()
        )
        self.assertFalse(
            GlobalSportsDataRecord.objects.filter(provider_record_id='private-global:1').exists()
        )
