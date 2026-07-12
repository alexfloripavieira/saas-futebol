from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from futebol.models import (
    AIAgent,
    AIProvider,
    SportsDataArtifact,
    SportsDataImportBatch,
    SportsDataSource,
    TacticalAgentOpinion,
    TacticalCommissionRun,
    TacticalCommissionTask,
    Tenant,
    TenantMembership,
)
from futebol.services.tactical_commission import (
    cancel_commission,
    claim_next_task,
    enqueue_commission,
    execute_claimed_task,
    review_commission,
    retry_task,
    serialize_run_status,
)


User = get_user_model()


class TacticalCommissionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Comissão Azul', slug='comissao-azul')
        self.user = User.objects.create_user('gestor-comissao')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        self.source = SportsDataSource.objects.create(
            tenant=self.tenant,
            code='tracking-comissao',
            name='Tracking Comissão',
            kind=SportsDataSource.Kind.SKILLCORNER_OPEN,
            capabilities=['tracking_frames'],
            license_id='MIT',
            attribution='SkillCorner',
            quality='research_sample',
            active=False,
            external_ai_processing_allowed=True,
            external_ai_provider_scope=AIProvider.Kind.OPENCODE,
            external_ai_authorization_note='Autorizado somente para métricas agregadas.',
            external_ai_authorized_at=timezone.now(),
            external_ai_authorized_by=self.user,
        )
        self.batch = SportsDataImportBatch.objects.create(
            tenant=self.tenant,
            source=self.source,
            dataset_id='tracking-comissao',
            dataset_version='v1',
            content_hash='a' * 64,
            status=SportsDataImportBatch.Status.COMPLETED,
            manifest={'usage_scope': 'research_only'},
            license_id='MIT',
            attribution='SkillCorner',
            quality='research_sample',
            imported_by=self.user,
        )
        self.artifact = SportsDataArtifact.objects.create(
            tenant=self.tenant,
            batch=self.batch,
            capability='tracking_frames',
            provider_object_id='match:commission-1',
            artifact_version='b' * 12,
            schema_version='v1',
            file='tracking/commission.jsonl',
            content_hash='b' * 64,
            byte_size=100,
            item_count=10,
            status=SportsDataArtifact.Status.READY,
            metadata={'tactical_engine': {
                'status': 'available',
                'limitations': [],
                'moments': [{
                    'kind': 'tactical_moment',
                    'evidence_id': 'e' * 64,
                    'moment_type': 'pressing',
                    'team_id': 'azul',
                    'period': 1,
                    'started_at': 1.0,
                    'ended_at': 2.0,
                    'duration': 1.0,
                    'metrics': {'samples': 10},
                    'limitations': ['P&D'],
                    'quality': {'eligible_for_operational_use': False},
                    'provenance': {
                        'source_code': self.source.code,
                        'batch_id': self.batch.pk,
                        'artifact_id': 1,
                        'content_hash': 'b' * 64,
                        'schema_version': 'v1',
                        'license_id': 'MIT',
                        'attribution': 'SkillCorner',
                        'usage_scope': 'research_only',
                        'algorithm_version': '1.0.0',
                    },
                    'agent_routes': ['tactical', 'attack'],
                }],
            }},
        )
        self.provider = AIProvider.objects.create(
            tenant=self.tenant,
            name='OpenCode Comissão',
            kind=AIProvider.Kind.OPENCODE,
            model_name='opencode-go/deepseek-v4-flash',
            active=True,
        )
        self.agents = {}
        for specialty in ('tactical', 'attack', 'coordinator'):
            self.agents[specialty] = AIAgent.objects.create(
                tenant=self.tenant,
                provider=self.provider,
                name=f'Agente {specialty}',
                slug=f'coach-{specialty}',
                purpose=f'Especialidade {specialty}',
                system_prompt=f'Analise como {specialty}.',
                temperature='0.20',
                active=True,
            )

    def _enqueue(self, **overrides):
        kwargs = {
            'artifact': self.artifact,
            'actor': self.user,
            'specialties': ['tactical', 'attack'],
            'idempotency_key': 'commission-request-1',
            'max_provider_calls': 8,
        }
        kwargs.update(overrides)
        return enqueue_commission(**kwargs)

    def _opinion(self, specialty, execution_mode=TacticalAgentOpinion.ExecutionMode.PROVIDER):
        return TacticalAgentOpinion.objects.create(
            tenant=self.tenant,
            artifact=self.artifact,
            agent=self.agents[specialty],
            specialty=specialty,
            summary=f'Parecer {specialty}',
            recommendations=['Treinar comportamento observado.'],
            limitations=[] if execution_mode == 'provider' else ['Fallback determinístico.'],
            confidence=70,
            evidence_ids=['e' * 64],
            execution_mode=execution_mode,
            provider_name=self.provider.name,
            model_name=self.provider.model_name,
            prompt_hash=(specialty[0] * 64),
            generated_by=self.user,
        )

    def test_enqueue_cria_tarefas_especialistas_e_coordenador_bloqueado(self):
        before = timezone.now()

        run = self._enqueue()

        self.assertEqual(run.status, TacticalCommissionRun.Status.QUEUED)
        self.assertEqual(run.max_provider_calls, 8)
        self.assertEqual(run.provider_calls_used, 0)
        tasks = run.tasks.order_by('specialty')
        self.assertEqual(
            set(tasks.values_list('specialty', flat=True)),
            {'tactical', 'attack', 'coordinator'},
        )
        coordinator = tasks.get(specialty='coordinator')
        self.assertEqual(coordinator.status, TacticalCommissionTask.Status.QUEUED)
        self.assertGreater(coordinator.available_at, before + timedelta(minutes=5))

    def test_enqueue_e_idempotente_por_tenant_e_chave(self):
        first = self._enqueue()
        second = self._enqueue()

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(TacticalCommissionRun.objects.count(), 1)
        self.assertEqual(TacticalCommissionTask.objects.count(), 3)

    def test_usuario_sem_papel_nao_pode_enfileirar(self):
        outsider = User.objects.create_user('sem-papel-comissao')

        with self.assertRaisesMessage(ValidationError, 'permissão'):
            self._enqueue(actor=outsider, idempotency_key='outsider')

        self.assertFalse(TacticalCommissionRun.objects.exists())

    def test_claim_reivindica_apenas_especialista_disponivel(self):
        run = self._enqueue()

        task = claim_next_task(worker_id='worker-a', lease_seconds=300)

        self.assertIn(task.specialty, {'tactical', 'attack'})
        self.assertEqual(task.status, TacticalCommissionTask.Status.RUNNING)
        self.assertEqual(task.lease_owner, 'worker-a')
        self.assertGreater(task.lease_expires_at, timezone.now())
        self.assertEqual(run.tasks.filter(status=TacticalCommissionTask.Status.RUNNING).count(), 1)

    @patch('futebol.services.tactical_commission.generate_tactical_agent_opinions')
    def test_execute_claimed_task_persiste_resultado_e_consumo(self, generate):
        run = self._enqueue(specialties=['tactical'])
        task = claim_next_task(worker_id='worker-a')
        generate.return_value = [self._opinion(task.specialty)]

        execute_claimed_task(task_id=task.pk, worker_id='worker-a')

        task.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(task.status, TacticalCommissionTask.Status.COMPLETED)
        self.assertIsNotNone(task.opinion_id)
        self.assertEqual(run.provider_calls_used, 1)
        generate.assert_called_once_with(
            artifact=self.artifact,
            actor=self.user,
            specialties=[task.specialty],
        )

    @patch('futebol.services.tactical_commission.generate_tactical_agent_opinions')
    def test_fallback_de_especialista_deixa_execucao_partial(self, generate):
        run = self._enqueue(specialties=['tactical'])
        task = claim_next_task(worker_id='worker-a')
        generate.return_value = [self._opinion(
            task.specialty, TacticalAgentOpinion.ExecutionMode.FALLBACK,
        )]

        execute_claimed_task(task_id=task.pk, worker_id='worker-a')

        coordinator = claim_next_task(worker_id='worker-a')
        self.assertEqual(coordinator.specialty, 'coordinator')
        generate.return_value = [self._opinion('coordinator')]
        execute_claimed_task(task_id=coordinator.pk, worker_id='worker-a')

        run.refresh_from_db()
        self.assertEqual(run.status, TacticalCommissionRun.Status.PARTIAL)

    @patch('futebol.services.tactical_commission.generate_tactical_agent_opinions')
    def test_especialistas_provider_e_coordenador_deterministico_concluem_execucao(self, generate):
        run = self._enqueue(specialties=['tactical'])
        specialist = claim_next_task(worker_id='worker-a')
        generate.return_value = [self._opinion('tactical')]
        execute_claimed_task(task_id=specialist.pk, worker_id='worker-a')
        coordinator = claim_next_task(worker_id='worker-a')

        execute_claimed_task(task_id=coordinator.pk, worker_id='worker-a')

        run.refresh_from_db()
        self.assertEqual(run.status, TacticalCommissionRun.Status.COMPLETED)
        self.assertEqual(len(run.plan_variants), 3)

    def test_cancelamento_impede_claim_de_tarefas_pendentes(self):
        run = self._enqueue()

        cancel_commission(run=run, actor=self.user)

        run.refresh_from_db()
        self.assertEqual(run.status, TacticalCommissionRun.Status.CANCELLED)
        self.assertIsNone(claim_next_task(worker_id='worker-a'))
        self.assertFalse(run.tasks.filter(status=TacticalCommissionTask.Status.QUEUED).exists())

    def test_retry_preserva_tentativa_anterior(self):
        run = self._enqueue(specialties=['tactical'])
        original = run.tasks.get(specialty='tactical')
        original.status = TacticalCommissionTask.Status.FAILED
        original.finished_at = timezone.now()
        original.save()

        retried = retry_task(task=original, actor=self.user)

        original.refresh_from_db()
        self.assertNotEqual(retried.pk, original.pk)
        self.assertEqual(original.status, TacticalCommissionTask.Status.FAILED)
        self.assertEqual(retried.attempt, original.attempt + 1)
        self.assertEqual(retried.status, TacticalCommissionTask.Status.QUEUED)
        self.assertEqual(run.tasks.filter(specialty='tactical').count(), 2)

    @patch('futebol.services.tactical_commission.generate_tactical_agent_opinions')
    def test_orcamento_bloqueia_chamada_excedente_ao_provider(self, generate):
        self._enqueue(max_provider_calls=1)
        first = claim_next_task(worker_id='worker-a')
        generate.return_value = [self._opinion(first.specialty)]
        execute_claimed_task(task_id=first.pk, worker_id='worker-a')
        second = claim_next_task(worker_id='worker-a')

        execute_claimed_task(task_id=second.pk, worker_id='worker-a')

        second.refresh_from_db()
        self.assertEqual(second.status, TacticalCommissionTask.Status.FAILED)
        self.assertEqual(generate.call_count, 1)

    def test_serializacao_contem_somente_dados_da_execucao_e_do_tenant(self):
        run = self._enqueue()
        other_tenant = Tenant.objects.create(name='Comissão Verde', slug='comissao-verde')
        other_user = User.objects.create_user('gestor-verde')
        TenantMembership.objects.create(
            tenant=other_tenant,
            user=other_user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        other_source = SportsDataSource.objects.create(
            tenant=other_tenant,
            code='tracking-verde',
            name='Tracking Verde',
            kind=SportsDataSource.Kind.SKILLCORNER_OPEN,
            capabilities=['tracking_frames'],
            license_id='MIT',
            attribution='SkillCorner',
            quality='research_sample',
            active=False,
        )
        other_batch = SportsDataImportBatch.objects.create(
            tenant=other_tenant,
            source=other_source,
            dataset_id='verde',
            dataset_version='v1',
            content_hash='c' * 64,
            status=SportsDataImportBatch.Status.COMPLETED,
            manifest={'usage_scope': 'research_only'},
            license_id='MIT',
            attribution='SkillCorner',
            quality='research_sample',
            imported_by=other_user,
        )
        other_artifact = SportsDataArtifact.objects.create(
            tenant=other_tenant,
            batch=other_batch,
            capability='tracking_frames',
            provider_object_id='match:verde',
            artifact_version='d' * 12,
            schema_version='v1',
            file='tracking/verde.jsonl',
            content_hash='d' * 64,
            byte_size=10,
            item_count=1,
            status=SportsDataArtifact.Status.READY,
            metadata={'scope': 'tenant-isolation-test'},
        )
        TacticalCommissionRun.objects.create(
            tenant=other_tenant,
            artifact=other_artifact,
            requested_by=other_user,
            idempotency_key='verde-secret-key',
            requested_specialties=['tactical'],
            status=TacticalCommissionRun.Status.QUEUED,
            max_provider_calls=8,
        )

        payload = serialize_run_status(run)
        serialized = str(payload)

        self.assertEqual(payload['id'], run.pk)
        self.assertEqual(len(payload['tasks']), 3)
        self.assertNotIn('verde-secret-key', serialized)
        self.assertNotIn('tracking/commission.jsonl', serialized)
        self.assertNotIn('external_ai_authorization_note', serialized)

    def test_worker_antigo_nao_conclui_tarefa_reivindicada_por_outro(self):
        self._enqueue(specialties=['tactical'])
        task = claim_next_task(worker_id='worker-antigo', lease_seconds=30)
        task.lease_expires_at = timezone.now() - timedelta(seconds=1)
        task.save(update_fields=['lease_expires_at', 'updated_at'])
        reclaimed = claim_next_task(worker_id='worker-novo', lease_seconds=300)
        self.assertEqual(reclaimed.pk, task.pk)

        with self.assertRaisesMessage(ValidationError, 'não pertence mais'):
            execute_claimed_task(task_id=task.pk, worker_id='worker-antigo')

        reclaimed.refresh_from_db()
        self.assertEqual(reclaimed.lease_owner, 'worker-novo')
        self.assertEqual(reclaimed.status, TacticalCommissionTask.Status.RUNNING)

    def test_revisao_humana_dos_cenarios_registra_decisao_e_responsavel(self):
        run = self._enqueue(specialties=['tactical'])
        run.status = TacticalCommissionRun.Status.PARTIAL
        run.finished_at = timezone.now()
        run.plan_variants = [{'variant': 'balanced', 'label': 'Equilibrado'}]
        run.save()

        review_commission(
            run=run, actor=self.user, decision='approved_training',
            note='Aprovado apenas para o treino de terça-feira.',
        )

        run.refresh_from_db()
        self.assertEqual(run.review_decision, 'approved_training')
        self.assertEqual(run.reviewed_by, self.user)
        self.assertIsNotNone(run.reviewed_at)
