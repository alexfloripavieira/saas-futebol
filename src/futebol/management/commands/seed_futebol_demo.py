from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from futebol.models import (
    AIAgent,
    AIAgentSourceLink,
    AIProvider,
    AthleteMatchAvailability,
    AthleteSportProfile,
    ApprovalDecision,
    ApprovalFlow,
    ApprovalFlowStep,
    ApprovalRequest,
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    CompetitionRuleSet,
    Contract,
    Evidence,
    ExternalSystem,
    IntegrationRecord,
    GamePlan,
    GamePlanPlayer,
    KnowledgeSource,
    LineupDraft,
    LineupDraftPlayer,
    Match,
    MatchEvent,
    MatchLineup,
    MatchDossier,
    Negotiation,
    Person,
    SpecialistOpinion,
    SportsDataImportBatch,
    SportsDataRecord,
    SportsDataSource,
    TeamCategory,
    Tenant,
    TenantBranding,
    TenantMembership,
    TenantModuleSubscription,
)
from futebol.modules import MODULE_CATALOG
from futebol.services.ai import seed_demo_ai_stack
from futebol.services.approvals import cast_decision, open_request
from futebol.services.intelligent_coach import generate_match_dossier
from futebol.services.sports_data import import_local_sports_dataset


class Command(BaseCommand):
    help = 'Cria um tenant demo completo para testar a SaaS localmente.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant-slug', default='demo-local')
        parser.add_argument('--tenant-name', default='Demo Local')
        parser.add_argument('--password', default='demo1234')
        parser.add_argument('--avai-pilot', action='store_true', help='Cria a experiência piloto Avaí FC.')

    @transaction.atomic
    def handle(self, *args, **options):
        slug = 'avai' if options['avai_pilot'] else options['tenant_slug']
        name = 'Avaí FC' if options['avai_pilot'] else options['tenant_name']
        password = options['password']

        existing_tenant = Tenant.objects.filter(slug=slug).first()
        if existing_tenant:
            self._clear_existing_tenant_data(existing_tenant)
            existing_tenant.delete()
        tenant = Tenant.objects.create(name=name, slug=slug, active=True)
        public_api_key = tenant.rotate_public_api_key()
        if options['avai_pilot']:
            TenantBranding.objects.create(
                tenant=tenant,
                primary_color='#0057b8',
                secondary_color='#003b7a',
                background_color='#031225',
                accent_color='#66b2ff',
                public_title='Avaí FC Intelligence',
                public_subtitle='Operação esportiva white-label do Leão da Ilha',
            )
            for module in MODULE_CATALOG:
                TenantModuleSubscription.objects.create(
                    tenant=tenant,
                    module_code=module['code'],
                    module_name=module['name'],
                    enabled=True,
                    plan_name='Piloto Avaí',
                )

        User = get_user_model()
        users = {
            'admin': self._create_user(User, 'demo_admin', 'Demo Admin', password, is_superuser=True),
            'gestor': self._create_user(User, 'demo_gestor', 'Demo Gestor', password),
            'aprovador': self._create_user(User, 'demo_aprovador', 'Demo Aprovador', password),
            'auditor': self._create_user(User, 'demo_auditor', 'Demo Auditor', password),
        }

        for user, role in (
            (users['gestor'], TenantMembership.Role.GESTOR_CLUBE),
            (users['aprovador'], TenantMembership.Role.APROVADOR),
            (users['auditor'], TenantMembership.Role.AUDITOR),
            (users['admin'], TenantMembership.Role.ADMIN_TENANT),
        ):
            TenantMembership.objects.update_or_create(
                user=user,
                tenant=tenant,
                role=role,
                defaults={'active': True},
            )

        clubs = {
            'aurora': Club.objects.create(
                tenant=tenant,
                name='Aurora FC',
                slug='aurora-fc',
                registration_code='AUR-001',
                city='São Paulo',
                state='SP',
            ),
            'horizonte': Club.objects.create(
                tenant=tenant,
                name='Horizonte EC',
                slug='horizonte-ec',
                registration_code='HOR-002',
                city='Campinas',
                state='SP',
            ),
            'escola': Club.objects.create(
                tenant=tenant,
                name='Clube Escola',
                slug='clube-escola',
                registration_code='ESC-003',
                city='Santos',
                state='SP',
            ),
        }

        TeamCategory.objects.create(
            tenant=tenant,
            club=clubs['aurora'],
            name='Sub-17',
            age_min=15,
            age_max=17,
        )

        people = {
            'joao': Person.objects.create(tenant=tenant, full_name='João Atacante', kind=Person.Kind.ATHLETE, birth_date=date(2007, 5, 14)),
            'pedro': Person.objects.create(tenant=tenant, full_name='Pedro Meio-Campo', kind=Person.Kind.ATHLETE, birth_date=date(2006, 11, 2)),
            'lucas': Person.objects.create(tenant=tenant, full_name='Lucas Zagueiro', kind=Person.Kind.ATHLETE, birth_date=date(2007, 2, 20)),
            'caio': Person.objects.create(tenant=tenant, full_name='Caio Goleiro', kind=Person.Kind.ATHLETE, birth_date=date(2006, 8, 30)),
        }
        extra_people = (
            ('maria', 'Maria Lateral', 'LD'),
            ('bruno', 'Bruno Defensor', 'ZAG'),
            ('diego', 'Diego Defensor', 'ZAG'),
            ('rafael', 'Rafael Lateral', 'LE'),
            ('andre', 'André Volante', 'VOL'),
            ('felipe', 'Felipe Central', 'MC'),
            ('vinicius', 'Vinícius Ponta', 'PD'),
            ('matheus', 'Matheus Ponta', 'PE'),
            ('gabriel', 'Gabriel Centroavante', 'ATA'),
        )
        opponent_people = (
            ('hugo_adv', 'Hugo Guarda-Redes', 'GOL'),
            ('tiago_adv', 'Tiago Lateral', 'LD'),
            ('nando_adv', 'Nando Zagueiro', 'ZAG'),
            ('cesar_adv', 'César Lateral', 'LE'),
            ('otavio_adv', 'Otávio Volante', 'VOL'),
            ('leo_adv', 'Léo Central', 'MC'),
            ('samuel_adv', 'Samuel Armador', 'MEI'),
            ('igor_adv', 'Igor Ponta', 'PD'),
            ('davi_adv', 'Davi Ponta', 'PE'),
            ('heitor_adv', 'Heitor Atacante', 'ATA'),
        )
        for key, full_name, _position in extra_people:
            people[key] = Person.objects.create(
                tenant=tenant, full_name=full_name, kind=Person.Kind.ATHLETE
            )
        for key, full_name, _position in opponent_people:
            people[key] = Person.objects.create(
                tenant=tenant, full_name=full_name, kind=Person.Kind.ATHLETE
            )

        profile_positions = {
            'joao': 'ATA', 'pedro': 'MEI', 'lucas': 'ZAG', 'caio': 'GOL',
            **{key: position for key, _name, position in extra_people},
            **{key: position for key, _name, position in opponent_people},
        }
        for key, position in profile_positions.items():
            AthleteSportProfile.objects.create(
                tenant=tenant,
                player=people[key],
                primary_position=position,
                tactical_roles=['função-base do elenco demo'],
            )

        competition = Competition.objects.create(
            tenant=tenant,
            name='Copa Demo Local',
            slug='copa-demo-local',
            scope=Competition.Scope.TOURNAMENT,
        )
        CompetitionRuleSet.objects.create(
            tenant=tenant,
            competition=competition,
            min_registration_notice_hours=24,
            red_card_suspension_matches=1,
            publish_quorum_percent=60,
            immutability_window_hours=12,
            import_export_max_mb=20,
            import_export_max_rows=1000,
            conflict_policy=CompetitionRuleSet.ConflictPolicy.SKIP,
        )
        edition = CompetitionEdition.objects.create(
            tenant=tenant,
            competition=competition,
            slug='2026',
            name='Edição 2026',
            season_year=2026,
            status=CompetitionEdition.Status.RUNNING,
            published_at=timezone.now(),
        )
        phase = CompetitionPhase.objects.create(
            tenant=tenant,
            edition=edition,
            code='fase-unica',
            name='Fase Única',
            order=1,
            status=CompetitionPhase.Status.ACTIVE,
            starts_at=timezone.now() - timedelta(days=10),
            ends_at=timezone.now() + timedelta(days=20),
        )

        match = Match.objects.create(
            tenant=tenant,
            phase=phase,
            home_club=clubs['aurora'],
            away_club=clubs['horizonte'],
            reference_code='DEM-2026-001',
            scheduled_at=timezone.now() - timedelta(days=3),
            venue='Estádio Demo',
            status=Match.Status.PLAYED,
            home_score=2,
            away_score=1,
            notes='Jogo-base para validar lineup, eventos e relatórios locais.',
        )
        future_match = Match.objects.create(
            tenant=tenant,
            phase=phase,
            home_club=clubs['aurora'],
            away_club=clubs['horizonte'],
            reference_code='DEM-2026-COACH-001',
            scheduled_at=timezone.now() + timedelta(days=5),
            venue='Estádio Demo',
            status=Match.Status.CONFIRMED,
            notes='Próxima partida para o Treinador Inteligente.',
        )

        MatchLineup.objects.create(tenant=tenant, match=match, player=people['joao'], club=clubs['aurora'], jersey_number=9, position='ATA', is_starter=True, captain=False)
        MatchLineup.objects.create(tenant=tenant, match=match, player=people['pedro'], club=clubs['aurora'], jersey_number=8, position='MEI', is_starter=True, captain=True)
        MatchLineup.objects.create(tenant=tenant, match=match, player=people['caio'], club=clubs['aurora'], jersey_number=1, position='GOL', is_starter=True, captain=False)
        MatchLineup.objects.create(tenant=tenant, match=match, player=people['lucas'], club=clubs['horizonte'], jersey_number=4, position='ZAG', is_starter=True, captain=False)
        for number, (key, _name, position) in enumerate(opponent_people, start=1):
            MatchLineup.objects.create(
                tenant=tenant,
                match=match,
                player=people[key],
                club=clubs['horizonte'],
                jersey_number=number,
                position=position,
                is_starter=True,
                captain=(position == 'MC'),
            )

        MatchEvent.objects.create(tenant=tenant, match=match, player=people['joao'], event_type=MatchEvent.EventType.GOAL, minute=14, period='1º tempo', details={'assist': 'Pedro Meio-Campo'})
        MatchEvent.objects.create(tenant=tenant, match=match, player=people['pedro'], event_type=MatchEvent.EventType.YELLOW_CARD, minute=52, period='2º tempo', details={'reason': 'Entrada atrasada'})

        Contract.objects.create(
            tenant=tenant,
            person=people['joao'],
            club=clubs['aurora'],
            start_date=date(2025, 7, 1),
            signed_at=timezone.now() - timedelta(days=90),
            status=Contract.Status.ACTIVE,
        )
        Contract.objects.create(
            tenant=tenant,
            person=people['caio'],
            club=clubs['aurora'],
            start_date=date(2025, 7, 1),
            signed_at=timezone.now() - timedelta(days=90),
            status=Contract.Status.ACTIVE,
        )
        for key, _full_name, _position in extra_people:
            Contract.objects.create(
                tenant=tenant,
                person=people[key],
                club=clubs['aurora'],
                start_date=date(2025, 8, 1),
                signed_at=timezone.now() - timedelta(days=45),
                status=Contract.Status.ACTIVE,
            )
        AthleteMatchAvailability.objects.create(
            tenant=tenant,
            match=future_match,
            player=people['vinicius'],
            club=clubs['aurora'],
            status=AthleteMatchAvailability.Status.LIMITED,
            max_minutes=60,
            readiness=72,
            note='Carga controlada no cenário demonstrativo.',
        )
        draft_contract = Contract.objects.create(
            tenant=tenant,
            person=people['lucas'],
            club=clubs['escola'],
            start_date=date(2026, 1, 10),
            status=Contract.Status.DRAFT,
        )

        transfer_flow = ApprovalFlow.objects.create(
            tenant=tenant,
            code='transferencia-demo',
            name='Transferência demo',
            target_kind=ApprovalFlow.TargetKind.TRANSFERENCIA,
            active=True,
        )
        transfer_step = ApprovalFlowStep.objects.create(
            tenant=tenant,
            flow=transfer_flow,
            order=1,
            required_role=TenantMembership.Role.GESTOR_CLUBE,
            requires_evidence=True,
        )

        Contract.objects.create(
            tenant=tenant,
            person=people['pedro'],
            club=clubs['aurora'],
            start_date=date(2025, 8, 1),
            signed_at=timezone.now() - timedelta(days=60),
            status=Contract.Status.ACTIVE,
        )
        negotiation = Negotiation.objects.create(
            tenant=tenant,
            club=clubs['horizonte'],
            person=people['pedro'],
            status=Negotiation.Status.OPEN,
        )
        Evidence.objects.create(
            tenant=tenant,
            content_type=ContentType.objects.get_for_model(Negotiation),
            object_id=str(negotiation.pk),
            uploaded_by=users['admin'],
            note='Análise tática local para a transferência de teste.',
            url='https://example.com/evidencia-demo',
        )
        transfer_request = open_request(negotiation, users['admin'], reason='Abrir caso de transferência para teste local')
        cast_decision(transfer_request, transfer_step, users['gestor'], 'approved', note='Aprovado no seed local')

        contract_flow = ApprovalFlow.objects.create(
            tenant=tenant,
            code='contrato-demo',
            name='Contrato demo',
            target_kind=ApprovalFlow.TargetKind.CONTRATO,
            active=True,
        )
        ApprovalFlowStep.objects.create(
            tenant=tenant,
            flow=contract_flow,
            order=1,
            required_role=TenantMembership.Role.APROVADOR,
            requires_evidence=False,
        )
        contract_request = open_request(draft_contract, users['admin'], reason='Contrato para testar fila de aprovação')

        external_system = ExternalSystem.objects.create(
            tenant=tenant,
            name='Sistema Estatístico Demo',
            kind=ExternalSystem.Kind.IMPORT,
            base_url='https://stats.example.com',
        )
        IntegrationRecord.objects.create(
            tenant=tenant,
            external_system=external_system,
            correlation_id='demo-import-001',
            external_object_id='match-001',
            payload={'source': 'demo', 'kind': 'match', 'reference_code': match.reference_code},
            status='received',
        )

        seed_demo_ai_stack(tenant=tenant, root=Path(settings.BASE_DIR).parent)
        import_local_sports_dataset(
            tenant=tenant,
            dataset_slug='demo-treinador-sintetico-v1',
            imported_by=users['admin'],
            root=Path(settings.BASE_DIR) / 'futebol' / 'data' / 'sports',
        )
        generate_match_dossier(
            match=future_match,
            club=clubs['aurora'],
            requested_by=users['admin'],
        )

        self.stdout.write(self.style.SUCCESS('Seed demo criado com sucesso.'))
        self.stdout.write(f'Tenant: {tenant.slug}')
        self.stdout.write(f'Chave da API pública: {public_api_key}')
        self.stdout.write('Usuários demo: demo_admin / demo_gestor / demo_aprovador / demo_auditor')
        self.stdout.write(f'Senha padrão: {password}')
        self.stdout.write(f'Match demo: {match.reference_code}')
        self.stdout.write(f'Solicitação de transferência: {transfer_request.pk} — aprovada')
        self.stdout.write(f'Solicitação de contrato: {contract_request.pk} — aberta')

    def _clear_existing_tenant_data(self, tenant):
        model_names = [
            'ApprovalDecision',
            'Evidence',
            'LineupDraftPlayer',
            'LineupDraft',
            'GamePlanPlayer',
            'GamePlan',
            'SpecialistOpinion',
            'MatchDossier',
            'AthleteMatchAvailability',
            'AthleteSportProfile',
            'MatchEvent',
            'MatchLineup',
            'SportsDataRecord',
            'SportsDataImportBatch',
            'SportsDataSource',
            'IntegrationRecord',
            'ApprovalRequest',
            'Match',
            'Contract',
            'Negotiation',
            'CompetitionPhase',
            'CompetitionEdition',
            'CompetitionRuleSet',
            'TeamCategory',
            'ApprovalFlowStep',
            'ApprovalFlow',
            'ExternalSystem',
            'AIAgentSourceLink',
            'AIAgent',
            'AIProvider',
            'KnowledgeSource',
            'TenantModuleSubscription',
            'TenantBranding',
            'Person',
            'Club',
            'TenantMembership',
        ]
        for model_name in model_names:
            model = globals()[model_name]
            model.objects.filter(tenant=tenant).delete()

    def _create_user(self, user_model, username, full_name, password, *, is_superuser=False):
        user, _ = user_model.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@example.com',
                'first_name': full_name.split(' ', 1)[0],
                'last_name': full_name.split(' ', 1)[1] if ' ' in full_name else '',
                'is_staff': True,
                'is_superuser': is_superuser,
                'is_active': True,
            },
        )
        user.email = f'{username}@example.com'
        user.first_name = full_name.split(' ', 1)[0]
        user.last_name = full_name.split(' ', 1)[1] if ' ' in full_name else ''
        user.is_staff = True
        user.is_superuser = is_superuser
        user.is_active = True
        user.set_password(password)
        user.save()
        return user
