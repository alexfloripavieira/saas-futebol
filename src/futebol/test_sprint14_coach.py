from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from futebol.models import (
    AthleteMatchAvailability,
    AthleteSportProfile,
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    Contract,
    GamePlan,
    GamePlanPlayer,
    LineupDraft,
    LineupDraftPlayer,
    Match,
    MatchDossier,
    MatchLineup,
    Person,
    SportsDataRecord,
    SpecialistOpinion,
    Tenant,
    TenantMembership,
    TenantModuleSubscription,
)
from futebol.services.intelligent_coach import (
    apply_game_plan_as_draft,
    generate_match_dossier,
    review_lineup_draft,
)
from futebol.services.sports_data import import_local_sports_dataset


User = get_user_model()


class IntelligentCoachModelRulesTests(TestCase):
    def test_modo_de_execucao_expoe_opcoes_controladas(self):
        field = SpecialistOpinion._meta.get_field('execution_mode')

        self.assertEqual(
            dict(field.choices),
            {
                'deterministic': 'Determinístico',
                'provider': 'Provedor de IA',
                'fallback': 'Fallback determinístico',
            },
        )

    def test_opiniao_especialista_inicia_com_evidencias_vazias(self):
        opinion = SpecialistOpinion()

        self.assertEqual(opinion.evidence, [])


class IntelligentCoachServiceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube Inteligente', slug='clube-inteligente')
        self.user = User.objects.create_user('treinador-inteligente', password='senha12345')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        self.our_club = Club.objects.create(tenant=self.tenant, name='Nosso FC', slug='nosso-fc')
        self.opponent = Club.objects.create(tenant=self.tenant, name='Adversário FC', slug='adversario-fc')
        competition = Competition.objects.create(
            tenant=self.tenant, name='Liga Inteligente', slug='liga-inteligente'
        )
        edition = CompetitionEdition.objects.create(
            tenant=self.tenant,
            competition=competition,
            slug='2026',
            name='Temporada 2026',
            season_year=2026,
        )
        phase = CompetitionPhase.objects.create(
            tenant=self.tenant, edition=edition, code='unica', name='Fase única', order=1
        )
        self.match = Match.objects.create(
            tenant=self.tenant,
            phase=phase,
            home_club=self.our_club,
            away_club=self.opponent,
            reference_code='COACH-001',
            scheduled_at=timezone.now() + timedelta(days=7),
        )
        self.players = []
        positions = ['GOL', 'LD', 'ZAG', 'ZAG', 'LE', 'VOL', 'MC', 'MEI', 'PD', 'PE', 'ATA', 'ATA']
        for index, position in enumerate(positions, start=1):
            player = Person.objects.create(
                tenant=self.tenant,
                full_name=f'Atleta {index:02d}',
                kind=Person.Kind.ATHLETE,
            )
            Contract.objects.create(
                tenant=self.tenant,
                person=player,
                club=self.our_club,
                start_date=timezone.localdate() - timedelta(days=30),
                status=Contract.Status.ACTIVE,
            )
            AthleteSportProfile.objects.create(
                tenant=self.tenant,
                player=player,
                primary_position=position,
                tactical_roles=['titular potencial'],
            )
            self.players.append(player)
        AthleteMatchAvailability.objects.create(
            tenant=self.tenant,
            match=self.match,
            player=self.players[-1],
            club=self.our_club,
            status=AthleteMatchAvailability.Status.UNAVAILABLE,
            note='Restrição registrada pela comissão.',
        )

    def _create_plan(self):
        dossier = MatchDossier.objects.create(
            tenant=self.tenant,
            match=self.match,
            analyzed_club=self.our_club,
            generated_by=self.user,
            data_snapshot={'origem': 'teste'},
        )
        return GamePlan.objects.create(
            tenant=self.tenant,
            dossier=dossier,
            variant=GamePlan.Variant.BALANCED,
            formation='4-3-3',
            summary='Plano para teste das regras de elegibilidade.',
            attacking_plan=['Comportamento ofensivo de teste.'],
            defensive_plan=['Comportamento defensivo de teste.'],
            transitions=['Transição de teste.'],
            set_pieces=['Bola parada de teste.'],
        )

    def _create_draft(self):
        plan = self._create_plan()
        return LineupDraft.objects.create(
            tenant=self.tenant,
            plan=plan,
            match=self.match,
            club=self.our_club,
            created_by=self.user,
        )

    def test_gera_dossie_com_tres_planos_e_exclui_indisponivel(self):
        import_local_sports_dataset(
            tenant=self.tenant,
            dataset_slug='demo-treinador-sintetico-v1',
            imported_by=self.user,
            root=Path(__file__).resolve().parent / 'data' / 'sports',
        )
        external_record = SportsDataRecord.objects.get(
            tenant=self.tenant,
            capability='standings_form',
            provider_record_id='demo-form-ilha-azul',
        )
        external_record.payload = {
            **external_record.payload,
            'team': self.our_club.name,
            'recent_points': [3, 1, 3],
        }
        external_record.save()
        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        self.assertIsInstance(dossier, MatchDossier)
        self.assertEqual(
            set(dossier.plans.values_list('variant', flat=True)),
            {GamePlan.Variant.BALANCED, GamePlan.Variant.OFFENSIVE, GamePlan.Variant.CONSERVATIVE},
        )
        self.assertEqual(dossier.opinions.count(), 8)
        self.assertTrue(
            dossier.opinions.filter(specialty=SpecialistOpinion.Specialty.COORDINATOR).exists()
        )
        self.assertNotIn(
            self.players[-1].pk,
            dossier.plans.values_list('players__player_id', flat=True),
        )
        self.assertEqual(MatchLineup.objects.filter(match=self.match).count(), 0)
        self.assertIn('data_quality', dossier.data_snapshot)
        self.assertEqual(dossier.data_snapshot['external_sources'][0]['quality'], 'synthetic')
        self.assertEqual(
            dossier.data_snapshot['external_sources'][0]['attribution'],
            'Dados sintéticos gerados pelo projeto SaaS do Futebol',
        )
        self.assertEqual(dossier.data_snapshot['external_form']['sequence'], [3, 1, 3])
        self.assertEqual(dossier.data_snapshot['external_evidence'][0]['record_id'], 'demo-form-ilha-azul')
        self.assertTrue(all(opinion.evidence for opinion in dossier.opinions.all()))
        starters = dossier.plans.get(variant=GamePlan.Variant.BALANCED).players.filter(
            is_starter=True
        )
        self.assertEqual(starters.count(), 11)
        coordinates = set(starters.values_list('pitch_x', 'pitch_y'))
        self.assertGreaterEqual(len(coordinates), 10)
        self.assertTrue(all(0 <= x <= 100 and 0 <= y <= 100 for x, y in coordinates))

    def test_aplica_plano_como_rascunho_sem_alterar_escalacao_oficial(self):
        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )
        plan = dossier.plans.get(variant=GamePlan.Variant.BALANCED)

        draft = apply_game_plan_as_draft(plan=plan, applied_by=self.user)
        same_draft = apply_game_plan_as_draft(plan=plan, applied_by=self.user)

        self.assertIsInstance(draft, LineupDraft)
        self.assertEqual(same_draft.pk, draft.pk)
        self.assertEqual(draft.players.count(), plan.players.count())
        self.assertEqual(MatchLineup.objects.filter(match=self.match).count(), 0)

    def test_rejeita_clube_que_nao_participa_da_partida(self):
        outsider = Club.objects.create(tenant=self.tenant, name='Terceiro FC', slug='terceiro-fc')

        with self.assertRaisesMessage(ValidationError, 'participar da partida'):
            generate_match_dossier(match=self.match, club=outsider, requested_by=self.user)

    def test_ignora_atleta_com_contrato_expirado_na_data_da_partida(self):
        expired = Person.objects.create(
            tenant=self.tenant,
            full_name='Atleta com contrato expirado',
            kind=Person.Kind.ATHLETE,
        )
        Contract.objects.create(
            tenant=self.tenant,
            person=expired,
            club=self.our_club,
            start_date=timezone.localdate() - timedelta(days=90),
            end_date=timezone.localdate() - timedelta(days=1),
            status=Contract.Status.ACTIVE,
        )

        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        self.assertFalse(dossier.plans.filter(players__player=expired).exists())

    def test_dado_externo_relevante_altera_planos_e_evidencias_por_especialidade(self):
        import_local_sports_dataset(
            tenant=self.tenant,
            dataset_slug='demo-treinador-sintetico-v1',
            imported_by=self.user,
            root=Path(__file__).resolve().parent / 'data' / 'sports',
        )
        our_record = SportsDataRecord.objects.get(
            tenant=self.tenant,
            capability='standings_form',
            provider_record_id='demo-form-ilha-azul',
        )
        our_record.payload = {**our_record.payload, 'team': self.our_club.name, 'recent_points': [0, 0, 1]}
        our_record.save()
        opponent_record = SportsDataRecord.objects.get(
            tenant=self.tenant,
            capability='standings_form',
            provider_record_id='demo-form-vale-dourado',
        )
        opponent_record.payload = {
            **opponent_record.payload,
            'team': self.opponent.name,
            'recent_points': [3, 3, 3],
        }
        opponent_record.save()

        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        balanced = dossier.plans.get(variant=GamePlan.Variant.BALANCED)
        self.assertIn('vantagem recente do adversário', balanced.summary)
        self.assertTrue(any('amostra externa' in risk for risk in balanced.risks))
        scout = dossier.opinions.get(specialty=SpecialistOpinion.Specialty.SCOUT)
        physical = dossier.opinions.get(specialty=SpecialistOpinion.Specialty.PHYSICAL)
        self.assertTrue(any(item.get('record_id') for item in scout.evidence))
        self.assertTrue(all(item.get('kind') == 'internal_snapshot' for item in physical.evidence))

    def test_plano_rejeita_atleta_sem_contrato_ativo_com_clube_analisado(self):
        plan = self._create_plan()
        athlete_without_contract = Person.objects.create(
            tenant=self.tenant,
            full_name='Atleta sem contrato',
            kind=Person.Kind.ATHLETE,
        )

        with self.assertRaisesMessage(ValidationError, 'contrato ativo'):
            GamePlanPlayer.objects.create(
                tenant=self.tenant,
                plan=plan,
                player=athlete_without_contract,
                club=self.our_club,
                position='ATA',
            )

    def test_plano_rejeita_atleta_indisponivel_para_partida(self):
        plan = self._create_plan()

        with self.assertRaisesMessage(ValidationError, 'indisponível'):
            GamePlanPlayer.objects.create(
                tenant=self.tenant,
                plan=plan,
                player=self.players[-1],
                club=self.our_club,
                position='ATA',
            )

    def test_rascunho_rejeita_atleta_sem_contrato_ativo_com_clube(self):
        draft = self._create_draft()
        athlete_without_contract = Person.objects.create(
            tenant=self.tenant,
            full_name='Atleta inelegível para rascunho',
            kind=Person.Kind.ATHLETE,
        )

        with self.assertRaisesMessage(ValidationError, 'contrato ativo'):
            LineupDraftPlayer.objects.create(
                tenant=self.tenant,
                draft=draft,
                player=athlete_without_contract,
                position='ATA',
            )

    def test_rascunho_rejeita_atleta_indisponivel_para_partida(self):
        draft = self._create_draft()

        with self.assertRaisesMessage(ValidationError, 'indisponível'):
            LineupDraftPlayer.objects.create(
                tenant=self.tenant,
                draft=draft,
                player=self.players[-1],
                position='ATA',
            )

    def test_rejeita_partida_passada(self):
        self.match.scheduled_at = timezone.now() - timedelta(minutes=1)
        self.match.save()

        with self.assertRaisesMessage(ValidationError, 'partida futura'):
            generate_match_dossier(
                match=self.match,
                club=self.our_club,
                requested_by=self.user,
            )

    def test_modelo_de_dossie_rejeita_partida_passada(self):
        self.match.scheduled_at = timezone.now() - timedelta(minutes=1)
        self.match.save()

        with self.assertRaisesMessage(ValidationError, 'partida futura'):
            MatchDossier.objects.create(
                tenant=self.tenant,
                match=self.match,
                analyzed_club=self.our_club,
                generated_by=self.user,
                data_snapshot={'origem': 'teste'},
            )

    def test_modelo_de_dossie_rejeita_status_fora_de_agendada_ou_confirmada(self):
        self.match.status = Match.Status.PLAYED
        self.match.save()

        with self.assertRaisesMessage(ValidationError, 'agendada ou confirmada'):
            MatchDossier.objects.create(
                tenant=self.tenant,
                match=self.match,
                analyzed_club=self.our_club,
                generated_by=self.user,
                data_snapshot={'origem': 'teste'},
            )


class IntelligentCoachHTTPTests(IntelligentCoachServiceTests):
    def setUp(self):
        super().setUp()
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='ia', module_name='IA', enabled=True
        )
        self.client.force_login(self.user)

    def test_usuario_gera_visualiza_e_aplica_rascunho(self):
        generate_response = self.client.post(
            reverse('intelligent-coach-generate', args=[self.match.pk]),
            {'club': self.our_club.pk},
        )
        dossier = MatchDossier.objects.get(match=self.match, analyzed_club=self.our_club)
        self.assertRedirects(
            generate_response,
            reverse('intelligent-coach-dossier', args=[dossier.pk]),
        )

        detail_response = self.client.get(reverse('intelligent-coach-dossier', args=[dossier.pk]))
        self.assertContains(detail_response, 'Comissão Técnica Digital')
        self.assertContains(detail_response, 'Plano equilibrado')
        self.assertContains(detail_response, 'Dados insuficientes para recomendação espacial')
        self.assertContains(detail_response, 'Espelho do adversário')
        self.assertContains(detail_response, 'Movimentos planejados')
        self.assertContains(detail_response, 'Gols pró/contra')
        self.assertContains(detail_response, 'Cartões recentes')

        plan = dossier.plans.get(variant=GamePlan.Variant.BALANCED)
        rejected_response = self.client.post(
            reverse('intelligent-coach-apply-draft', args=[plan.pk])
        )
        self.assertRedirects(
            rejected_response,
            reverse('intelligent-coach-dossier', args=[dossier.pk]),
        )
        self.assertFalse(LineupDraft.objects.filter(plan=plan).exists())

        apply_response = self.client.post(
            reverse('intelligent-coach-apply-draft', args=[plan.pk]),
            {'confirm': 'apply-draft'},
        )
        draft = LineupDraft.objects.get(plan=plan)
        self.assertRedirects(
            apply_response,
            reverse('intelligent-coach-draft', args=[draft.pk]),
        )
        self.assertContains(
            self.client.get(reverse('intelligent-coach-draft', args=[draft.pk])),
            'Rascunho de escalação',
        )

    def test_dossie_de_outro_tenant_nao_e_visivel(self):
        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )
        other_tenant = Tenant.objects.create(name='Outro Inteligente', slug='outro-inteligente')
        other_user = User.objects.create_user('outro-treinador', password='senha12345')
        TenantMembership.objects.create(
            tenant=other_tenant,
            user=other_user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        TenantModuleSubscription.objects.create(
            tenant=other_tenant, module_code='ia', module_name='IA', enabled=True
        )
        self.client.force_login(other_user)

        response = self.client.get(reverse('intelligent-coach-dossier', args=[dossier.pk]))

        self.assertEqual(response.status_code, 404)

    def test_treinador_substitui_titular_e_marca_rascunho_revisado(self):
        reserve = Person.objects.create(
            tenant=self.tenant,
            full_name='Reserva elegível',
            kind=Person.Kind.ATHLETE,
        )
        Contract.objects.create(
            tenant=self.tenant,
            person=reserve,
            club=self.our_club,
            start_date=timezone.localdate() - timedelta(days=10),
            status=Contract.Status.ACTIVE,
        )
        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )
        plan = dossier.plans.get(variant=GamePlan.Variant.BALANCED)
        draft = apply_game_plan_as_draft(plan=plan, applied_by=self.user)
        original_starters = list(draft.players.filter(is_starter=True).order_by('order'))
        bench_player = draft.players.get(player=reserve)
        selected_ids = [item.pk for item in original_starters[1:]] + [bench_player.pk]

        response = self.client.post(
            reverse('intelligent-coach-review-draft', args=[draft.pk]),
            {'starters': selected_ids},
        )

        draft.refresh_from_db()
        self.assertRedirects(response, reverse('intelligent-coach-draft', args=[draft.pk]))
        self.assertEqual(draft.status, LineupDraft.Status.REVIEWED)
        self.assertFalse(draft.players.get(pk=original_starters[0].pk).is_starter)
        self.assertTrue(draft.players.get(pk=bench_player.pk).is_starter)
        self.assertEqual(draft.players.filter(is_starter=True).count(), 11)
