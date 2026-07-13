from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant
from futebol.services.sports_data_transition import (
    inspect_legacy_public_copies,
    retire_legacy_public_copies,
)


class Command(BaseCommand):
    help = 'Remove cópias públicas legadas já substituídas pela Base Esportiva Global.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--confirm', action='store_true')

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'])
        except Tenant.DoesNotExist as exc:
            raise CommandError('Tenant não encontrado.') from exc
        _sources, _batches, report = inspect_legacy_public_copies(tenant=tenant)
        self.stdout.write(
            f'Escopo seguro: {report.sources} fonte(s), {report.batches} lote(s), '
            f'{report.records} registro(s); '
            f'{report.skipped_artifact_batches} lote(s) com artefato e '
            f'{report.skipped_unverified_batches} lote(s) sem cópia global comprovada '
            'preservado(s).'
        )
        if not options['confirm']:
            self.stdout.write('Simulação concluída. Use --confirm para executar.')
            return
        report = retire_legacy_public_copies(tenant=tenant)
        self.stdout.write(self.style.SUCCESS(
            f'Contração concluída: {report.records} registro(s) público(s) legado(s) '
            'removidos; dados privados e artefatos preservados.'
        ))
