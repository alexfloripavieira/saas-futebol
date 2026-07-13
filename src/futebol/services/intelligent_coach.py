from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from futebol.models import (
    AthleteMatchAvailability,
    AthleteSportProfile,
    AIAgent,
    Contract,
    GamePlan,
    GamePlanPlayer,
    LineupDraft,
    LineupDraftPlayer,
    Match,
    MatchDossier,
    MatchEvent,
    MatchLineup,
    Person,
    SpecialistOpinion,
    SportsDataRecord,
    TenantMembership,
)
from futebol.services.audit import log_audit_event, snapshot_instance
from futebol.services.sports_catalog import latest_records_for


ALLOWED_MANAGER_ROLES = (
    TenantMembership.Role.ADMIN_TENANT,
    TenantMembership.Role.GESTOR_CLUBE,
    TenantMembership.Role.ADMIN_PLATAFORMA,
)


def _require_manager(user, tenant_id):
    if user.is_superuser:
        return
    if not TenantMembership.objects.filter(
        tenant_id=tenant_id,
        user=user,
        role__in=ALLOWED_MANAGER_ROLES,
        active=True,
        tenant__active=True,
    ).exists():
        raise PermissionDenied('Sem permissão para gerar ou aplicar um Plano de Jogo.')


def _validate_match_club(match, club):
    if match.tenant_id != club.tenant_id:
        raise ValidationError('Partida e clube precisam pertencer ao mesmo tenant.')
    if club.pk not in {match.home_club_id, match.away_club_id}:
        raise ValidationError('O clube analisado precisa participar da partida.')
    if match.scheduled_at <= timezone.now() or match.status not in {
        Match.Status.SCHEDULED,
        Match.Status.CONFIRMED,
    }:
        raise ValidationError('O Dossiê só pode ser gerado para uma partida futura agendada ou confirmada.')


def _record_mentions_club(record, club_names):
    values = {
        str(value).strip().casefold()
        for value in record.payload.values()
        if isinstance(value, str)
    }
    return bool(values.intersection(club_names))


def _external_evidence(match, club):
    opponent = match.away_club if club.pk == match.home_club_id else match.home_club
    club_names = {club.name.casefold(), opponent.name.casefold()}
    global_records = list(
        latest_records_for(
            match.tenant, include_expired=True,
        ).filter(
            source__active=True,
            source__quality__in=(
                'production_primary', 'production_basic', 'licensed_production',
            ),
        ).select_related('source', 'batch')[:100]
    )
    legacy_records = list(
        SportsDataRecord.objects.filter(
            tenant=match.tenant,
            source__active=True,
            # Amostras abertas servem para desenvolver algoritmos, nunca para
            # sustentar silenciosamente uma recomendação comercial ao clube.
            source__quality__in=('production_primary', 'production_basic', 'licensed_production', 'synthetic'),
            batch__status='completed',
        )
        .select_related('source', 'batch')
        .order_by('-observed_at', '-batch__imported_at')[:100]
    )
    records_by_identity = {
        (record.source.code, record.capability, record.provider_record_id): record
        for record in legacy_records
    }
    records_by_identity.update({
        (record.source.code, record.capability, record.provider_record_id): record
        for record in global_records
    })
    records = list(records_by_identity.values())
    relevant = [record for record in records if _record_mentions_club(record, club_names)]
    now = timezone.now()
    valid_records = [
        record for record in relevant if record.expires_at is None or record.expires_at > now
    ]
    expired_records = [
        record for record in relevant if record.expires_at is not None and record.expires_at <= now
    ]

    def serialize_evidence(record, validity):
        return {
            'record_id': record.provider_record_id,
            'capability': record.capability,
            'source_code': record.source.code,
            'source_name': record.source.name,
            'observed_at': record.observed_at.isoformat() if record.observed_at else None,
            'expires_at': record.expires_at.isoformat() if record.expires_at else None,
            'source_url': record.source_url,
            'content_hash': record.content_hash,
            'validity': validity,
        }

    evidence = [serialize_evidence(record, 'valid') for record in valid_records]
    expired_evidence = [serialize_evidence(record, 'expired') for record in expired_records]
    batches = {
        (record.batch._meta.label_lower, record.batch_id): record.batch
        for record in relevant
    }
    def batch_timestamp(batch):
        return getattr(batch, 'published_at', None) or getattr(batch, 'imported_at', None)

    sources = [
        {
            'code': batch.source.code,
            'name': batch.source.name,
            'dataset_version': batch.dataset_version,
            'quality': batch.quality,
            'license_id': batch.license_id,
            'attribution': batch.attribution,
            'imported_at': (
                batch_timestamp(batch).isoformat() if batch_timestamp(batch) else None
            ),
            'age_days': (
                (timezone.now() - batch_timestamp(batch)).days
                if batch_timestamp(batch) else None
            ),
        }
        for batch in sorted(
            batches.values(),
            key=lambda item: batch_timestamp(item) or item.created_at,
            reverse=True,
        )
    ]
    def form_for(team):
        for record in valid_records:
            if (
                record.capability == 'standings_form'
                and str(record.payload.get('team', '')).casefold() == team.name.casefold()
                and isinstance(record.payload.get('recent_points'), list)
            ):
                points = [value for value in record.payload['recent_points'] if value in {0, 1, 3}]
                return {
                    'matches': len(points),
                    'points': sum(points),
                    'sequence': points,
                    'record_id': record.provider_record_id,
                }
        return None

    return evidence, expired_evidence, sources, form_for(club), form_for(opponent)


def _plan_signal(our_form, opponent_form):
    if not our_form or not opponent_form or not our_form['matches'] or not opponent_form['matches']:
        return {
            'summary': ' Sem comparação externa suficiente entre as duas equipes.',
            'attack': [],
            'defense': [],
            'risks': ['Amostra externa comparável insuficiente'],
            'confidence_delta': 0,
        }
    our_ppg = our_form['points'] / our_form['matches']
    opponent_ppg = opponent_form['points'] / opponent_form['matches']
    evidence_risk = (
        'Sinal de amostra externa: '
        f'nosso time {our_ppg:.1f} × adversário {opponent_ppg:.1f} pontos/jogo'
    )
    if opponent_ppg - our_ppg >= 0.75:
        return {
            'summary': (
                ' A amostra externa indica vantagem recente do adversário '
                f'({our_ppg:.1f} × {opponent_ppg:.1f} pontos/jogo).'
            ),
            'attack': ['Controlar o risco antes de aumentar o número de jogadores à frente da bola'],
            'defense': ['Reduzir transições concedidas diante da vantagem recente do adversário'],
            'risks': [evidence_risk],
            'confidence_delta': 5,
        }
    if our_ppg - opponent_ppg >= 0.75:
        return {
            'summary': (
                ' A amostra externa indica vantagem recente do nosso time '
                f'({our_ppg:.1f} × {opponent_ppg:.1f} pontos/jogo).'
            ),
            'attack': ['Sustentar o volume recente sem presumir superioridade espacial'],
            'defense': ['Preservar equilíbrio para não devolver iniciativa em transição'],
            'risks': [evidence_risk],
            'confidence_delta': 5,
        }
    return {
        'summary': (
            ' A forma externa recente é equilibrada '
            f'({our_ppg:.1f} × {opponent_ppg:.1f} pontos/jogo).'
        ),
        'attack': ['Buscar vantagem por execução, pois a forma recente é equilibrada'],
        'defense': ['Evitar assumir superioridade com base apenas na classificação'],
        'risks': [evidence_risk],
        'confidence_delta': 5,
    }


def _eligible_players(match, club):
    match_date = timezone.localtime(match.scheduled_at).date()
    players = list(
        Person.objects.filter(
            tenant=match.tenant,
            kind=Person.Kind.ATHLETE,
            active=True,
            contracts__tenant=match.tenant,
            contracts__club=club,
            contracts__status=Contract.Status.ACTIVE,
            contracts__start_date__lte=match_date,
        )
        .filter(Q(contracts__end_date__isnull=True) | Q(contracts__end_date__gte=match_date))
        .distinct()
        .order_by('full_name')
    )
    availability = {
        item.player_id: item
        for item in AthleteMatchAvailability.objects.filter(
            tenant=match.tenant, match=match, club=club, player__in=players
        )
    }
    eligible = [
        player for player in players
        if availability.get(player.pk, None) is None
        or availability[player.pk].status != AthleteMatchAvailability.Status.UNAVAILABLE
    ]
    return eligible, availability


def _profile_map(tenant, players):
    return {
        profile.player_id: profile
        for profile in AthleteSportProfile.objects.filter(tenant=tenant, player__in=players)
    }


def _recent_form(match, club):
    previous = list(
        Match.objects.filter(tenant=match.tenant, scheduled_at__lt=match.scheduled_at)
        .filter(home_club=club)[:5]
    )
    away_previous = list(
        Match.objects.filter(
            tenant=match.tenant, scheduled_at__lt=match.scheduled_at, away_club=club
        )[:5]
    )
    games = sorted(previous + away_previous, key=lambda item: item.scheduled_at, reverse=True)[:5]
    points = []
    goals_for_total = 0
    goals_against_total = 0
    cards_total = 0
    for game in games:
        if game.home_score is None or game.away_score is None:
            continue
        goals_for = game.home_score if game.home_club_id == club.pk else game.away_score
        goals_against = game.away_score if game.home_club_id == club.pk else game.home_score
        goals_for_total += goals_for
        goals_against_total += goals_against
        cards_total += MatchEvent.objects.filter(
            tenant=match.tenant,
            match=game,
            event_type__in=[MatchEvent.EventType.YELLOW_CARD, MatchEvent.EventType.RED_CARD],
            player__lineups__tenant=match.tenant,
            player__lineups__match=game,
            player__lineups__club=club,
        ).distinct().count()
        points.append(3 if goals_for > goals_against else 1 if goals_for == goals_against else 0)
    return {
        'matches': len(points),
        'points': sum(points),
        'sequence': points,
        'goals_for': goals_for_total,
        'goals_against': goals_against_total,
        'cards': cards_total,
    }


def _opinion_specs(*, available_count, limited_count, form, plan_signal):
    insufficient = ['Dados insuficientes para recomendação espacial']
    confidence = 45
    return (
        (
            SpecialistOpinion.Specialty.COORDINATOR,
            'Síntese coordenada da comissão: ' + plan_signal['summary'].strip(),
            [
                'Comparar os três cenários antes da decisão humana',
                (
                    f'Resolver o conflito entre ambição tática e limite físico de {limited_count} atleta(s)'
                    if limited_count
                    else 'Confirmar com a comissão se há restrição física ainda não registrada'
                ),
            ],
            insufficient,
        ),
        (
            SpecialistOpinion.Specialty.TACTICAL,
            'Estruturar o time com distâncias curtas e revisar o comportamento após os primeiros 15 minutos.',
            ['Controlar o centro', 'Evitar afirmar zonas preferenciais sem eventos coordenados'],
            insufficient,
        ),
        (
            SpecialistOpinion.Specialty.PHYSICAL,
            f'{available_count} atletas elegíveis e {limited_count} com limite de minutos registrado.',
            ['Respeitar limites individuais', 'Planejar substituições antes da partida'],
            [],
        ),
        (
            SpecialistOpinion.Specialty.DEFENSE,
            'Priorizar cobertura central e proteção após perda da posse.',
            ['Manter equilíbrio defensivo', 'Definir gatilhos simples de pressão'],
            insufficient,
        ),
        (
            SpecialistOpinion.Specialty.ATTACK,
            'Variar circulação e profundidade sem presumir uma fragilidade espacial do adversário.',
            ['Criar superioridade ao redor da bola', 'Atacar espaço somente após confirmação em campo'],
            insufficient,
        ),
        (
            SpecialistOpinion.Specialty.SCOUT,
            f'Amostra recente: {form["matches"]} partida(s) com {form["points"]} ponto(s).',
            ['Completar observação do adversário', 'Registrar lacunas de cobertura'],
            insufficient,
        ),
        (
            SpecialistOpinion.Specialty.SET_PIECES,
            'Preparar uma rotina ofensiva e uma organização defensiva de baixa complexidade.',
            ['Definir cobradores', 'Confirmar responsabilidades de marcação'],
            insufficient,
        ),
        (
            SpecialistOpinion.Specialty.ENVIRONMENT,
            'Clima, viagem e gramado ainda não foram fornecidos ao Dossiê.',
            ['Revisar condições até a véspera', 'Atualizar logística antes da reunião técnica'],
            ['Fonte ambiental ausente'],
        ),
    ), confidence


PLAN_SPECS = {
    GamePlan.Variant.BALANCED: {
        'formation': '4-3-3',
        'summary': 'Plano equilibrado para controlar o centro e preservar opções de progressão.',
        'attack': ['Circular com paciência', 'Alternar apoio e profundidade'],
        'defense': ['Bloco médio compacto', 'Pressão apenas com cobertura'],
        'transitions': ['Primeiro passe seguro após recuperação'],
        'set_pieces': ['Uma rotina curta e uma direta'],
        'risk': 'moderado',
    },
    GamePlan.Variant.OFFENSIVE: {
        'formation': '4-2-3-1',
        'summary': 'Plano ofensivo para aumentar presença entrelinhas e pressão pós-perda.',
        'attack': ['Ocupar entrelinhas', 'Aproximar extremos e meia'],
        'defense': ['Pressão pós-perda com cobertura dos volantes'],
        'transitions': ['Acelerar quando houver superioridade confirmada'],
        'set_pieces': ['Aumentar presença na área sem perder sobra'],
        'risk': 'alto',
    },
    GamePlan.Variant.CONSERVATIVE: {
        'formation': '5-3-2',
        'summary': 'Plano conservador para proteger o corredor central e reduzir exposição.',
        'attack': ['Saída apoiada quando segura', 'Usar transição com dois atacantes'],
        'defense': ['Linha de cinco sem afundar a intermediária'],
        'transitions': ['Priorizar retenção quando a transição não estiver limpa'],
        'set_pieces': ['Garantir duas coberturas fora da área'],
        'risk': 'baixo',
    },
}


SPECIALTY_AGENT_SLUGS = {
    SpecialistOpinion.Specialty.COORDINATOR: 'coach-coordinator',
    SpecialistOpinion.Specialty.TACTICAL: 'coach-tactical',
    SpecialistOpinion.Specialty.PHYSICAL: 'coach-physical',
    SpecialistOpinion.Specialty.DEFENSE: 'coach-defense',
    SpecialistOpinion.Specialty.ATTACK: 'coach-attack',
    SpecialistOpinion.Specialty.SCOUT: 'coach-scout',
    SpecialistOpinion.Specialty.SET_PIECES: 'coach-set-pieces',
    SpecialistOpinion.Specialty.ENVIRONMENT: 'coach-environment',
}


FORMATION_SLOTS = {
    GamePlan.Variant.BALANCED: (
        ('GOL', 7, 50, ('GOL',)),
        ('LD', 25, 14, ('LD', 'ALA-D')),
        ('ZAG', 23, 38, ('ZAG',)),
        ('ZAG', 23, 62, ('ZAG',)),
        ('LE', 25, 86, ('LE', 'ALA-E')),
        ('VOL', 48, 50, ('VOL',)),
        ('MC', 57, 30, ('MC', 'VOL')),
        ('MEI', 61, 70, ('MEI', 'MC', 'ATA')),
        ('PD', 81, 18, ('PD', 'ATA')),
        ('ATA', 88, 50, ('ATA',)),
        ('PE', 81, 82, ('PE', 'ATA')),
    ),
    GamePlan.Variant.OFFENSIVE: (
        ('GOL', 7, 50, ('GOL',)),
        ('LD', 24, 14, ('LD', 'ALA-D')),
        ('ZAG', 22, 38, ('ZAG',)),
        ('ZAG', 22, 62, ('ZAG',)),
        ('LE', 24, 86, ('LE', 'ALA-E')),
        ('VOL', 46, 38, ('VOL', 'MC')),
        ('MC', 46, 62, ('MC', 'VOL')),
        ('PD', 69, 18, ('PD', 'ATA')),
        ('MEI', 72, 50, ('MEI', 'ATA')),
        ('PE', 69, 82, ('PE', 'ATA')),
        ('ATA', 88, 50, ('ATA',)),
    ),
    GamePlan.Variant.CONSERVATIVE: (
        ('GOL', 7, 50, ('GOL',)),
        ('ALA-D', 26, 10, ('LD', 'PD')),
        ('ZAG', 21, 30, ('ZAG',)),
        ('ZAG', 19, 50, ('ZAG', 'VOL')),
        ('ZAG', 21, 70, ('ZAG', 'VOL')),
        ('ALA-E', 26, 90, ('LE', 'PE')),
        ('VOL', 48, 30, ('VOL', 'MC')),
        ('MC', 52, 50, ('MC', 'MEI')),
        ('MEI', 48, 70, ('MEI', 'MC', 'PD', 'PE')),
        ('ATA', 78, 38, ('ATA', 'PD')),
        ('ATA', 78, 62, ('ATA', 'PE')),
    ),
}


def _assign_slots(players, position_lookup, variant):
    remaining = sorted(players, key=lambda player: player.full_name)
    assignments = []
    for slot_position, x, y, accepted_positions in FORMATION_SLOTS[variant]:
        if not remaining:
            break
        candidate = next(
            (
                player for player in remaining
                if position_lookup.get(player.pk, '') in accepted_positions
            ),
            remaining[0],
        )
        remaining.remove(candidate)
        assignments.append((candidate, slot_position, x, y))
    return assignments, remaining


def _opponent_shape(match, analyzed_club):
    opponent = match.away_club if analyzed_club.pk == match.home_club_id else match.home_club
    latest = (
        MatchLineup.objects.filter(
            tenant=match.tenant,
            club=opponent,
            match__scheduled_at__lt=match.scheduled_at,
        )
        .filter(Q(match__home_club=opponent) | Q(match__away_club=opponent))
        .select_related('match')
        .order_by('-match__scheduled_at')
        .first()
    )
    if latest:
        lineups = list(
            MatchLineup.objects.filter(
                tenant=match.tenant, match_id=latest.match_id, club=opponent
            ).select_related('player').order_by('-is_starter', 'id')
        )
        starters = [lineup.player for lineup in lineups if lineup.is_starter][:11]
        positions = {lineup.player_id: lineup.position for lineup in lineups}
        assignments, _bench = _assign_slots(starters, positions, GamePlan.Variant.BALANCED)
        if assignments:
            return {
                'status': 'observed_lineup',
                'label': f'Última escalação observada ({latest.match.scheduled_at:%d/%m/%Y})',
                'players': [
                    {
                        'name': player.full_name,
                        'position': position,
                        'x': 100 - x,
                        'y': y,
                    }
                    for player, position, x, y in assignments
                ],
            }
    return {
        'status': 'hypothesis',
        'label': 'Hipótese espelhada — escalação recente indisponível',
        'players': [
            {
                'name': 'Hipótese',
                'position': position,
                'x': 100 - x,
                'y': y,
            }
            for position, x, y, _accepted in FORMATION_SLOTS[GamePlan.Variant.BALANCED]
        ],
    }


MINIMUM_LINEUP_PLAYERS = 11


def eligible_player_count(*, match, club):
    players, _availability = _eligible_players(match, club)
    return len(players)


@transaction.atomic
def generate_match_dossier(*, match, club, requested_by):
    match = Match.objects.select_for_update().select_related('home_club', 'away_club').get(
        pk=match.pk
    )
    _validate_match_club(match, club)
    _require_manager(requested_by, match.tenant_id)
    eligible, availability = _eligible_players(match, club)
    if len(eligible) < MINIMUM_LINEUP_PLAYERS:
        raise ValidationError(
            f'O Dossiê exige pelo menos {MINIMUM_LINEUP_PLAYERS} atletas elegíveis para a partida.'
        )
    profiles = _profile_map(match.tenant, eligible)
    form = _recent_form(match, club)
    limited_count = sum(
        1 for item in availability.values()
        if item.status in {AthleteMatchAvailability.Status.LIMITED, AthleteMatchAvailability.Status.DOUBT}
    )
    data_quality = 'limited_no_spatial_data'
    (
        external_evidence,
        expired_external_evidence,
        external_sources,
        external_form,
        opponent_external_form,
    ) = _external_evidence(match, club)
    form_for_analysis = external_form or form
    plan_signal = _plan_signal(external_form, opponent_external_form)
    opponent_shape = _opponent_shape(match, club)
    previous_version = MatchDossier.objects.select_for_update().filter(
        tenant=match.tenant, match=match, analyzed_club=club
    ).aggregate(value=Max('version'))['value'] or 0
    dossier = MatchDossier.objects.create(
        tenant=match.tenant,
        match=match,
        analyzed_club=club,
        version=previous_version + 1,
        generated_by=requested_by,
        generated_at=timezone.now(),
        status=MatchDossier.Status.READY,
        confidence=45,
        data_snapshot={
            'data_quality': data_quality,
            'spatial_coverage': False,
            'available_players': len(eligible),
            'limited_players': limited_count,
            'recent_form': form,
            'external_form': external_form,
            'opponent_external_form': opponent_external_form,
            'external_sources': external_sources,
            'external_evidence': external_evidence,
            'expired_external_evidence': expired_external_evidence,
            'plan_signal': plan_signal,
            'opponent_shape': opponent_shape,
            'availability': [
                {
                    'player_id': player.pk,
                    'status': availability[player.pk].status if player.pk in availability else 'available',
                    'max_minutes': availability[player.pk].max_minutes if player.pk in availability else None,
                }
                for player in eligible
            ],
        },
    )

    opinion_specs, opinion_confidence = _opinion_specs(
        available_count=len(eligible),
        limited_count=limited_count,
        form=form_for_analysis,
        plan_signal=plan_signal,
    )
    internal_evidence = [{
        'kind': 'internal_snapshot',
        'generated_at': dossier.generated_at.isoformat(),
        'description': 'Cadastro, contratos, disponibilidade e partidas do tenant.',
    }]
    specialties_using_external_data = {
        SpecialistOpinion.Specialty.COORDINATOR,
        SpecialistOpinion.Specialty.TACTICAL,
        SpecialistOpinion.Specialty.DEFENSE,
        SpecialistOpinion.Specialty.ATTACK,
        SpecialistOpinion.Specialty.SCOUT,
    }
    for specialty, summary, recommendations, limitations in opinion_specs:
        agent = AIAgent.objects.filter(
            tenant=match.tenant,
            slug=SPECIALTY_AGENT_SLUGS[specialty],
            active=True,
        ).select_related('provider').first()
        SpecialistOpinion.objects.create(
            tenant=match.tenant,
            dossier=dossier,
            agent=agent,
            specialty=specialty,
            summary=summary,
            recommendations=recommendations,
            confidence=opinion_confidence,
            limitations=limitations,
            evidence=(
                internal_evidence + external_evidence
                if specialty in specialties_using_external_data and external_evidence
                else internal_evidence
            ),
            execution_mode=SpecialistOpinion.ExecutionMode.DETERMINISTIC,
            model_name=(agent.model_override or agent.provider.model_name) if agent else '',
        )

    for variant, spec in PLAN_SPECS.items():
        plan = GamePlan.objects.create(
            tenant=match.tenant,
            dossier=dossier,
            variant=variant,
            formation=spec['formation'],
            summary=spec['summary'] + plan_signal['summary'],
            attacking_plan=spec['attack'] + plan_signal['attack'],
            defensive_plan=spec['defense'] + plan_signal['defense'],
            transitions=spec['transitions'],
            set_pieces=spec['set_pieces'],
            risks=[
                f'Risco tático {spec["risk"]}',
                'Dados insuficientes para recomendação espacial',
                *plan_signal['risks'],
            ],
            confidence=45 + plan_signal['confidence_delta'],
        )
        position_lookup = {
            player.pk: profiles[player.pk].primary_position if player.pk in profiles else ''
            for player in eligible
        }
        assignments, bench = _assign_slots(eligible, position_lookup, variant)
        selections = [
            (player, position, x, y, True)
            for player, position, x, y in assignments
        ] + [
            (player, position_lookup.get(player.pk) or 'NI', 5, 95, False)
            for player in bench
        ]
        for index, (player, position, pitch_x, pitch_y, is_starter) in enumerate(
            selections, start=1
        ):
            profile = profiles.get(player.pk)
            player_availability = availability.get(player.pk)
            GamePlanPlayer.objects.create(
                tenant=match.tenant,
                plan=plan,
                player=player,
                club=club,
                position=position,
                pitch_x=pitch_x,
                pitch_y=pitch_y,
                tactical_role=(profile.tactical_roles[0] if profile and profile.tactical_roles else ''),
                is_starter=is_starter,
                order=index,
                rationale='Elegível no snapshot; posição e disponibilidade consideradas.',
                minute_limit=player_availability.max_minutes if player_availability else None,
            )

    log_audit_event(
        tenant=match.tenant,
        actor=requested_by,
        action='create',
        obj=dossier,
        after_state=snapshot_instance(dossier),
    )
    return dossier


@transaction.atomic
def apply_game_plan_as_draft(*, plan, applied_by):
    plan = GamePlan.objects.select_for_update().select_related(
        'dossier', 'dossier__match', 'dossier__analyzed_club'
    ).get(pk=plan.pk)
    _require_manager(applied_by, plan.tenant_id)
    if LineupDraft.objects.filter(plan=plan).exists():
        return LineupDraft.objects.get(plan=plan)

    unavailable_ids = set(
        AthleteMatchAvailability.objects.filter(
            tenant=plan.tenant,
            match=plan.dossier.match,
            club=plan.dossier.analyzed_club,
            status=AthleteMatchAvailability.Status.UNAVAILABLE,
            player_id__in=plan.players.values_list('player_id', flat=True),
        ).values_list('player_id', flat=True)
    )
    if unavailable_ids:
        raise ValidationError('O plano contém atleta que ficou indisponível após a geração.')

    draft = LineupDraft.objects.create(
        tenant=plan.tenant,
        plan=plan,
        match=plan.dossier.match,
        club=plan.dossier.analyzed_club,
        created_by=applied_by,
    )
    for selection in plan.players.select_related('player'):
        LineupDraftPlayer.objects.create(
            tenant=plan.tenant,
            draft=draft,
            player=selection.player,
            position=selection.position,
            pitch_x=selection.pitch_x,
            pitch_y=selection.pitch_y,
            tactical_role=selection.tactical_role,
            is_starter=selection.is_starter,
            order=selection.order,
            rationale=selection.rationale,
            minute_limit=selection.minute_limit,
        )
    log_audit_event(
        tenant=plan.tenant,
        actor=applied_by,
        action='create',
        obj=draft,
        after_state={
            **snapshot_instance(draft),
            'players': list(draft.players.values_list('player_id', flat=True)),
        },
    )
    return draft


@transaction.atomic
def review_lineup_draft(*, draft, starter_selection_ids, reviewed_by):
    draft = LineupDraft.objects.select_for_update().select_related(
        'plan', 'match', 'club'
    ).get(pk=draft.pk)
    _require_manager(reviewed_by, draft.tenant_id)
    selections = list(draft.players.select_for_update().select_related('player'))
    selection_ids = {selection.pk for selection in selections}
    try:
        requested_ids = {int(value) for value in starter_selection_ids}
    except (TypeError, ValueError) as exc:
        raise ValidationError('A seleção de titulares contém um identificador inválido.') from exc
    if not requested_ids.issubset(selection_ids):
        raise ValidationError('A seleção contém atleta que não pertence a este rascunho.')
    required_starters = min(11, len(selections))
    if len(requested_ids) != required_starters:
        raise ValidationError(f'Selecione exatamente {required_starters} titular(es).')

    before_state = {
        **snapshot_instance(draft),
        'starters': [selection.pk for selection in selections if selection.is_starter],
    }
    starter_order = 1
    bench_order = required_starters + 1
    for selection in selections:
        selection.is_starter = selection.pk in requested_ids
        if selection.is_starter:
            selection.order = starter_order
            starter_order += 1
        else:
            selection.order = bench_order
            bench_order += 1
        selection.save(update_fields=['is_starter', 'order', 'updated_at'])
    draft.status = LineupDraft.Status.REVIEWED
    draft.save(update_fields=['status', 'updated_at'])
    log_audit_event(
        tenant=draft.tenant,
        actor=reviewed_by,
        action='update',
        obj=draft,
        before_state=before_state,
        after_state={
            **snapshot_instance(draft),
            'starters': sorted(requested_ids),
        },
    )
    return draft
