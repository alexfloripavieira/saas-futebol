import json
from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from futebol.models import (
    AIAgent, AIProvider, AthleteMatchAvailability, AthleteSportProfile, Club, Competition,
    CompetitionEdition, CompetitionPhase, Contract, GamePlan, Match,
    MatchDossier, Person, SpecialistOpinion, TacticalCommissionRun,
    TacticalCommissionTask, Tenant, TenantMembership,
)
from futebol.services.intelligent_coach import generate_match_dossier
from futebol.services.tactical_commission import (
    cancel_commission, claim_next_task, enqueue_dossier_commission, execute_claimed_task,
)


User = get_user_model()


class DossierAICommissionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube IA Real', slug='clube-ia-real')
        self.user = User.objects.create_user('gestor-ia-real')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        self.club = Club.objects.create(
            tenant=self.tenant, name='Clube IA', slug='clube-ia',
        )
        opponent = Club.objects.create(
            tenant=self.tenant, name='Adversário IA', slug='adversario-ia',
        )
        competition = Competition.objects.create(
            tenant=self.tenant, name='Liga IA', slug='liga-ia',
        )
        edition = CompetitionEdition.objects.create(
            tenant=self.tenant, competition=competition, slug='2026',
            name='2026', season_year=2026,
        )
        phase = CompetitionPhase.objects.create(
            tenant=self.tenant, edition=edition, code='unica', name='Única', order=1,
        )
        self.match = Match.objects.create(
            tenant=self.tenant, phase=phase, home_club=self.club,
            away_club=opponent, reference_code='IA-REAL-001',
            scheduled_at=timezone.now() + timedelta(days=6),
        )
        positions = ['GOL', 'LD', 'ZAG', 'ZAG', 'LE', 'VOL', 'MC', 'MEI', 'PD', 'PE', 'ATA']
        self.players = []
        for index, position in enumerate(positions, start=1):
            player = Person.objects.create(
                tenant=self.tenant, full_name=f'Atleta IA {index:02d}',
                kind=Person.Kind.ATHLETE,
            )
            Contract.objects.create(
                tenant=self.tenant, person=player, club=self.club,
                start_date=timezone.localdate() - timedelta(days=30),
                status=Contract.Status.ACTIVE,
            )
            AthleteSportProfile.objects.create(
                tenant=self.tenant, player=player, primary_position=position,
            )
            self.players.append(player)
        self.provider = AIProvider.objects.create(
            tenant=self.tenant, name='Provider real', kind=AIProvider.Kind.OPENCODE,
            model_name='opencode-go/deepseek-v4-flash', active=True,
            operational_data_processing_allowed=True,
            operational_data_authorization_note='Teste autorizado do Dossiê.',
            operational_data_authorized_at=timezone.now(),
            operational_data_authorized_by=self.user,
        )
        for specialty in ('tactical', 'coordinator'):
            AIAgent.objects.create(
                tenant=self.tenant, provider=self.provider,
                name=f'Agente {specialty}', slug=f'coach-{specialty}',
                system_prompt=f'Atue como {specialty}.', temperature=Decimal('0.20'),
                active=True,
            )
        self.dossier = generate_match_dossier(
            match=self.match, club=self.club, requested_by=self.user,
            decision_mode='provider',
        )

    def _run(self):
        return enqueue_dossier_commission(
            dossier=self.dossier, actor=self.user,
            specialties=['tactical'], max_provider_calls=2,
        )

    def _expire_active_dossier(self):
        MatchDossier.objects.filter(pk=self.dossier.pk).update(
            generated_at=timezone.now() - timedelta(minutes=3),
        )
        self.dossier.refresh_from_db()

    def _provider_result(self, answer, *, fallback=False):
        return SimpleNamespace(
            answer=json.dumps(answer, ensure_ascii=False),
            used_fallback=fallback,
            provider_name=self.provider.name,
            model_name=self.provider.model_name,
            provider_response=None,
        )

    def _specialist_payload(self):
        return {
            'schema_version': 'coach-dossier-specialist-v1',
            'specialty': 'tactical',
            'summary': 'A IA recomenda compactação com ajuste após leitura inicial.',
            'recommendations': ['Controlar o centro e validar o comportamento adversário.'],
            'limitations': ['Sem tracking operacional recente.'],
            'confidence': 68,
            'evidence_ids': [f'match:{self.match.pk}'],
            'requires_human_review': True,
        }

    def _coordinator_payload(self):
        starters = [{
            'player_id': player.pk,
            'position': profile.primary_position,
            'pitch_x': 10 + (index % 4) * 25,
            'pitch_y': 12 + (index // 4) * 32,
            'tactical_role': 'Função definida pela IA',
            'rationale': 'Selecionado pela IA a partir das evidências permitidas.',
        } for index, (player, profile) in enumerate(
            (item, item.sport_profiles.get(tenant=self.tenant)) for item in self.players
        )]
        plans = []
        for variant, formation in (
            ('balanced', '4-3-3'), ('offensive', '4-2-3-1'),
            ('conservative', '5-3-2'),
        ):
            plans.append({
                'variant': variant, 'formation': formation,
                'summary': f'Plano {variant} produzido pelo Coordenador de IA.',
                'attacking_plan': ['Progredir após reconhecer o bloco adversário.'],
                'defensive_plan': ['Compactar e ajustar gatilhos em campo.'],
                'transitions': ['Priorizar a primeira ação segura.'],
                'set_pieces': ['Validar responsabilidades na véspera.'],
                'risks': ['Amostra espacial limitada.'], 'confidence': 70,
                'starters': starters,
            })
        return {
            'schema_version': 'coach-dossier-decision-v1',
            'specialty': 'coordinator',
            'summary': 'Síntese produzida pelo Coordenador de IA.',
            'recommendations': ['Aplicar o plano somente após revisão humana.'],
            'limitations': ['Sem tracking operacional recente.'],
            'confidence': 70,
            'evidence_ids': [f'match:{self.match.pk}'],
            'requires_human_review': True,
            'training_microcycle': {
                'summary': 'Microciclo gerado pela IA para esta partida.',
                'sessions': [{
                    'day': 'D-1', 'focus': 'Ativação e plano de jogo',
                    'load': 'Baixa', 'objectives': ['Revisar gatilhos e bola parada.'],
                    'staff_decision': 'A comissão valida a carga individual.',
                }],
                'limitations': ['Sem GPS e carga interna individual.'],
            },
            'plans': plans,
        }

    @patch('futebol.services.dossier_ai.run_ai_agent_prompt')
    def test_provider_valido_produz_pareceres_planos_e_treino_sem_fallback(self, provider):
        self._run()
        provider.side_effect = [
            self._provider_result(self._specialist_payload()),
            self._provider_result(self._coordinator_payload()),
        ]

        specialist = claim_next_task(worker_id='worker-ia')
        execute_claimed_task(task_id=specialist.pk, worker_id='worker-ia')
        coordinator = claim_next_task(worker_id='worker-ia')
        self.assertEqual(coordinator.specialty, 'coordinator')
        execute_claimed_task(task_id=coordinator.pk, worker_id='worker-ia')

        self.dossier.refresh_from_db()
        run = TacticalCommissionRun.objects.get(dossier=self.dossier)
        self.assertEqual(self.dossier.status, MatchDossier.Status.READY)
        self.assertEqual(run.status, TacticalCommissionRun.Status.COMPLETED)
        self.assertEqual(self.dossier.opinions.count(), 2)
        self.assertFalse(self.dossier.opinions.exclude(
            execution_mode=SpecialistOpinion.ExecutionMode.PROVIDER,
        ).exists())
        self.assertEqual(set(self.dossier.plans.values_list('variant', flat=True)), {
            GamePlan.Variant.BALANCED, GamePlan.Variant.OFFENSIVE,
            GamePlan.Variant.CONSERVATIVE,
        })
        self.assertEqual(self.dossier.data_snapshot['decision_engine']['mode'], 'provider')
        coordinator_opinion = self.dossier.opinions.get(specialty='coordinator')
        self.assertEqual(coordinator_opinion.provider_name, self.provider.name)
        self.assertEqual(coordinator_opinion.prompt_version, 'coach-dossier-decision-v1')
        self.assertEqual(len(coordinator_opinion.prompt_hash), 64)
        self.assertEqual(provider.call_count, 2)

    @patch('futebol.services.dossier_ai.run_ai_agent_prompt')
    def test_provider_indisponivel_falha_sem_criar_opiniao_ou_plano(self, provider):
        self._run()
        provider.return_value = self._provider_result({}, fallback=True)

        task = claim_next_task(worker_id='worker-falha')
        execute_claimed_task(task_id=task.pk, worker_id='worker-falha')

        task.refresh_from_db()
        self.dossier.refresh_from_db()
        self.assertEqual(task.status, TacticalCommissionTask.Status.FAILED)
        self.assertEqual(self.dossier.status, MatchDossier.Status.FAILED)
        self.assertFalse(self.dossier.opinions.exists())
        self.assertFalse(self.dossier.plans.exists())
        self.assertIsNone(claim_next_task(worker_id='worker-falha'))

    @patch('futebol.services.dossier_ai.run_ai_agent_prompt')
    def test_cancelamento_durante_provider_descarta_resposta_tardia(self, provider):
        run = self._run()

        def cancel_during_call(**_kwargs):
            cancel_commission(run=run, actor=self.user)
            return self._provider_result(self._specialist_payload())

        provider.side_effect = cancel_during_call
        task = claim_next_task(worker_id='worker-cancelado')
        execute_claimed_task(task_id=task.pk, worker_id='worker-cancelado')

        task.refresh_from_db()
        self.dossier.refresh_from_db()
        self.assertEqual(task.status, TacticalCommissionTask.Status.CANCELLED)
        self.assertEqual(self.dossier.status, MatchDossier.Status.FAILED)
        self.assertFalse(self.dossier.opinions.exists())
        self.assertFalse(self.dossier.plans.exists())

    def test_provider_sem_autorizacao_operacional_nao_entra_na_fila(self):
        self.provider.operational_data_processing_allowed = False
        self.provider.operational_data_authorized_at = None
        self.provider.operational_data_authorized_by = None
        self.provider.save(update_fields=[
            'operational_data_processing_allowed', 'operational_data_authorized_at',
            'operational_data_authorized_by', 'updated_at',
        ])

        with self.assertRaisesMessage(ValidationError, 'Coordenador Técnico sem provider ativo'):
            self._run()

    def test_task_rejeita_parecer_de_outro_dossie_do_mesmo_tenant(self):
        run = self._run()
        self._expire_active_dossier()
        other_dossier = generate_match_dossier(
            match=self.match, club=self.club, requested_by=self.user,
            decision_mode='provider',
        )
        wrong_opinion = SpecialistOpinion.objects.create(
            tenant=self.tenant,
            dossier=other_dossier,
            agent=AIAgent.objects.get(tenant=self.tenant, slug='coach-tactical'),
            specialty=SpecialistOpinion.Specialty.TACTICAL,
            summary='Parecer pertencente a outro Dossiê.',
            recommendations=['Não deve ser associado à tarefa atual.'],
            execution_mode=SpecialistOpinion.ExecutionMode.PROVIDER,
        )
        task = run.tasks.get(specialty=SpecialistOpinion.Specialty.TACTICAL)
        task.specialist_opinion = wrong_opinion

        with self.assertRaisesMessage(ValidationError, 'mesmo Dossiê'):
            task.save()

    def test_task_rejeita_os_dois_tipos_de_parecer_simultaneamente(self):
        run = self._run()
        task = run.tasks.get(specialty=SpecialistOpinion.Specialty.TACTICAL)
        task.opinion_id = 999_999
        task.specialist_opinion_id = 999_998

        with self.assertRaisesMessage(ValidationError, 'simultaneamente'):
            task.clean()

    @patch('futebol.services.dossier_ai.run_ai_agent_prompt')
    def test_evidence_id_nao_textual_e_rejeitado_como_erro_de_validacao(self, provider):
        self._run()
        payload = self._specialist_payload()
        payload['evidence_ids'] = [{'id': f'match:{self.match.pk}'}]
        provider.return_value = self._provider_result(payload)

        task = claim_next_task(worker_id='worker-evidence-hostil')
        execute_claimed_task(task_id=task.pk, worker_id='worker-evidence-hostil')

        task.refresh_from_db()
        self.assertEqual(task.status, TacticalCommissionTask.Status.FAILED)
        self.assertEqual(task.error_code, 'validation_error')

    @patch('futebol.services.dossier_ai.run_ai_agent_prompt')
    def test_player_id_nao_inteiro_e_rejeitado_como_erro_de_validacao(self, provider):
        self._run()
        coordinator_payload = self._coordinator_payload()
        coordinator_payload['plans'][0]['starters'][0]['player_id'] = {'id': self.players[0].pk}
        provider.side_effect = [
            self._provider_result(self._specialist_payload()),
            self._provider_result(coordinator_payload),
        ]

        specialist = claim_next_task(worker_id='worker-player-hostil')
        execute_claimed_task(task_id=specialist.pk, worker_id='worker-player-hostil')
        coordinator = claim_next_task(worker_id='worker-player-hostil')
        execute_claimed_task(task_id=coordinator.pk, worker_id='worker-player-hostil')

        coordinator.refresh_from_db()
        self.assertEqual(coordinator.status, TacticalCommissionTask.Status.FAILED)
        self.assertEqual(coordinator.error_code, 'validation_error')
        self.assertFalse(self.dossier.plans.exists())

    @patch('futebol.services.dossier_ai.run_ai_agent_prompt')
    def test_titular_limitado_preserva_teto_de_minutos_em_todos_os_planos(self, provider):
        limited_player = self.players[-1]
        AthleteMatchAvailability.objects.create(
            tenant=self.tenant,
            match=self.match,
            player=limited_player,
            club=self.club,
            status=AthleteMatchAvailability.Status.LIMITED,
            max_minutes=30,
            readiness=62,
        )
        self._expire_active_dossier()
        self.dossier = generate_match_dossier(
            match=self.match, club=self.club, requested_by=self.user,
            decision_mode='provider',
        )
        self._run()
        provider.side_effect = [
            self._provider_result(self._specialist_payload()),
            self._provider_result(self._coordinator_payload()),
        ]

        specialist = claim_next_task(worker_id='worker-limite')
        execute_claimed_task(task_id=specialist.pk, worker_id='worker-limite')
        coordinator = claim_next_task(worker_id='worker-limite')
        execute_claimed_task(task_id=coordinator.pk, worker_id='worker-limite')

        selections = self.dossier.plans.filter(
            players__player=limited_player,
            players__is_starter=True,
        ).values_list('players__minute_limit', flat=True)
        self.assertEqual(list(selections), [30, 30, 30])
