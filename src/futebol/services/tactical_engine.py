"""Motor determinístico de momentos táticos sobre tracking canônico."""

import hashlib
import json
import math


AGENT_ROUTES = {
    'pressing': ['coordinator', 'tactical', 'defense', 'attack', 'physical'],
    'offensive_transition': ['coordinator', 'tactical', 'attack', 'defense', 'scout'],
    'low_block': ['coordinator', 'tactical', 'defense', 'attack', 'scout'],
    'wide_attack': ['coordinator', 'tactical', 'attack', 'defense', 'scout'],
}
AGENT_LABELS = {
    'coordinator': 'Coordenador Técnico', 'tactical': 'Analista Tático',
    'defense': 'Preparador de Defesa', 'attack': 'Preparador de Ataque',
    'physical': 'Preparador Físico', 'scout': 'Olheiro',
}
INSIGHT_TEMPLATES = {
    'pressing': {
        'tactical': 'Avaliar o gatilho, a altura e a sustentação da pressão observada.',
        'defense': 'Revisar coberturas atrás dos jogadores que saltam para pressionar.',
        'attack': 'Preparar rotas de saída para superar pressão com dois ou mais oponentes.',
        'physical': 'Validar a repetição do esforço antes de prescrever intensidade de pressão.',
        'scout': 'Registrar os gatilhos usados pelo adversário para iniciar a pressão.',
        'coordinator': 'Consolidar riscos e alternativas da pressão para decisão do treinador.',
    },
    'low_block': {
        'tactical': 'Comparar compactação, largura e espaço entrelinhas no bloco baixo.',
        'defense': 'Revisar proteção da área e controle do corredor oposto.',
        'attack': 'Explorar circulação rápida, amplitude e entradas no espaço entrelinhas.',
        'scout': 'Catalogar recorrência e vulnerabilidades do bloco baixo adversário.',
        'coordinator': 'Apresentar alternativas contra o bloco sem alterar o plano oficial.',
    },
    'offensive_transition': {
        'tactical': 'Avaliar ocupação dos corredores e apoio após a recuperação da posse.',
        'attack': 'Ensaiar primeira ação e profundidade na transição ofensiva.',
        'defense': 'Preparar proteção preventiva contra a transição observada.',
        'scout': 'Registrar origem, corredor e destino das transições adversárias.',
        'coordinator': 'Consolidar o risco da transição para revisão humana.',
    },
    'wide_attack': {
        'tactical': 'Avaliar superioridade e ocupação do corredor lateral.',
        'attack': 'Preparar apoio, ultrapassagem e presença na área pelo lado observado.',
        'defense': 'Revisar dobra de marcação e proteção do corredor central.',
        'scout': 'Registrar lado preferencial e padrão de progressão adversário.',
        'coordinator': 'Comparar respostas ao ataque lateral para decisão do treinador.',
    },
}


def _distance(first, second):
    return math.hypot(first['raw_x'] - second['raw_x'], first['raw_y'] - second['raw_y'])


def _group_candidates(candidates, *, minimum_duration):
    groups = []
    for candidate in candidates:
        delta = candidate['timestamp'] - groups[-1][-1]['timestamp'] if groups else None
        if (
            groups and candidate['period'] == groups[-1][-1]['period'] and
            0 <= delta <= 0.5
        ):
            groups[-1].append(candidate)
        else:
            groups.append([candidate])
    return [group for group in groups if group[-1]['timestamp'] - group[0]['timestamp'] >= minimum_duration]


def _evidence(moment_type, group, *, team_id, metrics, source_context):
    first, last = group[0], group[-1]
    labels = {
        'pressing': 'Pressão sustentada', 'offensive_transition': 'Transição ofensiva',
        'low_block': 'Bloco baixo', 'wide_attack': 'Ataque por corredor',
    }
    identity = {
        'type': moment_type, 'team': team_id, 'period': first['period'],
        'start': first['timestamp'], 'end': last['timestamp'],
        'artifact': source_context.get('artifact_id'),
    }
    evidence_id = hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    eligible = (
        source_context.get('operational_use_allowed') is True and
        source_context.get('usage_scope') == 'operational' and
        bool(source_context.get('license_id')) and
        source_context.get('quality') not in {'research_sample', 'synthetic'}
    )
    return {
        'kind': 'tactical_moment', 'evidence_id': evidence_id,
        'record_id': (
            f"tracking-artifact-{source_context.get('artifact_id')}:{moment_type}:"
            f"{first['period']}:{round(first['timestamp'] * 10)}"
        ),
        'capability': 'tracking_tactical_moments',
        'description': (
            f"{labels[moment_type]} da equipe {team_id} entre "
            f"{first['timestamp']:.1f}s e {last['timestamp']:.1f}s."
        ),
        'moment_type': moment_type, 'team_id': team_id,
        'period': first['period'], 'started_at': first['timestamp'],
        'ended_at': last['timestamp'],
        'duration': round(last['timestamp'] - first['timestamp'], 2),
        'metrics': metrics,
        'frame_refs': {
            'first': first['frame'], 'last': last['frame'], 'count': len(group),
        },
        'agent_routes': AGENT_ROUTES[moment_type],
        'agent_route_labels': [AGENT_LABELS[key] for key in AGENT_ROUTES[moment_type]],
        'provenance': {
            key: source_context.get(key) for key in (
                'source_code', 'batch_id', 'artifact_id', 'content_hash', 'schema_version',
                'license_id', 'attribution', 'usage_scope',
            )
        } | {'algorithm_version': '1.0.0'},
        'quality': {
            'eligible_for_operational_use': eligible,
            'detected_position_ratio': source_context.get('detected_position_ratio'),
        },
        'validity': 'valid' if eligible else 'research_only',
        'limitations': ([] if eligible else [
            'Amostra pública destinada exclusivamente a treinamento e P&D.',
        ]),
    }


def detect_tactical_moments(frames, *, team_directions=None, source_context=None):
    """Detecta momentos somente quando posse/direção estão explicitamente disponíveis."""
    frames = list(frames)
    team_directions = team_directions or {}
    source_context = source_context or {}
    limitations = []
    if not any(frame.get('possession_team_id') for frame in frames):
        limitations.append('possession_unavailable')
    if not team_directions:
        limitations.append('direction_unavailable')
    candidates = {kind: {} for kind in AGENT_ROUTES}
    previous_possession = ''
    transition_start = None
    previous_period = None
    missing_direction = False
    for frame in frames:
        if previous_period is not None and frame.get('period') != previous_period:
            previous_possession = ''
            transition_start = None
        previous_period = frame.get('period')
        possession = frame.get('possession_team_id', '')
        ball = frame.get('ball')
        period_directions = team_directions.get(str(frame.get('period')), team_directions)
        if not isinstance(period_directions, dict) or not period_directions:
            missing_direction = True
        if possession and ball:
            opponents = [
                player for player in frame['players']
                if player['team_id'] != possession and player['detected']
            ]
            carriers = [
                player for player in frame['players']
                if player['team_id'] == possession and player['detected'] and
                _distance(player, ball) <= 3
            ]
            if carriers:
                pressing_team = opponents[0]['team_id'] if opponents else ''
                close = sum(_distance(player, carriers[0]) <= 6 for player in opponents)
                if pressing_team and close >= 2:
                    candidates['pressing'].setdefault(pressing_team, []).append(frame)
            direction = period_directions.get(possession) if isinstance(period_directions, dict) else None
            if direction and abs(ball['raw_y']) >= 17:
                candidates['wide_attack'].setdefault(possession, []).append(frame)
            if previous_possession and possession != previous_possession and direction:
                transition_start = (frame, possession, ball['raw_x'])
            if transition_start and possession == transition_start[1]:
                start, team_id, start_x = transition_start
                elapsed = frame['timestamp'] - start['timestamp']
                if elapsed <= 6 and (ball['raw_x'] - start_x) * direction >= 15:
                    candidates['offensive_transition'].setdefault(team_id, []).extend([start, frame])
                    transition_start = None
                elif elapsed > 6:
                    transition_start = None
        previous_possession = possession or previous_possession
        if isinstance(period_directions, dict):
            for team_id, direction in period_directions.items():
                metrics = (frame.get('team_metrics') or {}).get(team_id) or {}
                if (
                    metrics.get('detected_players', 0) >= 7 and
                    metrics.get('depth', 999) <= 30 and
                    metrics.get('centroid_x', 0) * direction <= -17.5
                ):
                    candidates['low_block'].setdefault(team_id, []).append(frame)

    moments = []
    durations = {'pressing': 0.8, 'wide_attack': 2, 'low_block': 3}
    for kind in ('pressing', 'wide_attack', 'low_block'):
        for team_id, items in candidates[kind].items():
            for group in _group_candidates(items, minimum_duration=durations[kind]):
                moments.append(_evidence(
                    kind, group, team_id=team_id,
                    metrics={'samples': len(group)}, source_context=source_context,
                ))
    for team_id, items in candidates['offensive_transition'].items():
        for pair in zip(items[::2], items[1::2]):
            moments.append(_evidence(
                'offensive_transition', list(pair), team_id=team_id,
                metrics={'progression_m': 15}, source_context=source_context,
            ))
    moments.sort(key=lambda item: (item['started_at'], item['moment_type'], item['team_id']))
    if missing_direction and 'direction_unavailable' not in limitations:
        limitations.append('direction_unavailable_for_some_periods')
    return {
        'status': 'unavailable' if not moments and limitations else 'partial' if limitations else 'available',
        'moments': moments, 'limitations': limitations,
        'algorithm': {'name': 'tracking-tactical-moments', 'version': '1.0.0'},
    }


def build_agent_training_insights(engine):
    """Converte momentos em pareceres de treinamento, sempre sujeitos à revisão humana."""
    insights = {}
    for moment in engine.get('moments') or []:
        for agent in moment['agent_routes']:
            suggestion = INSIGHT_TEMPLATES.get(moment['moment_type'], {}).get(agent)
            if not suggestion:
                continue
            item = insights.setdefault(agent, {
                'agent': agent, 'agent_label': AGENT_LABELS[agent],
                'suggestions': [], 'evidence_ids': [], 'confidence': 55,
                'mode': 'training', 'requires_human_review': True,
                'eligible_for_operational_use': False,
            })
            if suggestion not in item['suggestions']:
                item['suggestions'].append(suggestion)
            item['evidence_ids'].append(moment['evidence_id'])
    return [insights[key] for key in sorted(insights)]
