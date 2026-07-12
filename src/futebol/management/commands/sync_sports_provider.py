import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant
from futebol.services.sports_data_providers import (
    sync_football_data_org,
    sync_skillcorner_open,
    sync_statsbomb_open,
)


class Command(BaseCommand):
    help = 'Sincroniza um provider esportivo autorizado para um tenant.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument(
            '--provider', required=True,
            choices=['football-data-org', 'statsbomb-open', 'skillcorner-open'],
        )
        parser.add_argument('--user', required=True)
        parser.add_argument('--competition', default='BSA')
        parser.add_argument('--competition-id')
        parser.add_argument('--season-id')
        parser.add_argument('--max-matches', type=int, default=1)
        parser.add_argument('--max-events', type=int, default=200)

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'], active=True)
        except Tenant.DoesNotExist as exc:
            raise CommandError('Tenant ativo não encontrado.') from exc
        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=options['user'], is_active=True)
        except user_model.DoesNotExist as exc:
            raise CommandError('Usuário ativo não encontrado.') from exc

        if options['provider'] == 'football-data-org':
            batch = sync_football_data_org(
                tenant=tenant,
                imported_by=user,
                api_key=os.getenv('FOOTBALL_DATA_ORG_API_KEY', ''),
                competition_code=options['competition'],
            )
        elif options['provider'] == 'statsbomb-open':
            if not options['competition_id'] or not options['season_id']:
                raise CommandError(
                    'StatsBomb exige --competition-id e --season-id.'
                )
            batch = sync_statsbomb_open(
                tenant=tenant,
                imported_by=user,
                competition_id=options['competition_id'],
                season_id=options['season_id'],
                max_matches=options['max_matches'],
                max_events=options['max_events'],
            )
        else:
            batch = sync_skillcorner_open(
                tenant=tenant,
                imported_by=user,
                max_matches=options['max_matches'],
            )
        self.stdout.write(
            self.style.SUCCESS(
                f'Lote {batch.pk} concluído: {batch.record_count} registros de {batch.source.name}.'
            )
        )
