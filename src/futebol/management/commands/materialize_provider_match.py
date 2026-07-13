from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant
from futebol.services.coach_workspace import materialize_provider_match
from futebol.services.sports_catalog import (
    latest_records_for,
    tenant_has_sports_intelligence,
)


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
        if not tenant_has_sports_intelligence(tenant):
            raise CommandError(
                'O Tenant não possui Inteligência Esportiva contratada.'
            )
        provider_record_id = f"match:{options['provider_match_id']}"
        record = (
            latest_records_for(
                tenant,
                provider_code='football-data-org',
                capability='fixtures_results',
            ).filter(provider_record_id=provider_record_id)
            .select_related('source', 'batch')
            .order_by('-batch__published_at', '-observed_at')
            .first()
        )
        if record is None:
            raise CommandError('Partida não encontrada nos dados sincronizados do provider.')
        match = materialize_provider_match(record=record, tenant=tenant)
        self.stdout.write(self.style.SUCCESS(
            f'Partida {match.reference_code} pronta: {match.home_club} x {match.away_club}.',
        ))
        self.stdout.write(
            'O Dossiê só poderá ser gerado após cadastrar contratos e perfis dos atletas do time.',
        )
