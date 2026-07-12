import io
import json

from django.test import SimpleTestCase

from futebol.services.tracking_analytics import (
    build_tracking_analysis,
    parse_tracking_stream,
)


class _BoundedStream(io.BytesIO):
    """Falha se o parser tentar materializar o arquivo inteiro de uma vez."""

    def read(self, size=-1):
        if size is None or size < 0:
            raise AssertionError('O tracking deve ser lido incrementalmente.')
        return super().read(size)


def _jsonl(*frames):
    content = ''.join(
        json.dumps(frame, separators=(',', ':')) + '\n'
        for frame in frames
    )
    return _BoundedStream(content.encode('utf-8'))


def _frame(timestamp, *, period=1, blue_a1_x=0, blue_a1_visible=True):
    return {
        'timestamp': timestamp,
        'period': period,
        'players': [
            {
                'player_id': 'azul-1', 'team_id': 'azul',
                'x': blue_a1_x, 'y': -10, 'visible': blue_a1_visible,
            },
            {
                'player_id': 'azul-2', 'team_id': 'azul',
                'x': 10, 'y': 10, 'visible': True,
            },
            {
                'player_id': 'verde-1', 'team_id': 'verde',
                'x': -5, 'y': -5, 'visible': True,
            },
            {
                'player_id': 'verde-2', 'team_id': 'verde',
                'x': -5, 'y': 5, 'visible': True,
            },
        ],
        'ball': {'x': 0, 'y': 0, 'visible': True},
    }


class TrackingStreamParserTests(SimpleTestCase):
    def test_processa_jsonl_incrementalmente_e_preserva_ordem(self):
        stream = _jsonl(
            _frame(0.0, blue_a1_x=0),
            _frame(0.1, blue_a1_x=1),
            _frame(0.2, blue_a1_x=2),
        )

        frames = list(parse_tracking_stream(stream))

        self.assertEqual(len(frames), 3)
        self.assertEqual([frame['timestamp'] for frame in frames], [0.0, 0.1, 0.2])
        self.assertEqual(frames[1]['players'][0]['player_id'], 'azul-1')
        self.assertEqual(frames[1]['players'][0]['x'], 1.0)
        self.assertEqual(frames[1]['ball'], {'x': 0.0, 'y': 0.0, 'visible': True})

    def test_ignora_linhas_vazias_sem_criar_frames_fantasmas(self):
        raw = (
            json.dumps(_frame(0.0)) + '\n\n  \n' +
            json.dumps(_frame(0.1, blue_a1_x=1)) + '\n'
        ).encode('utf-8')

        frames = list(parse_tracking_stream(_BoundedStream(raw)))

        self.assertEqual(len(frames), 2)
        self.assertEqual([frame['timestamp'] for frame in frames], [0.0, 0.1])

    def test_converte_timestamp_horas_minutos_segundos_da_skillcorner(self):
        frame = _frame('00:12:30.50')

        parsed = next(parse_tracking_stream(_jsonl(frame)))

        self.assertEqual(parsed['timestamp'], 750.5)


class TrackingAnalyticsTests(SimpleTestCase):
    def setUp(self):
        self.frames = list(parse_tracking_stream(_jsonl(
            _frame(0.0, blue_a1_x=0),
            _frame(0.1, blue_a1_x=1),
            _frame(0.2, blue_a1_x=2),
        )))

    def test_calcula_metricas_posicionais_e_trajetoria_deterministicas(self):
        analysis = build_tracking_analysis(self.frames, team_id='azul')

        self.assertTrue(analysis['available'])
        self.assertEqual(analysis['frame_count'], 3)
        self.assertEqual(analysis['coverage'], 100.0)
        self.assertEqual(analysis['average_width'], 20.0)
        self.assertEqual(analysis['average_depth'], 9.0)

        athlete = next(
            player for player in analysis['players']
            if player['player_id'] == 'azul-1'
        )
        self.assertEqual(athlete['distance'], 2.0)
        self.assertNotIn('average_speed', athlete)
        self.assertEqual(
            athlete['trajectory'],
            [
                {'timestamp': 0.0, 'x': 0.0, 'y': -10.0},
                {'timestamp': 0.1, 'x': 1.0, 'y': -10.0},
                {'timestamp': 0.2, 'x': 2.0, 'y': -10.0},
            ],
        )

    def test_filtra_equipe_e_periodo(self):
        frames = self.frames + list(parse_tracking_stream(_jsonl(
            _frame(45.0, period=2, blue_a1_x=20),
        )))

        analysis = build_tracking_analysis(frames, team_id='verde', period='1')

        self.assertEqual(analysis['frame_count'], 3)
        self.assertEqual({player['player_id'] for player in analysis['players']}, {
            'verde-1', 'verde-2',
        })
        self.assertEqual(analysis['average_width'], 10.0)
        self.assertEqual(analysis['average_depth'], 0.0)

    def test_nao_inventa_velocidade_quando_jogador_fica_invisivel(self):
        frames = list(parse_tracking_stream(_jsonl(
            _frame(0.0, blue_a1_x=0),
            _frame(0.1, blue_a1_x=1, blue_a1_visible=False),
            _frame(0.2, blue_a1_x=2),
        )))

        analysis = build_tracking_analysis(frames, team_id='azul')
        athlete = next(
            player for player in analysis['players']
            if player['player_id'] == 'azul-1'
        )

        self.assertEqual(athlete['trajectory'], [
            {'timestamp': 0.0, 'x': 0.0, 'y': -10.0},
            {'timestamp': 0.2, 'x': 2.0, 'y': -10.0},
        ])
        self.assertNotIn('average_speed', athlete)
        self.assertEqual(athlete['distance'], 0.0)
