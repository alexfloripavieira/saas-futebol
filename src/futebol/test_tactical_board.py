from datetime import timedelta
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from futebol.models import (
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    Contract,
    GamePlan,
    LineupDraft,
    LineupDraftPlayer,
    Match,
    MatchDossier,
    MatchLineup,
    Person,
    TacticalBoardVersion,
    Tenant,
    TenantMembership,
)
from futebol.services.tactical_board import (
    get_or_create_board,
    publish_board_version,
    restore_board_version,
    save_board,
)


User = get_user_model()


class TacticalBoardServiceTests(TestCase):
    """Contrato de persistência da prancheta ligada ao rascunho humano."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Clube da Prancheta', slug='clube-prancheta')
        self.manager = User.objects.create_user('treinador-prancheta', password='senha12345')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.manager,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        self.club = Club.objects.create(tenant=self.tenant, name='Nosso FC', slug='nosso-fc')
        opponent = Club.objects.create(
            tenant=self.tenant, name='Adversário FC', slug='adversario-fc'
        )
        competition = Competition.objects.create(
            tenant=self.tenant, name='Liga da Prancheta', slug='liga-prancheta'
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
            home_club=self.club,
            away_club=opponent,
            reference_code='BOARD-001',
            scheduled_at=timezone.now() + timedelta(days=7),
        )
        dossier = MatchDossier.objects.create(
            tenant=self.tenant,
            match=self.match,
            analyzed_club=self.club,
            generated_by=self.manager,
            data_snapshot={'origin': 'tactical-board-test'},
        )
        plan = GamePlan.objects.create(
            tenant=self.tenant,
            dossier=dossier,
            variant=GamePlan.Variant.BALANCED,
            formation='4-3-3',
            summary='Plano base para a prancheta.',
            attacking_plan=['Atacar com amplitude.'],
            defensive_plan=['Compactar o corredor central.'],
            transitions=['Acelerar após recuperação.'],
            set_pieces=['Bloqueio no primeiro poste.'],
        )
        self.draft = LineupDraft.objects.create(
            tenant=self.tenant,
            plan=plan,
            match=self.match,
            club=self.club,
            created_by=self.manager,
        )
        self.players = []
        for index, coordinates in enumerate(((0, 50), (100, 50)), start=1):
            player = Person.objects.create(
                tenant=self.tenant,
                full_name=f'Atleta da Prancheta {index}',
                kind=Person.Kind.ATHLETE,
            )
            Contract.objects.create(
                tenant=self.tenant,
                person=player,
                club=self.club,
                start_date=timezone.localdate() - timedelta(days=30),
                status=Contract.Status.ACTIVE,
            )
            LineupDraftPlayer.objects.create(
                tenant=self.tenant,
                draft=self.draft,
                player=player,
                position='ATA',
                pitch_x=coordinates[0],
                pitch_y=coordinates[1],
                is_starter=True,
                order=index,
            )
            self.players.append(player)

    def _document(self, elements=None):
        return {'schema_version': 1, 'elements': elements or []}

    def _position(self, player=None, **overrides):
        element = {
            'id': 'position-1',
            'type': 'position',
            'classification': 'recommended',
            'player_id': (player or self.players[0]).pk,
            'x': 25,
            'y': 50,
        }
        element.update(overrides)
        return element

    def test_primeira_prancheta_copia_posicoes_do_rascunho_e_e_idempotente(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        same_board = get_or_create_board(draft=self.draft, actor=self.manager)

        self.assertEqual(same_board.pk, board.pk)
        self.assertEqual(board.revision, 1)
        self.assertEqual(board.document['schema_version'], 1)
        positions = [item for item in board.document['elements'] if item['type'] == 'position']
        self.assertEqual({item['player_id'] for item in positions}, {item.pk for item in self.players})
        self.assertEqual({(item['x'], item['y']) for item in positions}, {(0, 50), (100, 50)})

    def test_aceita_todos_os_tipos_e_classificacoes_controlados(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        elements = [
            self._position(classification='observed'),
            {
                'id': 'arrow-1', 'type': 'arrow', 'classification': 'calculated',
                'x1': 10, 'y1': 20, 'x2': 40, 'y2': 60,
            },
            {
                'id': 'line-1', 'type': 'line', 'classification': 'recommended',
                'x1': 0, 'y1': 100, 'x2': 100, 'y2': 0,
            },
            {
                'id': 'zone-1', 'type': 'zone', 'classification': 'hypothesis',
                'x': 20, 'y': 30, 'width': 40, 'height': 50,
            },
            {
                'id': 'annotation-1', 'type': 'annotation',
                'classification': 'recommended', 'x': 50, 'y': 5, 'text': 'Pressionar aqui',
            },
        ]

        saved = save_board(
            board=board,
            document=self._document(elements),
            expected_revision=board.revision,
            actor=self.manager,
        )

        self.assertEqual(saved.revision, 2)
        self.assertEqual(
            {item['type'] for item in saved.document['elements']},
            {'position', 'arrow', 'line', 'zone', 'annotation'},
        )
        self.assertEqual(
            {item['classification'] for item in saved.document['elements']},
            {'observed', 'calculated', 'recommended', 'hypothesis'},
        )

    def test_rejeita_tipo_ou_classificacao_fora_do_contrato(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        for element in (
            self._position(type='video'),
            self._position(classification='fact'),
        ):
            with self.subTest(element=element):
                with self.assertRaises(ValidationError):
                    save_board(
                        board=board,
                        document=self._document([element]),
                        expected_revision=board.revision,
                        actor=self.manager,
                    )

    def test_rejeita_coordenadas_fora_de_zero_a_cem_e_geometria_incompleta(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        invalid_elements = (
            self._position(x=-1),
            self._position(y=101),
            {
                'id': 'arrow-1', 'type': 'arrow', 'classification': 'recommended',
                'x1': 10, 'y1': 20, 'x2': 40,
            },
            {
                'id': 'zone-1', 'type': 'zone', 'classification': 'hypothesis',
                'x': 80, 'y': 20, 'width': 30, 'height': 10,
            },
        )
        for element in invalid_elements:
            with self.subTest(element=element):
                with self.assertRaises(ValidationError):
                    save_board(
                        board=board,
                        document=self._document([element]),
                        expected_revision=board.revision,
                        actor=self.manager,
                    )

    def test_rejeita_atleta_que_nao_pertence_ao_rascunho(self):
        outsider = Person.objects.create(
            tenant=self.tenant, full_name='Atleta externo', kind=Person.Kind.ATHLETE
        )
        board = get_or_create_board(draft=self.draft, actor=self.manager)

        with self.assertRaises(ValidationError):
            save_board(
                board=board,
                document=self._document([self._position(player=outsider)]),
                expected_revision=board.revision,
                actor=self.manager,
            )

    def test_revision_otimista_impede_sobrescrever_edicao_concorrente(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        stale_revision = board.revision
        save_board(
            board=board,
            document=self._document([self._position(x=30)]),
            expected_revision=stale_revision,
            actor=self.manager,
        )

        with self.assertRaises(ValidationError):
            save_board(
                board=board,
                document=self._document([self._position(x=70)]),
                expected_revision=stale_revision,
                actor=self.manager,
            )
        board.refresh_from_db()
        self.assertEqual(board.document['elements'][0]['x'], 30)

    def test_publicacao_cria_snapshot_que_nao_muda_com_edicoes_posteriores(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        board = save_board(
            board=board,
            document=self._document([self._position(x=30)]),
            expected_revision=board.revision,
            actor=self.manager,
        )
        version = publish_board_version(
            board=board, actor=self.manager, change_note='Primeira ideia'
        )
        original_snapshot = version.document.copy()

        save_board(
            board=board,
            document=self._document([self._position(x=70)]),
            expected_revision=board.revision,
            actor=self.manager,
        )
        version.refresh_from_db()

        self.assertEqual(version.document, original_snapshot)
        self.assertEqual(version.version, 1)
        self.assertEqual(TacticalBoardVersion.objects.filter(board=board).count(), 1)
        version.change_note = 'Tentativa de adulterar o snapshot'
        with self.assertRaisesMessage(ValidationError, 'imutável'):
            version.save()
        with self.assertRaisesMessage(ValidationError, 'imutável'):
            version.delete()

    def test_restaurar_versao_cria_nova_revisao_sem_mutar_snapshot(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        board = save_board(
            board=board,
            document=self._document([self._position(x=20)]),
            expected_revision=board.revision,
            actor=self.manager,
        )
        version = publish_board_version(board=board, actor=self.manager, change_note='Plano A')
        board = save_board(
            board=board,
            document=self._document([self._position(x=80)]),
            expected_revision=board.revision,
            actor=self.manager,
        )

        restored = restore_board_version(
            version=version, actor=self.manager, expected_revision=board.revision
        )

        self.assertEqual(restored.revision, 4)
        self.assertEqual(restored.document, version.document)
        self.assertEqual(version.version, 1)

    def test_isolamento_de_tenant_impede_operar_prancheta_alheia(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        other_tenant = Tenant.objects.create(name='Outro Clube', slug='outro-clube')
        other_user = User.objects.create_user('outro-gestor', password='senha12345')
        TenantMembership.objects.create(
            tenant=other_tenant,
            user=other_user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )

        with self.assertRaises(PermissionDenied):
            save_board(
                board=board,
                document=self._document([self._position()]),
                expected_revision=board.revision,
                actor=other_user,
            )

    def test_usuario_sem_papel_de_gestao_nao_edita_nem_publica(self):
        auditor = User.objects.create_user('auditor-prancheta', password='senha12345')
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=auditor,
            role=TenantMembership.Role.AUDITOR,
        )
        board = get_or_create_board(draft=self.draft, actor=self.manager)

        with self.assertRaises(PermissionDenied):
            save_board(
                board=board,
                document=self._document([self._position()]),
                expected_revision=board.revision,
                actor=auditor,
            )
        with self.assertRaises(PermissionDenied):
            publish_board_version(board=board, actor=auditor)

    def test_editar_publicar_e_restaurar_nao_altera_escalacao_oficial(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        board = save_board(
            board=board,
            document=self._document([self._position(x=75)]),
            expected_revision=board.revision,
            actor=self.manager,
        )
        version = publish_board_version(board=board, actor=self.manager)
        restore_board_version(
            version=version, actor=self.manager, expected_revision=board.revision
        )

        self.assertEqual(MatchLineup.objects.filter(match=self.match).count(), 0)

    def test_jornada_http_abre_editor_salva_e_publica_versao(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('intelligent-coach-board-open', args=[self.draft.pk]),
        )
        board = self.draft.tactical_board
        self.assertRedirects(response, reverse('intelligent-coach-board', args=[board.pk]))
        page = self.client.get(response.url)
        self.assertContains(page, 'Prancheta tática')
        self.assertContains(page, 'Seta')
        self.assertContains(page, 'Zona')

        document = self._document([self._position(x=65)])
        published = self.client.post(
            reverse('intelligent-coach-board-publish', args=[board.pk]),
            {
                'expected_revision': board.revision,
                'document': json.dumps(document),
                'change_note': 'Alternativa de pressão alta',
            },
        )
        self.assertEqual(published.status_code, 302)
        board.refresh_from_db()
        self.assertEqual(board.document['elements'][0]['x'], 65)
        self.assertTrue(board.versions.filter(version=1).exists())
        self.assertEqual(board.versions.get(version=1).document, board.document)

    def test_editor_http_de_outro_tenant_retorna_404(self):
        board = get_or_create_board(draft=self.draft, actor=self.manager)
        other_tenant = Tenant.objects.create(name='Visitante FC', slug='visitante-fc')
        other_user = User.objects.create_user('visitante-board', password='senha12345')
        TenantMembership.objects.create(
            tenant=other_tenant, user=other_user,
            role=TenantMembership.Role.GESTOR_CLUBE,
        )
        self.client.force_login(other_user)

        response = self.client.get(reverse('intelligent-coach-board', args=[board.pk]))

        self.assertEqual(response.status_code, 404)
