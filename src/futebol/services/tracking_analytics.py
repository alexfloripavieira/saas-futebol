"""Ingestão e analytics determinísticos de tracking posicional."""

import json
import math
import re


SAFE_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')


def build_tracking_context(metadata):
    """Normaliza identidades, cores e direções declaradas pela fonte."""
    metadata = metadata or {}
    teams = {}
    for key, role in (('home_team', 'home'), ('away_team', 'away')):
        team = metadata.get(key) or {}
        team_id = str(team.get('id') or '')
        if not team_id:
            continue
        kit = (
            metadata.get(f'{role}_team_kit') or team.get('kit') or
            team.get('jersey') or {}
        )
        color = (
            kit.get('jersey_color') or team.get('jersey_color') or
            ('#68b8ff' if role == 'home' else '#ff8e98')
        )
        if not SAFE_COLOR.match(str(color)):
            color = '#68b8ff' if role == 'home' else '#ff8e98'
        teams[team_id] = {
            'id': team_id, 'name': team.get('short_name') or team.get('name') or team_id,
            'color': color, 'role': role,
        }
    players = {}
    for player in metadata.get('players') or []:
        player_id = str(player.get('id') or player.get('player_id') or '')
        if not player_id:
            continue
        role = player.get('player_role') or {}
        players[player_id] = {
            'id': player_id, 'team_id': str(player.get('team_id') or ''),
            'name': player.get('short_name') or player.get('name') or player_id,
            'number': player.get('number'),
            'position': role.get('acronym') or role.get('name') or '',
        }
    home_id = next((key for key, value in teams.items() if value['role'] == 'home'), '')
    away_id = next((key for key, value in teams.items() if value['role'] == 'away'), '')
    directions = {}
    sides = metadata.get('home_team_side') or []
    for index, side in enumerate(sides, start=1):
        home_direction = 1 if side == 'left_to_right' else -1 if side == 'right_to_left' else 0
        if home_direction and home_id:
            directions[str(index)] = {
                home_id: home_direction, away_id: -home_direction,
            }
    pitch = metadata.get('pitch_size') or {}
    def dimension(value, fallback, minimum, maximum):
        try:
            number = float(value)
            return number if math.isfinite(number) and minimum <= number <= maximum else fallback
        except (TypeError, ValueError):
            return fallback
    return {
        'teams': teams, 'players': players, 'directions_by_period': directions,
        'pitch_length': dimension(
            metadata.get('pitch_length') or pitch.get('length'), 105, 90, 120,
        ),
        'pitch_width': dimension(
            metadata.get('pitch_width') or pitch.get('width'), 68, 45, 90,
        ),
    }


def _seconds(value):
    if isinstance(value, (int, float)):
        return float(value)
    try:
        hours, minutes, seconds = str(value).split(':')
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (TypeError, ValueError):
        raise ValueError('Timestamp de tracking inválido.')


def parse_tracking_stream(stream, *, player_teams=None, max_line_bytes=1_000_000):
    """Produz frames canônicos lendo JSONL linha a linha."""
    player_teams = player_teams or {}
    previous_frame = None
    for raw_line in stream:
        if len(raw_line) > max_line_bytes:
            raise ValueError('Linha de tracking excede o limite permitido.')
        if not raw_line.strip():
            continue
        try:
            raw = json.loads(raw_line)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('Arquivo de tracking contém JSONL inválido.') from exc
        frame_number = raw.get('frame', 0 if previous_frame is None else previous_frame + 1)
        if not isinstance(frame_number, int) or (
            previous_frame is not None and frame_number <= previous_frame
        ):
            raise ValueError('Sequência de frames de tracking inválida.')
        previous_frame = frame_number
        players = []
        for player in raw.get('player_data') or raw.get('players') or []:
            player_id = str(player.get('player_id') or '')
            x, y = player.get('x'), player.get('y')
            if not player_id or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                continue
            if abs(x) > 60 or abs(y) > 45:
                continue
            players.append({
                'player_id': player_id,
                'team_id': str(player.get('team_id') or player_teams.get(player_id) or ''),
                'x': float(x), 'y': float(y),
                'detected': bool(player.get('is_detected', player.get('visible', False))),
            })
        ball = raw.get('ball_data') or raw.get('ball') or {}
        possession = raw.get('possession') or {}
        possession_player_id = str(possession.get('player_id') or '')
        yield {
            'frame': frame_number,
            'timestamp': _seconds(raw.get('timestamp') or 0),
            'period': int(raw.get('period') or 0),
            'players': players,
            'ball': ({
                'x': float(ball.get('x')), 'y': float(ball.get('y')),
                'visible': bool(ball.get('is_detected', ball.get('visible', False))),
            } if isinstance(ball.get('x'), (int, float)) and
                 isinstance(ball.get('y'), (int, float)) else {}),
            'possession_team_id': str(
                possession.get('team_id') or player_teams.get(possession_player_id) or ''
            ),
        }


def _percent(x, y, pitch_length=105, pitch_width=68):
    return {
        'x': round((x + pitch_length / 2) / pitch_length * 100, 2),
        'y': round((y + pitch_width / 2) / pitch_width * 100, 2),
    }


def _structure(players):
    by_team = {}
    for player in players:
        if not player['team_id']:
            continue
        by_team.setdefault(player['team_id'], []).append(player)
    metrics = {}
    for team_id, members in by_team.items():
        detected = [member for member in members if member['detected']]
        if len(detected) < 2:
            continue
        xs = [member['x'] for member in detected]
        ys = [member['y'] for member in detected]
        width = max(ys) - min(ys)
        depth = max(xs) - min(xs)
        metrics[team_id] = {
            'width': round(width, 2), 'depth': round(depth, 2),
            'compactness': round(math.hypot(width, depth), 2),
            'centroid_x': round(sum(xs) / len(xs), 2),
            'centroid_y': round(sum(ys) / len(ys), 2),
            'detected_players': len(detected),
        }
    return metrics


def build_tracking_analysis(frames, *, team_id='', period='', preview_limit=240, context=None):
    """Calcula cobertura, estrutura e uma prévia leve para SVG."""
    widths, depths, preview, trajectories = [], [], [], {}
    preview_by_period = {}
    total_positions = detected_positions = frame_count = analyzable_frame_count = 0
    previous = {}
    distance = {}
    player_trajectories = {}
    context = context or {}
    pitch_length = context.get('pitch_length', 105)
    pitch_width = context.get('pitch_width', 68)
    for frame in frames:
        if period and str(frame['period']) != str(period):
            continue
        frame_count += 1
        players = [
            player for player in frame['players']
            if not team_id or player['team_id'] == str(team_id)
        ]
        if not players:
            continue
        analyzable_frame_count += 1
        total_positions += len(players)
        detected_positions += sum(player['detected'] for player in players)
        detected = [player for player in players if player['detected']]
        if len(detected) >= 2:
            widths.append(max(p['y'] for p in detected) - min(p['y'] for p in detected))
            depths.append(max(p['x'] for p in detected) - min(p['x'] for p in detected))
        for player in detected:
            old = previous.get(player['player_id'])
            if old and frame['timestamp'] > old[0] and frame['timestamp'] - old[0] <= 1:
                distance[player['player_id']] = distance.get(player['player_id'], 0) + math.hypot(
                    player['x'] - old[1], player['y'] - old[2],
                )
            previous[player['player_id']] = (
                frame['timestamp'], player['x'], player['y'],
            )
            trajectory = player_trajectories.setdefault(player['player_id'], [])
            if len(trajectory) < preview_limit:
                trajectory.append({
                    'timestamp': frame['timestamp'], 'x': player['x'], 'y': player['y'],
                })
        invisible_ids = {p['player_id'] for p in players if not p['detected']}
        for player_id in invisible_ids:
            previous.pop(player_id, None)
        preview_count = preview_by_period.get(str(frame['period']), 0)
        if preview_count < preview_limit:
            points = []
            for player in players:
                point = _percent(player['x'], player['y'], pitch_length, pitch_width)
                point.update({
                    'player_id': player['player_id'], 'team_id': player['team_id'],
                    'detected': player['detected'],
                    'raw_x': player['x'], 'raw_y': player['y'],
                })
                points.append(point)
                trajectories.setdefault(player['player_id'], []).append(point)
            ball = frame.get('ball') or {}
            ball_point = (
                _percent(ball['x'], ball['y'], pitch_length, pitch_width)
                if isinstance(ball.get('x'), (int, float)) and
                isinstance(ball.get('y'), (int, float)) else None
            )
            if ball_point:
                ball_point.update({
                    'raw_x': ball['x'], 'raw_y': ball['y'],
                    'detected': ball.get('visible', False),
                })
            team_metrics = _structure(players)
            directions = (context.get('directions_by_period') or {}).get(
                str(frame['period']), {},
            )
            for metric_team, metrics in team_metrics.items():
                direction = directions.get(metric_team)
                metrics['block_height'] = (
                    round(pitch_length / 2 + metrics['centroid_x'] * direction, 2)
                    if direction else None
                )
            preview.append({
                'frame': frame['frame'], 'timestamp': frame['timestamp'],
                'period': frame['period'], 'players': points, 'ball': ball_point,
                'possession_team_id': frame.get('possession_team_id', ''),
                'team_metrics': team_metrics,
            })
            preview_by_period[str(frame['period'])] = preview_count + 1
    coverage = detected_positions / total_positions * 100 if total_positions else 0
    available = frame_count >= 3 and total_positions > 0
    players = [{
        'player_id': player_id,
        'distance': round(distance.get(player_id, 0), 2),
        'trajectory': trajectory,
    } for player_id, trajectory in player_trajectories.items()]
    return {
        'available': available,
        'reason': '' if available else 'Frames insuficientes para análise posicional.',
        'frame_count': frame_count,
        'analyzable_frame_count': analyzable_frame_count,
        'coverage': round(coverage, 1),
        'coverage_label': 'posições detectadas; demais posições são extrapoladas',
        'average_width': round(sum(widths) / len(widths), 2) if widths else None,
        'average_depth': round(sum(depths) / len(depths), 2) if depths else None,
        'distance_by_player': {key: round(value, 2) for key, value in distance.items()},
        'players': players,
        'preview': preview,
        'trajectories': trajectories,
        'coordinate_system': 'metros com origem no centro; visual convertido para 0–100',
        'direction': 'declarada por período' if context.get('directions_by_period') else 'não inferida',
    }
