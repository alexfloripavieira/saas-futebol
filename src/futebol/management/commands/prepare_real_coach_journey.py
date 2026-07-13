from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from futebol.models import Tenant, TenantMembership
from futebol.services.real_coach_journey import prepare_real_coach_journey


class Command(BaseCommand):
    help = 'Prepara uma jornada real e idempotente no Treinador, sem fabricar dados privados.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--user', required=True)
        parser.add_argument(
            '--confirm-cleanup', action='store_true',
            help='Confirma a remoção do footprint exato do seed demo.',
        )

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
        if not user.is_superuser and not TenantMembership.objects.filter(
            tenant=tenant, user=user, active=True,
        ).exists():
            raise CommandError('O usuário informado não pertence ao tenant.')
        try:
            result = prepare_real_coach_journey(
                tenant=tenant, actor=user,
                cleanup_synthetic=options['confirm_cleanup'],
            )
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc

        self.stdout.write(self.style.SUCCESS(
            f'Partida real preparada: {result.match.home_club} x {result.match.away_club}.',
        ))
        self.stdout.write(
            f'Limpeza segura: {result.removed_sources} fonte(s) e '
            f'{result.removed_dossiers} Dossiê(s) sintético(s), '
            f'{result.removed_seed_objects} objeto(s) marcado(s) do seed.'
        )
        if not options['confirm_cleanup']:
            self.stdout.write(
                'Limpeza do seed não executada. Use --confirm-cleanup para remover '
                'somente o footprint com marcadores exatos.'
            )
        if result.status == 'elenco_real_necessario':
            self.stdout.write(self.style.WARNING(
                'Modo operacional bloqueado: informe pelo menos 11 contratos do elenco '
                'privado real. Nenhum atleta ou contrato foi fabricado.'
            ))
        else:
            self.stdout.write(f'Estado da jornada: {result.status}.')
        self.stdout.write(f'Abrir: {result.coach_url}')
