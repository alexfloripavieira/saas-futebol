"""Integra dados normalizados ao fluxo operacional do Treinador Inteligente."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from futebol.models import (
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    CompetitionRuleSet,
    Match,
    SportsDataRecord,
)


PROVIDER_MATCH_STATUS = {
    'SCHEDULED': Match.Status.SCHEDULED,
    'TIMED': Match.Status.CONFIRMED,
    'IN_PLAY': Match.Status.CONFIRMED,
    'PAUSED': Match.Status.CONFIRMED,
    'FINISHED': Match.Status.PLAYED,
    'POSTPONED': Match.Status.POSTPONED,
    'CANCELLED': Match.Status.CANCELLED,
    'SUSPENDED': Match.Status.POSTPONED,
}


def _provider_club(*, tenant, provider_team_id, name):
    if not provider_team_id or not name:
        raise ValidationError('A partida do provider não identifica corretamente os dois clubes.')
    registration_code = f'football-data:{provider_team_id}'
    club = Club.objects.filter(
        tenant=tenant, registration_code=registration_code,
    ).first()
    if club:
        return club
    club = Club.objects.filter(tenant=tenant, name=name).first()
    if club:
        if club.registration_code and club.registration_code != registration_code:
            raise ValidationError(
                f'O clube {name} já está vinculado a outro identificador externo.'
            )
        club.registration_code = registration_code
        club.save(update_fields=['registration_code', 'updated_at'])
        return club
    base_slug = slugify(name)[:145] or f'time-{provider_team_id}'
    slug = base_slug
    if Club.objects.filter(tenant=tenant, slug=slug).exists():
        slug = f'{base_slug[:140]}-{provider_team_id}'
    return Club.objects.create(
        tenant=tenant,
        name=name,
        slug=slug,
        registration_code=registration_code,
    )


@transaction.atomic
def materialize_provider_match(*, record):
    """Cria o confronto operacional a partir de um registro normalizado e auditável.

    O registro esportivo permanece como fonte de verdade externa. A referência do
    provider torna a operação idempotente sem introduzir uma tabela paralela.
    """
    if record.capability != 'fixtures_results':
        raise ValidationError('Somente registros de partidas podem ser preparados no Treinador.')
    if record.source.code != 'football-data-org':
        raise ValidationError('Esta integração aceita partidas normalizadas do football-data.org.')
    payload = record.payload or {}
    provider_match_id = str(payload.get('provider_match_id') or '').strip()
    scheduled_at = parse_datetime(payload.get('scheduled_at') or '')
    if not provider_match_id or scheduled_at is None:
        raise ValidationError('A partida do provider não possui identificador e data válidos.')
    if timezone.is_naive(scheduled_at):
        scheduled_at = timezone.make_aware(scheduled_at, timezone.utc)

    tenant = record.tenant
    reference_code = f'FD-{provider_match_id}'
    home_club = _provider_club(
        tenant=tenant,
        provider_team_id=str(payload.get('home_team_id') or ''),
        name=(payload.get('home_team') or '').strip(),
    )
    away_club = _provider_club(
        tenant=tenant,
        provider_team_id=str(payload.get('away_team_id') or ''),
        name=(payload.get('away_team') or '').strip(),
    )
    competition_code = str(payload.get('competition_code') or 'BSA').upper()
    competition, _ = Competition.objects.get_or_create(
        tenant=tenant,
        slug=f'football-data-{competition_code.lower()}',
        defaults={
            'name': 'Campeonato Brasileiro — dados básicos do provider',
            'scope': Competition.Scope.CHAMPIONSHIP,
        },
    )
    if competition.name == 'Campeonato Brasileiro — dados oficiais do provider':
        competition.name = 'Campeonato Brasileiro — dados básicos do provider'
        competition.save(update_fields=['name', 'updated_at'])
    CompetitionRuleSet.objects.get_or_create(tenant=tenant, competition=competition)
    season_year = scheduled_at.year
    edition, _ = CompetitionEdition.objects.get_or_create(
        tenant=tenant,
        competition=competition,
        season_year=season_year,
        defaults={
            'slug': str(season_year),
            'name': f'Temporada {season_year}',
            'status': CompetitionEdition.Status.RUNNING,
            'published_at': timezone.now(),
        },
    )
    phase, _ = CompetitionPhase.objects.get_or_create(
        tenant=tenant,
        edition=edition,
        code='temporada-regular',
        defaults={
            'name': 'Temporada regular',
            'order': 1,
            'status': CompetitionPhase.Status.ACTIVE,
        },
    )
    score = payload.get('score') or {}
    observed_at = record.observed_at or timezone.now()
    notes = (
        f'Partida integrada do football-data.org; registro {record.provider_record_id}; '
        f'fonte observada em {observed_at.isoformat()}.'
    )
    existing = Match.objects.filter(tenant=tenant, reference_code=reference_code).first()
    if existing:
        existing.home_club = home_club
        existing.away_club = away_club
        existing.scheduled_at = scheduled_at
        existing.status = PROVIDER_MATCH_STATUS.get(
            payload.get('status'), Match.Status.SCHEDULED,
        )
        existing.home_score = score.get('home')
        existing.away_score = score.get('away')
        existing.notes = notes
        existing.save()
        return existing
    return Match.objects.create(
        tenant=tenant,
        phase=phase,
        home_club=home_club,
        away_club=away_club,
        reference_code=reference_code,
        scheduled_at=scheduled_at,
        status=PROVIDER_MATCH_STATUS.get(payload.get('status'), Match.Status.SCHEDULED),
        home_score=score.get('home'),
        away_score=score.get('away'),
        notes=notes,
    )


def refresh_materialized_provider_matches(*, tenant):
    """Atualiza somente partidas já promovidas ao domínio operacional."""
    refreshed = 0
    references = Match.objects.filter(
        tenant=tenant, reference_code__startswith='FD-',
    ).values_list('reference_code', flat=True)
    for reference in references:
        provider_match_id = reference.removeprefix('FD-')
        record = (
            SportsDataRecord.objects.filter(
                tenant=tenant,
                source__code='football-data-org',
                capability='fixtures_results',
                provider_record_id=f'match:{provider_match_id}',
            )
            .select_related('source', 'tenant')
            .order_by('-observed_at', '-created_at')
            .first()
        )
        if record:
            materialize_provider_match(record=record)
            refreshed += 1
    return refreshed
