from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    ApprovalFlow,
    ApprovalFlowStep,
    ApprovalRequest,
    AuditLog,
    Club,
    Contract,
    Evidence,
    Negotiation,
    Person,
    Tenant,
    TenantMembership,
    TenantModuleSubscription,
)


class PilotPersonJourneyTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Piloto FC', slug='piloto')
        self.user = get_user_model().objects.create_user('gestor-piloto', password='senha12345')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        self.client.login(username='gestor-piloto', password='senha12345')

    def test_gestor_cadastra_pessoa_pela_interface(self):
        response = self.client.post(reverse('person-create'), {
            'full_name': 'Atleta do Piloto',
            'document_id': 'DOC-13',
            'kind': Person.Kind.ATHLETE,
            'birth_date': '2000-01-02',
            'active': 'on',
        })

        self.assertRedirects(response, reverse('person-list'))
        self.assertTrue(Person.objects.filter(
            tenant=self.tenant,
            full_name='Atleta do Piloto',
        ).exists())


class PilotTransferHttpJourneyTests(TestCase):
    def setUp(self):
        self.media_dir = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_dir.cleanup)
        self.tenant = Tenant.objects.create(name='Transferência Piloto', slug='transferencia-piloto')
        self.user = get_user_model().objects.create_user('gestor-transferencia', password='senha12345')
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role=TenantMembership.Role.GESTOR_CLUBE,
        )
        for code in ('transferencias', 'aprovacoes'):
            TenantModuleSubscription.objects.create(
                tenant=self.tenant, module_code=code, module_name=code.title(), enabled=True,
            )
        self.person = Person.objects.create(tenant=self.tenant, full_name='Atleta Transferível')
        self.club = Club.objects.create(tenant=self.tenant, name='Destino FC', slug='destino')
        self.negotiation = Negotiation.objects.create(
            tenant=self.tenant, person=self.person, club=self.club,
        )
        self.flow = ApprovalFlow.objects.create(
            tenant=self.tenant,
            code='transferencia-piloto',
            name='Transferência do piloto',
            target_kind=ApprovalFlow.TargetKind.TRANSFERENCIA,
        )
        ApprovalFlowStep.objects.create(
            tenant=self.tenant,
            flow=self.flow,
            order=1,
            required_role=TenantMembership.Role.APROVADOR,
            requires_evidence=True,
        )
        self.client.login(username='gestor-transferencia', password='senha12345')

    def test_opens_approval_from_negotiation_without_manual_target_ids(self):
        response = self.client.post(reverse('transfer-approval-open', args=[self.negotiation.pk]))

        self.assertRedirects(response, reverse('negotiation-list'))
        approval_request = ApprovalRequest.objects.get(tenant=self.tenant)
        self.assertEqual(approval_request.content_object, self.negotiation)

    def test_uploads_evidence_from_negotiation_context(self):
        response = self.client.post(
            reverse('transfer-evidence-create', args=[self.negotiation.pk]),
            {
                'file': SimpleUploadedFile(
                    'documento.pdf', b'%PDF-1.7\nconteudo piloto', content_type='application/pdf',
                ),
                'url': '',
                'note': 'Documento da transferência',
            },
        )

        self.assertRedirects(response, reverse('negotiation-list'))
        evidence = Evidence.objects.get(tenant=self.tenant)
        self.assertEqual(evidence.content_object, self.negotiation)

    def test_negotiation_list_uses_the_portuguese_status_label(self):
        self.negotiation.status = Negotiation.Status.ACCEPTED
        self.negotiation.save()

        response = self.client.get(reverse('negotiation-list'))

        self.assertContains(response, 'Aceita')
        self.assertNotContains(response, '>accepted<')


class PilotEndToEndHttpJourneyTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Piloto HTTP', slug='piloto-http')
        self.manager = get_user_model().objects.create_user('gestor-http', password='senha12345')
        self.approver = get_user_model().objects.create_user('aprovador-http', password='senha12345')
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.manager, role=TenantMembership.Role.GESTOR_CLUBE,
        )
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.approver, role=TenantMembership.Role.APROVADOR,
        )
        for code in ('transferencias', 'aprovacoes'):
            TenantModuleSubscription.objects.create(
                tenant=self.tenant, module_code=code, module_name=code.title(), enabled=True,
            )
        self.origin = Club.objects.create(tenant=self.tenant, name='Origem HTTP', slug='origem-http')
        self.destination = Club.objects.create(
            tenant=self.tenant, name='Destino HTTP', slug='destino-http',
        )
        self.flow = ApprovalFlow.objects.create(
            tenant=self.tenant,
            code='transferencia-http',
            name='Transferência HTTP',
            target_kind=ApprovalFlow.TargetKind.TRANSFERENCIA,
        )
        ApprovalFlowStep.objects.create(
            tenant=self.tenant,
            flow=self.flow,
            order=1,
            required_role=TenantMembership.Role.APROVADOR,
            requires_evidence=True,
        )

    def test_jornada_vertical_completa_pela_interface_http(self):
        self.client.force_login(self.manager)
        person_response = self.client.post(reverse('person-create'), {
            'full_name': 'Atleta HTTP',
            'document_id': 'HTTP-13',
            'kind': Person.Kind.ATHLETE,
            'birth_date': '2001-02-03',
            'active': 'on',
        })
        self.assertRedirects(person_response, reverse('person-list'))
        person = Person.objects.get(tenant=self.tenant, document_id='HTTP-13')

        contract_response = self.client.post(reverse('contract-create'), {
            'person': person.pk,
            'club': self.origin.pk,
            'start_date': '2026-07-01',
            'end_date': '',
            'signed_at': '',
            'status': Contract.Status.ACTIVE,
            'termination_reason': '',
        })
        self.assertRedirects(contract_response, reverse('contract-list'))
        origin_contract = Contract.objects.get(person=person, club=self.origin)

        negotiation_response = self.client.post(reverse('negotiation-create'), {
            'person': person.pk,
            'club': self.destination.pk,
            'status': Negotiation.Status.OPEN,
            'closed_at': '',
        })
        self.assertRedirects(negotiation_response, reverse('negotiation-list'))
        negotiation = Negotiation.objects.get(person=person, club=self.destination)

        approval_response = self.client.post(
            reverse('transfer-approval-open', args=[negotiation.pk]),
            {'reason': 'Jornada vertical HTTP'},
        )
        self.assertRedirects(approval_response, reverse('negotiation-list'))
        approval_request = ApprovalRequest.objects.get(tenant=self.tenant, object_id=str(negotiation.pk))

        evidence_response = self.client.post(
            reverse('transfer-evidence-create', args=[negotiation.pk]),
            {'file': '', 'url': '', 'note': 'Evidência da jornada HTTP'},
        )
        self.assertRedirects(evidence_response, reverse('negotiation-list'))

        self.client.force_login(self.approver)
        decision_response = self.client.post(
            reverse('approval-request-approve', args=[approval_request.pk]),
        )
        self.assertRedirects(decision_response, reverse('approval-request-list'))

        approval_request.refresh_from_db()
        origin_contract.refresh_from_db()
        negotiation.refresh_from_db()
        self.assertEqual(approval_request.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(origin_contract.status, Contract.Status.TERMINATED)
        self.assertEqual(negotiation.status, Negotiation.Status.ACCEPTED)
        self.assertTrue(Contract.objects.filter(
            tenant=self.tenant,
            person=person,
            club=self.destination,
            status=Contract.Status.ACTIVE,
        ).exists())
        self.assertTrue(AuditLog.objects.filter(tenant=self.tenant, actor=self.approver).exists())


class PilotAuthorizationMatrixTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Matriz Piloto', slug='matriz-piloto')
        for code in ('transferencias', 'aprovacoes'):
            TenantModuleSubscription.objects.create(
                tenant=self.tenant, module_code=code, module_name=code.title(), enabled=True,
            )
        self.users_by_role = {}
        for role, _label in TenantMembership.Role.choices:
            user = get_user_model().objects.create_user(f'papel-{role}', password='senha12345')
            TenantMembership.objects.create(tenant=self.tenant, user=user, role=role)
            self.users_by_role[role] = user

    def test_matriz_de_leitura_e_operacoes_criticas_por_papel(self):
        all_roles = set(self.users_by_role)
        allowed = {
            'person-list': all_roles,
            'person-create': {
                TenantMembership.Role.ADMIN_TENANT,
                TenantMembership.Role.GESTOR_CLUBE,
                TenantMembership.Role.ADMIN_PLATAFORMA,
            },
            'approval-request-create': {
                TenantMembership.Role.ADMIN_TENANT,
                TenantMembership.Role.GESTOR_CLUBE,
                TenantMembership.Role.GESTOR_COMPETICAO,
                TenantMembership.Role.DELEGADO_PARTIDA,
                TenantMembership.Role.ADMIN_PLATAFORMA,
            },
            'evidence-create': {
                TenantMembership.Role.ADMIN_TENANT,
                TenantMembership.Role.GESTOR_CLUBE,
                TenantMembership.Role.GESTOR_COMPETICAO,
                TenantMembership.Role.APROVADOR,
                TenantMembership.Role.ADMIN_PLATAFORMA,
            },
            'contract-list': {
                TenantMembership.Role.ADMIN_TENANT,
                TenantMembership.Role.GESTOR_CLUBE,
                TenantMembership.Role.ADMIN_PLATAFORMA,
            },
        }

        for route_name, allowed_roles in allowed.items():
            for role, user in self.users_by_role.items():
                with self.subTest(route=route_name, role=role):
                    self.client.force_login(user)
                    response = self.client.get(reverse(route_name))
                    self.assertEqual(response.status_code, 200 if role in allowed_roles else 403)
