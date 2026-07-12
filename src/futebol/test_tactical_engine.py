from django.test import SimpleTestCase

from futebol.services.tactical_engine import (
    build_agent_training_insights, detect_tactical_moments,
)


def _frame(timestamp, *, possession='azul', defenders=2, ball_x=0, ball_y=0):
    players = [{
        'player_id': 'portador', 'team_id': 'azul', 'raw_x': ball_x,
        'raw_y': ball_y, 'detected': True, 'x': 50, 'y': 50,
    }]
    players.extend({
        'player_id': f'verde-{index}', 'team_id': 'verde',
        'raw_x': ball_x + 4 + index, 'raw_y': ball_y,
        'detected': True, 'x': 50, 'y': 50,
    } for index in range(defenders))
    return {
        'frame': round(timestamp * 10), 'timestamp': timestamp, 'period': 1,
        'possession_team_id': possession, 'players': players,
        'ball': {'raw_x': ball_x, 'raw_y': ball_y, 'x': 50, 'y': 50},
        'team_metrics': {},
    }


class TacticalEngineTests(SimpleTestCase):
    def test_pressao_exige_posse_explicita(self):
        frames = [_frame(index / 10, possession='') for index in range(10)]

        result = detect_tactical_moments(frames, team_directions={'1': {'azul': 1}})

        self.assertEqual(result['moments'], [])
        self.assertIn('possession_unavailable', result['limitations'])

    def test_detecta_pressao_sustentada_e_gera_evidencia_canonica(self):
        frames = [_frame(index / 10) for index in range(10)]

        result = detect_tactical_moments(
            frames, team_directions={'1': {'azul': 1, 'verde': -1}},
            source_context={
                'artifact_id': 8, 'batch_id': 7, 'source_code': 'skillcorner-open',
                'content_hash': 'a' * 64, 'schema_version': 'v1',
                'quality': 'research_sample', 'detected_position_ratio': 1,
            },
        )

        pressing = [item for item in result['moments'] if item['moment_type'] == 'pressing']
        self.assertEqual(len(pressing), 1)
        self.assertTrue(pressing[0]['description'])
        self.assertEqual(pressing[0]['validity'], 'research_only')
        self.assertFalse(pressing[0]['quality']['eligible_for_operational_use'])
        self.assertIn('physical', pressing[0]['agent_routes'])
        insights = build_agent_training_insights(result)
        physical = next(item for item in insights if item['agent'] == 'physical')
        self.assertTrue(physical['suggestions'])
        self.assertTrue(physical['requires_human_review'])
        self.assertFalse(physical['eligible_for_operational_use'])

    def test_evidence_id_e_deterministico(self):
        frames = [_frame(index / 10) for index in range(10)]
        context = {'1': {'azul': 1, 'verde': -1}}
        first = detect_tactical_moments(frames, team_directions=context)
        second = detect_tactical_moments(frames, team_directions=context)

        self.assertEqual(
            first['moments'][0]['evidence_id'], second['moments'][0]['evidence_id'],
        )

    def test_gate_operacional_e_fail_closed_sem_direitos_explicitos(self):
        frames = [_frame(index / 10) for index in range(10)]
        directions = {'1': {'azul': 1, 'verde': -1}}
        research = detect_tactical_moments(
            frames, team_directions=directions,
            source_context={
                'quality': 'verified', 'usage_scope': 'research_only',
                'license_id': 'open', 'operational_use_allowed': True,
            },
        )
        licensed = detect_tactical_moments(
            frames, team_directions=directions,
            source_context={
                'quality': 'verified', 'usage_scope': 'operational',
                'license_id': 'licensed', 'operational_use_allowed': True,
            },
        )

        self.assertEqual(research['moments'][0]['validity'], 'research_only')
        self.assertEqual(licensed['moments'][0]['validity'], 'valid')

    def test_nao_agrupa_momentos_entre_periodos(self):
        frames = [
            *[_frame(2699 + index / 10) for index in range(10)],
            *[{**_frame(index / 10), 'period': 2} for index in range(10)],
        ]
        result = detect_tactical_moments(
            frames,
            team_directions={
                '1': {'azul': 1, 'verde': -1},
                '2': {'azul': -1, 'verde': 1},
            },
        )

        pressing = [item for item in result['moments'] if item['moment_type'] == 'pressing']
        self.assertEqual(len(pressing), 2)
        self.assertEqual({item['period'] for item in pressing}, {1, 2})
