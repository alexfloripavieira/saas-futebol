from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant, TenantMembership
from futebol.services.sports_data_providers import sync_skillcorner_tracking


PUBLIC_PROVIDERS = {'football-data-org', 'statsbomb-open', 'skillcorner-open'}


class Command(BaseCommand):
    help = 'Importa tracking privado da SkillCorner para um Tenant.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant')
        parser.add_argument(
            '--provider', required=True,
            choices=[*sorted(PUBLIC_PROVIDERS), 'skillcorner-tracking'],
        )
        parser.add_argument('--user')
        parser.add_argument('--tracking-match-id')

    def handle(self, *args, **options):
        if options['provider'] in PUBLIC_PROVIDERS:
            raise CommandError(
                'Dados públicos pertencem à Base Esportiva Global. Use '
                '`sync_platform_sports_provider --provider '
                f"{options['provider']}` sem --tenant e --user."
            )
        if not options['tenant'] or not options['user']:
            raise CommandError(
                'Tracking privado exige --tenant e --user.'
            )
        if not options['tracking_match_id']:
            raise CommandError(
                'Tracking privado exige --tracking-match-id.'
            )
        try:
            tenant = Tenant.objects.get(slug=options['tenant'], active=True)
        except Tenant.DoesNotExist as exc:
            raise CommandError('Tenant ativo não encontrado.') from exc
        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=options['user'], is_active=True)
        except user_model.DoesNotExist as exc:
            raise CommandError('Usuário ativo não encontrado.') from exc
        if not user.is_superuser and not TenantMembership.objects.filter(
            tenant=tenant, user=user, active=True,
        ).exists():
            raise CommandError('O usuário informado não pertence ao tenant.')

        batch = sync_skillcorner_tracking(
            tenant=tenant,
            imported_by=user,
            match_id=options['tracking_match_id'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Lote {batch.pk} concluído: {batch.record_count} registros de {batch.source.name}.'
            )
        )
