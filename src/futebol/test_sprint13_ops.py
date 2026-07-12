import importlib
import os
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Club, Evidence, Tenant, TenantMembership
from .services.evidence_files import user_can_download_evidence


class EvidenceFileTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media_dir.cleanup)
        self.user = get_user_model().objects.create_user('operador', password='senha-forte')
        self.outsider = get_user_model().objects.create_user('externo', password='senha-forte')
        self.tenant = Tenant.objects.create(name='Tenant A', slug='tenant-a')
        self.club = Club.objects.create(tenant=self.tenant, name='Clube A', slug='clube-a')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        self.other_tenant = Tenant.objects.create(name='Tenant B', slug='tenant-b')
        TenantMembership.objects.create(
            tenant=self.other_tenant,
            user=self.outsider,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )

    def evidence(self, uploaded_file):
        return Evidence(
            tenant=self.tenant,
            content_type=ContentType.objects.get_for_model(Club),
            object_id=str(self.club.pk),
            file=uploaded_file,
            uploaded_by=self.user,
        )

    def test_accepts_valid_pdf_and_persists_it_under_tenant_directory(self):
        evidence = self.evidence(
            SimpleUploadedFile('contrato.pdf', b'%PDF-1.7\nconteudo', content_type='application/pdf')
        )
        evidence.save()

        self.assertTrue(evidence.file.name.startswith(f'evidencias/{self.tenant.pk}/'))
        self.assertNotIn('contrato', evidence.file.name)
        self.assertTrue(Path(evidence.file.path).exists())
        evidence.refresh_from_db()
        with evidence.file.open('rb') as persisted:
            self.assertTrue(persisted.read().startswith(b'%PDF-'))

    @override_settings(EVIDENCE_MAX_UPLOAD_SIZE=8)
    def test_rejects_file_above_configured_limit(self):
        evidence = self.evidence(
            SimpleUploadedFile('grande.pdf', b'%PDF-123456', content_type='application/pdf')
        )
        with self.assertRaisesMessage(ValidationError, 'deve ter no máximo'):
            evidence.full_clean()

    def test_rejects_disguised_or_unsupported_file(self):
        disguised = self.evidence(
            SimpleUploadedFile('ata.pdf', b'executavel', content_type='application/pdf')
        )
        with self.assertRaisesMessage(ValidationError, 'não corresponde à extensão'):
            disguised.full_clean()

        unsupported = self.evidence(
            SimpleUploadedFile('script.exe', b'MZ payload', content_type='application/octet-stream')
        )
        with self.assertRaisesMessage(ValidationError, 'Tipo de arquivo não permitido'):
            unsupported.full_clean()

    def test_rejects_empty_evidence(self):
        with self.assertRaisesMessage(ValidationError, 'Informe um arquivo, uma URL ou uma observação'):
            self.evidence(None).full_clean()

    def test_download_policy_is_isolated_by_tenant(self):
        evidence = self.evidence(None)
        self.assertTrue(user_can_download_evidence(self.user, evidence))
        self.assertFalse(user_can_download_evidence(self.outsider, evidence))
        self.assertFalse(user_can_download_evidence(None, evidence))

    def test_private_download_route_enforces_active_tenant(self):
        evidence = self.evidence(
            SimpleUploadedFile('contrato.pdf', b'%PDF-1.7\nconteudo', content_type='application/pdf')
        )
        evidence.save()
        self.client.force_login(self.user)
        allowed = self.client.get(reverse('evidence-download', args=[evidence.pk]))
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.streaming)

        self.client.force_login(self.outsider)
        denied = self.client.get(reverse('evidence-download', args=[evidence.pk]))
        self.assertEqual(denied.status_code, 404)


class ProductionSettingsTests(TestCase):
    def test_production_defaults_enable_https_controls(self):
        environment = {
            'DJANGO_SECRET_KEY': 'segredo-de-producao-com-tamanho-adequado',
            'DJANGO_SECURE_SSL_REDIRECT': '1',
        }
        with mock.patch.dict(os.environ, environment, clear=False):
            module = importlib.import_module('config.settings_production')
            module = importlib.reload(module)

        self.assertFalse(module.DEBUG)
        self.assertTrue(module.SECURE_SSL_REDIRECT)
        self.assertTrue(module.SESSION_COOKIE_SECURE)
        self.assertTrue(module.CSRF_COOKIE_SECURE)
        self.assertEqual(module.SECURE_HSTS_SECONDS, 31536000)
        self.assertEqual(module.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'))
