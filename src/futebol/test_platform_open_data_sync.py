import json
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from futebol.models import (
    GlobalSportsDataBatch,
    GlobalSportsDataRecord,
    GlobalSportsDataSource,
    GlobalSportsSyncRun,
)
from futebol.services.sports_data_providers import (
    sync_platform_football_data,
    sync_platform_skillcorner_open,
    sync_platform_statsbomb_open,
)


class _Response:
    def __init__(self, payload, requests_available='8'):
        self.payload = payload
        self.headers = {
            'X-RequestsAvailable': requests_available,
            'X-RequestCounter-Reset': '42',
            'X-API-Version': 'v4',
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode('utf-8')


class PlatformOpenDataSyncTests(TestCase):
    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_ciclos_sucessivos_rotacionam_equipes_ainda_nao_observadas(self, urlopen):
        matches = {'matches': [
            {
                'id': 101, 'utcDate': '2026-07-15T19:00:00Z',
                'status': 'SCHEDULED',
                'homeTeam': {'id': 1, 'name': 'Time 1'},
                'awayTeam': {'id': 2, 'name': 'Time 2'},
                'score': {'fullTime': {'home': None, 'away': None}},
            },
            {
                'id': 102, 'utcDate': '2026-07-16T19:00:00Z',
                'status': 'SCHEDULED',
                'homeTeam': {'id': 3, 'name': 'Time 3'},
                'awayTeam': {'id': 4, 'name': 'Time 4'},
                'score': {'fullTime': {'home': None, 'away': None}},
            },
        ]}

        def team(team_id):
            return {'id': team_id, 'name': f'Time {team_id}', 'squad': []}

        urlopen.side_effect = [
            _Response(matches), _Response({'standings': []}),
            _Response(team(1)), _Response(team(2)),
            _Response(matches), _Response({'standings': []}),
            _Response(team(3)), _Response(team(4)),
        ]

        sync_platform_football_data(
            api_key='segredo', competition_code='BSA', max_teams=2,
        )
        sync_platform_football_data(
            api_key='segredo', competition_code='BSA', max_teams=2,
        )

        requested_team_urls = [
            call.args[0].full_url for call in urlopen.call_args_list
            if '/v4/teams/' in call.args[0].full_url
        ]
        self.assertEqual(requested_team_urls, [
            'https://api.football-data.org/v4/teams/1',
            'https://api.football-data.org/v4/teams/2',
            'https://api.football-data.org/v4/teams/3',
            'https://api.football-data.org/v4/teams/4',
        ])

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_equipes_explicitas_tem_prioridade_e_fixture_completa_limite(self, urlopen):
        matches = {'matches': [{
            'id': 101, 'utcDate': '2026-07-15T19:00:00Z', 'status': 'SCHEDULED',
            'homeTeam': {'id': 100, 'name': 'Time do fixture'},
            'awayTeam': {'id': 200, 'name': 'Outro time'},
            'score': {'fullTime': {'home': None, 'away': None}},
        }]}

        def team(team_id, name):
            return {'id': team_id, 'name': name, 'squad': []}

        urlopen.side_effect = [
            _Response(matches),
            _Response({'standings': []}),
            _Response(team(4241, 'Coritiba')),
            _Response(team(100, 'Time do fixture')),
        ]

        sync_platform_football_data(
            api_key='segredo', competition_code='BSA', max_teams=2,
            team_ids=('4241', '4241'),
        )

        requested_urls = [call.args[0].full_url for call in urlopen.call_args_list]
        self.assertEqual(requested_urls[2:], [
            'https://api.football-data.org/v4/teams/4241',
            'https://api.football-data.org/v4/teams/100',
        ])
        self.assertEqual(
            set(GlobalSportsDataBatch.objects.filter(
                dataset_id__startswith='team-',
            ).values_list('dataset_id', flat=True)),
            {'team-4241-squad', 'team-100-squad'},
        )

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_rejeita_id_explicito_nao_numerico_antes_da_rede(self, urlopen):
        with self.assertRaisesMessage(ValidationError, 'devem ser numéricos'):
            sync_platform_football_data(
                api_key='segredo', competition_code='BSA', max_teams=2,
                team_ids=('coritiba',),
            )
        urlopen.assert_not_called()

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_statsbomb_global_e_idempotente_sem_tenant(self, urlopen):
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
            'id': 'evt-1', 'index': 1, 'period': 1,
            'timestamp': '00:00:00.000',
            'type': {'id': 35, 'name': 'Starting XI'},
            'team': {'id': 1, 'name': 'Azul FC'},
        }]
        urlopen.side_effect = [
            _Response(matches), _Response(events),
            _Response(matches), _Response(events),
        ]

        first = sync_platform_statsbomb_open(
            competition_id='9', season_id='281', max_matches=1, max_events=1,
        )
        second = sync_platform_statsbomb_open(
            competition_id='9', season_id='281', max_matches=1, max_events=1,
        )

        self.assertEqual(first.batch_id, second.batch_id)
        self.assertEqual(GlobalSportsDataBatch.objects.count(), 1)
        self.assertEqual(GlobalSportsDataRecord.objects.count(), 2)
        self.assertEqual(GlobalSportsSyncRun.objects.count(), 2)
        self.assertEqual(first.source.quality, 'research_sample')
        self.assertFalse(first.source.active)
        self.assertIsNotNone(first.source.last_success_at)
        self.assertEqual(first.batch.manifest['limits']['max_events_per_match'], 1)

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_skillcorner_global_registra_falha_e_recuperacao(self, urlopen):
        urlopen.side_effect = OSError('indisponível')
        with self.assertRaises(OSError):
            sync_platform_skillcorner_open(max_matches=1)

        source = GlobalSportsDataSource.objects.get(code='skillcorner-open')
        failed_run = source.sync_runs.get()
        self.assertEqual(failed_run.status, GlobalSportsSyncRun.Status.FAILED)
        self.assertEqual(
            source.operational_status,
            GlobalSportsDataSource.OperationalStatus.DEGRADED,
        )

        catalog = [{
            'id': 2017461, 'date_time': '2025-05-17T09:35:00Z',
            'home_team': {'id': 868, 'short_name': 'Melbourne V FC'},
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
            'players': [{'id': 1}],
        }
        urlopen.side_effect = [_Response(catalog), _Response(metadata)]
        run = sync_platform_skillcorner_open(max_matches=1)

        source.refresh_from_db()
        self.assertEqual(run.status, GlobalSportsSyncRun.Status.COMPLETED)
        self.assertEqual(
            source.operational_status,
            GlobalSportsDataSource.OperationalStatus.RESEARCH_ONLY,
        )
        self.assertEqual(run.batch.record_count, 2)

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_football_data_importa_elenco_global_e_respeita_rate_limit(self, urlopen):
        matches = {'matches': [{
            'id': 101,
            'utcDate': '2026-07-15T19:00:00Z',
            'status': 'SCHEDULED',
            'homeTeam': {'id': 4241, 'name': 'Coritiba FBC'},
            'awayTeam': {'id': 1769, 'name': 'SE Palmeiras'},
            'score': {'fullTime': {'home': None, 'away': None}},
        }]}
        team = {
            'id': 4241, 'name': 'Coritiba FBC', 'shortName': 'Coritiba',
            'lastUpdated': '2026-07-13T18:30:00Z',
            'squad': [{
                'id': 7001, 'name': 'Atleta Real', 'position': 'Defence',
                'dateOfBirth': '2000-01-02', 'nationality': 'Brazil',
            }],
        }
        urlopen.side_effect = [
            _Response(matches), _Response({'standings': []}),
            _Response(team, requests_available='1'),
        ]

        run = sync_platform_football_data(
            api_key='segredo', competition_code='BSA', max_teams=2,
        )

        self.assertEqual(len(run.rate_limit['teams']), 1)
        team_batch = GlobalSportsDataBatch.objects.get(dataset_id='team-4241-squad')
        squad = team_batch.records.get(capability='team_squad')
        player = team_batch.records.get(capability='player_profile')
        self.assertEqual(squad.payload['player_count'], 1)
        self.assertEqual(player.payload['name'], 'Atleta Real')
        self.assertEqual(player.payload['provider_team_id'], '4241')
        self.assertEqual(run.batch.record_count, 1)
        self.assertEqual(GlobalSportsSyncRun.objects.count(), 2)
        self.assertEqual(urlopen.call_count, 3)

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_rotacao_nao_renova_elenco_de_equipe_nao_observada(self, urlopen):
        def matches(team_id, team_name):
            return {'matches': [{
                'id': team_id,
                'utcDate': '2026-07-15T19:00:00Z',
                'status': 'SCHEDULED',
                'homeTeam': {'id': team_id, 'name': team_name},
                'awayTeam': {'id': 9999, 'name': 'Adversário'},
                'score': {'fullTime': {'home': None, 'away': None}},
            }]}

        def team(team_id, name, player_id):
            return {
                'id': team_id, 'name': name,
                'lastUpdated': '2026-07-13T18:30:00Z',
                'squad': [{'id': player_id, 'name': f'Atleta {player_id}'}],
            }

        urlopen.side_effect = [
            _Response(matches(4241, 'Coritiba')),
            _Response({'standings': []}),
            _Response(team(4241, 'Coritiba', 7001)),
        ]
        sync_platform_football_data(
            api_key='segredo', competition_code='BSA', max_teams=1,
        )
        old_record = GlobalSportsDataRecord.objects.get(
            provider_record_id='player:7001',
        )
        old_expiry = old_record.expires_at

        urlopen.side_effect = [
            _Response(matches(1769, 'Palmeiras')),
            _Response({'standings': []}),
            _Response(team(1769, 'Palmeiras', 8001)),
        ]
        sync_platform_football_data(
            api_key='segredo', competition_code='BSA', max_teams=1,
        )

        old_record.refresh_from_db()
        self.assertEqual(old_record.expires_at, old_expiry)
        self.assertTrue(GlobalSportsDataBatch.objects.filter(
            dataset_id='team-1769-squad',
        ).exists())
        self.assertEqual(
            GlobalSportsSyncRun.objects.filter(dataset_id='team-4241-squad').count(),
            1,
        )

    @patch('futebol.services.sports_data_providers.safe_urlopen')
    def test_elenco_a_b_a_reutiliza_versao_e_renova_somente_equipe(self, urlopen):
        matches = {'matches': [{
            'id': 101, 'utcDate': '2026-07-15T19:00:00Z', 'status': 'SCHEDULED',
            'homeTeam': {'id': 4241, 'name': 'Coritiba'},
            'awayTeam': {'id': 9999, 'name': 'Adversário'},
            'score': {'fullTime': {'home': None, 'away': None}},
        }]}

        def team(player_name):
            return {
                'id': 4241, 'name': 'Coritiba',
                'lastUpdated': '2026-07-13T18:30:00Z',
                'squad': [{'id': 7001, 'name': player_name}],
            }

        urlopen.side_effect = [
            _Response(matches), _Response({'standings': []}), _Response(team('A')),
            _Response(matches), _Response({'standings': []}), _Response(team('B')),
            _Response(matches), _Response({'standings': []}), _Response(team('A')),
        ]
        for _index in range(3):
            sync_platform_football_data(
                api_key='segredo', competition_code='BSA', max_teams=1,
                team_ids=('4241',),
            )

        team_batches = GlobalSportsDataBatch.objects.filter(
            dataset_id='team-4241-squad',
        ).order_by('-published_at')
        self.assertEqual(team_batches.count(), 2)
        self.assertEqual(
            team_batches.first().records.get(capability='player_profile').payload['name'],
            'A',
        )
        self.assertEqual(
            GlobalSportsSyncRun.objects.filter(dataset_id='team-4241-squad').count(),
            3,
        )
