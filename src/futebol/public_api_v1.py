from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Club, Competition, Contract, Match, MatchEvent, Tenant
from .services.public_api import (
    PublicAPIAuthenticationError,
    authenticate_public_api_request,
)


def public_api_endpoint(view_func):
    @wraps(view_func)
    def wrapped(request, tenant_slug, *args, **kwargs):
        tenant = get_object_or_404(Tenant, slug=tenant_slug, active=True)
        try:
            authenticate_public_api_request(request, tenant)
        except PublicAPIAuthenticationError as exc:
            response = JsonResponse({'detail': exc.detail}, status=exc.status_code)
            retry_after = getattr(exc, 'retry_after', None)
            if retry_after:
                response['Retry-After'] = str(retry_after)
            return response
        return view_func(request, tenant, *args, **kwargs)

    return wrapped


def _match_payload(match):
    return {
        'reference_code': match.reference_code,
        'competition': match.phase.edition.competition.name,
        'competition_slug': match.phase.edition.competition.slug,
        'edition': match.phase.edition.name,
        'phase': match.phase.name,
        'home_club': match.home_club.name,
        'away_club': match.away_club.name,
        'status': match.get_status_display(),
        'status_code': match.status,
        'score': None if match.home_score is None or match.away_score is None else {
            'home': match.home_score,
            'away': match.away_score,
        },
        'scheduled_at': match.scheduled_at.strftime('%Y-%m-%dT%H:%M:%S'),
        'venue': match.venue,
    }


def _matches(tenant):
    return Match.objects.filter(tenant=tenant).select_related(
        'phase', 'phase__edition', 'phase__edition__competition', 'home_club', 'away_club',
    )


@public_api_endpoint
def overview(request, tenant):
    matches = _matches(tenant)
    events = MatchEvent.objects.filter(tenant=tenant).select_related('match', 'player')
    contracts = Contract.objects.filter(tenant=tenant)
    return JsonResponse({
        'api_version': 'v1',
        'tenant': {'name': tenant.name, 'slug': tenant.slug},
        'generated_at': timezone.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'summary_cards': [
            {'label': 'Clubes', 'value': Club.objects.filter(tenant=tenant).count()},
            {'label': 'Competições', 'value': Competition.objects.filter(tenant=tenant).count()},
            {'label': 'Partidas', 'value': matches.count()},
            {'label': 'Partidas disputadas', 'value': matches.filter(status=Match.Status.PLAYED).count()},
            {'label': 'Gols registrados', 'value': events.filter(event_type=MatchEvent.EventType.GOAL).count()},
            {'label': 'Contratos ativos', 'value': contracts.filter(status=Contract.Status.ACTIVE).count()},
        ],
        'recent_matches': [_match_payload(match) for match in matches[:5]],
    })


@public_api_endpoint
def matches(request, tenant):
    queryset = _matches(tenant).order_by('-scheduled_at')
    competition_slug = request.GET.get('competition')
    status = request.GET.get('status')
    if competition_slug:
        queryset = queryset.filter(phase__edition__competition__slug=competition_slug)
    if status:
        queryset = queryset.filter(status=status)
    return JsonResponse({
        'api_version': 'v1',
        'tenant': {'name': tenant.name, 'slug': tenant.slug},
        'generated_at': timezone.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'count': queryset.count(),
        'results': [_match_payload(match) for match in queryset[:50]],
    })
