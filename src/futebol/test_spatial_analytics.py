from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from futebol.models import (
    SportsDataImportBatch, SportsDataRecord, SportsDataSource, Tenant,
    TenantMembership, TenantModuleSubscription,
)
from futebol.services.spatial_analytics import build_event_analysis


class SpatialAnalyticsTests(SimpleTestCase):
    def _record(self, event_type, player, location, **extra):
        return SimpleNamespace(
            payload={
                'provider_event_id': player + event_type,
                'event_type': event_type,
                'team': 'Azul',
                'player': player,
                'period': 1,
                'timestamp': '12:30.000',
                'location': location,
                'pass': extra.get('pass_data', {}),
                'shot': extra.get('shot_data', {}),
            },
            raw_payload={},
        )

    def test_constroi_mapa_rede_de_passes_e_xg(self):
        records = [
            self._record('Pass', 'Ana', [60, 40], pass_data={'recipient': 'Bia'}),
            self._record('Ball Receipt*', 'Bia', [84, 32]),
            self._record('Pass', 'Ana', [62, 42], pass_data={
                'recipient': 'Bia', 'outcome': 'Incomplete',
            }),
            self._record('Shot', 'Bia', [108, 40], shot_data={
                'xg': 0.25, 'outcome': 'Goal',
            }),
        ]

        analysis = build_event_analysis(records, team='Azul')

        self.assertEqual(analysis['coverage'], 100.0)
        self.assertEqual(analysis['total_xg'], 0.25)
        self.assertEqual(len(analysis['pass_edges']), 1)
        self.assertEqual(analysis['pass_edges'][0]['count'], 1)
        self.assertEqual(analysis['shots'][0]['x'], 90.0)
        self.assertTrue(analysis['shots'][0]['goal'])

    def test_filtro_de_equipe_e_coordenada_invalida(self):
        records = [self._record('Pressure', 'Ana', None)]
        records.append(SimpleNamespace(
            payload={**records[0].payload, 'team': 'Verde', 'location': [30, 20]},
            raw_payload={},
        ))

        analysis = build_event_analysis(records, team='Azul')

        self.assertEqual(analysis['event_count'], 1)
        self.assertEqual(analysis['spatial_count'], 0)

    def test_timestamp_statsbomb_e_filtro_de_periodo(self):
        first = self._record('Pressure', 'Ana', [30, 20])
        first.payload['timestamp'] = '00:12:30.000'
        second = self._record('Pressure', 'Bia', [60, 40])
        second.payload['period'] = 2

        analysis = build_event_analysis([first, second], period='1')

        self.assertEqual(analysis['event_count'], 1)
        self.assertEqual(analysis['actions'][0]['minute'], 12.5)


class TacticalAnalysisLabHTTPTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Laboratório Azul', slug='laboratorio-azul')
        self.user = get_user_model().objects.create_user('analista-lab', password='senha')
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role=TenantMembership.Role.GESTOR_CLUBE,
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='ia', module_name='IA', enabled=True,
        )
        source = SportsDataSource.objects.create(
            tenant=self.tenant, code='statsbomb-open', name='StatsBomb Open Data',
            kind=SportsDataSource.Kind.STATSBOMB_OPEN,
            capabilities=['event_stream'], license_id='open-data',
            attribution='StatsBomb', quality='research_sample', active=False,
            operational_status=SportsDataSource.OperationalStatus.RESEARCH_ONLY,
        )
        self.batch = SportsDataImportBatch.objects.create(
            tenant=self.tenant, source=source, dataset_id='lab', dataset_version='1',
            content_hash='a' * 64, status=SportsDataImportBatch.Status.COMPLETED,
            record_count=1, manifest={'limits': {'max_events_per_match': 5000}},
            license_id='open-data', attribution='StatsBomb', quality='research_sample',
            imported_by=self.user,
        )
        SportsDataRecord.objects.create(
            tenant=self.tenant, source=source, batch=self.batch,
            capability='event_stream', provider_record_id='event:1',
            payload={
                'provider_match_id': '123', 'provider_event_id': '1',
                'event_type': 'Shot', 'team': 'Azul', 'player': 'Atacante',
                'period': 1, 'timestamp': '10:00.000', 'location': [108, 40],
                'shot': {'xg': 0.4, 'outcome': 'Goal'},
            },
            raw_payload={},
            content_hash='b' * 64,
        )
        self.client.force_login(self.user)

    def test_renderiza_svg_com_proveniencia_e_xg(self):
        response = self.client.get(reverse('tactical-analysis-lab', args=[self.batch.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Laboratório Tático')
        self.assertContains(response, 'StatsBomb')
        self.assertContains(response, '0,4')
        self.assertContains(response, '<svg', html=False)

    def test_nao_expoe_lote_de_outro_tenant(self):
        other = Tenant.objects.create(name='Outro', slug='outro-lab')
        self.batch.tenant = other
        self.batch.source = SportsDataSource.objects.create(
            tenant=other, code='outra', name='Outra', kind=SportsDataSource.Kind.LOCAL_DATASET,
            capabilities=['event_stream'], license_id='x', attribution='x',
            quality='research_sample', active=False,
        )
        self.batch.content_hash = 'c' * 64
        self.batch.dataset_id = 'outro'
        self.batch.save()

        response = self.client.get(reverse('tactical-analysis-lab', args=[self.batch.pk]))

        self.assertEqual(response.status_code, 404)
