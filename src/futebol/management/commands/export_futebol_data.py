from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant
from futebol.services.data_io import export_csv


class Command(BaseCommand):
    help = 'Exporta dados do núcleo de futebol em CSV.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--model', required=True, choices=['club', 'competition', 'edition', 'phase', 'match'])
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f'Tenant não encontrado: {options["tenant"]}') from exc

        csv_data = export_csv(tenant, options['model'])
        with open(options['output'], 'w', encoding='utf-8') as fh:
            fh.write(csv_data)
        self.stdout.write(self.style.SUCCESS(f'Exportado para {options["output"]}'))
