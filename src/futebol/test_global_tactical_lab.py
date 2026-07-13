from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from futebol.models import (
    GlobalSportsDataBatch,
    GlobalSportsDataRecord,
    GlobalSportsDataSource,
    SportsDataImportBatch,
    Tenant,
    TenantMembership,
    TenantModuleSubscription,
)
from futebol.services.sports_catalog import capability_entitlement_code


User = get_user_model()


class GlobalTacticalLabTests(TestCase):
    def setUp(self):
        self.source = GlobalSportsDataSource.objects.create(
            code='statsbomb-open',
            name='StatsBomb Open Data',
            kind=GlobalSportsDataSource.Kind.STATSBOMB_OPEN,
            capabilities=['event_stream', 'xg'],
            license_id='statsbomb-open-data',
            attribution='StatsBomb Open Data.',
            quality='research_sample',
            active=True,
            operational_status=GlobalSportsDataSource.OperationalStatus.RESEARCH_ONLY,
        )
        self.batch = GlobalSportsDataBatch.objects.create(
            source=self.source,
            dataset_id='competition-9-season-281',
            dataset_version='open-v1',
            content_hash='a' * 64,
            status=GlobalSportsDataBatch.Status.COMPLETED,
            record_count=13,
            manifest={'provider': 'StatsBomb Open Data', 'limits': {}},
            license_id=self.source.license_id,
            attribution=self.source.attribution,
            quality=self.source.quality,
            published_at=timezone.now(),
        )
        for index in range(12):
            self._event(
                index,
                event_type='Pass',
                player='Jogador A' if index % 2 == 0 else 'Jogador B',
                extra={'pass': {
                    'recipient': 'Jogador B' if index % 2 == 0 else 'Jogador A',
                    'outcome': '',
                }},
            )
        self._event(
            12,
            event_type='Shot',
            player='Jogador A',
            extra={'shot': {'xg': 0.32, 'outcome': 'Goal'}},
        )

    def _event(self, index, *, event_type, player, extra):
        now = timezone.now()
        GlobalSportsDataRecord.objects.create(
            source=self.source,
            batch=self.batch,
            capability='event_stream',
            provider_record_id=f'event:123:{index}',
            observed_at=now,
            ingested_at=now,
            payload={
                'provider_match_id': '123',
                'provider_event_id': str(index),
                'event_type': event_type,
                'team': 'Time Real',
                'player': player,
                'period': 1,
                'timestamp': f'00:{index:02d}:00',
                'location': [20 + index * 3, 30 + index],
                **extra,
            },
            content_hash=f'{index + 1:064x}',
        )

    def _client_for(self, slug, *, ia=True):
        tenant = Tenant.objects.create(name=slug.title(), slug=slug)
        user = User.objects.create_user(f'user-{slug}', password='senha12345')
        TenantMembership.objects.create(
            tenant=tenant,
            user=user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        TenantModuleSubscription.objects.create(
            tenant=tenant,
            module_code='ia' if ia else 'integracoes',
            module_name='IA' if ia else 'Integrações',
            enabled=True,
        )
        self.client.force_login(user)
        return tenant

    def test_dois_tenants_analisam_o_mesmo_lote_global_sem_copia(self):
        url = reverse('global-tactical-analysis-lab', args=[self.batch.pk])
        self._client_for('tenant-a')
        first = self.client.get(url, {'team': 'Time Real'})
        self.client.logout()
        self._client_for('tenant-b')
        second = self.client.get(url, {'team': 'Time Real'})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertContains(first, 'Mapa de ações')
        self.assertContains(first, 'Rede de passes')
        self.assertContains(first, '0,32')
        self.assertContains(first, 'cx="16.67"')
        self.assertNotContains(first, 'cx="16,67"')
        self.assertEqual(GlobalSportsDataBatch.objects.count(), 1)
        self.assertEqual(SportsDataImportBatch.objects.count(), 0)

    def test_tenant_sem_inteligencia_nao_acessa_laboratorio_global(self):
        self._client_for('tenant-sem-ia', ia=False)

        response = self.client.get(
            reverse('global-tactical-analysis-lab', args=[self.batch.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Módulo não contratado', status_code=403)

    def test_capacidade_xg_nao_libera_event_stream_do_laboratorio(self):
        tenant = self._client_for('tenant-so-xg')
        TenantModuleSubscription.objects.create(
            tenant=tenant,
            module_code=capability_entitlement_code('xg'),
            module_name='Capacidade xG',
            enabled=True,
        )

        response = self.client.get(
            reverse('global-tactical-analysis-lab', args=[self.batch.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Capacidade não contratada', status_code=403)
