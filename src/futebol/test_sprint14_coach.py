from datetime import timedelta
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from futebol.models import (
    AIAgent,
    AIProvider,
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
    TacticalCommissionRun,
    TacticalCommissionTask,
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
        TenantModuleSubscription.objects.create(
            tenant=self.tenant,
            module_code='ia',
            module_name='IA',
            enabled=True,
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

    def test_dossie_converte_forma_real_do_provider_em_amostra_comparavel(self):
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
        our_record.payload = {
            **our_record.payload,
            'team': self.our_club.name,
            'form': 'W,D,L,W,W',
        }
        our_record.payload.pop('recent_points', None)
        our_record.save()
        opponent_record = SportsDataRecord.objects.get(
            tenant=self.tenant,
            capability='standings_form',
            provider_record_id='demo-form-vale-dourado',
        )
        opponent_record.payload = {
            **opponent_record.payload,
            'team': self.opponent.name,
            'form': 'L,L,D,L,W',
        }
        opponent_record.payload.pop('recent_points', None)
        opponent_record.save()

        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        self.assertEqual(dossier.data_snapshot['external_form']['sequence'], [3, 1, 0, 3, 3])
        self.assertEqual(dossier.data_snapshot['opponent_external_form']['sequence'], [0, 0, 1, 0, 3])
        self.assertIn('vantagem recente do nosso time', dossier.plans.get(
            variant=GamePlan.Variant.BALANCED,
        ).summary)

    def test_dossie_nao_perde_evidencia_do_clube_apos_cem_registros_irrelevantes(self):
        import_local_sports_dataset(
            tenant=self.tenant,
            dataset_slug='demo-treinador-sintetico-v1',
            imported_by=self.user,
            root=Path(__file__).resolve().parent / 'data' / 'sports',
        )
        relevant = SportsDataRecord.objects.get(
            tenant=self.tenant,
            capability='standings_form',
            provider_record_id='demo-form-ilha-azul',
        )
        relevant.payload = {
            **relevant.payload,
            'team': self.our_club.name,
            'recent_points': [3, 3, 1],
        }
        relevant.save()
        for index in range(101):
            SportsDataRecord.objects.create(
                tenant=self.tenant,
                source=relevant.source,
                batch=relevant.batch,
                capability='fixtures_results',
                provider_record_id=f'irrelevante-{index:03d}',
                observed_at=timezone.now() + timedelta(seconds=index),
                payload={'home_team': f'Outro Clube {index}', 'away_team': 'Terceiro Clube'},
                content_hash=f'{index:064d}',
            )

        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        self.assertEqual(dossier.data_snapshot['external_form']['sequence'], [3, 3, 1])
        self.assertTrue(any(
            item['record_id'] == relevant.provider_record_id
            for item in dossier.data_snapshot['external_evidence']
        ))

    def test_dossie_projeta_escalacao_adversaria_com_cinco_jogos_observados(self):
        opponent_players = []
        opponent_positions = [
            'GOL', 'LD', 'ZAG', 'ZAG', 'LE', 'VOL', 'MC', 'MEI', 'PD', 'PE', 'ATA', 'ATA',
        ]
        for index, position in enumerate(opponent_positions, start=1):
            player = Person.objects.create(
                tenant=self.tenant,
                full_name=f'Adversário {index:02d}',
                kind=Person.Kind.ATHLETE,
            )
            opponent_players.append((player, position))
        for game_index in range(5):
            observed_match = Match.objects.create(
                tenant=self.tenant,
                phase=self.match.phase,
                home_club=self.opponent,
                away_club=self.our_club,
                reference_code=f'OPP-HISTORY-{game_index}',
                scheduled_at=timezone.now() - timedelta(days=game_index + 2),
                status=Match.Status.PLAYED,
                home_score=1,
                away_score=0,
            )
            starters = opponent_players[:11]
            if game_index == 0:
                starters = opponent_players[:10] + [opponent_players[11]]
            for player, position in starters:
                MatchLineup.objects.create(
                    tenant=self.tenant,
                    match=observed_match,
                    player=player,
                    club=self.opponent,
                    position=position,
                    is_starter=True,
                )

        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        prediction = dossier.data_snapshot['opponent_prediction']
        self.assertEqual(prediction['status'], 'data_supported')
        self.assertEqual(prediction['sample_matches'], 5)
        self.assertEqual(len(prediction['players']), 11)
        regular = next(item for item in prediction['candidates'] if item['name'] == 'Adversário 01')
        rotational = next(item for item in prediction['candidates'] if item['name'] == 'Adversário 12')
        self.assertGreater(regular['start_probability'], rotational['start_probability'])
        self.assertEqual(prediction['method'], 'weighted-start-frequency-v1')
        self.assertEqual(prediction['formation_status'], 'hypothesis')
        self.assertTrue(any(
            'núcleo provável' in item
            for item in dossier.plans.get(
                variant=GamePlan.Variant.BALANCED,
            ).defensive_plan
        ))

    def test_plano_prioriza_atleta_apto_e_expoe_pontuacao_da_recomendacao(self):
        current_forward = self.players[10]
        AthleteMatchAvailability.objects.create(
            tenant=self.tenant,
            match=self.match,
            player=current_forward,
            club=self.our_club,
            status=AthleteMatchAvailability.Status.DOUBT,
            readiness=30,
            max_minutes=35,
            note='Baixa prontidão registrada pela preparação física.',
        )
        ready_forward = Person.objects.create(
            tenant=self.tenant,
            full_name='Atacante em alta prontidão',
            kind=Person.Kind.ATHLETE,
        )
        Contract.objects.create(
            tenant=self.tenant,
            person=ready_forward,
            club=self.our_club,
            start_date=timezone.localdate() - timedelta(days=30),
            status=Contract.Status.ACTIVE,
        )
        AthleteSportProfile.objects.create(
            tenant=self.tenant,
            player=ready_forward,
            primary_position='ATA',
            secondary_positions=['PD'],
            tactical_roles=['atacar profundidade'],
        )
        AthleteMatchAvailability.objects.create(
            tenant=self.tenant,
            match=self.match,
            player=ready_forward,
            club=self.our_club,
            status=AthleteMatchAvailability.Status.AVAILABLE,
            readiness=95,
        )

        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        balanced = dossier.plans.get(variant=GamePlan.Variant.BALANCED)
        recommended = balanced.players.get(player=ready_forward)
        restricted = balanced.players.get(player=current_forward)
        self.assertTrue(recommended.is_starter)
        self.assertFalse(restricted.is_starter)
        self.assertIn('prontidão 95/100', recommended.rationale)
        self.assertIn('pontuação', recommended.rationale)
        self.assertEqual(
            dossier.data_snapshot['lineup_recommendation']['method'],
            'position-readiness-history-v1',
        )

    def test_historico_de_titularidade_nao_conta_partida_sem_escalacao_observada(self):
        Match.objects.create(
            tenant=self.tenant,
            phase=self.match.phase,
            home_club=self.our_club,
            away_club=self.opponent,
            reference_code='SEM-ESCALACAO',
            scheduled_at=timezone.now() - timedelta(days=2),
            status=Match.Status.PLAYED,
            home_score=1,
            away_score=0,
        )

        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        starter = dossier.plans.get(
            variant=GamePlan.Variant.BALANCED,
        ).players.filter(is_starter=True).first()
        self.assertIn('titular em 0/0 jogos observados', starter.rationale)

    def test_dossie_rejeita_elenco_sem_goleiro_apto(self):
        goalkeeper_profile = AthleteSportProfile.objects.get(player=self.players[0])
        goalkeeper_profile.primary_position = 'ZAG'
        goalkeeper_profile.save()

        with self.assertRaisesMessage(ValidationError, 'goleiro apto'):
            generate_match_dossier(
                match=self.match,
                club=self.our_club,
                requested_by=self.user,
            )

    def test_dossie_sugere_microciclo_contextual_sem_simular_dado_fisico_ausente(self):
        AthleteMatchAvailability.objects.create(
            tenant=self.tenant,
            match=self.match,
            player=self.players[0],
            club=self.our_club,
            status=AthleteMatchAvailability.Status.LIMITED,
            readiness=55,
            max_minutes=60,
            note='Carga individual sob revisão.',
        )

        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
        )

        microcycle = dossier.data_snapshot['training_microcycle']
        self.assertEqual(microcycle['method'], 'match-relative-microcycle-v1')
        self.assertEqual(microcycle['status'], 'suggestion_for_staff_review')
        self.assertTrue(microcycle['sessions'])
        self.assertTrue(any(item['day'] == 'D-1' for item in microcycle['sessions']))
        self.assertTrue(any('GPS' in item for item in microcycle['limitations']))
        self.assertEqual(microcycle['restricted_players'], 1)

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
        provider = AIProvider.objects.create(
            tenant=self.tenant,
            name='Provider operacional',
            kind=AIProvider.Kind.OPENCODE,
            model_name='opencode-go/deepseek-v4-flash',
            active=True,
            operational_data_processing_allowed=True,
            operational_data_authorization_note='Teste autorizado do Dossiê.',
            operational_data_authorized_at=timezone.now(),
            operational_data_authorized_by=self.user,
        )
        specialist_slugs = {
            'coordinator': 'coach-coordinator', 'tactical': 'coach-tactical',
            'physical': 'coach-physical', 'defense': 'coach-defense',
            'attack': 'coach-attack', 'scout': 'coach-scout',
            'set_pieces': 'coach-set-pieces', 'environment': 'coach-environment',
        }
        for specialty, slug in specialist_slugs.items():
            AIAgent.objects.create(
                tenant=self.tenant,
                provider=provider,
                name=f'Agente {specialty}',
                slug=slug,
                purpose=f'Análise {specialty}',
                system_prompt=f'Atue como especialista {specialty}.',
                temperature=Decimal('0.20'),
                active=True,
            )
        self.client.force_login(self.user)

    @patch('futebol.services.dossier_ai.run_ai_agent_prompt')
    def test_usuario_enfileira_ia_sem_chamar_provider_na_requisicao(self, provider_run):
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
        self.assertContains(detail_response, 'Sala da Próxima Partida')
        self.assertContains(detail_response, 'Estamos preparando sua recomendação')
        self.assertContains(detail_response, 'Reunindo dados do time e do adversário')
        self.assertNotContains(detail_response, 'Provider de IA obrigatório')
        self.assertNotContains(detail_response, 'Plano equilibrado')
        provider_run.assert_not_called()
        dossier.refresh_from_db()
        self.assertEqual(dossier.status, MatchDossier.Status.PROCESSING)
        run = TacticalCommissionRun.objects.get(dossier=dossier)
        self.assertEqual(run.tasks.count(), 8)
        self.assertFalse(dossier.opinions.exists())
        self.assertFalse(dossier.plans.exists())

        counts_before = (
            MatchDossier.objects.count(),
            GamePlan.objects.count(),
            GamePlanPlayer.objects.count(),
        )
        self.client.get(reverse('intelligent-coach-dossier', args=[dossier.pk]))
        self.assertEqual(counts_before, (
            MatchDossier.objects.count(),
            GamePlan.objects.count(),
            GamePlanPlayer.objects.count(),
        ))

        status_response = self.client.get(
            reverse('intelligent-coach-dossier-ai-status', args=[dossier.pk]),
            {'run': run.pk},
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(
            status_response.json()['dossier_status'],
            MatchDossier.Status.PROCESSING,
        )

        failed_task = run.tasks.exclude(specialty='coordinator').first()
        failed_task.status = TacticalCommissionTask.Status.FAILED
        failed_task.error_code = 'provider_execution_failed'
        failed_task.finished_at = timezone.now()
        failed_task.save(update_fields=['status', 'error_code', 'finished_at', 'updated_at'])
        dossier.status = MatchDossier.Status.PARTIAL
        dossier.save(update_fields=['status', 'updated_at'])

        retry_response = self.client.post(reverse(
            'intelligent-coach-dossier-ai-retry', args=[failed_task.pk],
        ))
        self.assertRedirects(
            retry_response, reverse('intelligent-coach-dossier', args=[dossier.pk]),
        )
        dossier.refresh_from_db()
        self.assertEqual(dossier.status, MatchDossier.Status.PROCESSING)
        self.assertTrue(run.tasks.filter(
            specialty=failed_task.specialty,
            attempt=failed_task.attempt + 1,
            status=TacticalCommissionTask.Status.QUEUED,
        ).exists())

    def test_dossie_deterministico_nao_e_apresentado_como_resposta_da_ia(self):
        dossier = generate_match_dossier(
            match=self.match, club=self.our_club, requested_by=self.user,
        )

        response = self.client.get(reverse(
            'intelligent-coach-dossier', args=[dossier.pk],
        ))

        self.assertContains(response, 'Dossiê legado calculado por regras')
        self.assertContains(response, 'Recomendação calculada por regras explicáveis')
        self.assertNotContains(response, 'Sugestão produzida pelo Coordenador de IA')
        self.assertNotContains(response, 'Posições escolhidas pelo Coordenador de IA')

    def test_dossie_provider_pronto_com_proveniencia_identifica_conteudo_da_ia(self):
        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
            decision_mode='provider',
        )
        coordinator = AIAgent.objects.get(tenant=self.tenant, slug='coach-coordinator')
        SpecialistOpinion.objects.create(
            tenant=self.tenant,
            dossier=dossier,
            agent=coordinator,
            specialty=SpecialistOpinion.Specialty.COORDINATOR,
            summary='Síntese produzida pelo provider.',
            recommendations=['Submeter a decisão à comissão humana.'],
            evidence=[{'record_id': f'match:{self.match.pk}'}],
            confidence=70,
            execution_mode=SpecialistOpinion.ExecutionMode.PROVIDER,
            provider_name='Provider operacional',
            model_name='opencode-go/deepseek-v4-flash',
            prompt_version='coach-dossier-decision-v1',
        )
        snapshot = dict(dossier.data_snapshot)
        snapshot['decision_engine'] = {
            'mode': 'provider',
            'provider': 'Provider operacional',
            'model': 'opencode-go/deepseek-v4-flash',
            'generated_at': timezone.now().isoformat(),
            'requires_human_review': True,
        }
        snapshot['lineup_recommendation'] = {
            'method': 'coach-dossier-decision-v1',
            'provider': 'Provider operacional',
            'model': 'opencode-go/deepseek-v4-flash',
            'requires_human_review': True,
        }
        dossier.data_snapshot = snapshot
        dossier.status = MatchDossier.Status.READY
        dossier.save(update_fields=['data_snapshot', 'status', 'updated_at'])

        response = self.client.get(reverse(
            'intelligent-coach-dossier', args=[dossier.pk],
        ))

        self.assertContains(response, 'Sugestão produzida pelo Coordenador de IA')
        self.assertNotContains(response, 'Dossiê legado calculado por regras')

    def test_estados_sem_execucao_nao_afirmam_que_a_ia_esta_trabalhando(self):
        dossier = generate_match_dossier(
            match=self.match,
            club=self.our_club,
            requested_by=self.user,
            decision_mode='provider',
        )

        processing_response = self.client.get(reverse(
            'intelligent-coach-dossier', args=[dossier.pk],
        ))
        self.assertContains(processing_response, 'A análise aguarda o início da execução')
        self.assertNotContains(
            processing_response, 'A Comissão Técnica Digital está trabalhando',
        )

        dossier.status = MatchDossier.Status.PARTIAL
        dossier.save(update_fields=['status', 'updated_at'])
        partial_response = self.client.get(reverse(
            'intelligent-coach-dossier', args=[dossier.pk],
        ))
        self.assertContains(partial_response, 'Estado parcial sem execução associada')
        self.assertNotContains(partial_response, 'A IA interrompeu a análise')

        dossier.status = MatchDossier.Status.FAILED
        dossier.save(update_fields=['status', 'updated_at'])

        response = self.client.get(reverse(
            'intelligent-coach-dossier', args=[dossier.pk],
        ))

        self.assertContains(response, 'Não foi possível iniciar a análise de IA')
        self.assertContains(response, 'Nenhuma execução foi criada')
        self.assertNotContains(response, 'A Comissão Técnica Digital está trabalhando')
        self.assertNotContains(response, 'data-poll-active="true"')

    def test_processamento_expoe_progresso_e_polling_atualizavel(self):
        response = self.client.post(
            reverse('intelligent-coach-generate', args=[self.match.pk]),
            {'club': self.our_club.pk},
        )
        dossier = MatchDossier.objects.get(match=self.match, analyzed_club=self.our_club)
        self.assertRedirects(
            response, reverse('intelligent-coach-dossier', args=[dossier.pk]),
        )

        detail = self.client.get(reverse(
            'intelligent-coach-dossier', args=[dossier.pk],
        ))

        self.assertContains(detail, 'id="ai-progress"')
        self.assertContains(detail, 'id="ai-provider-calls"')
        self.assertContains(detail, 'data-task-id=')
        self.assertContains(detail, 'data-poll-active="true"')
        self.assertContains(detail, 'state.provider_calls.used')
        self.assertNotContains(detail, 'window.setInterval')

    def test_falha_terminal_traduz_erro_e_nao_mantem_polling(self):
        self.client.post(
            reverse('intelligent-coach-generate', args=[self.match.pk]),
            {'club': self.our_club.pk},
        )
        dossier = MatchDossier.objects.get(match=self.match, analyzed_club=self.our_club)
        run = TacticalCommissionRun.objects.get(dossier=dossier)
        failed_task = run.tasks.exclude(specialty='coordinator').first()
        failed_task.status = TacticalCommissionTask.Status.FAILED
        failed_task.error_code = 'provider_execution_failed'
        failed_task.finished_at = timezone.now()
        failed_task.save(update_fields=['status', 'error_code', 'finished_at', 'updated_at'])
        dossier.status = MatchDossier.Status.PARTIAL
        dossier.save(update_fields=['status', 'updated_at'])

        response = self.client.get(reverse(
            'intelligent-coach-dossier', args=[dossier.pk],
        ))
        content = response.content.decode()

        self.assertContains(response, 'Análise parcialmente concluída')
        self.assertContains(response, 'O provider não respondeu corretamente.')
        self.assertNotIn('provider_execution_failed', content)
        self.assertNotContains(response, 'data-poll-active="true"')

    def test_dossie_renderiza_evidencia_canonica_sem_descricao(self):
        dossier = generate_match_dossier(
            match=self.match, club=self.our_club, requested_by=self.user,
        )
        opinion = dossier.opinions.first()
        opinion.evidence = [{
            'record_id': 'demo-match-002',
            'capability': 'fixtures_results',
            'source_name': 'Fonte canônica',
        }]
        opinion.save(update_fields=['evidence', 'updated_at'])

        response = self.client.get(reverse(
            'intelligent-coach-dossier', args=[dossier.pk],
        ))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'demo-match-002')

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
