from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings

from .models import PublicAPICredential, Tenant
from .services.public_api import (
    PublicAPIAuthenticationError,
    PublicAPIRateLimitExceeded,
    authenticate_public_api_request,
)


class PublicAPICredentialTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube API', slug='clube-api')

    def test_emissao_armazena_somente_prefixo_e_hash(self):
        raw_key = self.tenant.rotate_public_api_key()

        credential = PublicAPICredential.objects.get(tenant=self.tenant)
        self.assertTrue(raw_key.startswith(f'sf_pub_{credential.key_prefix}_'))
        self.assertNotIn(raw_key, credential.key_hash)
        self.assertTrue(credential.matches(raw_key))
        self.assertFalse(hasattr(self.tenant, 'public_api_key'))

    def test_rotacao_invalida_a_chave_anterior(self):
        old_key = self.tenant.rotate_public_api_key()
        new_key = self.tenant.rotate_public_api_key()

        credential = PublicAPICredential.objects.get(tenant=self.tenant)
        self.assertNotEqual(old_key, new_key)
        self.assertFalse(credential.matches(old_key))
        self.assertTrue(credential.matches(new_key))

    def test_revogacao_invalida_a_chave(self):
        raw_key = self.tenant.rotate_public_api_key()

        self.tenant.revoke_public_api_key()

        credential = PublicAPICredential.objects.get(tenant=self.tenant)
        self.assertFalse(credential.active)
        self.assertIsNotNone(credential.revoked_at)
        self.assertFalse(credential.matches(raw_key))


class PublicAPIAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(name='Clube API', slug='clube-api')
        self.raw_key = self.tenant.rotate_public_api_key()

    def tearDown(self):
        cache.clear()

    def test_autentica_exclusivamente_pelo_header(self):
        request = self.factory.get('/', HTTP_X_SAAS_FUTEBOL_API_KEY=self.raw_key)
        credential = authenticate_public_api_request(request, self.tenant)
        self.assertEqual(credential.tenant, self.tenant)

        query_request = self.factory.get('/', {'api_key': self.raw_key})
        with self.assertRaises(PublicAPIAuthenticationError):
            authenticate_public_api_request(query_request, self.tenant)

    def test_chave_de_outro_tenant_nao_autentica(self):
        other = Tenant.objects.create(name='Outro clube', slug='outro-clube')
        request = self.factory.get('/', HTTP_X_SAAS_FUTEBOL_API_KEY=self.raw_key)

        with self.assertRaises(PublicAPIAuthenticationError):
            authenticate_public_api_request(request, other)

    @override_settings(PUBLIC_API_RATE_LIMIT=1, PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_chave_invalida_nao_consume_a_cota_da_credencial(self):
        invalid_request = self.factory.get(
            '/', HTTP_X_SAAS_FUTEBOL_API_KEY='sf_pub_prefixo_invalido_segredo',
        )
        with self.assertRaises(PublicAPIAuthenticationError):
            authenticate_public_api_request(invalid_request, self.tenant)

        credential = PublicAPICredential.objects.get(tenant=self.tenant)
        self.assertEqual(credential.rate_request_count, 0)

        valid_request = self.factory.get('/', HTTP_X_SAAS_FUTEBOL_API_KEY=self.raw_key)
        authenticate_public_api_request(valid_request, self.tenant)

    @override_settings(PUBLIC_API_RATE_LIMIT=2, PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_limite_de_requisicoes_bloqueia_excesso(self):
        request = self.factory.get('/', HTTP_X_SAAS_FUTEBOL_API_KEY=self.raw_key)
        authenticate_public_api_request(request, self.tenant)
        authenticate_public_api_request(request, self.tenant)

        with self.assertRaises(PublicAPIRateLimitExceeded) as raised:
            authenticate_public_api_request(request, self.tenant)

        self.assertGreaterEqual(raised.exception.retry_after, 1)


@override_settings(ROOT_URLCONF='futebol.public_api_urls', PUBLIC_API_RATE_LIMIT=30)
class PublicAPIVersioningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.tenant = Tenant.objects.create(name='Clube API', slug='clube-api')
        self.raw_key = self.tenant.rotate_public_api_key()

    def tearDown(self):
        cache.clear()

    def test_v1_expoe_endpoint_versionado_e_rejeita_chave_na_query(self):
        url = f'/api/publica/v1/{self.tenant.slug}/visao-geral/'
        response = self.client.get(url, HTTP_X_SAAS_FUTEBOL_API_KEY=self.raw_key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tenant']['slug'], self.tenant.slug)

        query_response = self.client.get(url, {'api_key': self.raw_key})
        self.assertEqual(query_response.status_code, 403)

    @override_settings(PUBLIC_API_RATE_LIMIT=1, PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_v1_responde_429_com_retry_after(self):
        url = f'/api/publica/v1/{self.tenant.slug}/partidas/'
        first = self.client.get(url, HTTP_X_SAAS_FUTEBOL_API_KEY=self.raw_key)
        second = self.client.get(url, HTTP_X_SAAS_FUTEBOL_API_KEY=self.raw_key)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn('Retry-After', second)
