from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from futebol.models import LineupDraft, MatchDossier, SportsDataSource, Tenant


SYNTHETIC_SOURCE_CODES = {'demo-treinador-sintetico-v1'}
SEEDED_MATCH_REFERENCES = {'DEM-2026-001', 'DEM-2026-COACH-001'}


class Command(BaseCommand):
    help = 'Remove somente dados esportivos sintéticos e análises derivadas, preservando o tenant.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--confirm', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'])
        except Tenant.DoesNotExist as exc:
            raise CommandError('Tenant não encontrado.') from exc
        sources = SportsDataSource.objects.filter(
            tenant=tenant, code__in=SYNTHETIC_SOURCE_CODES,
        )
        source_ids = list(sources.values_list('id', flat=True))
        dossiers = []
        for dossier in MatchDossier.objects.filter(tenant=tenant):
            external_sources = dossier.data_snapshot.get('external_sources') or []
            if dossier.match.reference_code in SEEDED_MATCH_REFERENCES or any(
                source.get('code') in SYNTHETIC_SOURCE_CODES
                or source.get('quality') == 'synthetic'
                for source in external_sources
                if isinstance(source, dict)
            ):
                dossiers.append(dossier.pk)
        record_count = sum(source.records.count() for source in sources)
        self.stdout.write(
            f'Escopo: {len(source_ids)} fonte(s), {record_count} registro(s), '
            f'{len(dossiers)} Dossiê(s) derivado(s).',
        )
        if not options['confirm']:
            self.stdout.write('Simulação concluída. Use --confirm para executar a remoção.')
            transaction.set_rollback(True)
            return
        LineupDraft.objects.filter(
            tenant=tenant, plan__dossier_id__in=dossiers,
        ).delete()
        MatchDossier.objects.filter(tenant=tenant, pk__in=dossiers).delete()
        # A fonte usa PROTECT para os lotes; os registros e lotes são removidos
        # explicitamente para manter a intenção da limpeza visível.
        for source in sources:
            source.import_batches.all().delete()
            source.delete()
        self.stdout.write(self.style.SUCCESS(
            'Dados sintéticos de análise removidos. Tenant, cadastros, dados reais, providers e agentes foram preservados.',
        ))
