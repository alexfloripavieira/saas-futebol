from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from futebol.models import (
    SportsDataArtifact, SportsDataImportBatch, SportsDataSource, Tenant,
    TacticalInsightReview, TenantMembership, TenantModuleSubscription,
)


class TrackingAnalysisLabHTTPTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Tracking Azul', slug='tracking-azul')
        self.user = get_user_model().objects.create_user('tracking-user', password='senha')
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role=TenantMembership.Role.GESTOR_CLUBE,
        )
        TenantModuleSubscription.objects.create(
            tenant=self.tenant, module_code='ia', module_name='IA', enabled=True,
        )
        source = SportsDataSource.objects.create(
            tenant=self.tenant, code='skillcorner-open', name='SkillCorner Open Data',
            kind=SportsDataSource.Kind.SKILLCORNER_OPEN,
            capabilities=['tracking_frames'], license_id='MIT', attribution='SkillCorner',
            quality='research_sample', active=False,
        )
        self.batch = SportsDataImportBatch.objects.create(
            tenant=self.tenant, source=source, dataset_id='tracking-1',
            dataset_version='abc', content_hash='a' * 64,
            status=SportsDataImportBatch.Status.COMPLETED, record_count=0,
            manifest={'provider_match_id': '2017461'}, license_id='MIT',
            attribution='SkillCorner', quality='research_sample', imported_by=self.user,
        )
        self.artifact = SportsDataArtifact.objects.create(
            tenant=self.tenant, batch=self.batch, capability='tracking_frames',
            provider_object_id='match:2017461', artifact_version='b' * 12,
            schema_version='v1', file='tracking/fake.jsonl', content_hash='b' * 64,
            byte_size=100, item_count=3, status=SportsDataArtifact.Status.READY,
            metadata={'preview_scope': 'teste', 'tactical_engine': {
                'status': 'available', 'limitations': [], 'moments': [{
                    'evidence_id': 'd' * 64, 'description': 'Pressão de teste.',
                    'duration': 1, 'frame_refs': {'count': 10},
                    'validity': 'research_only', 'period': 1,
                    'agent_route_labels': ['Analista Tático'],
                    'agent_routes': ['tactical'], 'moment_type': 'pressing',
                }],
            }, 'analysis': {
                'available': True, 'frame_count': 3, 'coverage': 100,
                'average_width': 20, 'average_depth': 10,
                'coordinate_system': 'metros', 'direction': 'não inferida',
                'preview': [{'frame': 1, 'players': [
                    {'player_id': '1', 'team_id': 'azul', 'x': 50, 'y': 50},
                ]}],
            }},
        )
        self.client.force_login(self.user)

    def test_renderiza_tracking_observado_com_proveniencia(self):
        response = self.client.get(reverse('tracking-analysis-lab', args=[self.batch.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tracking posicional')
        self.assertContains(response, 'SkillCorner')
        self.assertContains(response, '<svg', html=False)
        self.assertContains(response, 'Linha do tempo')
        self.assertContains(response, 'Motor de momentos táticos')
        self.assertContains(response, 'tracking-playback-data')
        self.assertContains(response, 'Espelhar')

    def test_registra_revisao_humana_sem_alterar_dado_oficial(self):
        response = self.client.post(
            reverse('tracking-analysis-lab', args=[self.batch.pk]),
            {'evidence_id': 'd' * 64, 'decision': 'approved_training'},
        )

        self.assertEqual(response.status_code, 302)
        review = TacticalInsightReview.objects.get(artifact=self.artifact)
        self.assertEqual(review.decision, 'approved_training')
        self.assertEqual(review.reviewed_by, self.user)

    def test_nao_expoe_tracking_de_outro_tenant(self):
        other = Tenant.objects.create(name='Outro Tracking', slug='outro-tracking')
        self.batch.tenant = other
        self.batch.source = SportsDataSource.objects.create(
            tenant=other, code='skillcorner-open', name='SkillCorner',
            kind=SportsDataSource.Kind.SKILLCORNER_OPEN,
            capabilities=['tracking_frames'], license_id='MIT', attribution='SkillCorner',
            quality='research_sample', active=False,
        )
        self.batch.content_hash = 'c' * 64
        self.batch.save()

        response = self.client.get(reverse('tracking-analysis-lab', args=[self.batch.pk]))

        self.assertEqual(response.status_code, 404)
