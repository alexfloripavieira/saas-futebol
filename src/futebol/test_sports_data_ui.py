from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from futebol.models import (
    GlobalSportsDataBatch,
    GlobalSportsDataSource,
    SportsDataSource,
    Tenant,
    TenantMembership,
    TenantModuleSubscription,
)


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
            tenant=self.tenant, module_code='ia', module_name='IA', enabled=True
        )
        self.source = GlobalSportsDataSource.objects.create(
            code='football-data-org',
            name='football-data.org',
            kind=GlobalSportsDataSource.Kind.FOOTBALL_DATA_ORG,
            capabilities=['fixtures_results', 'standings_form'],
            license_id='provider-terms',
            attribution='Dados fornecidos por football-data.org',
            quality='external',
        )
        self.client.force_login(self.user)

    def test_centro_lista_base_global_e_nao_expoe_fonte_privada_alheia(self):
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
        self.assertContains(response, 'Treinador Inteligente')
        self.assertNotContains(response, 'Atualizar agora')

    def test_detalhe_global_inexistente_retorna_404(self):
        response = self.client.get(reverse('sports-data-source-detail', args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_modulo_ia_desabilitado_bloqueia_centro(self):
        TenantModuleSubscription.objects.filter(tenant=self.tenant, module_code='ia').update(
            enabled=False
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant,
            module_code='integracoes',
            module_name='Integrações',
            enabled=True,
        )

        response = self.client.get(reverse('sports-data-source-list'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Módulo não contratado', status_code=403)

    def test_usuario_anonimo_e_redirecionado_para_login(self):
        self.client.logout()

        response = self.client.get(reverse('sports-data-source-list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_centro_exibe_estado_verificavel_da_sincronizacao(self):
        response = self.client.get(reverse('sports-data-source-list'))

        self.assertContains(response, 'Atualização da plataforma')
        self.assertContains(response, 'Operada continuamente pela SaaS')
        self.assertNotContains(response, 'Sincronizar agora')

    def test_centro_exibe_publicacao_da_ultima_versao_global(self):
        GlobalSportsDataBatch.objects.create(
            source=self.source,
            dataset_id='competition-bsa',
            dataset_version='2026-07-13',
            content_hash='a' * 64,
            status=GlobalSportsDataBatch.Status.COMPLETED,
            record_count=0,
            manifest={'provider': 'football-data.org'},
            license_id=self.source.license_id,
            attribution=self.source.attribution,
            quality=self.source.quality,
            published_at=datetime(2026, 7, 13, 18, 30, tzinfo=timezone.utc),
        )

        response = self.client.get(reverse('sports-data-source-list'))

        self.assertContains(response, 'Última atualização')
        self.assertContains(response, '13/07/2026 15:30')
        self.assertNotContains(response, 'Em processamento')
