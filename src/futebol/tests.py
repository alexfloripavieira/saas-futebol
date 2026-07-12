from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import (
    AIAgent,
    AIAgentSourceLink,
    AIProvider,
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
    KnowledgeSource,
    Match,
    MatchEvent,
    MatchLineup,
    MatchDossier,
    Negotiation,
    Notification,
    Person,
    Proposal,
    SportsDataSource,
    Tenant,
    TenantBranding,
    TenantMembership,
    TenantModuleSubscription,
)
from .modules import MODULE_NAMES
from .services.data_io import export_csv, import_payload


class Sprint3BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alex', password='senha12345')
        self.requester_user = User.objects.create_user(username='solicitante-base', password='senha12345')
        self.tenant = Tenant.objects.create(name='Clube Exemplo', slug='clube-exemplo')
        TenantMembership.objects.create(user=self.user, tenant=self.tenant, role=TenantMembership.Role.ADMIN_TENANT)
        TenantMembership.objects.create(
            user=self.requester_user,
            tenant=self.tenant,
            role=TenantMembership.Role.GESTOR_COMPETICAO,
        )
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
        ApprovalFlowStep.objects.create(
            tenant=self.tenant,
            flow=self.flow,
            order=1,
            required_role=TenantMembership.Role.ADMIN_TENANT,
        )
        self.match = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_a,
            away_club=self.club_b,
            reference_code='BASE-001',
            scheduled_at=timezone.now() + timedelta(days=3),
        )


class AIFeatureTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.provider = AIProvider.objects.create(
            tenant=self.tenant,
            name='OpenAI Produção',
            kind=AIProvider.Kind.OPENAI,
            model_name='gpt-4.1-mini',
            active=True,
        )
        self.source = KnowledgeSource.objects.create(
            tenant=self.tenant,
            identifier='docs/aula-1.md',
            title='Aula 1',
            kind=KnowledgeSource.Kind.DOCUMENT,
            source_path='docs/aula-1.md',
            content='# Aula 1\nConteúdo base.',
            summary='Aula 1',
            active=True,
        )
        self.agent = AIAgent.objects.create(
            tenant=self.tenant,
            provider=self.provider,
            name='Scout IA',
            slug='scout-ia',
            purpose='Responder perguntas sobre o produto.',
            system_prompt='Use as fontes vinculadas.',
            model_override='',
            temperature='0.20',
            active=True,
        )
        AIAgentSourceLink.objects.create(tenant=self.tenant, agent=self.agent, source=self.source, order=0, active=True)

    def test_ai_pages_render_with_cadastrados(self):
        self.client.login(username='alex', password='senha12345')
        for url_name in ['ai-center', 'ai-provider-list', 'ai-agent-list', 'knowledge-source-list']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
        center = self.client.get(reverse('ai-center'))
        self.assertContains(center, 'Providers')
        self.assertContains(center, 'Agentes')
        self.assertContains(center, 'Fontes')
        self.assertContains(center, 'Scout IA')
        self.assertContains(center, 'Aula 1')

    def test_knowledge_source_list_exposes_import_url_tab(self):
        self.client.login(username='alex', password='senha12345')
        response = self.client.get(reverse('knowledge-source-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Importar URL')
        self.assertContains(response, 'Nova fonte manual')
        self.assertContains(response, 'Documentos, relatórios e páginas públicas')

    @patch('futebol.services.ai.safe_urlopen')
    def test_knowledge_source_import_url_creates_source_from_public_page(self, urlopen_mock):
        class FakeHeaders:
            def get(self, key, default=None):
                if key.lower() == 'content-type':
                    return 'text/html; charset=utf-8'
                return default

            def get_content_charset(self):
                return 'utf-8'

        class FakeResponse:
            def __init__(self, body):
                self._body = body.encode('utf-8')
                self.headers = FakeHeaders()

            def read(self):
                return self._body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        urlopen_mock.return_value = FakeResponse(
            '''
            <html>
              <head>
                <title>FIFA Training Centre Demo</title>
                <meta name="description" content="Resumo da página">
              </head>
              <body>
                <h1>Página FIFA</h1>
                <p>Conteúdo principal da fonte.</p>
              </body>
            </html>
            '''
        )
        self.client.login(username='alex', password='senha12345')
        response = self.client.post(
            reverse('knowledge-source-import-url'),
            {'url': 'https://fifatrainingcentre.com/en/demo', 'identifier': '', 'title': ''},
        )
        self.assertEqual(response.status_code, 302)
        source = KnowledgeSource.objects.get(tenant=self.tenant, source_url='https://fifatrainingcentre.com/en/demo')
        self.assertEqual(source.title, 'FIFA Training Centre Demo')
        self.assertEqual(source.summary, 'Resumo da página')
        self.assertIn('Conteúdo principal da fonte.', source.content)

    def test_provider_list_shows_model_catalog(self):
        self.client.login(username='alex', password='senha12345')
        response = self.client.get(reverse('ai-provider-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Catálogo de LLMs por provider')
        self.assertContains(response, 'opencode-go/deepseek-v4-flash')
        self.assertContains(response, 'DeepSeek V4 Flash')
        self.assertContains(response, 'OpenAI GPT-4.1 Mini')

    def test_import_ai_sources_command_imports_files_and_seeds_agent(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / 'docs').mkdir(parents=True)
            (root / 'orchestrator' / 'reports').mkdir(parents=True)
            (root / 'docs' / 'aula-2.md').write_text('# Aula 2\nTexto da aula 2.', encoding='utf-8')
            (root / 'orchestrator' / 'reports' / 'relatorio-ia.md').write_text('# Relatório IA\nBase documental.', encoding='utf-8')
            call_command('import_ai_sources', tenant=self.tenant.slug, root=str(root), seed_agent=True)

        self.assertEqual(KnowledgeSource.objects.filter(tenant=self.tenant).count(), 10)
        self.assertEqual(AIProvider.objects.filter(tenant=self.tenant).count(), 2)
        self.assertTrue(AIAgent.objects.filter(tenant=self.tenant, slug='scout-ia').exists())
        self.assertEqual(
            AIAgent.objects.filter(tenant=self.tenant, slug__startswith='coach-').count(),
            8,
        )
        self.assertEqual(
            AIAgentSourceLink.objects.filter(
                tenant=self.tenant,
                agent__slug='scout-ia',
            ).count(),
            10,
        )
        self.assertEqual(KnowledgeSource.objects.get(tenant=self.tenant, identifier='external:kaggle').source_url, 'https://www.kaggle.com/')


    def test_ai_center_can_run_agent_and_show_result(self):
        self.client.login(username='alex', password='senha12345')
        response = self.client.post(
            reverse('ai-center'),
            {'tenant': self.tenant.pk, 'agent': self.agent.pk, 'question': 'O que a fonte diz sobre o conteúdo?'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Executar agente')
        self.assertContains(response, 'Scout IA')
        self.assertContains(response, 'Aula 1')


    def test_ai_center_can_run_opencode_agent_when_cli_is_available(self):
        self.client.login(username='alex', password='senha12345')
        opencode_provider = AIProvider.objects.create(
            tenant=self.tenant,
            name='OpenCode Go',
            kind=AIProvider.Kind.OPENCODE,
            model_name='opencode-go/deepseek-v4-flash',
            active=True,
        )
        opencode_agent = AIAgent.objects.create(
            tenant=self.tenant,
            provider=opencode_provider,
            name='Scout IA OpenCode',
            slug='scout-ia-opencode',
            purpose='Responder perguntas sobre o produto.',
            system_prompt='Use as fontes vinculadas.',
            model_override='',
            temperature='0.20',
            active=True,
        )
        AIAgentSourceLink.objects.create(tenant=self.tenant, agent=opencode_agent, source=self.source, order=0, active=True)

        with patch('futebol.services.ai._find_opencode_binary', return_value='/usr/bin/opencode'), patch(
            'futebol.services.ai.subprocess.run'
        ) as run_mock:
            run_mock.return_value = type('R', (), {'stdout': 'Resposta OpenCode', 'stderr': '', 'returncode': 0})()
            response = self.client.post(
                reverse('ai-center'),
                {'tenant': self.tenant.pk, 'agent': opencode_agent.pk, 'question': 'O que a fonte diz sobre o conteúdo?'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resposta OpenCode')
        self.assertContains(response, 'OpenCode Go')

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
            requested_by=self.requester_user,
            content_type=ContentType.objects.get_for_model(Match),
            object_id=str(self.match.pk),
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
            object_id=str(self.match.pk),
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

    def test_ai_provider_form_exposes_api_key_and_syncs_credentials(self):
        opencode_provider = AIProvider.objects.create(
            tenant=self.tenant,
            name='OpenCode Go',
            kind=AIProvider.Kind.OPENCODE,
            model_name='opencode-go/deepseek-v4-flash',
            active=True,
        )

        response = self.client.get(reverse('ai-provider-edit', args=[opencode_provider.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Chave da API')
        self.assertContains(response, 'provider-model-suggestions')
        self.assertContains(response, 'provider-model-catalog')
        self.assertContains(response, 'Modelos sugeridos por provider')

        with patch('futebol.views.sync_opencode_provider_credentials') as sync_mock:
            sync_mock.return_value = {'returncode': 0}
            post = self.client.post(
                reverse('ai-provider-edit', args=[opencode_provider.pk]),
                {
                    'name': 'OpenCode Go',
                    'kind': AIProvider.Kind.OPENCODE,
                    'model_name': 'opencode-go/deepseek-v4-flash',
                    'api_base_url': 'alex',
                    'active': 'on',
                    'notes': 'Configuração da credencial',
                    'api_key': 'sk-teste',
                },
                follow=True,
            )

        self.assertEqual(post.status_code, 200)
        self.assertContains(post, 'Provider atualizado com sucesso.')
        sync_mock.assert_called_once_with(
            api_key='sk-teste',
            provider_name='OpenCode Go',
            provider_kind=AIProvider.Kind.OPENCODE,
            model_name='opencode-go/deepseek-v4-flash',
        )
        opencode_provider.refresh_from_db()
        self.assertEqual(opencode_provider.api_base_url, '')

    def test_sync_opencode_provider_credentials_writes_config_file(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / '.config' / 'opencode'
            config_dir.mkdir(parents=True)
            (config_dir / 'opencode.json').write_text(
                json.dumps({'$schema': 'https://opencode.ai/config.json', 'mcp': {'pencil': {'enabled': True}}}, indent=2),
                encoding='utf-8',
            )

            with patch('futebol.services.ai.Path.home', return_value=root):
                from futebol.services.ai import sync_opencode_provider_credentials

                result = sync_opencode_provider_credentials(
                    api_key='sk-test',
                    provider_name='OpenCode Go',
                    provider_kind='opencode',
                    model_name='opencode-go/deepseek-v4-flash',
                )

            self.assertEqual(result['returncode'], 0)
            config = json.loads((config_dir / 'opencode.json').read_text(encoding='utf-8'))
            self.assertEqual(config['$schema'], 'https://opencode.ai/config.json')
            self.assertEqual(config['model'], 'opencode-go/deepseek-v4-flash')
            self.assertEqual(config['provider']['opencode-go']['options']['apiKey'], 'sk-test')
            self.assertIn('deepseek-v4-flash', config['provider']['opencode-go']['models'])
            self.assertTrue(config['mcp']['pencil']['enabled'])

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
            requested_by=self.requester_user,
            content_type=ContentType.objects.get_for_model(Match),
            object_id=str(self.match.pk),
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


class WhiteLabelModuleGatingTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')
        TenantModuleSubscription.objects.create(
            tenant=self.tenant,
            module_code='operacao',
            module_name='Operação',
            enabled=True,
        )

    def test_uncontracted_module_is_blocked_even_when_url_is_accessed_directly(self):
        response = self.client.get(reverse('ai-center'))

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'futebol/module_unavailable.html')
        self.assertContains(response, 'Módulo não contratado', status_code=403)
        self.assertContains(response, 'IA', status_code=403)

    def test_base_operation_module_remains_available(self):
        response = self.client.get(reverse('club-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clubes')


class TenantAdminSprint2Tests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')

    def test_tenant_admin_page_lists_members_branding_and_modules(self):
        TenantBranding.objects.create(
            tenant=self.tenant,
            primary_color='#123456',
            public_title='Portal Clube Exemplo',
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant,
            module_code='operacao',
            module_name='Operação',
            enabled=True,
        )

        response = self.client.get(reverse('tenant-admin'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Administração do tenant')
        self.assertContains(response, 'alex')
        self.assertContains(response, 'Portal Clube Exemplo')
        self.assertContains(response, 'Operação')
        self.assertContains(response, 'Prévia do branding')

    def test_admin_tenant_can_create_user_with_initial_role(self):
        response = self.client.post(
            reverse('tenant-user-create'),
            {
                'username': 'analista',
                'first_name': 'Ana',
                'last_name': 'Lista',
                'email': 'ana@example.com',
                'password1': 'senha12345',
                'password2': 'senha12345',
                'role': TenantMembership.Role.GESTOR_CLUBE,
                'active': 'on',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuário criado com sucesso.')
        created = User.objects.get(username='analista')
        self.assertTrue(
            TenantMembership.objects.filter(
                user=created,
                tenant=self.tenant,
                role=TenantMembership.Role.GESTOR_CLUBE,
                active=True,
            ).exists()
        )

    def test_admin_tenant_can_update_membership_role_and_status(self):
        user = User.objects.create_user(username='operador', password='senha12345')
        membership = TenantMembership.objects.create(
            user=user,
            tenant=self.tenant,
            role=TenantMembership.Role.GESTOR_CLUBE,
            active=True,
        )

        response = self.client.post(
            reverse('tenant-membership-edit', args=[membership.pk]),
            {
                'role': TenantMembership.Role.AUDITOR,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vínculo atualizado com sucesso.')
        membership.refresh_from_db()
        self.assertEqual(membership.role, TenantMembership.Role.AUDITOR)
        self.assertFalse(membership.active)

    def test_admin_tenant_can_update_user_profile(self):
        user = User.objects.create_user(
            username='analista-antigo',
            password='senha12345',
            first_name='Nome',
            last_name='Antigo',
            email='antigo@example.com',
        )
        TenantMembership.objects.create(
            user=user,
            tenant=self.tenant,
            role=TenantMembership.Role.GESTOR_CLUBE,
            active=True,
        )

        response = self.client.post(
            reverse('tenant-user-edit', args=[user.pk]),
            {
                'username': 'analista-novo',
                'first_name': 'Ana',
                'last_name': 'Nova',
                'email': 'nova@example.com',
                'is_active': 'on',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuário atualizado com sucesso.')
        user.refresh_from_db()
        self.assertEqual(user.username, 'analista-novo')
        self.assertEqual(user.first_name, 'Ana')
        self.assertEqual(user.email, 'nova@example.com')

    def test_admin_tenant_can_update_branding_and_modules(self):
        response = self.client.post(
            reverse('tenant-admin'),
            {
                'form_kind': 'settings',
                'primary_color': '#001f5b',
                'secondary_color': '#002f7a',
                'background_color': '#031225',
                'accent_color': '#66b2ff',
                'logo_url': 'https://example.com/logo.png',
                'favicon_url': '',
                'symbol_url': '',
                'public_title': 'Portal Atualizado',
                'public_subtitle': 'Gestão do clube',
                'modules': ['ia'],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configurações do tenant atualizadas.')
        branding = self.tenant.branding
        self.assertEqual(branding.primary_color, '#001f5b')
        self.assertEqual(branding.logo_url, 'https://example.com/logo.png')
        self.assertTrue(TenantModuleSubscription.objects.get(tenant=self.tenant, module_code='operacao').enabled)
        self.assertTrue(TenantModuleSubscription.objects.get(tenant=self.tenant, module_code='ia').enabled)
        self.assertFalse(TenantModuleSubscription.objects.get(tenant=self.tenant, module_code='aprovacoes').enabled)

    def test_non_admin_tenant_cannot_open_tenant_admin(self):
        user = User.objects.create_user(username='auditor-s2', password='senha12345')
        TenantMembership.objects.create(user=user, tenant=self.tenant, role=TenantMembership.Role.AUDITOR)
        self.client.logout()
        self.client.login(username='auditor-s2', password='senha12345')

        response = self.client.get(reverse('tenant-admin'))

        self.assertEqual(response.status_code, 403)


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
        self.assertContains(hub, 'Integrações externas')
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
        self.assertContains(hub, 'Integrações externas')
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


class Sprint11PublicApiTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.api_key = self.tenant.rotate_public_api_key()
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
        response = self.client.get(reverse('public-api-v1-overview', args=[self.tenant.slug]))
        self.assertEqual(response.status_code, 403)

    def test_public_api_rejects_wrong_key(self):
        response = self.client.get(
            reverse('public-api-v1-overview', args=[self.tenant.slug]),
            HTTP_X_SAAS_FUTEBOL_API_KEY='chave-errada',
        )
        self.assertEqual(response.status_code, 403)

    def test_public_api_key_is_scoped_per_tenant(self):
        # Um segundo tenant com a SUA própria chave.
        other = Tenant.objects.create(name='Outro Clube', slug='outro-clube')
        other_key = other.rotate_public_api_key()
        # A chave do tenant atual NÃO dá acesso ao outro tenant (sem vazamento cross-tenant).
        cross = self.client.get(
            reverse('public-api-v1-overview', args=[other.slug]),
            HTTP_X_SAAS_FUTEBOL_API_KEY=self.api_key,
        )
        self.assertEqual(cross.status_code, 403)
        # A chave própria do outro tenant funciona no próprio tenant.
        own = self.client.get(
            reverse('public-api-v1-overview', args=[other.slug]),
            HTTP_X_SAAS_FUTEBOL_API_KEY=other_key,
        )
        self.assertEqual(own.status_code, 200)

    def test_public_api_disabled_when_key_blank(self):
        self.tenant.revoke_public_api_key()
        response = self.client.get(
            reverse('public-api-v1-overview', args=[self.tenant.slug]),
            HTTP_X_SAAS_FUTEBOL_API_KEY='',
        )
        self.assertEqual(response.status_code, 403)

    def test_public_api_overview_and_matches(self):
        response = self.client.get(
            reverse('public-api-v1-overview', args=[self.tenant.slug]),
            HTTP_X_SAAS_FUTEBOL_API_KEY=self.api_key,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['tenant']['slug'], self.tenant.slug)
        self.assertTrue(any(card['label'] == 'Partidas' for card in payload['summary_cards']))
        self.assertTrue(any(item['reference_code'] == 'API-001' for item in payload['recent_matches']))
        self.assertEqual(payload['api_version'], 'v1')

        matches_response = self.client.get(
            reverse('public-api-v1-matches', args=[self.tenant.slug]),
            {'competition': self.competition.slug},
            HTTP_X_SAAS_FUTEBOL_API_KEY=self.api_key,
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
        self.assertContains(response, 'Centro de IA e agentes')
        self.assertContains(response, 'Centro de IA e agentes')
        self.assertContains(response, 'Cobertura do elenco')
        self.assertContains(response, 'Atletas observados')
        self.assertContains(response, 'Partidas recentes analisadas')
        self.assertContains(response, 'Atleta Scout A')
        self.assertContains(response, 'Atacante')
        self.assertContains(response, 'Meia')


class RemainingPrdSprintTests(Sprint3BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='alex', password='senha12345')
        self.athlete = Person.objects.create(tenant=self.tenant, full_name='Atleta Previsão', kind=Person.Kind.ATHLETE, active=True)
        self.played_match = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_a,
            away_club=self.club_b,
            reference_code='PREV-001',
            scheduled_at=timezone.now() - timedelta(days=2),
            status=Match.Status.PLAYED,
            home_score=2,
            away_score=0,
        )
        self.next_match = Match.objects.create(
            tenant=self.tenant,
            phase=self.phase,
            home_club=self.club_b,
            away_club=self.club_a,
            reference_code='PREV-002',
            scheduled_at=timezone.now() + timedelta(days=7),
            status=Match.Status.SCHEDULED,
        )
        MatchLineup.objects.create(
            tenant=self.tenant,
            match=self.played_match,
            player=self.athlete,
            club=self.club_a,
            position='Atacante',
            is_starter=True,
        )
        MatchEvent.objects.create(
            tenant=self.tenant,
            match=self.played_match,
            player=self.athlete,
            event_type=MatchEvent.EventType.YELLOW_CARD,
            minute=72,
        )
        KnowledgeSource.objects.create(
            tenant=self.tenant,
            identifier='previsoes/scouting.md',
            title='Relatório de scouting',
            kind=KnowledgeSource.Kind.REPORT,
            content='Base para próximo adversário e tendência de performance.',
            summary='Scouting',
            active=True,
        )

    def test_prediction_center_renders_forecasts_commission_view_sources_and_triggers(self):
        response = self.client.get(reverse('prediction-center'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Previsões inteligentes')
        self.assertContains(response, 'Próximo adversário')
        self.assertContains(response, 'Tendência de performance')
        self.assertContains(response, 'Risco de suspensão')
        self.assertContains(response, 'Visão da comissão técnica')
        self.assertContains(response, 'Relatório de scouting')
        self.assertContains(response, 'Gatilhos de automação')

    def test_automation_center_exposes_prediction_alert_triggers(self):
        response = self.client.get(reverse('automation-center'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gatilhos de automação')
        self.assertContains(response, 'Previsão de suspensão')
        self.assertContains(response, 'Próximo adversário')

    def test_main_pages_stay_under_query_budget(self):
        for url_name in ['home', 'tenant-admin', 'report-center', 'bi-center', 'prediction-center']:
            with self.subTest(url_name=url_name):
                with CaptureQueriesContext(connection) as captured:
                    response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertLessEqual(len(captured), 80)

    def test_avai_pilot_seed_creates_branded_tenant_and_modules(self):
        call_command('seed_futebol_demo', avai_pilot=True, password='demo1234')

        tenant = Tenant.objects.get(slug='avai')
        self.assertEqual(tenant.name, 'Avaí FC')
        self.assertEqual(tenant.branding.public_title, 'Avaí FC Intelligence')
        self.assertTrue(TenantModuleSubscription.objects.filter(tenant=tenant, module_code='previsoes', enabled=True).exists())
        self.assertEqual(AIAgent.objects.filter(tenant=tenant, slug__startswith='coach-').count(), 8)
        self.assertTrue(MatchDossier.objects.filter(tenant=tenant, status=MatchDossier.Status.READY).exists())
        self.assertTrue(SportsDataSource.objects.filter(tenant=tenant, quality='synthetic').exists())


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
        TenantMembership.objects.create(
            user=self.requester,
            tenant=self.tenant,
            role=TenantMembership.Role.GESTOR_COMPETICAO,
        )
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
            requested_by=self.requester_user,
            content_type=ContentType.objects.get_for_model(Match),
            object_id=str(self.match.pk),
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



class WhiteLabelPhase1Tests(TestCase):
    """PRD Fase 1 — white-label, módulos contratados, institucional e onboarding."""

    def setUp(self):
        self.user = User.objects.create_user(username='gestor', password='senha12345')
        self.tenant = Tenant.objects.create(name='Avaí FC', slug='avai')
        TenantMembership.objects.create(
            user=self.user,
            tenant=self.tenant,
            role=TenantMembership.Role.ADMIN_TENANT,
        )

    def _subscribe(self, *codes):
        for code in codes:
            TenantModuleSubscription.objects.create(
                tenant=self.tenant, module_code=code, module_name=code.title(), enabled=True,
            )

    def test_landing_page_is_public_for_anonymous(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'white-label')
        self.assertContains(response, reverse('login'))

    def test_landing_apresenta_inteligencia_tatica_e_catalogo_completo(self):
        response = self.client.get(reverse('landing'))

        self.assertContains(response, 'Treinador Inteligente')
        self.assertContains(response, 'Comissão Técnica Digital')
        self.assertContains(response, 'Prancheta temporal')
        self.assertContains(response, 'Revisão humana')
        for module_name in MODULE_NAMES.values():
            self.assertContains(response, module_name)
        self.assertEqual(
            response.content.count(b'class="module-card"'),
            len(MODULE_NAMES),
        )

    def test_root_redirects_authenticated_without_tenant_to_onboarding(self):
        User.objects.create_user(username='novo', password='senha12345')
        self.client.login(username='novo', password='senha12345')
        response = self.client.get('/')
        self.assertRedirects(response, reverse('onboarding'))

    def test_root_redirects_authenticated_with_tenant_to_painel(self):
        self.client.login(username='gestor', password='senha12345')
        response = self.client.get('/')
        self.assertRedirects(response, reverse('home'))

    def test_onboarding_creates_tenant_branding_modules_and_membership(self):
        newbie = User.objects.create_user(username='novo', password='senha12345')
        self.client.login(username='novo', password='senha12345')
        self.assertEqual(self.client.get(reverse('onboarding')).status_code, 200)

        payload = {
            'tenant_name': 'Figueirense', 'tenant_slug': 'figueira',
            'role': TenantMembership.Role.ADMIN_TENANT,
            'modules': ['operacao', 'ia'],
            'public_title': 'Portal Figueira', 'public_subtitle': 'Futebol de Santa Catarina',
            'primary_color': '#000000', 'secondary_color': '#111111',
            'background_color': '#222222', 'accent_color': '#333333',
            'logo_url': '', 'favicon_url': '',
        }
        response = self.client.post(reverse('onboarding'), payload)
        self.assertRedirects(response, reverse('home'))

        tenant = Tenant.objects.get(slug='figueira')
        self.assertTrue(TenantBranding.objects.filter(tenant=tenant, primary_color='#000000', public_title='Portal Figueira').exists())
        self.assertEqual(TenantModuleSubscription.objects.filter(tenant=tenant, enabled=True).count(), 2)
        self.assertTrue(TenantMembership.objects.filter(user=newbie, tenant=tenant, role=TenantMembership.Role.ADMIN_TENANT).exists())

    def test_onboarding_redirects_when_user_already_has_tenant(self):
        self.client.login(username='gestor', password='senha12345')
        response = self.client.get(reverse('onboarding'))
        self.assertRedirects(response, reverse('home'))

    def test_onboarding_does_not_offer_platform_admin_role(self):
        from .forms import OnboardingForm

        role_values = [value for value, _ in OnboardingForm().fields['role'].choices]
        self.assertNotIn(TenantMembership.Role.ADMIN_PLATAFORMA, role_values)
        self.assertIn(TenantMembership.Role.ADMIN_TENANT, role_values)

    def test_branding_is_applied_in_base_template(self):
        TenantBranding.objects.create(tenant=self.tenant, primary_color='#abcdef', public_title='Portal Avaí')
        self.client.login(username='gestor', password='senha12345')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '#abcdef')
        self.assertContains(response, 'Portal Avaí')

    def test_menu_shows_only_contracted_modules(self):
        self._subscribe('operacao')
        self.client.login(username='gestor', password='senha12345')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Clubes')
        self.assertNotContains(response, 'Centro de IA')

    def test_uncontracted_module_is_blocked(self):
        self._subscribe('operacao')
        self.client.login(username='gestor', password='senha12345')
        response = self.client.get(reverse('ai-provider-list'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'não contratado', status_code=403)

    def test_unprovisioned_tenant_keeps_full_access(self):
        self.client.login(username='gestor', password='senha12345')
        self.assertEqual(self.client.get(reverse('ai-provider-list')).status_code, 200)

    def test_module_subscription_is_unique_per_tenant(self):
        self._subscribe('operacao')
        with self.assertRaises(ValidationError):
            TenantModuleSubscription(
                tenant=self.tenant, module_code='operacao', module_name='Operação', enabled=True,
            ).save()


class PublicLoginJourneyTests(TestCase):
    """Issue #8 — jornada pública e primeiro acesso: a tela de login é pública
    e não expõe o shell operacional (sidebar/menus)."""

    def test_login_page_is_public_and_not_operational_shell(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        # Não deve renderizar o shell operacional (barra lateral de navegação).
        self.assertNotContains(response, 'class="sidebar"')
        # Deve oferecer caminho de volta à tela institucional pública.
        self.assertContains(response, reverse('landing'))
        # E manter o formulário de autenticação.
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_login_comunica_valor_do_produto_sem_expor_shell(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, 'Seu clube pensa, decide e evolui')
        self.assertContains(response, 'Treinador Inteligente')
        self.assertContains(response, 'Operação e governança')
        self.assertContains(response, 'Dados e inteligência')
        self.assertEqual(
            response.content.count(b'class="module-chip"'),
            len(MODULE_NAMES),
        )
        self.assertContains(response, 'mailto:comercial@saasdofutebol.com')
        self.assertNotContains(response, 'class="sidebar"')


class TenantAdminIALinksTests(TestCase):
    """Issue #10 (gap) — a central do tenant oferece atalhos para providers,
    agentes e fontes quando o módulo IA está contratado."""

    def setUp(self):
        self.user = User.objects.create_user(username='gestor', password='senha12345')
        self.tenant = Tenant.objects.create(name='Avaí FC', slug='avai')
        TenantMembership.objects.create(
            user=self.user, tenant=self.tenant, role=TenantMembership.Role.ADMIN_TENANT,
        )
        self.client.login(username='gestor', password='senha12345')

    def _subscribe(self, code, enabled=True):
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code=code, module_name=code.title(), enabled=enabled,
        )

    def test_ia_paths_shown_when_ia_contracted(self):
        self._subscribe('operacao')
        self._subscribe('ia')
        response = self.client.get(reverse('tenant-admin'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inteligência artificial e fontes')
        self.assertContains(response, reverse('ai-provider-list'))
        self.assertContains(response, reverse('ai-agent-list'))
        self.assertContains(response, reverse('knowledge-source-list'))

    def test_ia_paths_hidden_when_ia_not_contracted(self):
        self._subscribe('operacao')  # IA não contratada
        response = self.client.get(reverse('tenant-admin'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Inteligência artificial e fontes')


class MainPagesPerformanceTests(TestCase):
    """Issue #15 (gap) — validação de performance básica: guarda contra N+1 nas
    páginas principais, limitando o número de queries por request."""

    def setUp(self):
        self.user = User.objects.create_user(username='perf', password='senha12345')
        self.tenant = Tenant.objects.create(name='Perf FC', slug='perf')
        TenantMembership.objects.create(
            user=self.user, tenant=self.tenant, role=TenantMembership.Role.ADMIN_TENANT,
        )

    def _query_count(self, url_name):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse(url_name))
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def test_landing_stays_within_query_budget(self):
        self.assertLess(self._query_count('landing'), 12)

    def test_painel_stays_within_query_budget(self):
        self.client.login(username='perf', password='senha12345')
        self.assertLess(self._query_count('home'), 40)


class SsrfHardeningTests(TestCase):
    """Correções das duas HIGH do security review: SSRF no import de fontes e
    exfiltração de credencial/SSRF via api_base_url de provider."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='SSRF FC', slug='ssrf')

    # --- guard genérico (services/net.py) ---
    def test_ensure_public_http_url_rejects_internal_and_bad_scheme(self):
        from .services.net import UnsafeURLError, ensure_public_http_url

        for bad in [
            'http://127.0.0.1/x',
            'http://10.0.0.5/x',
            'http://192.168.1.10/x',
            'http://169.254.169.254/latest/meta-data/',
            'http://[::1]/x',
            'ftp://8.8.8.8/x',
            'file:///etc/passwd',
        ]:
            with self.assertRaises(UnsafeURLError):
                ensure_public_http_url(bad)
        # IP público literal é aceito
        ensure_public_http_url('https://8.8.8.8/')

    # --- Vuln 2: import de fonte por URL não alcança rede interna ---
    def test_url_import_blocks_loopback(self):
        from .services.ai import import_knowledge_source_from_url

        with self.assertRaises(ValueError):
            import_knowledge_source_from_url(tenant=self.tenant, url='http://127.0.0.1/segredo')

    def test_url_import_blocks_cloud_metadata(self):
        from .services.ai import import_knowledge_source_from_url

        with self.assertRaises(ValueError):
            import_knowledge_source_from_url(
                tenant=self.tenant, url='http://169.254.169.254/latest/meta-data/iam/security-credentials/'
            )

    # --- Vuln 1: allowlist de host do provider ---
    def test_provider_endpoint_rejects_non_allowlisted_host(self):
        from .services.ai import _provider_endpoint

        provider = AIProvider(
            tenant=self.tenant, name='evil', kind=AIProvider.Kind.OPENAI,
            model_name='gpt-4.1-mini', api_base_url='http://attacker.example/v1',
        )
        with self.assertRaises(RuntimeError):
            _provider_endpoint(provider)

    def test_provider_endpoint_allows_official_host(self):
        from .services.ai import _provider_endpoint

        provider = AIProvider(
            tenant=self.tenant, name='ok', kind=AIProvider.Kind.OPENAI,
            model_name='gpt-4.1-mini', api_base_url='',
        )
        base_url, _key, _headers = _provider_endpoint(provider)
        self.assertEqual(base_url, 'https://api.openai.com/v1')

    def test_provider_form_rejects_evil_base_url(self):
        from .forms import AIProviderForm

        form = AIProviderForm(
            data={
                'name': 'x', 'kind': AIProvider.Kind.OPENAI, 'model_name': 'gpt-4.1-mini',
                'api_base_url': 'http://attacker.example/v1', 'active': 'on', 'notes': '',
            },
            tenant=self.tenant,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('api_base_url', form.errors)


class Sprint13ActiveTenantTests(TestCase):
    """Sprint 13.1 — o contexto operacional usa um único tenant explícito."""

    def setUp(self):
        self.user = User.objects.create_user(username='multi-tenant', password='senha12345')
        self.tenant_a = Tenant.objects.create(name='Clube Alfa', slug='clube-alfa')
        self.tenant_b = Tenant.objects.create(name='Clube Beta', slug='clube-beta')
        for tenant in (self.tenant_a, self.tenant_b):
            TenantMembership.objects.create(
                user=self.user,
                tenant=tenant,
                role=TenantMembership.Role.ADMIN_TENANT,
            )
        Club.objects.create(tenant=self.tenant_a, name='Elenco Alfa', slug='elenco-alfa')
        Club.objects.create(tenant=self.tenant_b, name='Elenco Beta', slug='elenco-beta')
        self.client.login(username='multi-tenant', password='senha12345')

    def test_user_switches_active_tenant_and_lists_only_its_data(self):
        response = self.client.post(
            reverse('tenant-select'),
            {'tenant': self.tenant_b.pk, 'next': reverse('club-list')},
        )

        self.assertRedirects(response, reverse('club-list'))
        response = self.client.get(reverse('club-list'))
        self.assertContains(response, 'Elenco Beta')
        self.assertNotContains(response, 'Elenco Alfa')
        self.assertEqual(self.client.session['active_tenant_id'], self.tenant_b.pk)

    def test_user_cannot_select_tenant_without_membership(self):
        tenant_forbidden = Tenant.objects.create(name='Clube Restrito', slug='clube-restrito')

        response = self.client.post(reverse('tenant-select'), {'tenant': tenant_forbidden.pk})

        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(self.client.session.get('active_tenant_id'), tenant_forbidden.pk)

    def test_created_record_belongs_to_active_tenant(self):
        self.client.post(reverse('tenant-select'), {'tenant': self.tenant_b.pk})

        response = self.client.post(reverse('club-create'), {
            'name': 'Novo Beta', 'slug': 'novo-beta', 'registration_code': '',
            'city': 'Florianópolis', 'state': 'SC', 'active': 'on',
        })

        self.assertRedirects(response, reverse('club-list'))
        self.assertTrue(Club.objects.filter(tenant=self.tenant_b, slug='novo-beta').exists())
        self.assertFalse(Club.objects.filter(tenant=self.tenant_a, slug='novo-beta').exists())


class Sprint13NotificationPrivacyTests(TestCase):
    """Sprint 13.2 — mensagens pessoais não vazam entre membros do tenant."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Privacidade FC', slug='privacidade')
        self.user = User.objects.create_user(username='destinatario', password='senha12345')
        self.other = User.objects.create_user(username='colega', password='senha12345')
        for user in (self.user, self.other):
            TenantMembership.objects.create(
                user=user, tenant=self.tenant, role=TenantMembership.Role.GESTOR_CLUBE,
            )
        self.own = Notification.objects.create(
            tenant=self.tenant, recipient=self.user, subject='Mensagem pessoal', body='Somente para mim',
        )
        self.foreign = Notification.objects.create(
            tenant=self.tenant, recipient=self.other, subject='Mensagem alheia', body='Somente para colega',
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='aprovacoes', module_name='Aprovações', enabled=True,
        )
        self.client.login(username='destinatario', password='senha12345')

    def test_non_admin_lists_only_own_notifications(self):
        response = self.client.get(reverse('notification-list'))

        self.assertContains(response, 'Mensagem pessoal')
        self.assertNotContains(response, 'Mensagem alheia')

    def test_non_admin_cannot_mark_another_users_notification_read(self):
        response = self.client.post(reverse('notification-mark-read', args=[self.foreign.pk]))

        self.assertEqual(response.status_code, 404)
        self.foreign.refresh_from_db()
        self.assertNotEqual(self.foreign.status, Notification.Status.READ)
