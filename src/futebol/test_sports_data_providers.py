import json
import io
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from futebol.models import (
    IntegrationRecord,
    SportsDataImportBatch,
    SportsDataArtifact,
    SportsDataRecord,
    SportsDataSource,
    Tenant,
)
from futebol.services.sports_data_providers import (
    provision_provider_catalog,
    sync_football_data_org,
    sync_skillcorner_open,
    sync_skillcorner_tracking,
    sync_statsbomb_open,
)


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


class _BinaryResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


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
        self.assertEqual(first.manifest['rate_limit']['standings']['requests_available'], '8')
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
    def test_statsbomb_open_importa_amostra_com_proveniencia_sem_ativar_fonte(self, urlopen):
        matches = [{
            'match_id': 9001,
            'match_date': '2024-04-10',
            'kick_off': '20:00:00.000',
            'home_team': {'home_team_id': 1, 'home_team_name': 'Azul FC'},
            'away_team': {'away_team_id': 2, 'away_team_name': 'Verde FC'},
            'home_score': 2,
            'away_score': 1,
        }]
        events = [{
            'id': 'evt-1',
            'index': 1,
            'period': 1,
            'timestamp': '00:00:00.000',
            'type': {'id': 35, 'name': 'Starting XI'},
            'team': {'id': 1, 'name': 'Azul FC'},
            'player': {'id': 10, 'name': 'Atleta Um'},
            'location': [60.0, 40.0],
        }, {
            'id': 'evt-2',
            'index': 2,
            'period': 1,
            'timestamp': '00:00:01.000',
            'type': {'id': 30, 'name': 'Pass'},
            'team': {'id': 1, 'name': 'Azul FC'},
        }]
        urlopen.side_effect = [_Response(matches), _Response(events)]

        batch = sync_statsbomb_open(
            tenant=self.tenant,
            imported_by=self.user,
            competition_id='9',
            season_id='281',
            max_matches=1,
            max_events=1,
        )

        self.assertEqual(batch.record_count, 2)
        self.assertEqual(batch.quality, 'research_sample')
        self.assertTrue(batch.manifest['research_only'])
        self.assertEqual(batch.manifest['limits']['max_events_per_match'], 1)
        self.assertEqual(
            set(batch.records.values_list('capability', flat=True)),
            {'fixtures_results', 'event_stream'},
        )
        event = batch.records.get(capability='event_stream')
        self.assertEqual(event.raw_payload['id'], 'evt-1')
        self.assertEqual(event.payload['event_type'], 'Starting XI')
        self.assertTrue(event.content_hash)
        source = batch.source
        self.assertFalse(source.active)
        self.assertEqual(
            source.operational_status,
            SportsDataSource.OperationalStatus.RESEARCH_ONLY,
        )
        integration = IntegrationRecord.objects.get(
            correlation_id=f'statsbomb-open:{batch.content_hash}'
        )
        self.assertTrue(integration.payload['research_only'])
        self.assertNotIn('X-auth-token', urlopen.call_args_list[0].args[0].headers)

    def test_statsbomb_open_rejeita_amostra_acima_do_limite_antes_da_rede(self):
        with self.assertRaisesMessage(ValidationError, 'entre 1 e 3 partidas'):
            sync_statsbomb_open(
                tenant=self.tenant,
                imported_by=self.user,
                competition_id='9',
                season_id='281',
                max_matches=4,
            )

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_skillcorner_sincroniza_amostra_controlada_sem_tracking(self, urlopen):
        catalog = [{
            'id': 2017461, 'date_time': '2025-05-17T09:35:00Z',
            'home_team': {'id': 868, 'short_name': 'Melbourne V FC'},
            'away_team': {'id': 4177, 'short_name': 'Auckland FC'},
            'status': 'closed', 'competition_id': 61, 'season_id': 95,
        }, {
            'id': 2015213, 'date_time': '2025-05-03T08:00:00Z',
            'home_team': {'id': 1803, 'short_name': 'Western United'},
            'away_team': {'id': 4177, 'short_name': 'Auckland FC'},
            'status': 'closed', 'competition_id': 61, 'season_id': 95,
        }]
        metadata = {
            'id': 2017461, 'date_time': '2025-05-17T09:35:00Z',
            'home_team_score': 0, 'away_team_score': 1,
            'home_team': {'id': 868, 'short_name': 'Melbourne V FC'},
            'away_team': {'id': 4177, 'short_name': 'Auckland FC'},
            'competition_edition': {
                'competition': {'id': 61, 'name': 'A-League', 'area': 'AUS'},
            },
            'players': [{'id': 1}, {'id': 2}],
            'match_periods': [{'period': 1, 'duration_minutes': 46.17}],
        }
        urlopen.side_effect = [_Response(catalog), _Response(metadata)]

        batch = sync_skillcorner_open(
            tenant=self.tenant, imported_by=self.user, max_matches=1,
        )

        self.assertEqual(batch.quality, 'research_sample')
        self.assertEqual(batch.record_count, 3)
        self.assertEqual(batch.manifest['usage_scope'], 'research_only')
        self.assertIn('tracking_extrapolated', batch.manifest['excluded_large_files'])
        metadata_record = batch.records.get(capability='match_metadata')
        self.assertEqual(metadata_record.payload['players_count'], 2)
        self.assertEqual(metadata_record.raw_payload['home_team_score'], 0)
        self.assertFalse(batch.source.active)
        self.assertEqual(
            batch.source.operational_status,
            SportsDataSource.OperationalStatus.RESEARCH_ONLY,
        )
        integration = IntegrationRecord.objects.get(
            external_system__name='SkillCorner Open Data'
        )
        self.assertEqual(integration.payload['quality'], 'research_sample')

    def test_skillcorner_limita_quantidade_de_metadados(self):
        with self.assertRaisesMessage(ValidationError, 'entre 1 e 3'):
            sync_skillcorner_open(
                tenant=self.tenant, imported_by=self.user, max_matches=4,
            )

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_skillcorner_tracking_gera_artefato_privado_e_idempotente(self, urlopen):
        frames = b''.join(json.dumps({
            'frame': index, 'timestamp': index / 10, 'period': 1,
            'player_data': [
                {'player_id': 1, 'x': index, 'y': 0, 'is_detected': True},
                {'player_id': 2, 'x': 10, 'y': 10, 'is_detected': True},
            ],
            'ball_data': {'x': 0, 'y': 0, 'is_detected': True},
        }).encode() + b'\n' for index in range(3))
        urlopen.side_effect = [_BinaryResponse(frames), _BinaryResponse(frames)]
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            batch = sync_skillcorner_tracking(
                tenant=self.tenant, imported_by=self.user, match_id='2017461',
            )
            artifact = SportsDataArtifact.objects.get(batch=batch)
            second = sync_skillcorner_tracking(
                tenant=self.tenant, imported_by=self.user, match_id='2017461',
            )

            self.assertEqual(second.pk, batch.pk)
            self.assertEqual(artifact.status, SportsDataArtifact.Status.READY)
            self.assertEqual(artifact.item_count, 3)
            self.assertEqual(len(artifact.content_hash), 64)
            self.assertEqual(batch.records.count(), 0)
            self.assertEqual(batch.manifest['frame_count'], 3)
            self.assertTrue(artifact.file.name.startswith(
                f'tracking/{self.tenant.pk}/{batch.pk}/'
            ))
            self.assertEqual(urlopen.call_count, 2)
            self.assertTrue(IntegrationRecord.objects.filter(
                correlation_id=f'skillcorner-tracking:{artifact.content_hash}',
                status='processed',
            ).exists())
            artifact.byte_size += 1
            with self.assertRaisesMessage(ValidationError, 'imutável'):
                artifact.save()

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
