#!/usr/bin/env python3
"""Mantém a Base Esportiva Global atualizada pela infraestrutura da plataforma."""

import os
import subprocess
import sys
import time
from pathlib import Path


def run_provider(project_root, provider, extra):
    command = [
        sys.executable,
        'src/manage.py',
        'sync_platform_sports_provider',
        '--provider',
        provider,
        *extra,
    ]
    completed = subprocess.run(command, cwd=project_root)
    if completed.returncode:
        print(f'[sports-sync] falha em {provider}: exit={completed.returncode}', flush=True)
    return completed.returncode


def run_provider_with_retry(project_root, provider, extra):
    attempts = max(1, int(os.getenv('SPORTS_SYNC_RETRY_ATTEMPTS', '3')))
    base_delay = max(1, int(os.getenv('SPORTS_SYNC_RETRY_DELAY_SECONDS', '30')))
    for attempt in range(1, attempts + 1):
        status = run_provider(project_root, provider, extra)
        if status == 0:
            return 0
        if attempt < attempts:
            delay = min(300, base_delay * (2 ** (attempt - 1)))
            print(
                f'[sports-sync] nova tentativa de {provider} em {delay}s '
                f'({attempt + 1}/{attempts}).',
                flush=True,
            )
            time.sleep(delay)
    return status


def main():
    project_root = Path(os.getenv('SPORTS_SYNC_PROJECT_ROOT', '/app'))
    interval = max(900, int(os.getenv('SPORTS_SYNC_INTERVAL_SECONDS', '21600')))
    once = '--once' in sys.argv

    while True:
        statuses = [
            run_provider_with_retry(
                project_root, 'football-data-org',
                [
                    '--competition', os.getenv('SPORTS_SYNC_COMPETITION', 'BSA'),
                    '--max-teams', os.getenv('FOOTBALL_DATA_ORG_MAX_TEAMS', '4'),
                ],
            ),
            run_provider_with_retry(
                project_root, 'statsbomb-open',
                [
                    '--competition-id', os.getenv('STATSBOMB_OPEN_COMPETITION_ID', '43'),
                    '--season-id', os.getenv('STATSBOMB_OPEN_SEASON_ID', '106'),
                    '--max-matches', os.getenv('STATSBOMB_OPEN_MAX_MATCHES', '1'),
                    '--max-events', os.getenv('STATSBOMB_OPEN_MAX_EVENTS', '5000'),
                ],
            ),
            run_provider_with_retry(
                project_root, 'skillcorner-open',
                ['--max-matches', os.getenv('SKILLCORNER_OPEN_MAX_MATCHES', '2')],
            ),
        ]
        if once:
            return 0 if all(status == 0 for status in statuses) else 1
        time.sleep(interval)


if __name__ == '__main__':
    raise SystemExit(main())
