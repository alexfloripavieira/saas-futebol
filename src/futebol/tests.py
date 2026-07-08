from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    ApprovalFlow,
    ApprovalFlowStep,
    ApprovalDecision,
    ApprovalRequest,
    AuditLog,
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    CompetitionRuleSet,
    Contract,
    ExternalSystem,
    Evidence,
    IntegrationRecord,
    Match,
    MatchEvent,
    MatchLineup,
    Negotiation,
    Notification,
    Person,
    Proposal,
    Tenant,
    TenantMembership,
)
from .services.data_io import export_csv, import_payload


class Sprint3BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alex', password='senha12345')
        self.tenant = Tenant.objects.create(name='Clube Exemplo', slug='clube-exemplo')
        TenantMembership.objects.create(user=self.user, tenant=self.tenant, role=TenantMembership.Role.ADMIN_TENANT)
        self.club_a = Club.objects.create(tenant=self.tenant, name='Clube A', slug='clube-a', city='São Paulo', state='SP')
        self.club_b = Club.objects.create(tenant=self.tenant, name='Clube B', slug='clube-b', city='Rio', state='RJ')
        self.competition = Competition.objects.create(tenant=self.tenant, name='Liga Principal', slug='liga-principal')
        self.ruleset = CompetitionRuleSet.objects.create(tenant=self.tenant, competition=self.competition)
        self.edition = CompetitionEdition.objects.create(
            tenant=self.tenant,
            competition=self.competition,
            slug='2026',
            name='Liga Principal 2026',
            season_year=2026,
            status=CompetitionEdition.Status.OPEN,
        )
        self.phase = CompetitionPhase.objects.create(
            tenant=self.tenant,
            edition=self.edition,
            code='fase-1',
            name='Fase 1',
            order=1,
            status=CompetitionPhase.Status.ACTIVE,
        )
        self.flow = ApprovalFlow.objects.create(
            tenant=self.tenant,
            code='alteracao-partida',
            name='Alteração de partida',
            target_kind=ApprovalFlow.TargetKind.PARTIDA,
        )


class HomeAndListingTests(Sprint3BaseTestCase):
    def test_home_requires_login(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_club_list_search_and_render(self):
        self.client.login(username='alex', password='senha12345')
        response = self.client.get(reverse('club-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clube A')
        self.assertContains(response, 'Clube B')

        filtered = self.client.get(reverse('club-list'), {'q': 'A'})
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, 'Clube A')
        self.assertNotContains(filtered, 'Clube B')

    def test_operational_pages_render(self):
        self.client.login(username='alex', password='senha12345')
        approval_request = ApprovalRequest.objects.create(
            tenant=self.tenant,
            flow=self.flow,
            requested_by=self.user,
            content_type=ContentType.objects.get_for_model(Match),
            object_id='123',
            reason='Ajuste manual',
        )
        notification = Notification.objects.create(
            tenant=self.tenant,
            recipient=self.user,
            subject='Teste de notificação',
            body='Conteúdo de teste',
        )

        approval_flow_response = self.client.get(reverse('approval-flow-list'))
        self.assertEqual(approval_flow_response.status_code, 200)
        self.assertContains(approval_flow_response, 'Alteração de partida')

        approval_request_response = self.client.get(reverse('approval-request-list'))
        self.assertEqual(approval_request_response.status_code, 200)
        self.assertContains(approval_request_response, 'Ajuste manual')
        self.assertContains(approval_request_response, 'Aberta')

        notification_response = self.client.get(reverse('notification-list'))
        self.assertEqual(notification_response.status_code, 200)
        self.assertContains(notification_response, 'Teste de notificação')

        approve_response = self.client.post(reverse('approval-request-approve', args=[approval_request.pk]))
        self.assertEqual(approve_response.status_code, 302)
        approval_request.refresh_from_db()
        self.assertEqual(approval_request.status, ApprovalRequest.Status.APPROVED)
        self.assertIsNotNone(approval_request.resolved_at)

        read_response = self.client.post(reverse('notification-mark-read', args=[notification.pk]))
        self.assertEqual(read_response.status_code, 302)
        notification.refresh_from_db()
        self.assertEqual(notification.status, Notification.Status.READ)


class IntegrityTests(Sprint3BaseTestCase):
    def test_match_rejects_same_home_and_away(self):
        match = Match(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_a,
            away_club=self.club_a,
            reference_code='JOGO-ERRADO',
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            match.full_clean()

    def test_match_auto_sets_immutability_window(self):
        scheduled = timezone.now() + timedelta(days=1)
        match = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_a,
            away_club=self.club_b,
            reference_code='JOGO-002',
            scheduled_at=scheduled,
        )
        self.assertIsNotNone(match.immutable_after)
        self.assertEqual(match.immutable_after, scheduled + timedelta(hours=24))

    def test_approval_request_requires_tenant_membership(self):
        outsider = User.objects.create_user(username='fora', password='senha12345')
        request = ApprovalRequest(
            tenant=self.tenant,
            flow=self.flow,
            requested_by=outsider,
            content_type=ContentType.objects.get_for_model(Match),
            object_id='123',
        )
        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_notification_requires_tenant_membership(self):
        outsider = User.objects.create_user(username='fora2', password='senha12345')
        notification = Notification(
            tenant=self.tenant,
            recipient=outsider,
            subject='Notificação',
            body='Mensagem',
        )
        with self.assertRaises(ValidationError):
            notification.full_clean()


class InterfaceSprint4Tests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')

    def test_dashboard_shows_quick_actions_and_states(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estados do sistema')
        self.assertContains(response, 'Novo clube')
        self.assertContains(response, 'Nova partida')

    def test_club_create_form_validates_and_saves(self):
        response = self.client.get(reverse('club-create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nome do clube')
        self.assertContains(response, 'Slug')

        invalid = self.client.post(reverse('club-create'), {'name': '', 'slug': '', 'city': '', 'state': ''})
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'Corrija os campos destacados')
        self.assertContains(invalid, 'Este campo é obrigatório.')

        valid = self.client.post(
            reverse('club-create'),
            {'name': 'Clube Novo', 'slug': 'clube-novo', 'registration_code': '', 'city': 'Belo Horizonte', 'state': 'MG', 'active': 'on'},
            follow=True,
        )
        self.assertEqual(valid.status_code, 200)
        self.assertContains(valid, 'Clube criado com sucesso.')
        self.assertTrue(Club.objects.filter(tenant=self.tenant, slug='clube-novo').exists())

    def test_match_form_rejects_same_home_and_away(self):
        response = self.client.post(
            reverse('match-create'),
            {
                'phase': self.phase.pk,
                'home_club': self.club_a.pk,
                'away_club': self.club_a.pk,
                'reference_code': 'JOGO-UI-01',
                'scheduled_at': '2026-07-01T18:00',
                'venue': 'Arena Exemplo',
                'status': Match.Status.SCHEDULED,
                'home_score': '',
                'away_score': '',
                'notes': 'Teste de validação',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mandante e visitante precisam ser clubes diferentes.')

    def test_lists_show_item_actions(self):
        approval_request = ApprovalRequest.objects.create(
            tenant=self.tenant,
            flow=self.flow,
            requested_by=self.user,
            content_type=ContentType.objects.get_for_model(Match),
            object_id='123',
            reason='Ajuste manual',
        )
        notification = Notification.objects.create(
            tenant=self.tenant,
            recipient=self.user,
            subject='Teste de notificação',
            body='Conteúdo de teste',
        )

        approval_response = self.client.get(reverse('approval-request-list'))
        self.assertEqual(approval_response.status_code, 200)
        self.assertContains(approval_response, 'Aprovar')
        self.assertContains(approval_response, 'Rejeitar')
        self.assertContains(approval_response, 'Cancelar')

        notification_response = self.client.get(reverse('notification-list'))
        self.assertEqual(notification_response.status_code, 200)
        self.assertContains(notification_response, 'Marcar lida')


class ImportExportTests(Sprint3BaseTestCase):
    def test_export_clubs_to_csv(self):
        csv_data = export_csv(self.tenant, 'club')
        self.assertIn('name,slug,registration_code,city,state,active', csv_data)
        self.assertIn('Clube A', csv_data)

    def test_import_clubs_skip_and_overwrite(self):
        payload = 'name,slug,registration_code,city,state,active\nClube A Editado,clube-a,123,Campinas,SP,true\nClube C,clube-c,,Fortaleza,CE,true\n'
        skipped = import_payload(self.tenant, 'club', payload, conflict_policy='skip')
        self.assertEqual(skipped.created, 1)
        self.assertEqual(skipped.skipped, 1)
        self.assertEqual(Club.objects.get(tenant=self.tenant, slug='clube-a').name, 'Clube A')

        overwritten = import_payload(self.tenant, 'club', payload, conflict_policy='overwrite')
        self.assertEqual(overwritten.updated, 1)
        self.assertEqual(Club.objects.get(tenant=self.tenant, slug='clube-a').name, 'Clube A Editado')
        self.assertEqual(Club.objects.filter(tenant=self.tenant).count(), 3)


class Sprint5IntegrationTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')

    def test_integration_hub_and_static_pages_render(self):
        hub = self.client.get(reverse('integration-hub'))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, 'Integrações, automações e IA')
        self.assertContains(hub, 'Sprint 9 · Integrações resilientes')
        self.assertContains(hub, 'Sistemas externos')
        self.assertContains(hub, 'Automações')
        self.assertContains(hub, 'IA')

        automacoes = self.client.get(reverse('automation-center'))
        self.assertEqual(automacoes.status_code, 200)
        self.assertContains(automacoes, 'Tarefas repetitivas')
        self.assertContains(automacoes, 'Gatilhos')

        ia = self.client.get(reverse('ai-center'))
        self.assertEqual(ia.status_code, 200)
        self.assertContains(ia, 'Casos de uso')
        self.assertContains(ia, 'Fallback manual')

    def test_external_system_crud_and_records_list(self):
        create = self.client.post(
            reverse('external-system-create'),
            {'name': 'Webhook Financeiro', 'kind': 'payment', 'base_url': 'https://example.com/webhook', 'active': 'on'},
            follow=True,
        )
        self.assertEqual(create.status_code, 200)
        self.assertContains(create, 'Sistema externo criado com sucesso.')
        external = ExternalSystem.objects.get(tenant=self.tenant, name='Webhook Financeiro')

        edit = self.client.post(
            reverse('external-system-edit', args=[external.pk]),
            {'name': 'Webhook Financeiro v2', 'kind': 'payment', 'base_url': 'https://example.com/webhook', 'active': 'on'},
            follow=True,
        )
        self.assertEqual(edit.status_code, 200)
        self.assertContains(edit, 'Sistema externo atualizado com sucesso.')
        self.assertTrue(ExternalSystem.objects.filter(tenant=self.tenant, name='Webhook Financeiro v2').exists())

        IntegrationRecord.objects.create(
            tenant=self.tenant,
            external_system=ExternalSystem.objects.get(tenant=self.tenant, name='Webhook Financeiro v2'),
            correlation_id='abc-123',
            external_object_id='obj-7',
            payload={'status': 'ok'},
            status='processed',
        )
        records = self.client.get(reverse('integration-record-list'))
        self.assertEqual(records.status_code, 200)
        self.assertContains(records, 'abc-123')
        self.assertContains(records, 'processed')
        self.assertContains(records, 'Webhook Financeiro v2')

    def test_import_and_export_workflow(self):
        payload = 'name,slug,registration_code,city,state,active\nClube Importado,clube-importado,,Natal,RN,true\n'
        response = self.client.post(
            reverse('integration-import'),
            {'model': 'club', 'payload': payload, 'conflict_policy': 'skip'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Importação concluída')
        self.assertTrue(Club.objects.filter(tenant=self.tenant, slug='clube-importado').exists())

        export = self.client.post(reverse('integration-export'), {'model': 'club'})
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="club.csv"', export['Content-Disposition'])
        self.assertIn('name,slug,registration_code,city,state,active', export.content.decode())


class Sprint9IntegrationResilienceTests(Sprint5IntegrationTests):
    def test_integration_record_retry_and_mark_processed(self):
        external = ExternalSystem.objects.create(
            tenant=self.tenant,
            name='Webhook Operacional',
            kind='payment',
            base_url='https://example.com/webhook',
            active=True,
        )
        record = IntegrationRecord.objects.create(
            tenant=self.tenant,
            external_system=external,
            correlation_id='retry-001',
            external_object_id='evt-1',
            payload={'ok': False},
            status='error',
            error_message='Timeout no provedor externo',
        )

        hub = self.client.get(reverse('integration-hub'))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, 'Sprint 9 · Integrações resilientes')
        self.assertContains(hub, 'Erros')
        self.assertContains(hub, '1')

        retry = self.client.post(reverse('integration-record-retry', args=[record.pk]), follow=True)
        self.assertEqual(retry.status_code, 200)
        self.assertContains(retry, 'Registro reenfileirado para reprocessamento.')
        record.refresh_from_db()
        self.assertEqual(record.status, 'retry')
        self.assertIsNone(record.processed_at)
        self.assertEqual(record.error_message, 'Timeout no provedor externo')

        processed = self.client.post(reverse('integration-record-mark-processed', args=[record.pk]), follow=True)
        self.assertEqual(processed.status_code, 200)
        self.assertContains(processed, 'Registro marcado como processado.')
        record.refresh_from_db()
        self.assertEqual(record.status, 'processed')
        self.assertIsNotNone(record.processed_at)
        self.assertEqual(record.error_message, '')
        records = self.client.get(reverse('integration-record-list'))
        self.assertEqual(records.status_code, 200)
        self.assertContains(records, 'Processado')


class Sprint10BiCenterTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')
        self.other_club = Club.objects.create(tenant=self.tenant, name='Clube C', slug='clube-c', city='Belo Horizonte', state='MG')
        self.person = Person.objects.create(tenant=self.tenant, full_name='Atleta BI')
        self.match_played = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_a,
            away_club=self.club_b,
            reference_code='BI-001',
            scheduled_at=timezone.now() + timedelta(days=1),
            status=Match.Status.PLAYED,
            home_score=2,
            away_score=1,
        )
        self.match_scheduled = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_b,
            away_club=self.other_club,
            reference_code='BI-002',
            scheduled_at=timezone.now() + timedelta(days=2),
            status=Match.Status.SCHEDULED,
        )
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            person=self.person,
            club=self.club_a,
            start_date=timezone.now().date(),
            status=Contract.Status.ACTIVE,
        )
        MatchEvent.objects.create(
            tenant=self.tenant,
            match=self.match_played,
            player=self.person,
            event_type=MatchEvent.EventType.GOAL,
            minute=12,
        )

    def test_bi_center_renders_and_exports_json(self):
        response = self.client.get(reverse('bi-center'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sprint 10')
        self.assertContains(response, 'BI self-service')
        self.assertContains(response, 'Partidas disputadas')
        self.assertContains(response, 'Gol')
        self.assertContains(response, 'Aplicar filtros')
        self.assertContains(response, 'Exportar JSON')

        json_response = self.client.get(reverse('bi-center'), {'format': 'json'})
        self.assertEqual(json_response.status_code, 200)
        payload = json_response.json()
        self.assertEqual(payload['selected_tenant'], self.tenant.name)
        self.assertTrue(any(card['label'] == 'Partidas' for card in payload['summary_cards']))
        self.assertTrue(any(row['label'] == 'Disputada' for row in payload['breakdowns'][0]['rows']))
        self.assertTrue(any(item['pair'] == 'Clube A x Clube B' for item in payload['recent_matches']))
        self.assertTrue(any(item['type'] == 'Gol' for item in payload['recent_events']))


@override_settings(PUBLIC_API_KEY='chave-publica-teste')
class Sprint11PublicApiTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.other_club = Club.objects.create(tenant=self.tenant, name='Clube C', slug='clube-c', city='Belo Horizonte', state='MG')
        self.person = Person.objects.create(tenant=self.tenant, full_name='Atleta API')
        self.match_played = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_a,
            away_club=self.club_b,
            reference_code='API-001',
            scheduled_at=timezone.now() + timedelta(days=1),
            status=Match.Status.PLAYED,
            home_score=3,
            away_score=2,
        )
        self.match_scheduled = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_b,
            away_club=self.other_club,
            reference_code='API-002',
            scheduled_at=timezone.now() + timedelta(days=2),
            status=Match.Status.SCHEDULED,
        )
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            person=self.person,
            club=self.club_a,
            start_date=timezone.now().date(),
            status=Contract.Status.ACTIVE,
        )
        MatchEvent.objects.create(
            tenant=self.tenant,
            match=self.match_played,
            player=self.person,
            event_type=MatchEvent.EventType.GOAL,
            minute=12,
        )

    def test_public_api_requires_key(self):
        response = self.client.get(reverse('public-api-overview', args=[self.tenant.slug]))
        self.assertEqual(response.status_code, 403)

    def test_public_api_overview_and_matches(self):
        response = self.client.get(
            reverse('public-api-overview', args=[self.tenant.slug]),
            HTTP_X_SAAS_FUTEBOL_API_KEY='chave-publica-teste',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['tenant']['slug'], self.tenant.slug)
        self.assertTrue(any(card['label'] == 'Partidas' for card in payload['summary_cards']))
        self.assertTrue(any(item['reference_code'] == 'API-001' for item in payload['recent_matches']))
        self.assertTrue(any(item['type'] == 'Gol' for item in payload['recent_events']))

        matches_response = self.client.get(
            reverse('public-api-matches', args=[self.tenant.slug]),
            {'competition': self.competition.slug},
            HTTP_X_SAAS_FUTEBOL_API_KEY='chave-publica-teste',
        )
        self.assertEqual(matches_response.status_code, 200)
        matches_payload = matches_response.json()
        self.assertEqual(matches_payload['tenant']['slug'], self.tenant.slug)
        self.assertTrue(any(item['reference_code'] == 'API-001' for item in matches_payload['results']))


from .services import approvals  # noqa: E402


class Sprint12ScoutingTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')
        self.athlete_a = Person.objects.create(tenant=self.tenant, full_name='Atleta Scout A', kind=Person.Kind.ATHLETE, active=True)
        self.athlete_b = Person.objects.create(tenant=self.tenant, full_name='Atleta Scout B', kind=Person.Kind.ATHLETE, active=True)
        self.match_played = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_a,
            away_club=self.club_b,
            reference_code='SCOUT-001',
            scheduled_at=timezone.now() + timedelta(days=1),
            status=Match.Status.PLAYED,
            home_score=2,
            away_score=1,
        )
        MatchLineup.objects.create(
            tenant=self.tenant,
            match=self.match_played,
            player=self.athlete_a,
            club=self.club_a,
            jersey_number=9,
            position='Atacante',
            is_starter=True,
        )
        MatchLineup.objects.create(
            tenant=self.tenant,
            match=self.match_played,
            player=self.athlete_b,
            club=self.club_b,
            jersey_number=5,
            position='Meia',
            is_starter=False,
        )
        MatchEvent.objects.create(
            tenant=self.tenant,
            match=self.match_played,
            player=self.athlete_a,
            event_type=MatchEvent.EventType.GOAL,
            minute=20,
        )
        MatchEvent.objects.create(
            tenant=self.tenant,
            match=self.match_played,
            player=self.athlete_b,
            event_type=MatchEvent.EventType.YELLOW_CARD,
            minute=55,
        )

    def test_scouting_center_renders_tactical_leads(self):
        response = self.client.get(reverse('scouting-center'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Análise tática e scouting')
        self.assertContains(response, 'Sprint 12 · Análise tática e scouting')
        self.assertContains(response, 'Cobertura do elenco')
        self.assertContains(response, 'Atletas observados')
        self.assertContains(response, 'Partidas recentes analisadas')
        self.assertContains(response, 'Atleta Scout A')
        self.assertContains(response, 'Atacante')
        self.assertContains(response, 'Meia')


class ApprovalEngineTests(TestCase):
    """Matriz do motor de aprovações multi-etapas (ADR-0001)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='T1', slug='t1')
        self.tenant2 = Tenant.objects.create(name='T2', slug='t2')
        self.requester = User.objects.create_user('req', password='x')
        self.approver = User.objects.create_user('apr', password='x')
        self.competicao = User.objects.create_user('cmp', password='x')
        self.approver2 = User.objects.create_user('apr2', password='x')
        R = TenantMembership.Role
        TenantMembership.objects.create(user=self.requester, tenant=self.tenant, role=R.GESTOR_CLUBE)
        TenantMembership.objects.create(user=self.approver, tenant=self.tenant, role=R.APROVADOR)
        TenantMembership.objects.create(user=self.competicao, tenant=self.tenant, role=R.GESTOR_COMPETICAO)
        TenantMembership.objects.create(user=self.approver2, tenant=self.tenant2, role=R.APROVADOR)
        self.club_a = Club.objects.create(tenant=self.tenant, name='A', slug='a')
        self.club_b = Club.objects.create(tenant=self.tenant, name='B', slug='b')
        self.person = Person.objects.create(tenant=self.tenant, full_name='Atleta X')

        self.contract_flow = ApprovalFlow.objects.create(
            tenant=self.tenant, code='contrato', name='Contrato',
            target_kind=ApprovalFlow.TargetKind.CONTRATO,
        )
        ApprovalFlowStep.objects.create(
            tenant=self.tenant, flow=self.contract_flow, order=1, required_role=R.APROVADOR,
        )

        self.transfer_flow = ApprovalFlow.objects.create(
            tenant=self.tenant, code='transferencia', name='Transferência',
            target_kind=ApprovalFlow.TargetKind.TRANSFERENCIA,
        )
        self.t_step1 = ApprovalFlowStep.objects.create(
            tenant=self.tenant, flow=self.transfer_flow, order=1, required_role=R.GESTOR_COMPETICAO,
        )
        self.t_step2 = ApprovalFlowStep.objects.create(
            tenant=self.tenant, flow=self.transfer_flow, order=2,
            required_role=R.APROVADOR, requires_evidence=True,
        )

    def _draft_contract(self):
        return Contract.objects.create(
            tenant=self.tenant, person=self.person, club=self.club_a,
            start_date=timezone.now().date(), status=Contract.Status.DRAFT,
        )

    def test_single_step_approval_activates_contract(self):
        contract = self._draft_contract()
        req = approvals.open_request(contract, self.requester)
        step = self.contract_flow.steps.get(order=1)
        approvals.cast_decision(req, step, self.approver, ApprovalDecision.Outcome.APPROVED)
        contract.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.ACTIVE)
        self.assertEqual(req.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(req.decisions.count(), 1)

    def test_self_approval_forbidden(self):
        TenantMembership.objects.create(user=self.requester, tenant=self.tenant, role=TenantMembership.Role.APROVADOR)
        contract = self._draft_contract()
        req = approvals.open_request(contract, self.requester)
        step = self.contract_flow.steps.get(order=1)
        with self.assertRaises(ValidationError):
            approvals.cast_decision(req, step, self.requester, ApprovalDecision.Outcome.APPROVED)

    def test_role_mismatch_forbidden(self):
        contract = self._draft_contract()
        req = approvals.open_request(contract, self.requester)
        step = self.contract_flow.steps.get(order=1)
        with self.assertRaises(ValidationError):
            approvals.cast_decision(req, step, self.competicao, ApprovalDecision.Outcome.APPROVED)

    def test_tenant_isolation(self):
        contract = self._draft_contract()
        req = approvals.open_request(contract, self.requester)
        step = self.contract_flow.steps.get(order=1)
        with self.assertRaises(ValidationError):
            approvals.cast_decision(req, step, self.approver2, ApprovalDecision.Outcome.APPROVED)

    def test_terminal_rejection(self):
        contract = self._draft_contract()
        req = approvals.open_request(contract, self.requester)
        step = self.contract_flow.steps.get(order=1)
        approvals.cast_decision(req, step, self.approver, ApprovalDecision.Outcome.REJECTED)
        contract.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.REJECTED)
        self.assertEqual(contract.status, Contract.Status.TERMINATED)

    def test_cancel_pending_then_cannot_cancel_resolved(self):
        contract = self._draft_contract()
        req = approvals.open_request(contract, self.requester)
        approvals.cancel_request(req, self.requester)
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.CANCELLED)
        with self.assertRaises(ValidationError):
            approvals.cancel_request(req, self.requester)

    def test_two_step_transfer_ordering_evidence_and_effects(self):
        Contract.objects.create(
            tenant=self.tenant, person=self.person, club=self.club_a,
            start_date=timezone.now().date(), status=Contract.Status.ACTIVE,
        )
        negotiation = Negotiation.objects.create(tenant=self.tenant, club=self.club_b, person=self.person)
        req = approvals.open_request(negotiation, self.requester)

        # ordenação: não pode decidir a etapa 2 antes da 1
        with self.assertRaises(ValidationError):
            approvals.cast_decision(req, self.t_step2, self.approver, ApprovalDecision.Outcome.APPROVED)

        # etapa 1 aprovada — ainda sem efeito colateral, solicitação segue aberta
        approvals.cast_decision(req, self.t_step1, self.competicao, ApprovalDecision.Outcome.APPROVED)
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.OPEN)

        # etapa 2 sem evidência -> bloqueia
        with self.assertRaises(ValidationError):
            approvals.cast_decision(req, self.t_step2, self.approver, ApprovalDecision.Outcome.APPROVED)

        Evidence.objects.create(
            tenant=self.tenant,
            content_type=ContentType.objects.get_for_model(Negotiation),
            object_id=str(negotiation.pk),
            uploaded_by=self.requester,
            note='documentação',
        )
        approvals.cast_decision(req, self.t_step2, self.approver, ApprovalDecision.Outcome.APPROVED)
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.APPROVED)
        # efeito atômico: contrato destino ativo em club_b, origem em club_a rescindido
        self.assertTrue(Contract.objects.filter(
            tenant=self.tenant, person=self.person, club=self.club_b, status=Contract.Status.ACTIVE,
        ).exists())
        self.assertFalse(Contract.objects.filter(
            tenant=self.tenant, person=self.person, club=self.club_a, status=Contract.Status.ACTIVE,
        ).exists())

    def test_match_reopen_discards_events(self):
        flow = ApprovalFlow.objects.create(
            tenant=self.tenant, code='reabertura', name='Reabertura de partida',
            target_kind=ApprovalFlow.TargetKind.PARTIDA,
        )
        ApprovalFlowStep.objects.create(
            tenant=self.tenant, flow=flow, order=1, required_role=TenantMembership.Role.APROVADOR,
        )
        competition = Competition.objects.create(tenant=self.tenant, name='Liga', slug='liga')
        edition = CompetitionEdition.objects.create(
            tenant=self.tenant, competition=competition, slug='2026', name='Liga 2026', season_year=2026,
        )
        phase = CompetitionPhase.objects.create(
            tenant=self.tenant, edition=edition, code='f1', name='Fase 1', order=1,
        )
        match = Match.objects.create(
            tenant=self.tenant, phase=phase, home_club=self.club_a, away_club=self.club_b,
            reference_code='R1', scheduled_at=timezone.now() - timedelta(days=1),
            status=Match.Status.PLAYED, home_score=2, away_score=1,
        )
        MatchEvent.objects.create(
            tenant=self.tenant, match=match, event_type=MatchEvent.EventType.GOAL, minute=10,
        )
        req = approvals.open_request(match, self.requester)
        approvals.cast_decision(req, flow.steps.get(order=1), self.approver, ApprovalDecision.Outcome.APPROVED)
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.SCHEDULED)
        self.assertIsNone(match.home_score)
        self.assertEqual(match.events.count(), 0)


class Sprint6GovernanceTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')

    def test_audit_log_records_club_creation_and_is_listed(self):
        response = self.client.post(
            reverse('club-create'),
            {'name': 'Clube Novo', 'slug': 'clube-novo-s6', 'registration_code': '', 'city': 'Curitiba', 'state': 'PR', 'active': 'on'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Club.objects.filter(tenant=self.tenant, slug='clube-novo-s6').exists())
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                action='create',
                content_type=ContentType.objects.get_for_model(Club),
                object_id__isnull=False,
            ).exists()
        )
        audit_page = self.client.get(reverse('audit-log-list'))
        self.assertEqual(audit_page.status_code, 200)
        self.assertContains(audit_page, 'Auditoria')

    def test_auditor_can_read_but_not_write(self):
        auditor = User.objects.create_user(username='auditor', password='senha12345')
        TenantMembership.objects.create(user=auditor, tenant=self.tenant, role=TenantMembership.Role.AUDITOR)
        self.client.logout()
        self.client.login(username='auditor', password='senha12345')
        self.assertEqual(self.client.get(reverse('club-create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('audit-log-list')).status_code, 200)

    def test_import_and_export_are_audited(self):
        export_csv(self.tenant, 'club')
        import_payload(self.tenant, 'club', 'name,slug,city,state\nClube S6,clube-s6,Fortaleza,CE\n')
        actions = list(
            AuditLog.objects.filter(tenant=self.tenant, content_type=ContentType.objects.get_for_model(Tenant)).values_list('action', flat=True)
        )
        self.assertIn('export', actions)
        self.assertIn('import', actions)


class Sprint7TransferTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')
        self.person = Person.objects.create(tenant=self.tenant, full_name='Atleta Sprint 7')
        self.negotiation = Negotiation.objects.create(tenant=self.tenant, club=self.club_a, person=self.person)

    def test_transfer_center_exposes_the_new_workspace(self):
        response = self.client.get(reverse('transfer-center'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Transferências, contratos e evidências')
        self.assertContains(response, 'Contratos')
        self.assertContains(response, 'Evidências')

    def test_contract_and_evidence_create_are_audited(self):
        contract_response = self.client.post(
            reverse('contract-create'),
            {
                'person': self.person.pk,
                'club': self.club_a.pk,
                'start_date': timezone.now().date().isoformat(),
                'end_date': '',
                'signed_at': '',
                'status': Contract.Status.DRAFT,
                'termination_reason': '',
            },
            follow=True,
        )
        self.assertEqual(contract_response.status_code, 200)
        self.assertTrue(Contract.objects.filter(tenant=self.tenant, person=self.person, club=self.club_a).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                action='create',
                content_type=ContentType.objects.get_for_model(Contract),
            ).exists()
        )

        evidence_response = self.client.post(
            reverse('evidence-create'),
            {
                'content_type': ContentType.objects.get_for_model(Negotiation).pk,
                'object_id': str(self.negotiation.pk),
                'url': 'https://example.com/evidence',
                'note': 'Documento da negociação',
            },
            follow=True,
        )
        self.assertEqual(evidence_response.status_code, 200)
        self.assertTrue(
            Evidence.objects.filter(
                tenant=self.tenant,
                uploaded_by=self.user,
                note='Documento da negociação',
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                tenant=self.tenant,
                action='create',
                content_type=ContentType.objects.get_for_model(Evidence),
            ).exists()
        )

    def test_evidence_validation_blocks_cross_tenant_targets(self):
        other_tenant = Tenant.objects.create(name='Outro Tenant', slug='outro-tenant')
        other_club = Club.objects.create(tenant=other_tenant, name='Outro Clube', slug='outro-clube')
        other_person = Person.objects.create(tenant=other_tenant, full_name='Pessoa Externa')
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            person=other_person,
            club=other_club,
            start_date=timezone.now().date(),
        )
        evidence = Evidence(
            tenant=self.tenant,
            content_type=ContentType.objects.get_for_model(Contract),
            object_id=str(other_contract.pk),
            uploaded_by=self.user,
            note='fora do tenant',
        )
        with self.assertRaises(ValidationError):
            evidence.full_clean()


class Sprint8ReportingTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')
        self.person = Person.objects.create(tenant=self.tenant, full_name='Atleta Sprint 8')
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            person=self.person,
            club=self.club_a,
            start_date=timezone.now().date(),
            status=Contract.Status.ACTIVE,
        )
        self.negotiation = Negotiation.objects.create(
            tenant=self.tenant,
            club=self.club_b,
            person=self.person,
            status=Negotiation.Status.ACCEPTED,
        )
        self.proposal = Proposal.objects.create(
            tenant=self.tenant,
            negotiation=self.negotiation,
            club=self.club_b,
            amount='5000.00',
            currency='BRL',
            status=Proposal.Status.SENT,
        )
        self.approval_request = ApprovalRequest.objects.create(
            tenant=self.tenant,
            flow=self.flow,
            requested_by=self.user,
            content_type=ContentType.objects.get_for_model(Match),
            object_id='abc-123',
            reason='Relatório de teste',
        )
        self.notification = Notification.objects.create(
            tenant=self.tenant,
            recipient=self.user,
            subject='Notificação Sprint 8',
            body='Mensagem para o painel de relatórios',
        )
        AuditLog.objects.create(
            tenant=self.tenant,
            actor=self.user,
            action=AuditLog.Action.CREATE,
            content_type=ContentType.objects.get_for_model(Contract),
            object_id=str(self.contract.pk),
            before_state={},
            after_state={'status': Contract.Status.ACTIVE},
        )

    def test_report_center_renders_metrics_and_recent_records(self):
        response = self.client.get(reverse('report-center'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Relatórios e indicadores')
        self.assertContains(response, 'Contratos por status')
        self.assertContains(response, 'Contratos ativos')
        self.assertContains(response, 'Últimas solicitações')
        self.assertContains(response, 'Últimas auditorias')
        self.assertContains(response, 'Notificação Sprint 8')
        self.assertContains(response, 'Relatório de teste')

