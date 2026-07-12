from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from futebol.models import (
    ApprovalDecision,
    ApprovalFlow,
    ApprovalFlowStep,
    ApprovalRequest,
    AuditLog,
    Club,
    Contract,
    Evidence,
    Negotiation,
    OperationalMetric,
    Person,
    Tenant,
    TenantMembership,
)
from futebol.services import approvals


User = get_user_model()


class JourneyHardeningTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Piloto', slug='piloto-hardening')
        self.other_tenant = Tenant.objects.create(name='Outro', slug='outro-hardening')
        self.manager = User.objects.create_user('manager-hardening', password='x')
        self.approver = User.objects.create_user('approver-hardening', password='x')
        self.auditor = User.objects.create_user('auditor-hardening', password='x')
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.manager, role=TenantMembership.Role.GESTOR_CLUBE
        )
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.approver, role=TenantMembership.Role.APROVADOR
        )
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.auditor, role=TenantMembership.Role.AUDITOR
        )
        self.origin = Club.objects.create(tenant=self.tenant, name='Origem', slug='origem-hardening')
        self.destination = Club.objects.create(tenant=self.tenant, name='Destino', slug='destino-hardening')
        self.person = Person.objects.create(tenant=self.tenant, full_name='Atleta Hardening')
        self.contract_flow = ApprovalFlow.objects.create(
            tenant=self.tenant,
            code='contract-hardening',
            name='Contrato',
            target_kind=ApprovalFlow.TargetKind.CONTRATO,
        )
        ApprovalFlowStep.objects.create(
            tenant=self.tenant,
            flow=self.contract_flow,
            order=1,
            required_role=TenantMembership.Role.APROVADOR,
        )
        self.transfer_flow = ApprovalFlow.objects.create(
            tenant=self.tenant,
            code='transfer-hardening',
            name='Transferência',
            target_kind=ApprovalFlow.TargetKind.TRANSFERENCIA,
        )
        self.transfer_step = ApprovalFlowStep.objects.create(
            tenant=self.tenant,
            flow=self.transfer_flow,
            order=1,
            required_role=TenantMembership.Role.APROVADOR,
            requires_evidence=True,
        )

    def test_request_rejects_missing_and_cross_tenant_target(self):
        content_type = ContentType.objects.get_for_model(Contract)
        missing = ApprovalRequest(
            tenant=self.tenant,
            flow=self.contract_flow,
            requested_by=self.manager,
            content_type=content_type,
            object_id='999999',
        )
        with self.assertRaisesMessage(ValidationError, 'não existe'):
            missing.full_clean()

        other_club = Club.objects.create(tenant=self.other_tenant, name='Outro clube', slug='outro-clube-hardening')
        other_person = Person.objects.create(tenant=self.other_tenant, full_name='Outro atleta hardening')
        other_contract = Contract.objects.create(
            tenant=self.other_tenant,
            person=other_person,
            club=other_club,
            start_date=timezone.now().date(),
        )
        cross_tenant = ApprovalRequest(
            tenant=self.tenant,
            flow=self.contract_flow,
            requested_by=self.manager,
            content_type=content_type,
            object_id=str(other_contract.pk),
        )
        with self.assertRaisesMessage(ValidationError, 'mesmo tenant'):
            cross_tenant.full_clean()

    def test_open_request_enforces_proponent_steps_and_single_open_case(self):
        contract = Contract.objects.create(
            tenant=self.tenant,
            person=self.person,
            club=self.origin,
            start_date=timezone.now().date(),
        )
        with self.assertRaisesMessage(ValidationError, 'papel exigido'):
            approvals.open_request(contract, self.auditor)

        request = approvals.open_request(contract, self.manager)
        self.assertEqual(request.status, ApprovalRequest.Status.OPEN)
        with self.assertRaisesMessage(ValidationError, 'Já existe'):
            approvals.open_request(contract, self.manager)

        request.status = ApprovalRequest.Status.CANCELLED
        request.save(update_fields=['status'])
        self.contract_flow.steps.all().delete()
        with self.assertRaisesMessage(ValidationError, 'ao menos uma etapa'):
            approvals.open_request(contract, self.manager)

    def test_service_refuses_legacy_request_with_empty_flow(self):
        empty_flow = ApprovalFlow.objects.create(
            tenant=self.tenant,
            code='empty-hardening',
            name='Vazio',
            target_kind=ApprovalFlow.TargetKind.PARTIDA,
        )
        contract = Contract.objects.create(
            tenant=self.tenant,
            person=self.person,
            club=self.origin,
            start_date=timezone.now().date(),
        )
        legacy_request = ApprovalRequest(
            tenant=self.tenant,
            flow=empty_flow,
            requested_by=self.manager,
            content_type=ContentType.objects.get_for_model(Contract),
            object_id=str(contract.pk),
        )
        ApprovalRequest.objects.bulk_create([legacy_request])
        with self.assertRaisesMessage(ValidationError, 'não possui etapas'):
            approvals.cast_decision(legacy_request, None, self.approver, ApprovalDecision.Outcome.APPROVED)

    def test_transfer_effects_are_individually_audited(self):
        origin_contract = Contract.objects.create(
            tenant=self.tenant,
            person=self.person,
            club=self.origin,
            start_date=timezone.now().date(),
            status=Contract.Status.ACTIVE,
        )
        negotiation = Negotiation.objects.create(
            tenant=self.tenant,
            person=self.person,
            club=self.destination,
        )
        request = approvals.open_request(negotiation, self.manager)
        Evidence.objects.create(
            tenant=self.tenant,
            content_type=ContentType.objects.get_for_model(Negotiation),
            object_id=str(negotiation.pk),
            uploaded_by=self.manager,
            note='Documento',
        )
        approvals.cast_decision(
            request, self.transfer_step, self.approver, ApprovalDecision.Outcome.APPROVED
        )

        origin_contract.refresh_from_db()
        negotiation.refresh_from_db()
        destination_contract = Contract.objects.get(
            tenant=self.tenant,
            person=self.person,
            club=self.destination,
            status=Contract.Status.ACTIVE,
        )
        self.assertEqual(origin_contract.status, Contract.Status.TERMINATED)
        self.assertEqual(negotiation.status, Negotiation.Status.ACCEPTED)
        contract_type = ContentType.objects.get_for_model(Contract)
        negotiation_type = ContentType.objects.get_for_model(Negotiation)
        self.assertTrue(AuditLog.objects.filter(
            actor=self.approver, content_type=contract_type, object_id=str(origin_contract.pk), action='update'
        ).exists())
        self.assertTrue(AuditLog.objects.filter(
            actor=self.approver, content_type=contract_type, object_id=str(destination_contract.pk), action='create'
        ).exists())
        self.assertTrue(AuditLog.objects.filter(
            actor=self.approver, content_type=negotiation_type, object_id=str(negotiation.pk), action='update'
        ).exists())


class OperationalMetricsTests(TestCase):
    def test_authenticated_request_records_low_cardinality_metric(self):
        tenant = Tenant.objects.create(name='Métricas', slug='metricas-hardening')
        user = User.objects.create_user('metric-user', password='x')
        TenantMembership.objects.create(
            tenant=tenant, user=user, role=TenantMembership.Role.ADMIN_TENANT
        )
        self.client.force_login(user)

        response = self.client.get(reverse('root'), HTTP_X_REQUEST_ID='metric-request-id')

        self.assertEqual(response.status_code, 302)
        metric = OperationalMetric.objects.get(tenant=tenant, route_name='root')
        self.assertEqual(metric.kind, OperationalMetric.Kind.USAGE)
        self.assertEqual(metric.method, 'GET')
        self.assertEqual(metric.status_code, 302)
        self.assertEqual(metric.correlation_id, 'metric-request-id')
        self.assertEqual(metric.metadata, {})


class PilotReadinessCommandTests(TestCase):
    def test_ready_tenant_passes_automatic_gate(self):
        tenant = Tenant.objects.create(name='Ready FC', slug='ready-hardening')
        manager = User.objects.create_user('ready-manager', password='x')
        approver = User.objects.create_user('ready-approver', password='x')
        TenantMembership.objects.create(
            tenant=tenant, user=manager, role=TenantMembership.Role.GESTOR_CLUBE
        )
        TenantMembership.objects.create(
            tenant=tenant, user=approver, role=TenantMembership.Role.APROVADOR
        )
        for order, kind in enumerate(
            (ApprovalFlow.TargetKind.CONTRATO, ApprovalFlow.TargetKind.TRANSFERENCIA), start=1
        ):
            flow = ApprovalFlow.objects.create(
                tenant=tenant, code=f'ready-{order}', name=f'Fluxo {order}', target_kind=kind
            )
            ApprovalFlowStep.objects.create(
                tenant=tenant,
                flow=flow,
                order=1,
                required_role=TenantMembership.Role.APROVADOR,
            )

        stdout = StringIO()
        call_command('check_pilot_readiness', tenant=tenant.slug, stdout=stdout)
        self.assertIn('apto para revisão humana', stdout.getvalue())
