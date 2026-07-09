from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from futebol.models import Tenant
from futebol.services.ai import seed_demo_ai_stack, sync_knowledge_sources


class Command(BaseCommand):
    help = 'Importa fontes documentais da IA a partir do repositório ou do Segundo Cérebro.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--root', default=str(Path(settings.BASE_DIR).parent), help='Raiz do repositório SaaS do Futebol')
        parser.add_argument('--vault-root', default='', help='Raiz do vault Obsidian / Segundo Cérebro')
        parser.add_argument('--seed-agent', action='store_true')

    def _sync_from_project(self, tenant: Tenant, root: Path):
        return sync_knowledge_sources(tenant=tenant, root=root, relative_roots=('docs', 'orchestrator/reports'))

    def _sync_from_vault(self, tenant: Tenant, vault_root: Path):
        return sync_knowledge_sources(
            tenant=tenant,
            root=vault_root,
            relative_roots=('Areas/CBF Academy', '📚 Relatórios', '🚀 Projetos'),
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f'Tenant não encontrado: {options["tenant"]}') from exc

        root = Path(options['root'])
        if not root.exists():
            raise CommandError(f'Raiz do projeto não encontrada: {root}')

        vault_root = Path(options['vault_root']) if options.get('vault_root') else None
        if vault_root is not None and not vault_root.exists():
            raise CommandError(f'Raiz do vault não encontrada: {vault_root}')

        project_result = self._sync_from_project(tenant, root)
        total_created = project_result.created
        total_updated = project_result.updated
        total_skipped = project_result.skipped

        if vault_root is not None:
            vault_result = self._sync_from_vault(tenant, vault_root)
            total_created += vault_result.created
            total_updated += vault_result.updated
            total_skipped += vault_result.skipped

        if options['seed_agent']:
            seed_root = vault_root or root
            seed_result = seed_demo_ai_stack(tenant=tenant, root=seed_root)
            total_created += seed_result.created
            total_updated += seed_result.updated
            total_skipped += seed_result.skipped

        self.stdout.write(self.style.SUCCESS(
            f'Fontes importadas: {total_created + total_updated} | Criadas: {total_created} | Atualizadas: {total_updated} | Ignoradas: {total_skipped}'
        ))
