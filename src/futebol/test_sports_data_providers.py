import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from futebol.models import (
    IntegrationRecord,
    SportsDataImportBatch,
    SportsDataRecord,
    SportsDataSource,
    Tenant,
)
from futebol.services.sports_data_providers import (
    provision_provider_catalog,
    sync_football_data_org,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode('utf-8')


class SportsDataProviderTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube Integrado', slug='clube-integrado')
        self.user = get_user_model().objects.create_user('integrador', password='x')

    def test_catalogo_separa_fontes_operacionais_pesquisa_e_contrato(self):
        sources = provision_provider_catalog(tenant=self.tenant)

        self.assertEqual(len(sources), 7)
        football_data = SportsDataSource.objects.get(
            tenant=self.tenant, code='football-data-org'
        )
        self.assertEqual(football_data.kind, SportsDataSource.Kind.FOOTBALL_DATA_ORG)
        self.assertIn('fixtures_results', football_data.capabilities)
        self.assertEqual(football_data.quality, 'production_basic')
        self.assertFalse(
            SportsDataSource.objects.get(tenant=self.tenant, code='hudl-wyscout').active
        )

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_sincroniza_football_data_com_proveniencia_e_idempotencia(self, urlopen):
        matches = {
            'matches': [
                {
                    'id': 101,
                    'utcDate': '2026-07-15T19:00:00Z',
                    'status': 'SCHEDULED',
                    'homeTeam': {'id': 1, 'name': 'Clube Azul'},
                    'awayTeam': {'id': 2, 'name': 'Clube Verde'},
                    'score': {'fullTime': {'home': None, 'away': None}},
                }
            ]
        }
        standings = {
            'standings': [
                {
                    'type': 'TOTAL',
                    'table': [
                        {
                            'position': 1,
                            'team': {'id': 1, 'name': 'Clube Azul'},
                            'playedGames': 10,
                            'points': 24,
                            'form': 'W,W,D,W,L',
                        }
                    ],
                }
            ]
        }
        urlopen.side_effect = [_Response(matches), _Response(standings)]

        first = sync_football_data_org(
            tenant=self.tenant,
            imported_by=self.user,
            api_key='segredo',
            competition_code='BSA',
        )
        urlopen.side_effect = [_Response(matches), _Response(standings)]
        second = sync_football_data_org(
            tenant=self.tenant,
            imported_by=self.user,
            api_key='segredo',
            competition_code='BSA',
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.status, SportsDataImportBatch.Status.COMPLETED)
        self.assertEqual(first.record_count, 2)
        self.assertEqual(
            set(first.records.values_list('capability', flat=True)),
            {'fixtures_results', 'standings_form'},
        )
        match = SportsDataRecord.objects.get(capability='fixtures_results')
        self.assertEqual(match.payload['home_team'], 'Clube Azul')
        self.assertEqual(match.raw_payload['id'], 101)
        self.assertEqual(match.source_url, 'https://api.football-data.org/v4/matches/101')
        self.assertEqual(match.source.operational_status, SportsDataSource.OperationalStatus.ACTIVE)
        self.assertTrue(IntegrationRecord.objects.filter(status='processed').exists())
        request = urlopen.call_args_list[0].args[0]
        self.assertEqual(request.headers['X-auth-token'], 'segredo')

    def test_football_data_exige_credencial(self):
        with self.assertRaisesMessage(ValidationError, 'credencial'):
            sync_football_data_org(
                tenant=self.tenant,
                imported_by=self.user,
                api_key='',
                competition_code='BSA',
            )

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_falha_do_provider_e_registrada_sem_armazenar_credencial(self, urlopen):
        urlopen.side_effect = TimeoutError('timeout com segredo-super-secreto')

        with self.assertRaises(TimeoutError):
            sync_football_data_org(
                tenant=self.tenant,
                imported_by=self.user,
                api_key='segredo-super-secreto',
                competition_code='BSA',
            )

        source = SportsDataSource.objects.get(tenant=self.tenant, code='football-data-org')
        self.assertEqual(source.operational_status, SportsDataSource.OperationalStatus.DEGRADED)
        failure = IntegrationRecord.objects.get(status='error')
        self.assertNotIn('segredo-super-secreto', json.dumps(failure.payload))
        self.assertNotIn('segredo-super-secreto', failure.error_message)
