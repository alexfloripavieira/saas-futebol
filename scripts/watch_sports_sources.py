#!/usr/bin/env python3
"""Sincroniza periodicamente fontes esportivas autorizadas e amostras de P&D."""

import os
import subprocess
import sys
import time
from pathlib import Path


def run_provider(project_root, common, provider, extra):
    command = [
        sys.executable,
        'src/manage.py',
        'sync_sports_provider',
        *common,
        '--provider',
        provider,
        *extra,
    ]
    completed = subprocess.run(command, cwd=project_root)
    if completed.returncode:
        print(f'[sports-sync] falha em {provider}: exit={completed.returncode}', flush=True)
    return completed.returncode


def main():
    project_root = Path(os.getenv('SPORTS_SYNC_PROJECT_ROOT', '/app'))
    tenant = os.getenv('SPORTS_SYNC_TENANT', 'avai')
    user = os.getenv('SPORTS_SYNC_USER', 'demo_admin')
    interval = max(900, int(os.getenv('SPORTS_SYNC_INTERVAL_SECONDS', '21600')))
    once = '--once' in sys.argv
    common = ['--tenant', tenant, '--user', user]

    while True:
        statuses = [
            run_provider(
                project_root, common, 'football-data-org',
                ['--competition', os.getenv('SPORTS_SYNC_COMPETITION', 'BSA')],
            ),
            run_provider(
                project_root, common, 'statsbomb-open',
                [
                    '--competition-id', os.getenv('STATSBOMB_OPEN_COMPETITION_ID', '43'),
                    '--season-id', os.getenv('STATSBOMB_OPEN_SEASON_ID', '106'),
                    '--max-matches', os.getenv('STATSBOMB_OPEN_MAX_MATCHES', '1'),
                    '--max-events', os.getenv('STATSBOMB_OPEN_MAX_EVENTS', '200'),
                ],
            ),
            run_provider(
                project_root, common, 'skillcorner-open',
                ['--max-matches', os.getenv('SKILLCORNER_OPEN_MAX_MATCHES', '2')],
            ),
        ]
        if once:
            return 0 if all(status == 0 for status in statuses) else 1
        time.sleep(interval)


if __name__ == '__main__':
    raise SystemExit(main())
