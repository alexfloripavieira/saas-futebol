from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant
from futebol.services.data_io import import_payload


class Command(BaseCommand):
    help = 'Importa dados do núcleo de futebol a partir de CSV ou JSON.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--model', required=True, choices=['club', 'competition', 'edition', 'phase', 'match'])
        parser.add_argument('--input', required=True)
        parser.add_argument('--conflict-policy', default='skip', choices=['skip', 'overwrite', 'error'])

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f'Tenant não encontrado: {options["tenant"]}') from exc

        input_path = Path(options['input'])
        if not input_path.exists():
            raise CommandError(f'Arquivo não encontrado: {input_path}')

        raw_payload = input_path.read_text(encoding='utf-8')
        result = import_payload(tenant, options['model'], raw_payload, conflict_policy=options['conflict_policy'])
        self.stdout.write(self.style.SUCCESS(f'Criados: {result.created} | Atualizados: {result.updated} | Ignorados: {result.skipped} | Falhas: {result.failed}'))
        if result.errors:
            for error in result.errors:
                self.stderr.write(f'Linha {error["row"]}: {error["error"]}')
