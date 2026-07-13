from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from futebol.models import (
    AthleteSportProfile,
    Club,
    Contract,
    GlobalSportsDataBatch,
    GlobalSportsDataRecord,
    GlobalSportsDataSource,
    Match,
    MatchDossier,
    Person,
    SportsDataRecord,
    SportsDataImportBatch,
    SportsDataSource,
    Tenant,
    TenantMembership,
    TenantModuleSubscription,
)
from futebol.services.coach_workspace import materialize_provider_match
from futebol.services.intelligent_coach import generate_match_dossier


User = get_user_model()


class ProviderMatchMaterializationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube acadêmico', slug='clube-academico')
        self.source = SportsDataSource.objects.create(
            tenant=self.tenant,
            code='football-data-org',
            name='football-data.org',
            kind=SportsDataSource.Kind.FOOTBALL_DATA_ORG,
            quality='production_basic',
            license_id='football-data-org-terms',
            attribution='Dados fornecidos por football-data.org.',
            capabilities=['fixtures_results', 'standings_form'],
        )
        imported_by = User.objects.create_user('importador-provider')
        batch = SportsDataImportBatch.objects.create(
            tenant=self.tenant,
            source=self.source,
            dataset_id='competition-bsa',
            dataset_version='2026-07-13',
            content_hash='a' * 64,
            status=SportsDataImportBatch.Status.COMPLETED,
            record_count=1,
            manifest={'provider': 'football-data.org'},
            license_id=self.source.license_id,
            attribution=self.source.attribution,
            quality=self.source.quality,
            imported_by=imported_by,
            imported_at=timezone.now(),
        )
        self.record = SportsDataRecord.objects.create(
            tenant=self.tenant,
            source=self.source,
            batch=batch,
            capability='fixtures_results',
            provider_record_id='match:554924',
            observed_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=2),
            content_hash='b' * 64,
            payload={
                'provider_match_id': '554924',
                'scheduled_at': (timezone.now() + timedelta(days=7)).isoformat(),
                'status': 'TIMED',
                'home_team_id': '4241',
                'home_team': 'Coritiba FBC',
                'away_team_id': '1769',
                'away_team': 'SE Palmeiras',
                'score': {'home': None, 'away': None},
            },
        )

    def test_materializa_partida_real_de_forma_idempotente(self):
        first = materialize_provider_match(record=self.record)
        competition = first.phase.edition.competition
        competition.name = 'Campeonato Brasileiro — dados oficiais do provider'
        competition.save(update_fields=['name', 'updated_at'])
        second = materialize_provider_match(record=self.record)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Match.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(
            set(Club.objects.filter(tenant=self.tenant).values_list('registration_code', flat=True)),
            {'football-data:4241', 'football-data:1769'},
        )
        self.assertEqual(first.reference_code, 'FD-554924')
        self.assertIn('football-data.org', first.notes)
        competition.refresh_from_db()
        self.assertEqual(
            competition.name, 'Campeonato Brasileiro — dados básicos do provider'
        )


class CoachWorkspaceHTTPTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube Inteligente', slug='clube-inteligente')
        self.user = User.objects.create_user('gestor-workspace', password='senha12345')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='ia', module_name='IA', enabled=True,
        )
        self.our_club = Club.objects.create(
            tenant=self.tenant, name='Nosso FC', slug='nosso-fc',
        )
        self.opponent = Club.objects.create(
            tenant=self.tenant, name='Adversário FC', slug='adversario-fc',
        )

        player = Person.objects.create(
            tenant=self.tenant, full_name='Atleta cadastrado', kind=Person.Kind.ATHLETE,
        )
        Contract.objects.create(
            tenant=self.tenant,
            person=player,
            club=self.our_club,
            start_date=timezone.localdate() - timedelta(days=10),
            status=Contract.Status.ACTIVE,
        )
        from futebol.models import Competition, CompetitionEdition, CompetitionPhase
        competition = Competition.objects.create(
            tenant=self.tenant, name='Liga', slug='liga',
        )
        edition = CompetitionEdition.objects.create(
            tenant=self.tenant, competition=competition, slug='2026',
            name='Temporada 2026', season_year=2026,
        )
        phase = CompetitionPhase.objects.create(
            tenant=self.tenant, edition=edition, code='unica', name='Fase única', order=1,
        )
        self.match = Match.objects.create(
            tenant=self.tenant,
            phase=phase,
            home_club=self.our_club,
            away_club=self.opponent,
            reference_code='WORKSPACE-001',
            scheduled_at=timezone.now() + timedelta(days=7),
            status=Match.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

    def test_menu_destaca_treinador_inteligente_como_acesso_primario(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="coach-primary-shortcut"')
        self.assertContains(response, reverse('intelligent-coach-center'))

    def test_central_explica_dados_motor_e_proximo_passo_do_time(self):
        response = self.client.get(
            reverse('intelligent-coach-center'), {'club': self.our_club.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preparação de Partida')
        self.assertContains(response, 'Nosso FC contra Adversário FC')
        self.assertContains(response, '1 atleta elegível')
        self.assertContains(response, 'Motor de regras')
        self.assertContains(response, 'Provider não acionado')
        self.assertContains(response, 'Completar elenco de Nosso FC')
        self.assertNotContains(response, 'Analisar Adversário FC')

    def test_servico_bloqueia_dossie_com_menos_de_onze_elegiveis(self):
        with self.assertRaisesMessage(ValidationError, 'pelo menos 11 atletas elegíveis'):
            generate_match_dossier(
                match=self.match, club=self.our_club, requested_by=self.user,
            )

    def test_limpeza_de_demo_preserva_dossie_de_partida_real(self):
        dossier = MatchDossier.objects.create(
            tenant=self.tenant,
            match=self.match,
            analyzed_club=self.our_club,
            data_snapshot={'external_sources': []},
            generated_by=self.user,
        )

        call_command(
            'purge_demo_data',
            tenant=self.tenant.slug,
            confirm=True,
            stdout=StringIO(),
        )

        self.assertTrue(MatchDossier.objects.filter(pk=dossier.pk).exists())

    def test_treinador_combina_base_global_com_elenco_privado_do_tenant(self):
        registered_player = Person.objects.get(
            tenant=self.tenant, full_name='Atleta cadastrado',
        )
        AthleteSportProfile.objects.create(
            tenant=self.tenant, player=registered_player, primary_position='GOL',
        )
        positions = ['LD', 'ZAG', 'ZAG', 'LE', 'VOL', 'MC', 'MEI', 'PD', 'PE', 'ATA']
        for index, position in enumerate(positions):
            player = Person.objects.create(
                tenant=self.tenant,
                full_name=f'Atleta privado {index + 2}',
                kind=Person.Kind.ATHLETE,
            )
            Contract.objects.create(
                tenant=self.tenant,
                person=player,
                club=self.our_club,
                start_date=timezone.localdate() - timedelta(days=10),
                status=Contract.Status.ACTIVE,
            )
            AthleteSportProfile.objects.create(
                tenant=self.tenant, player=player, primary_position=position,
            )
        source = GlobalSportsDataSource.objects.create(
            code='football-data-org',
            name='football-data.org',
            kind=GlobalSportsDataSource.Kind.FOOTBALL_DATA_ORG,
            capabilities=['fixtures_results'],
            license_id='provider-terms',
            attribution='Dados globais da plataforma.',
            quality='production_basic',
            active=True,
            operational_status=GlobalSportsDataSource.OperationalStatus.ACTIVE,
            last_checked_at=timezone.now(),
            last_success_at=timezone.now(),
        )
        batch = GlobalSportsDataBatch.objects.create(
            source=source,
            dataset_id='competition-bsa',
            dataset_version='2026-07-13',
            content_hash='a' * 64,
            status=GlobalSportsDataBatch.Status.COMPLETED,
            record_count=1,
            manifest={'provider': 'football-data.org'},
            license_id=source.license_id,
            attribution=source.attribution,
            quality=source.quality,
            published_at=timezone.now(),
        )
        GlobalSportsDataRecord.objects.create(
            source=source,
            batch=batch,
            capability='fixtures_results',
            provider_record_id='match:global-1',
            observed_at=timezone.now(),
            ingested_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            payload={
                'home_team': self.our_club.name,
                'away_team': self.opponent.name,
            },
            content_hash='b' * 64,
        )

        dossier = generate_match_dossier(
            match=self.match, club=self.our_club, requested_by=self.user,
        )

        self.assertEqual(dossier.tenant, self.tenant)
        self.assertEqual(
            dossier.data_snapshot['external_sources'][0]['code'],
            'football-data-org',
        )
