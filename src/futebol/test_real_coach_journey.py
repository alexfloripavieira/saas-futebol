from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from futebol.models import (
    AthleteSportProfile, Club, Competition, Contract, GlobalSportsDataBatch,
    GlobalSportsDataRecord, GlobalSportsDataSource,
    Match, MatchDossier, Person, SportsDataImportBatch, SportsDataRecord, SportsDataSource,
    Tenant, TenantMembership, TenantModuleSubscription,
)
from futebol.services.real_coach_journey import prepare_real_coach_journey, public_squad_players
from futebol.services.sports_catalog import capability_entitlement_code


User = get_user_model()


class RealCoachJourneyTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Avaí Futebol Clube', slug='avai')
        self.user = User.objects.create_user('gestor-avai')
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='ia', module_name='IA', enabled=True,
        )
        self.source = GlobalSportsDataSource.objects.create(
            code='football-data-org', name='football-data.org',
            kind=GlobalSportsDataSource.Kind.FOOTBALL_DATA_ORG,
            capabilities=['fixtures_results', 'team_squad'],
            license_id='provider-terms', attribution='football-data.org',
            quality='production_basic', active=True,
            operational_status=GlobalSportsDataSource.OperationalStatus.ACTIVE,
            last_checked_at=timezone.now(), last_success_at=timezone.now(),
        )
        self.batch = GlobalSportsDataBatch.objects.create(
            source=self.source, dataset_id='competition-bsa', dataset_version='2026',
            content_hash='a' * 64, status=GlobalSportsDataBatch.Status.COMPLETED,
            record_count=2, manifest={'provider': 'football-data.org'},
            license_id=self.source.license_id, attribution=self.source.attribution,
            quality=self.source.quality, published_at=timezone.now(),
        )
        self.fixture = GlobalSportsDataRecord.objects.create(
            source=self.source, batch=self.batch, capability='fixtures_results',
            provider_record_id='match:real-101', observed_at=timezone.now(),
            ingested_at=timezone.now(), expires_at=timezone.now() + timedelta(hours=24),
            content_hash='b' * 64,
            payload={
                'provider_match_id': 'real-101',
                'scheduled_at': (timezone.now() + timedelta(days=5)).isoformat(),
                'status': 'TIMED', 'competition_code': 'BSA',
                'home_team_id': '4241', 'home_team': 'Coritiba FBC',
                'away_team_id': '1769', 'away_team': 'SE Palmeiras',
                'score': {'home': None, 'away': None},
            },
        )

    def test_preparacao_materializa_partida_real_de_forma_idempotente(self):
        first = prepare_real_coach_journey(tenant=self.tenant, actor=self.user)
        second = prepare_real_coach_journey(tenant=self.tenant, actor=self.user)

        self.assertEqual(first.match.pk, second.match.pk)
        self.assertEqual(first.match.reference_code, 'FD-real-101')
        self.assertEqual(Match.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(first.status, 'elenco_real_necessario')
        self.assertEqual(first.eligible_players, 0)

    def test_limpeza_remove_so_derivados_com_marcador_sintetico_explicito(self):
        real = prepare_real_coach_journey(tenant=self.tenant, actor=self.user)
        real_dossier = MatchDossier.objects.create(
            tenant=self.tenant, match=real.match, analyzed_club=real.club,
            generated_by=self.user, data_snapshot={'external_sources': []},
        )
        demo_club = Club.objects.create(
            tenant=self.tenant, name='Clube marcado', slug='clube-marcado',
        )
        demo_match = Match.objects.create(
            tenant=self.tenant, phase=real.match.phase, home_club=demo_club,
            away_club=real.club, reference_code='DEM-2026-COACH-001',
            scheduled_at=timezone.now() + timedelta(days=2), status=Match.Status.CONFIRMED,
        )
        demo_dossier = MatchDossier.objects.create(
            tenant=self.tenant, match=demo_match, analyzed_club=demo_club,
            generated_by=self.user, data_snapshot={'external_sources': []},
        )
        private_source = SportsDataSource.objects.create(
            tenant=self.tenant, code='gps-avai', name='GPS Avaí',
            kind=SportsDataSource.Kind.CLUB_INTERNAL, capabilities=['gps'],
            license_id='private', attribution='Avaí', quality='internal',
        )

        result = prepare_real_coach_journey(
            tenant=self.tenant, actor=self.user, cleanup_synthetic=True,
        )

        self.assertFalse(MatchDossier.objects.filter(pk=demo_dossier.pk).exists())
        self.assertTrue(MatchDossier.objects.filter(pk=real_dossier.pk).exists())
        self.assertTrue(SportsDataSource.objects.filter(pk=private_source.pk).exists())
        self.assertFalse(Match.objects.filter(pk=demo_match.pk).exists())
        self.assertEqual(result.removed_dossiers, 1)

    def test_limpeza_confirmada_remove_footprint_exato_do_seed_e_preserva_real(self):
        seeded_club = Club.objects.create(
            tenant=self.tenant, name='Aurora FC', slug='aurora-fc',
            registration_code='AUR-001',
        )
        seeded_person = Person.objects.create(
            tenant=self.tenant, full_name='João Atacante', kind=Person.Kind.ATHLETE,
        )
        AthleteSportProfile.objects.create(
            tenant=self.tenant, player=seeded_person, primary_position='ATA',
            tactical_roles=['função-base do elenco demo'],
        )
        Contract.objects.create(
            tenant=self.tenant, club=seeded_club, person=seeded_person,
            start_date=timezone.localdate(), status=Contract.Status.ACTIVE,
        )
        seeded_competition = Competition.objects.create(
            tenant=self.tenant, name='Copa Demo Local', slug='copa-demo-local',
        )
        real_club = Club.objects.create(
            tenant=self.tenant, name='Avaí real', slug='avai-real',
            registration_code='AVA-REAL',
        )
        real_person = Person.objects.create(
            tenant=self.tenant, full_name='Atleta real', kind=Person.Kind.ATHLETE,
        )

        prepare_real_coach_journey(
            tenant=self.tenant, actor=self.user, cleanup_synthetic=True,
        )

        self.assertFalse(Club.objects.filter(pk=seeded_club.pk).exists())
        self.assertFalse(Person.objects.filter(pk=seeded_person.pk).exists())
        self.assertFalse(Competition.objects.filter(pk=seeded_competition.pk).exists())
        self.assertTrue(Club.objects.filter(pk=real_club.pk).exists())
        self.assertTrue(Person.objects.filter(pk=real_person.pk).exists())

    def test_comando_informa_url_e_bloqueio_sem_fabricar_elenco(self):
        output = StringIO()

        call_command('prepare_real_coach_journey', tenant='avai', user='gestor-avai', stdout=output)

        text = output.getvalue()
        self.assertIn('/ia/treinador/?club=', text)
        self.assertIn('elenco privado real', text)

    def test_central_guia_decisoes_da_proxima_partida(self):
        result = prepare_real_coach_journey(tenant=self.tenant, actor=self.user)
        self.client.force_login(self.user)

        response = self.client.get(reverse('intelligent-coach-center'), {'club': result.club.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sala da Próxima Partida')
        self.assertContains(response, 'A IA responde estas perguntas para você')
        self.assertContains(response, 'Quem deve começar e por quê?')
        self.assertContains(response, 'Como o adversário tende a jogar?')
        self.assertContains(response, 'O que treinar até a partida?')
        self.assertContains(response, 'configure pelo menos 11 atletas')

    def test_ensaio_com_elenco_publico_nao_cria_dado_privado(self):
        for index in range(11):
            GlobalSportsDataRecord.objects.create(
                source=self.source, batch=self.batch, capability='player_profile',
                provider_record_id=f'player:{index + 1}', observed_at=timezone.now(),
                ingested_at=timezone.now(), expires_at=timezone.now() + timedelta(hours=24),
                content_hash=f'{index + 10:064x}',
                payload={
                    'provider_player_id': str(index + 1),
                    'provider_team_id': '4241', 'team': 'Coritiba FBC',
                    'name': f'Atleta público {index + 1}', 'position': 'Defence',
                },
            )
        result = prepare_real_coach_journey(tenant=self.tenant, actor=self.user)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('intelligent-coach-public-rehearsal', args=[result.match.pk]),
            {'club': result.club.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ensaio com elenco público não confirmado')
        self.assertContains(response, 'Não é uma escalação operacional')
        self.assertContains(response, 'Plano equilibrado')
        self.assertContains(response, 'Prancheta de ensaio')
        self.assertEqual(Person.objects.filter(tenant=self.tenant).count(), 0)
        self.assertEqual(Contract.objects.filter(tenant=self.tenant).count(), 0)
        self.assertEqual(MatchDossier.objects.filter(tenant=self.tenant).count(), 0)

    def test_entitlement_granular_oculta_elenco_publico_nao_contratado(self):
        TenantModuleSubscription.objects.create(
            tenant=self.tenant,
            module_code=capability_entitlement_code('fixtures_results'),
            module_name='Partidas', enabled=True,
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant,
            module_code=capability_entitlement_code('player_profile'),
            module_name='Elencos', enabled=False,
        )
        GlobalSportsDataRecord.objects.create(
            source=self.source, batch=self.batch, capability='player_profile',
            provider_record_id='player:oculto', observed_at=timezone.now(),
            ingested_at=timezone.now(), content_hash='f' * 64,
            payload={
                'provider_player_id': 'oculto', 'provider_team_id': '4241',
                'name': 'Atleta não contratado',
            },
        )
        result = prepare_real_coach_journey(tenant=self.tenant, actor=self.user)

        self.assertEqual(
            public_squad_players(tenant=self.tenant, club=result.match.home_club), []
        )

    def test_ensaio_sem_onze_nomes_publicados_retorna_ao_treinador(self):
        result = prepare_real_coach_journey(tenant=self.tenant, actor=self.user)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('intelligent-coach-public-rehearsal', args=[result.match.pk]),
            {'club': result.club.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('intelligent-coach-center'), response.url)

    def test_auditor_nao_pode_executar_preparacao_destrutiva(self):
        auditor = User.objects.create_user('auditor-avai')
        TenantMembership.objects.create(
            tenant=self.tenant, user=auditor, role=TenantMembership.Role.AUDITOR,
        )

        with self.assertRaisesMessage(ValidationError, 'não pode preparar'):
            prepare_real_coach_journey(
                tenant=self.tenant, actor=auditor, cleanup_synthetic=True,
            )
