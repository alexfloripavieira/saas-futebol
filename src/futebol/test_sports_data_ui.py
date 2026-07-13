from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from futebol.models import SportsDataSource, Tenant, TenantMembership, TenantModuleSubscription


User = get_user_model()


class SportsDataSourceUITests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube dos Dados', slug='clube-dos-dados')
        self.user = User.objects.create_user('gestor-dados', password='senha12345')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='integracoes', module_name='Integrações', enabled=True
        )
        self.source = SportsDataSource.objects.create(
            tenant=self.tenant,
            code='football-data-org',
            name='football-data.org',
            kind=SportsDataSource.Kind.FOOTBALL_DATA_ORG,
            capabilities=['fixtures_results', 'standings_form'],
            license_id='provider-terms',
            attribution='Dados fornecidos por football-data.org',
            quality='external',
        )
        self.client.force_login(self.user)

    def test_centro_lista_somente_fontes_do_tenant_ativo(self):
        other_tenant = Tenant.objects.create(name='Outro clube', slug='outro-clube')
        SportsDataSource.objects.create(
            tenant=other_tenant,
            code='fonte-secreta',
            name='Fonte secreta',
            kind=SportsDataSource.Kind.CLUB_INTERNAL,
            capabilities=['fixtures_results'],
            license_id='interno',
            attribution='Outro clube',
            quality='internal',
        )

        response = self.client.get(reverse('sports-data-source-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'football-data.org')
        self.assertNotContains(response, 'Fonte secreta')

    def test_detalhe_de_fonte_de_outro_tenant_retorna_404(self):
        other_tenant = Tenant.objects.create(name='Outro clube', slug='outro-clube')
        other_source = SportsDataSource.objects.create(
            tenant=other_tenant,
            code='outra',
            name='Outra fonte',
            kind=SportsDataSource.Kind.CLUB_INTERNAL,
            capabilities=['fixtures_results'],
            license_id='interno',
            attribution='Outro clube',
            quality='internal',
        )

        response = self.client.get(reverse('sports-data-source-detail', args=[other_source.pk]))

        self.assertEqual(response.status_code, 404)

    def test_modulo_integracoes_desabilitado_bloqueia_centro(self):
        TenantModuleSubscription.objects.filter(tenant=self.tenant, module_code='integracoes').update(
            enabled=False
        )

        response = self.client.get(reverse('sports-data-source-list'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Módulo não contratado', status_code=403)

    def test_usuario_anonimo_e_redirecionado_para_login(self):
        self.client.logout()

        response = self.client.get(reverse('sports-data-source-list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_sincronizacao_recorrente_respeita_modulo_automacoes(self):
        output = StringIO()

        call_command(
            'sync_sports_provider',
            tenant=self.tenant.slug,
            provider='football-data-org',
            user=self.user.username,
            scheduled=True,
            stdout=output,
        )

        self.assertIn('módulo Automações desativado', output.getvalue())

    def test_centro_exibe_estado_verificavel_da_sincronizacao(self):
        response = self.client.get(reverse('sports-data-source-list'))

        self.assertContains(response, 'Sincronização')
        self.assertContains(response, 'Controlada')
        self.assertContains(response, 'Última checagem confirmada')
        self.assertNotContains(response, 'próxima prevista')
