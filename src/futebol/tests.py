from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    ApprovalFlow,
    ApprovalRequest,
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    CompetitionRuleSet,
    Match,
    Notification,
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
            target_model='futebol.Match',
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
            target_model='futebol.Match',
            target_object_id='123',
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
        self.assertContains(approval_request_response, 'pending')

        notification_response = self.client.get(reverse('notification-list'))
        self.assertEqual(notification_response.status_code, 200)
        self.assertContains(notification_response, 'Teste de notificação')

        approve_response = self.client.post(reverse('approval-request-approve', args=[approval_request.pk]))
        self.assertEqual(approve_response.status_code, 302)
        approval_request.refresh_from_db()
        self.assertEqual(approval_request.status, ApprovalRequest.Status.APPROVED)
        self.assertIsNotNone(approval_request.decided_at)

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
            target_model='futebol.Match',
            target_object_id='123',
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
            target_model='futebol.Match',
            target_object_id='123',
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
