import os

from django.core.management.base import BaseCommand

from futebol.services.sports_data_providers import (
    sync_platform_football_data,
    sync_platform_skillcorner_open,
    sync_platform_statsbomb_open,
)


class Command(BaseCommand):
    help = 'Atualiza um provider da Base Esportiva Global operada pela plataforma.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider', required=True,
            choices=['football-data-org', 'statsbomb-open', 'skillcorner-open'],
        )
        parser.add_argument('--competition', default='BSA')
        parser.add_argument('--competition-id', default='43')
        parser.add_argument('--season-id', default='106')
        parser.add_argument('--max-matches', type=int, default=1)
        parser.add_argument('--max-events', type=int, default=5000)
        parser.add_argument('--max-teams', type=int, default=4)
        parser.add_argument(
            '--team-id', action='append', default=[],
            help='ID football-data.org prioritário; pode ser repetido.',
        )
        parser.add_argument('--trigger', default='scheduler')

    def handle(self, *args, **options):
        provider = options['provider']
        if provider == 'football-data-org':
            run = sync_platform_football_data(
                api_key=os.getenv('FOOTBALL_DATA_ORG_API_KEY', ''),
                competition_code=options['competition'],
                max_teams=options['max_teams'],
                team_ids=tuple(options['team_id']),
                trigger=options['trigger'],
            )
        elif provider == 'statsbomb-open':
            run = sync_platform_statsbomb_open(
                competition_id=options['competition_id'],
                season_id=options['season_id'],
                max_matches=options['max_matches'],
                max_events=options['max_events'],
                trigger=options['trigger'],
            )
        else:
            run = sync_platform_skillcorner_open(
                max_matches=options['max_matches'],
                trigger=options['trigger'],
            )
        self.stdout.write(self.style.SUCCESS(
            f'Base Esportiva Global atualizada: {run.batch.record_count} registros '
            f'de {run.source.name}.',
        ))
