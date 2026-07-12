from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant
from futebol.services.sports_data_providers import provision_provider_catalog


class Command(BaseCommand):
    help = 'Provisiona o catálogo seguro de fontes esportivas para um ou todos os tenants.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='Slug do tenant; sem o argumento provisiona todos.')

    def handle(self, *args, **options):
        tenants = Tenant.objects.filter(active=True)
        if options['tenant']:
            tenants = tenants.filter(slug=options['tenant'])
        if not tenants.exists():
            raise CommandError('Nenhum tenant ativo encontrado.')
        total = 0
        for tenant in tenants:
            total += len(provision_provider_catalog(tenant=tenant))
        self.stdout.write(self.style.SUCCESS(f'{total} fontes provisionadas com segurança.'))
