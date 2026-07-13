from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ValidationError
from django.test import TestCase

from futebol.models import Tenant, TenantMembership
from futebol.services.sports_data_providers import (
    sync_football_data_org,
    sync_skillcorner_open,
    sync_statsbomb_open,
)


class LegacySportsSyncCommandTests(TestCase):
    def test_servicos_publicos_por_tenant_tambem_estao_bloqueados(self):
        calls = (
            lambda: sync_football_data_org(
                tenant=None, imported_by=None, api_key='x', competition_code='BSA',
            ),
            lambda: sync_statsbomb_open(
                tenant=None, imported_by=None, competition_id='43', season_id='106',
            ),
            lambda: sync_skillcorner_open(
                tenant=None, imported_by=None, max_matches=1,
            ),
        )
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaisesMessage(ValidationError, 'desativada'):
                    call()

    def test_recusa_provider_publico_sem_exigir_tenant_ou_usuario(self):
        for provider in ('football-data-org', 'statsbomb-open', 'skillcorner-open'):
            with self.subTest(provider=provider):
                with self.assertRaisesMessage(
                    CommandError, 'sync_platform_sports_provider',
                ):
                    call_command(
                        'sync_sports_provider',
                        provider=provider,
                        stderr=StringIO(),
                    )

    @patch(
        'futebol.management.commands.sync_sports_provider.'
        'sync_skillcorner_tracking'
    )
    def test_preserva_importacao_privada_de_tracking(self, sync_tracking):
        tenant = Tenant.objects.create(name='Clube Privado', slug='clube-privado')
        user = get_user_model().objects.create_user('analista', password='x')
        TenantMembership.objects.create(
            tenant=tenant,
            user=user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        sync_tracking.return_value = SimpleNamespace(
            pk=17,
            record_count=0,
            source=SimpleNamespace(name='SkillCorner Open Data'),
        )

        call_command(
            'sync_sports_provider',
            provider='skillcorner-tracking',
            tenant=tenant.slug,
            user=user.username,
            tracking_match_id='2017461',
            stdout=StringIO(),
        )

        sync_tracking.assert_called_once_with(
            tenant=tenant,
            imported_by=user,
            match_id='2017461',
        )

    def test_tracking_privado_exige_escopo_do_tenant(self):
        with self.assertRaisesMessage(CommandError, '--tenant e --user'):
            call_command(
                'sync_sports_provider',
                provider='skillcorner-tracking',
                tracking_match_id='2017461',
                stderr=StringIO(),
            )
