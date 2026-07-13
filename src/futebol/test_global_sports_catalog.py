import json
import os
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase

from futebol.models import (
    GlobalSportsDataBatch,
    GlobalSportsDataRecord,
    GlobalSportsDataSource,
    GlobalSportsSyncRun,
    Tenant,
    TenantModuleSubscription,
)
from futebol.services.sports_catalog import latest_records_for, sources_for
from futebol.services.sports_data_providers import sync_platform_football_data


class _Response:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {
            'X-RequestsAvailable': '8',
            'X-RequestCounter-Reset': '42',
            'X-API-Version': 'v4',
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode('utf-8')


class GlobalSportsCatalogTests(TestCase):
    def _tenant_with_intelligence(self, slug):
        tenant = Tenant.objects.create(name=slug.title(), slug=slug)
        TenantModuleSubscription.objects.create(
            tenant=tenant,
            module_code='ia',
            module_name='IA',
            enabled=True,
        )
        return tenant

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_plataforma_sincroniza_uma_base_global_sem_tenant(self, urlopen):
        matches = {
            'matches': [{
                'id': 101,
                'utcDate': '2026-07-15T19:00:00Z',
                'lastUpdated': '2026-07-13T18:30:00Z',
                'status': 'SCHEDULED',
                'homeTeam': {'id': 1, 'name': 'Clube Azul'},
                'awayTeam': {'id': 2, 'name': 'Clube Verde'},
                'score': {'fullTime': {'home': None, 'away': None}},
            }],
        }
        standings = {'standings': []}
        urlopen.side_effect = [_Response(matches), _Response(standings)]

        first = sync_platform_football_data(
            api_key='segredo', competition_code='BSA', trigger='scheduler',
        )
        urlopen.side_effect = [_Response(matches), _Response(standings)]
        second = sync_platform_football_data(
            api_key='segredo', competition_code='BSA', trigger='scheduler',
        )

        self.assertEqual(first.batch_id, second.batch_id)
        self.assertEqual(GlobalSportsDataSource.objects.count(), 1)
        self.assertEqual(GlobalSportsDataBatch.objects.count(), 1)
        self.assertEqual(GlobalSportsDataRecord.objects.count(), 1)
        self.assertEqual(GlobalSportsSyncRun.objects.count(), 2)
        record = GlobalSportsDataRecord.objects.get()
        self.assertEqual(record.payload['home_team'], 'Clube Azul')
        self.assertEqual(
            record.provider_updated_at.isoformat(), '2026-07-13T18:30:00+00:00'
        )
        self.assertIsNotNone(record.ingested_at)
        self.assertIsNotNone(record.expires_at)

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_dois_tenants_contratantes_leem_o_mesmo_registro_global(self, urlopen):
        tenant_a = self._tenant_with_intelligence('clube-a')
        tenant_b = self._tenant_with_intelligence('clube-b')
        matches = {
            'matches': [{
                'id': 202,
                'utcDate': '2026-07-20T19:00:00Z',
                'status': 'SCHEDULED',
                'homeTeam': {'id': 1, 'name': 'Azul'},
                'awayTeam': {'id': 2, 'name': 'Verde'},
                'score': {'fullTime': {'home': None, 'away': None}},
            }],
        }
        urlopen.side_effect = [_Response(matches), _Response({'standings': []})]
        sync_platform_football_data(api_key='segredo', competition_code='BSA')

        source_a = sources_for(tenant_a).get(code='football-data-org')
        source_b = sources_for(tenant_b).get(code='football-data-org')
        record_a = latest_records_for(
            tenant_a, capability='fixtures_results', provider_code='football-data-org',
        ).get(provider_record_id='match:202')
        record_b = latest_records_for(
            tenant_b, capability='fixtures_results', provider_code='football-data-org',
        ).get(provider_record_id='match:202')

        self.assertEqual(source_a.pk, source_b.pk)
        self.assertEqual(record_a.pk, record_b.pk)
        self.assertEqual(GlobalSportsDataRecord.objects.count(), 1)

    def test_tenant_sem_inteligencia_nao_consulta_catalogo_global(self):
        tenant = Tenant.objects.create(name='Sem IA', slug='sem-ia')
        TenantModuleSubscription.objects.create(
            tenant=tenant,
            module_code='integracoes',
            module_name='Integrações',
            enabled=True,
        )

        with self.assertRaises(PermissionDenied):
            sources_for(tenant)

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_rechecagem_a_b_a_torna_a_ultima_observacao_canonica(self, urlopen):
        tenant = self._tenant_with_intelligence('clube-canonico')

        def matches(status):
            return {'matches': [{
                'id': 303,
                'utcDate': '2026-07-20T19:00:00Z',
                'status': status,
                'homeTeam': {'id': 1, 'name': 'Azul'},
                'awayTeam': {'id': 2, 'name': 'Verde'},
                'score': {'fullTime': {'home': None, 'away': None}},
            }]}

        empty_standings = {'standings': []}
        urlopen.side_effect = [
            _Response(matches('SCHEDULED')), _Response(empty_standings),
            _Response(matches('POSTPONED')), _Response(empty_standings),
            _Response(matches('SCHEDULED')), _Response(empty_standings),
        ]
        for _index in range(3):
            sync_platform_football_data(api_key='segredo', competition_code='BSA')

        canonical = latest_records_for(
            tenant,
            capability='fixtures_results',
            provider_code='football-data-org',
        ).get(provider_record_id='match:303')

        self.assertEqual(canonical.payload['status'], 'SCHEDULED')
        self.assertEqual(GlobalSportsDataBatch.objects.count(), 2)
        self.assertEqual(GlobalSportsSyncRun.objects.count(), 3)

    @patch(
        'futebol.management.commands.sync_platform_sports_provider.'
        'sync_platform_football_data'
    )
    def test_comando_da_plataforma_nao_recebe_tenant_nem_usuario(self, sync):
        sync.return_value.batch.record_count = 17

        with patch.dict(os.environ, {'FOOTBALL_DATA_ORG_API_KEY': 'segredo'}):
            call_command(
                'sync_platform_sports_provider',
                provider='football-data-org',
                competition='BSA',
                team_id=['4241', '1769'],
                stdout=StringIO(),
            )

        sync.assert_called_once_with(
            api_key='segredo', competition_code='BSA', max_teams=4,
            team_ids=('4241', '1769'),
            trigger='scheduler',
        )
