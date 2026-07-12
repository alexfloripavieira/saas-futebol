"""Analytics espaciais determinísticos sobre eventos canônicos de futebol."""

from collections import defaultdict


def _point(location):
    if not isinstance(location, list) or len(location) < 2:
        return None
    try:
        return {
            'x': round(max(0, min(100, float(location[0]) / 120 * 100)), 2),
            'y': round(max(0, min(100, float(location[1]) / 80 * 100)), 2),
        }
    except (TypeError, ValueError):
        return None


def _minute(timestamp):
    try:
        parts = str(timestamp or '0:0').split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 60 + int(minutes) + float(seconds) / 60
        minutes, seconds = parts[:2]
        return int(minutes) + float(seconds) / 60
    except (TypeError, ValueError):
        return 0


def build_event_analysis(records, *, team='', period=''):
    events = []
    for record in records:
        payload = record.payload
        if team and payload.get('team') != team:
            continue
        if period and str(payload.get('period') or '') != str(period):
            continue
        point = _point(payload.get('location'))
        event = {
            'id': payload.get('provider_event_id'),
            'type': payload.get('event_type', ''),
            'team': payload.get('team', ''),
            'player': payload.get('player', ''),
            'period': payload.get('period'),
            'minute': _minute(payload.get('timestamp')),
            'point': point,
            'pass': payload.get('pass') or {},
            'shot': payload.get('shot') or {},
        }
        events.append(event)

    teams = sorted({event['team'] for event in events if event['team']})
    spatial = [event for event in events if event['point']]
    cells = defaultdict(int)
    for event in spatial:
        cells[(min(11, int(event['point']['x'] / 100 * 12)),
               min(7, int(event['point']['y'] / 100 * 8)))] += 1
    maximum = max(cells.values(), default=1)
    heatmap = [
        {
            'x': round(column * 100 / 12, 2),
            'y': round(row * 100 / 8, 2),
            'width': round(100 / 12, 2),
            'height': round(100 / 8, 2),
            'count': count,
            'opacity': round(0.12 + 0.68 * count / maximum, 2),
        }
        for (column, row), count in sorted(cells.items())
    ]

    node_positions = defaultdict(list)
    edges = defaultdict(int)
    shots = []
    total_xg = 0.0
    for event in spatial:
        if event['player']:
            node_positions[(event['team'], event['player'])].append(event['point'])
        if event['type'] == 'Pass':
            pass_data = event['pass']
            recipient = pass_data.get('recipient', '')
            completed = not pass_data.get('outcome')
            if completed and event['player'] and recipient:
                edges[((event['team'], event['player']),
                       (event['team'], recipient))] += 1
        if event['type'] == 'Shot':
            shot_data = event['shot']
            xg = float(shot_data.get('xg') or 0)
            total_xg += xg
            shots.append({
                'player': event['player'], 'team': event['team'],
                'x': event['point']['x'], 'y': event['point']['y'],
                'xg': round(xg, 3),
                'radius': round(1.2 + min(5, xg * 8), 2),
                'outcome': shot_data.get('outcome', ''),
                'goal': shot_data.get('outcome') == 'Goal',
            })

    nodes = []
    for (event_team, player), points in node_positions.items():
        nodes.append({
            'key': f'{event_team}:{player}', 'team': event_team, 'player': player,
            'x': round(sum(point['x'] for point in points) / len(points), 2),
            'y': round(sum(point['y'] for point in points) / len(points), 2),
            'actions': len(points),
        })
    positions = {(node['team'], node['player']): node for node in nodes}
    pass_edges = [
        {
            'source': source[1], 'target': target[1], 'count': count,
            'x1': positions[source]['x'], 'y1': positions[source]['y'],
            'x2': positions[target]['x'], 'y2': positions[target]['y'],
            'width': min(6, 0.6 + count * 0.45),
        }
        for (source, target), count in edges.items()
        if source in positions and target in positions
    ]
    return {
        'teams': teams,
        'selected_team': team,
        'selected_period': str(period),
        'event_count': len(events),
        'spatial_count': len(spatial),
        'coverage': round(len(spatial) / len(events) * 100, 1) if events else 0,
        'heatmap': heatmap,
        'actions': spatial[:350],
        'nodes': nodes,
        'pass_edges': pass_edges,
        'shots': shots,
        'total_xg': round(total_xg, 2),
        'heatmap_available': len(spatial) >= 10,
        'pass_network_available': bool(team and pass_edges),
        'shots_available': bool(shots),
        'direction': 'não normalizada; interpretar por período',
        'coordinate_system': 'StatsBomb 120×80 convertido para 0–100',
        'partial': False,
    }
