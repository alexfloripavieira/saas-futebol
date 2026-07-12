"""Ingestão e analytics determinísticos de tracking posicional."""

import json
import math


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
        }


def _percent(x, y, pitch_length=105, pitch_width=68):
    return {
        'x': round((x + pitch_length / 2) / pitch_length * 100, 2),
        'y': round((y + pitch_width / 2) / pitch_width * 100, 2),
    }


def build_tracking_analysis(frames, *, team_id='', period='', preview_limit=240):
    """Calcula cobertura, estrutura e uma prévia leve para SVG."""
    widths, depths, preview, trajectories = [], [], [], {}
    total_positions = detected_positions = frame_count = analyzable_frame_count = 0
    previous = {}
    distance = {}
    player_trajectories = {}
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
        if len(preview) < preview_limit:
            points = []
            for player in players:
                point = _percent(player['x'], player['y'])
                point.update({
                    'player_id': player['player_id'], 'team_id': player['team_id'],
                    'detected': player['detected'],
                })
                points.append(point)
                trajectories.setdefault(player['player_id'], []).append(point)
            preview.append({
                'frame': frame['frame'], 'timestamp': frame['timestamp'],
                'period': frame['period'], 'players': points,
            })
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
        'direction': 'não inferida',
    }
