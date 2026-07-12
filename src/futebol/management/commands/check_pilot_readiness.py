from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from futebol.models import ApprovalFlow, Tenant, TenantMembership
from futebol.modules import tenant_has_module


class Command(BaseCommand):
    help = 'Valida os pré-requisitos automáticos para liberar um tenant piloto.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant piloto.')

    def handle(self, *args, **options):
        failures = []
        tenant = Tenant.objects.filter(slug=options['tenant']).first()
        if tenant is None:
            raise CommandError(f'Tenant "{options["tenant"]}" não encontrado.')
        if not tenant.active:
            failures.append('tenant está inativo')

        migration_executor = MigrationExecutor(connection)
        pending_migrations = migration_executor.migration_plan(
            migration_executor.loader.graph.leaf_nodes()
        )
        if pending_migrations:
            failures.append(f'há {len(pending_migrations)} migração(ões) pendente(s)')

        for module_code in ('transferencias', 'aprovacoes', 'auditoria'):
            if not tenant_has_module(tenant, module_code):
                failures.append(f'módulo obrigatório não habilitado: {module_code}')

        for target_kind in (
            ApprovalFlow.TargetKind.CONTRATO,
            ApprovalFlow.TargetKind.TRANSFERENCIA,
        ):
            flow = ApprovalFlow.objects.filter(
                tenant=tenant,
                target_kind=target_kind,
                active=True,
            ).first()
            if flow is None:
                failures.append(f'fluxo ativo ausente: {target_kind}')
                continue
            steps = list(flow.steps.order_by('order'))
            if not steps:
                failures.append(f'fluxo sem etapas: {flow.code}')
                continue
            for step in steps:
                has_approver = TenantMembership.objects.filter(
                    tenant=tenant,
                    role=step.required_role,
                    active=True,
                    user__is_active=True,
                ).exists()
                if not has_approver:
                    failures.append(
                        f'nenhum usuário ativo para {step.required_role} '
                        f'na etapa {step.order} do fluxo {flow.code}'
                    )

        has_proponent = TenantMembership.objects.filter(
            tenant=tenant,
            role__in=(TenantMembership.Role.GESTOR_CLUBE, TenantMembership.Role.ADMIN_TENANT),
            active=True,
            user__is_active=True,
        ).exists()
        if not has_proponent:
            failures.append('nenhum gestor de clube ou administrador ativo para iniciar a jornada')

        if failures:
            for failure in failures:
                self.stderr.write(self.style.ERROR(f'NO-GO: {failure}'))
            raise CommandError(f'Piloto bloqueado por {len(failures)} pendência(s).')

        self.stdout.write(self.style.SUCCESS(f'GO automático: tenant {tenant.slug} apto para revisão humana.'))
