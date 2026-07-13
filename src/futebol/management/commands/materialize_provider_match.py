from django.core.management.base import BaseCommand, CommandError

from futebol.models import SportsDataRecord, Tenant
from futebol.services.coach_workspace import materialize_provider_match


class Command(BaseCommand):
    help = 'Materializa uma partida normalizada do football-data.org no domínio operacional.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--provider-match-id', required=True)

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'])
        except Tenant.DoesNotExist as exc:
            raise CommandError('Tenant não encontrado.') from exc
        provider_record_id = f"match:{options['provider_match_id']}"
        record = (
            SportsDataRecord.objects.filter(
                tenant=tenant,
                source__code='football-data-org',
                capability='fixtures_results',
                provider_record_id=provider_record_id,
            )
            .select_related('source', 'tenant')
            .order_by('-observed_at', '-created_at')
            .first()
        )
        if record is None:
            raise CommandError('Partida não encontrada nos dados sincronizados do provider.')
        match = materialize_provider_match(record=record)
        self.stdout.write(self.style.SUCCESS(
            f'Partida {match.reference_code} pronta: {match.home_club} x {match.away_club}.',
        ))
        self.stdout.write(
            'O Dossiê só poderá ser gerado após cadastrar contratos e perfis dos atletas do time.',
        )
