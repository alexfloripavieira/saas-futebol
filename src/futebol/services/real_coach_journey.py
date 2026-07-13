"""Prepara uma jornada real e repetível para o Treinador Inteligente.

Este módulo nunca fabrica atletas, contratos ou disponibilidade. O catálogo
global fornece o confronto; os dados privados do tenant determinam se o modo
operacional pode avançar para Dossiê, Plano e Prancheta.
"""

from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from futebol.models import (
    ApprovalFlow, ApprovalRequest, AthleteMatchAvailability, AthleteSportProfile,
    Club, Competition, Contract, Evidence, ExternalSystem, IntegrationRecord,
    LineupDraft, Match, MatchDossier, MatchEvent, MatchLineup, Negotiation, Person,
    SportsDataSource, TeamCategory, TenantMembership,
)
from futebol.services.coach_workspace import materialize_provider_match
from futebol.services.intelligent_coach import eligible_player_count
from futebol.services.sports_catalog import latest_records_for


SYNTHETIC_SOURCE_CODES = frozenset({'demo-treinador-sintetico-v1'})
SEEDED_MATCH_REFERENCES = frozenset({'DEM-2026-001', 'DEM-2026-COACH-001'})
SEEDED_CLUB_CODES = frozenset({'AUR-001', 'HOR-002', 'ESC-003'})
SEEDED_COMPETITION_SLUGS = frozenset({'copa-demo-local'})
SEEDED_FLOW_CODES = frozenset({'transferencia-demo', 'contrato-demo'})
SEEDED_PERSON_NAMES = frozenset({
    'João Atacante', 'Pedro Meio-Campo', 'Lucas Zagueiro', 'Caio Goleiro',
    'Maria Lateral', 'Bruno Defensor', 'Diego Defensor', 'Rafael Lateral',
    'André Volante', 'Felipe Central', 'Vinícius Ponta', 'Matheus Ponta',
    'Gabriel Centroavante', 'Hugo Guarda-Redes', 'Tiago Lateral', 'Nando Zagueiro',
    'César Lateral', 'Otávio Volante', 'Léo Central', 'Samuel Armador',
    'Igor Ponta', 'Davi Ponta', 'Heitor Atacante',
})


@dataclass(frozen=True)
class RealCoachJourneyResult:
    match: Match
    club: object
    opponent: object
    eligible_players: int
    status: str
    removed_sources: int = 0
    removed_dossiers: int = 0
    removed_seed_objects: int = 0

    @property
    def coach_url(self):
        return f'/ia/treinador/?club={self.club.pk}&match={self.match.pk}'


REHEARSAL_FORMATIONS = (
    {
        'code': 'balanced', 'label': 'Equilibrado', 'formation': '4-3-3',
        'summary': 'Controle do centro, amplitude e cobertura equilibrada.',
    },
    {
        'code': 'offensive', 'label': 'Ofensivo', 'formation': '4-2-3-1',
        'summary': 'Mais presença entrelinhas e pressão após a perda.',
    },
    {
        'code': 'conservative', 'label': 'Conservador', 'formation': '5-3-2',
        'summary': 'Proteção central e saída por transições controladas.',
    },
)

REHEARSAL_POSITIONS = (
    (8, 50), (24, 14), (22, 38), (22, 62), (24, 86),
    (48, 30), (52, 50), (48, 70), (78, 18), (86, 50), (78, 82),
)


def public_squad_players(*, tenant, club):
    """Retorna perfis públicos para ensaio, sem projetá-los como ``Person``."""
    registration_code = club.registration_code or ''
    if not registration_code.startswith('football-data:'):
        return []
    team_id = registration_code.split(':', 1)[1]
    now = timezone.now()
    if club.tenant_id != tenant.pk:
        raise ValidationError('O time do ensaio precisa pertencer ao tenant ativo.')
    records = latest_records_for(
        tenant, provider_code='football-data-org', capability='player_profile',
        valid_at=now,
    ).filter(
        payload__provider_team_id=team_id,
    ).select_related('batch').order_by(
        '-batch__published_at', '-observed_at', 'provider_record_id',
    )
    players = []
    seen = set()
    for record in records:
        player_id = str((record.payload or {}).get('provider_player_id') or '')
        name = str((record.payload or {}).get('name') or '').strip()
        if not player_id or not name or player_id in seen:
            continue
        seen.add(player_id)
        players.append({
            'provider_player_id': player_id,
            'name': name,
            'position': (record.payload or {}).get('position') or 'Não informada',
            'nationality': (record.payload or {}).get('nationality') or '',
            'source_record_id': record.provider_record_id,
        })
    return players


def build_public_rehearsal(*, match, club):
    if club.pk not in {match.home_club_id, match.away_club_id}:
        raise ValidationError('O time do ensaio precisa participar da partida.')
    players = public_squad_players(tenant=match.tenant, club=club)
    if len(players) < 11:
        raise ValidationError(
            'O ensaio exige ao menos 11 atletas publicados pelo provider para este time.'
        )
    starters = players[:11]
    plans = []
    for spec in REHEARSAL_FORMATIONS:
        plans.append({
            **spec,
            'players': [
                {**player, 'x': x, 'y': y}
                for player, (x, y) in zip(starters, REHEARSAL_POSITIONS)
            ],
        })
    opponent = match.away_club if club.pk == match.home_club_id else match.home_club
    return {
        'match': match, 'club': club, 'opponent': opponent,
        'players': players, 'plans': plans,
        'source': 'football-data.org',
        'limitations': [
            'Elenco público não confirmado pelo tenant.',
            'Sem contratos, disponibilidade, GPS ou informação médica privada.',
            'Não pode gerar escalação oficial nem decisão operacional.',
        ],
    }


def _is_synthetic_dossier(dossier):
    if dossier.match.reference_code in SEEDED_MATCH_REFERENCES:
        return True
    snapshot = dossier.data_snapshot if isinstance(dossier.data_snapshot, dict) else {}
    sources = snapshot.get('external_sources') or []
    return any(
        isinstance(source, dict) and (
            source.get('code') in SYNTHETIC_SOURCE_CODES
            or source.get('quality') == 'synthetic'
        )
        for source in sources
    )


def _cleanup_synthetic_analysis(*, tenant):
    sources = list(SportsDataSource.objects.filter(
        tenant=tenant, code__in=SYNTHETIC_SOURCE_CODES,
    ))
    dossier_ids = [
        dossier.pk
        for dossier in MatchDossier.objects.filter(tenant=tenant).select_related('match')
        if _is_synthetic_dossier(dossier)
    ]
    LineupDraft.objects.filter(
        tenant=tenant, plan__dossier_id__in=dossier_ids,
    ).delete()
    MatchDossier.objects.filter(tenant=tenant, pk__in=dossier_ids).delete()
    for source in sources:
        source.import_batches.all().delete()
        source.delete()

    # Footprint do seed local: a combinação de marcadores é exata e
    # deliberadamente não alcança cadastros reais sem esses identificadores.
    matches = Match.objects.filter(
        tenant=tenant, reference_code__in=SEEDED_MATCH_REFERENCES,
    )
    match_ids = list(matches.values_list('pk', flat=True))
    clubs = Club.objects.filter(
        tenant=tenant, registration_code__in=SEEDED_CLUB_CODES,
    )
    club_ids = list(clubs.values_list('pk', flat=True))
    people = Person.objects.filter(
        tenant=tenant, full_name__in=SEEDED_PERSON_NAMES,
        sport_profiles__tactical_roles__contains=['função-base do elenco demo'],
    ).distinct()
    person_ids = list(people.values_list('pk', flat=True))
    contracts = Contract.objects.filter(tenant=tenant).filter(
        Q(club_id__in=club_ids) | Q(person_id__in=person_ids)
    )
    negotiations = Negotiation.objects.filter(tenant=tenant).filter(
        Q(club_id__in=club_ids) | Q(person_id__in=person_ids)
    )
    for model, queryset in ((Contract, contracts), (Negotiation, negotiations)):
        object_ids = [str(pk) for pk in queryset.values_list('pk', flat=True)]
        content_type = ContentType.objects.get_for_model(model)
        ApprovalRequest.objects.filter(
            tenant=tenant, content_type=content_type, object_id__in=object_ids,
        ).delete()
        Evidence.objects.filter(
            tenant=tenant, content_type=content_type, object_id__in=object_ids,
        ).delete()
    AthleteMatchAvailability.objects.filter(tenant=tenant, match_id__in=match_ids).delete()
    MatchEvent.objects.filter(tenant=tenant, match_id__in=match_ids).delete()
    MatchLineup.objects.filter(tenant=tenant, match_id__in=match_ids).delete()
    matches.delete()
    negotiations.delete()
    contracts.delete()
    AthleteSportProfile.objects.filter(tenant=tenant, player_id__in=person_ids).delete()
    TeamCategory.objects.filter(tenant=tenant, club_id__in=club_ids).delete()
    Person.objects.filter(tenant=tenant, pk__in=person_ids).delete()
    clubs.delete()
    Competition.objects.filter(
        tenant=tenant, slug__in=SEEDED_COMPETITION_SLUGS,
    ).delete()
    ApprovalFlow.objects.filter(tenant=tenant, code__in=SEEDED_FLOW_CODES).delete()
    IntegrationRecord.objects.filter(
        tenant=tenant, correlation_id='demo-import-001',
    ).delete()
    ExternalSystem.objects.filter(
        tenant=tenant, name='Sistema Estatístico Demo',
    ).delete()
    removed_seed_objects = len(match_ids) + len(club_ids) + len(person_ids)
    return len(sources), len(dossier_ids), removed_seed_objects


def _future_fixture_records(*, tenant, now):
    records = latest_records_for(
        tenant, provider_code='football-data-org', capability='fixtures_results',
        valid_at=now,
    ).select_related('source', 'batch')
    candidates = []
    for record in records:
        scheduled_at = parse_datetime(str((record.payload or {}).get('scheduled_at') or ''))
        if scheduled_at and timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(scheduled_at, timezone.utc)
        if scheduled_at and scheduled_at > now and (record.payload or {}).get('status') in {
            'SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED',
        }:
            candidates.append((scheduled_at, record))
    return [record for _scheduled_at, record in sorted(candidates, key=lambda item: item[0])]


def _choose_fixture(*, tenant, now):
    records = _future_fixture_records(tenant=tenant, now=now)
    if not records:
        raise ValidationError(
            'Nenhuma partida futura e válida está disponível no catálogo global.'
        )
    provider_team_ids = set()
    operational_team_ids = set()
    for club in tenant.clubs.exclude(registration_code=''):
        code = club.registration_code
        if code.startswith('football-data:'):
            team_id = code.split(':', 1)[1]
            provider_team_ids.add(team_id)
            if Contract.objects.filter(
                tenant=tenant, club=club, status=Contract.Status.ACTIVE,
            ).count() >= 11:
                operational_team_ids.add(team_id)
    if operational_team_ids:
        for record in records:
            payload = record.payload or {}
            if operational_team_ids.intersection({
                str(payload.get('home_team_id') or ''),
                str(payload.get('away_team_id') or ''),
            }):
                return record
    # Para apresentação, prefira um confronto que já tenha elenco público.
    squad_counts = {}
    for team_id in latest_records_for(
        tenant, provider_code='football-data-org', capability='player_profile',
        valid_at=now,
    ).values_list('payload__provider_team_id', flat=True):
        squad_counts[str(team_id)] = squad_counts.get(str(team_id), 0) + 1
    squad_team_ids = {
        team_id for team_id, count in squad_counts.items() if count >= 11
    }
    for record in records:
        payload = record.payload or {}
        if squad_team_ids.intersection({
            str(payload.get('home_team_id') or ''),
            str(payload.get('away_team_id') or ''),
        }):
            return record
    if provider_team_ids:
        for record in records:
            payload = record.payload or {}
            if provider_team_ids.intersection({
                str(payload.get('home_team_id') or ''),
                str(payload.get('away_team_id') or ''),
            }):
                return record
    return records[0]


def _journey_status(*, tenant, match, club, eligible_players):
    if eligible_players < 11:
        return 'elenco_real_necessario'
    dossier = MatchDossier.objects.filter(
        tenant=tenant, match=match, analyzed_club=club,
    ).order_by('-version').first()
    if dossier is None:
        return 'pronto_para_dossie'
    drafts = LineupDraft.objects.filter(tenant=tenant, plan__dossier=dossier)
    if drafts.filter(tactical_board__isnull=False).exists():
        return 'prancheta_pronta'
    if drafts.exists():
        return 'plano_aplicado'
    return 'dossie_pronto'


@transaction.atomic
def prepare_real_coach_journey(*, tenant, actor, cleanup_synthetic=False):
    """Limpa análises sintéticas marcadas e projeta uma partida global real.

    ``actor`` explicita quem solicitou a preparação, mas não é usado para
    criar dados de domínio: a jornada continua sujeita às permissões normais.
    """
    if not tenant.active:
        raise ValidationError('O tenant precisa estar ativo para preparar a jornada.')
    if not actor.is_active:
        raise ValidationError('O usuário responsável precisa estar ativo.')
    if not actor.is_superuser and not TenantMembership.objects.filter(
        tenant=tenant, user=actor, active=True,
        role__in=[
            TenantMembership.Role.ADMIN_TENANT,
            TenantMembership.Role.GESTOR_CLUBE,
            TenantMembership.Role.ADMIN_PLATAFORMA,
        ],
    ).exists():
        raise ValidationError('O usuário responsável não pode preparar a jornada do tenant.')
    if cleanup_synthetic:
        removed_sources, removed_dossiers, removed_seed_objects = (
            _cleanup_synthetic_analysis(tenant=tenant)
        )
    else:
        removed_sources = removed_dossiers = removed_seed_objects = 0
    record = _choose_fixture(tenant=tenant, now=timezone.now())
    match = materialize_provider_match(record=record, tenant=tenant)

    home_count = eligible_player_count(match=match, club=match.home_club)
    away_count = eligible_player_count(match=match, club=match.away_club)
    if home_count == away_count and home_count < 11:
        home_public = len(public_squad_players(tenant=tenant, club=match.home_club))
        away_public = len(public_squad_players(tenant=tenant, club=match.away_club))
        club = match.home_club if home_public >= away_public else match.away_club
    else:
        club = match.home_club if home_count >= away_count else match.away_club
    eligible_players = max(home_count, away_count)
    opponent = match.away_club if club.pk == match.home_club_id else match.home_club
    return RealCoachJourneyResult(
        match=match, club=club, opponent=opponent,
        eligible_players=eligible_players,
        status=_journey_status(
            tenant=tenant, match=match, club=club, eligible_players=eligible_players,
        ),
        removed_sources=removed_sources, removed_dossiers=removed_dossiers,
        removed_seed_objects=removed_seed_objects,
    )
