from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant
from futebol.services.sports_data import import_local_sports_dataset


class Command(BaseCommand):
    help = 'Importa uma Fonte de Dados Esportivos local com proveniência e hash.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant de destino.')
        parser.add_argument('--dataset', required=True, help='Identificador seguro do dataset.')
        parser.add_argument('--user', required=True, help='Usuário responsável pela importação.')
        parser.add_argument(
            '--root',
            default=str(Path(settings.BASE_DIR) / 'futebol' / 'data' / 'sports'),
            help='Raiz permitida para datasets locais.',
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'])
        except Tenant.DoesNotExist as exc:
            raise CommandError('Tenant não encontrado.') from exc
        try:
            user = get_user_model().objects.get(username=options['user'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário responsável não encontrado.') from exc

        batch = import_local_sports_dataset(
            tenant=tenant,
            dataset_slug=options['dataset'],
            imported_by=user,
            root=Path(options['root']),
        )
        self.stdout.write(self.style.SUCCESS(
            f'Importação {batch.dataset_id} v{batch.dataset_version}: '
            f'{batch.record_count} registro(s), qualidade={batch.quality}.'
        ))
