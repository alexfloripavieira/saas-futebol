import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from futebol.models import (
    AIAgent, AIProvider, AuditLog, SportsDataArtifact, SportsDataImportBatch,
    OperationalMetric, SportsDataSource, TacticalAgentOpinion, Tenant,
    TenantMembership,
)
from futebol.services.ai import run_ai_agent_prompt
from futebol.services.sports_data_authorization import authorize_external_ai_processing
from futebol.services.tactical_ai import generate_tactical_agent_opinions


class TacticalAIProviderTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='IA Tática', slug='ia-tatica')
        self.user = get_user_model().objects.create_user('gerador-tatico')
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role=TenantMembership.Role.GESTOR_CLUBE,
        )
        self.source = SportsDataSource.objects.create(
            tenant=self.tenant, code='tracking-open', name='Tracking aberto',
            kind=SportsDataSource.Kind.SKILLCORNER_OPEN,
            capabilities=['tracking_frames'], license_id='MIT', attribution='SkillCorner',
            quality='research_sample', active=False,
            external_ai_processing_allowed=True,
            external_ai_provider_scope='opencode',
            external_ai_authorization_note='Autorizado para métricas agregadas de P&D.',
            external_ai_authorized_at=timezone.now(),
            external_ai_authorized_by=self.user,
        )
        self.batch = SportsDataImportBatch.objects.create(
            tenant=self.tenant, source=self.source, dataset_id='tracking',
            dataset_version='v1', content_hash='a' * 64,
            status=SportsDataImportBatch.Status.COMPLETED,
            manifest={'usage_scope': 'research_only'}, license_id='MIT',
            attribution='SkillCorner', quality='research_sample', imported_by=self.user,
        )
        self.artifact = SportsDataArtifact.objects.create(
            tenant=self.tenant, batch=self.batch, capability='tracking_frames',
            provider_object_id='match:1', artifact_version='b' * 12,
            schema_version='v1', file='tracking/test.jsonl', content_hash='b' * 64,
            byte_size=100, item_count=10, status=SportsDataArtifact.Status.READY,
            metadata={'tactical_engine': {
                'status': 'available', 'limitations': [], 'moments': [{
                    'kind': 'tactical_moment', 'evidence_id': 'e' * 64,
                    'moment_type': 'pressing', 'team_id': 'azul', 'period': 1,
                    'started_at': 1.0, 'ended_at': 2.0, 'duration': 1.0,
                    'metrics': {'samples': 10}, 'limitations': ['P&D'],
                    'quality': {'eligible_for_operational_use': False},
                    'provenance': {
                        'source_code': 'tracking-open', 'batch_id': 1,
                        'artifact_id': 1, 'content_hash': 'b' * 64,
                        'schema_version': 'v1', 'license_id': 'MIT',
                        'attribution': 'SkillCorner', 'usage_scope': 'research_only',
                        'algorithm_version': '1.0.0',
                    },
                    'agent_routes': ['tactical'],
                }],
            }},
        )
        self.provider = AIProvider.objects.create(
            tenant=self.tenant, name='OpenCode Go', kind=AIProvider.Kind.OPENCODE,
            model_name='opencode-go/deepseek-v4-flash', active=True,
        )
        self.agent = AIAgent.objects.create(
            tenant=self.tenant, provider=self.provider, name='Analista Tático',
            slug='coach-tactical', purpose='Análise tática',
            system_prompt='Analise evidências táticas.', temperature='0.20', active=True,
        )

    def _provider_result(self, **overrides):
        payload = {
            'schema_version': 'tactical-agent-insight-v1', 'specialty': 'tactical',
            'summary': 'Pressão coordenada identificada.',
            'recommendations': ['Treinar saída apoiada sob pressão.'],
            'evidence_ids': ['e' * 64], 'confidence': 68,
            'limitations': ['Amostra de treinamento.'],
            'requires_human_review': True,
        }
        payload.update(overrides)
        return SimpleNamespace(
            answer=json.dumps(payload), used_fallback=False,
            provider_name='OpenCode Go', model_name=self.provider.model_name,
            provider_response=None,
        )

    @patch('futebol.services.tactical_ai.run_ai_agent_prompt')
    def test_executa_provider_configurado_e_persiste_json_validado(self, run):
        run.return_value = self._provider_result()

        opinions = generate_tactical_agent_opinions(
            artifact=self.artifact, actor=self.user,
        )

        self.assertEqual(len(opinions), 1)
        opinion = opinions[0]
        self.assertEqual(opinion.execution_mode, TacticalAgentOpinion.ExecutionMode.PROVIDER)
        self.assertEqual(opinion.evidence_ids, ['e' * 64])
        self.assertTrue(opinion.requires_human_review)
        self.assertFalse(opinion.eligible_for_operational_use)
        prompt = run.call_args.kwargs['prompt']
        self.assertIn('TACTICAL_EVIDENCE_DATA', prompt)
        self.assertNotIn('player_id', prompt)
        self.assertNotIn('tracking/test.jsonl', prompt)
        self.assertTrue(AuditLog.objects.filter(action='create').exists())
        metric = OperationalMetric.objects.get(event='tactical_ai_provider')
        self.assertEqual(metric.metadata['provider'], 'OpenCode Go')
        self.assertFalse(metric.metadata['usage_available'])

    @patch('futebol.services.tactical_ai.run_ai_agent_prompt')
    def test_evidencia_inventada_aciona_fallback_deterministico(self, run):
        run.return_value = self._provider_result(evidence_ids=['inventada'])

        opinion = generate_tactical_agent_opinions(
            artifact=self.artifact, actor=self.user,
        )[0]

        self.assertEqual(opinion.execution_mode, TacticalAgentOpinion.ExecutionMode.FALLBACK)
        self.assertIn('fallback determinístico', opinion.limitations[0])

    def test_fonte_sem_autorizacao_externa_bloqueia_antes_do_provider(self):
        self.source.external_ai_processing_allowed = False
        self.source.save(update_fields=['external_ai_processing_allowed', 'updated_at'])

        with self.assertRaisesMessage(ValidationError, 'não autoriza'):
            generate_tactical_agent_opinions(artifact=self.artifact, actor=self.user)

    def test_autorizacao_externa_registra_responsavel_fundamento_e_auditoria(self):
        self.source.external_ai_processing_allowed = False
        self.source.external_ai_provider_scope = ''
        self.source.external_ai_authorization_note = ''
        self.source.external_ai_authorized_at = None
        self.source.external_ai_authorized_by = None
        self.source.save()

        authorize_external_ai_processing(
            source=self.source,
            actor=self.user,
            provider_scope=AIProvider.Kind.OPENCODE,
            note='Autorização restrita a métricas táticas agregadas.',
        )

        self.source.refresh_from_db()
        self.assertTrue(self.source.external_ai_processing_allowed)
        self.assertEqual(self.source.external_ai_authorized_by, self.user)
        self.assertIsNotNone(self.source.external_ai_authorized_at)
        audit = AuditLog.objects.filter(action='update').latest('occurred_at')
        self.assertEqual(audit.after_state['external_ai_provider_scope'], 'opencode')
        self.assertNotIn('Autorização restrita', str(audit.after_state))

    def test_usuario_sem_papel_nao_pode_autorizar_envio_externo(self):
        outsider = get_user_model().objects.create_user('sem-papel')

        with self.assertRaisesMessage(ValidationError, 'sem permissão'):
            authorize_external_ai_processing(
                source=self.source,
                actor=outsider,
                provider_scope=AIProvider.Kind.OPENCODE,
                note='Autorização restrita a métricas táticas agregadas.',
            )

    @patch('futebol.services.tactical_ai.run_ai_agent_prompt')
    def test_fallback_nao_impede_nova_tentativa_quando_provider_recupera(self, run):
        run.side_effect = [
            SimpleNamespace(
                answer='', used_fallback=True, provider_name='OpenCode Go',
                model_name=self.provider.model_name, provider_response=None,
            ),
            self._provider_result(),
        ]

        first = generate_tactical_agent_opinions(
            artifact=self.artifact, actor=self.user,
        )[0]
        second = generate_tactical_agent_opinions(
            artifact=self.artifact, actor=self.user,
        )[0]

        self.assertEqual(first.execution_mode, TacticalAgentOpinion.ExecutionMode.FALLBACK)
        self.assertEqual(second.execution_mode, TacticalAgentOpinion.ExecutionMode.PROVIDER)
        self.assertEqual(TacticalAgentOpinion.objects.filter(artifact=self.artifact).count(), 2)

    @patch('futebol.services.ai.subprocess.run')
    @patch('futebol.services.ai._find_opencode_binary', return_value='/usr/bin/opencode')
    def test_opencode_recebe_prompt_por_stdin_e_nao_por_argumento(self, find, run):
        run.return_value = SimpleNamespace(
            stdout='{"ok":true}', stderr='', returncode=0,
        )

        run_ai_agent_prompt(agent=self.agent, prompt='PACOTE-SENSIVEL-AGREGADO')

        command = run.call_args.args[0]
        self.assertNotIn('PACOTE-SENSIVEL-AGREGADO', command)
        self.assertIn('PACOTE-SENSIVEL-AGREGADO', run.call_args.kwargs['input'])
