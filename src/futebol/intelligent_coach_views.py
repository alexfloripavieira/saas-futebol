from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from futebol.models import (
    Club, GamePlan, LineupDraft, Match, MatchDossier, SportsDataImportBatch,
)
from futebol.modules import tenant_has_module
from futebol.services.intelligent_coach import (
    apply_game_plan_as_draft,
    generate_match_dossier,
    review_lineup_draft,
)
from futebol.services.tenancy import active_tenant


def intelligent_coach_module_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        tenant = active_tenant(request)
        if request.user.is_superuser or tenant_has_module(tenant, 'ia'):
            return view_func(request, *args, **kwargs)
        return render(
            request,
            'futebol/module_unavailable.html',
            {'title': 'Módulo não contratado', 'module_name': 'IA'},
            status=403,
        )

    return wrapped


@login_required
@intelligent_coach_module_required
def intelligent_coach_center(request):
    tenant = active_tenant(request)
    matches = list(
        Match.objects.filter(
            tenant=tenant,
            scheduled_at__gte=timezone.now(),
            status__in=[Match.Status.SCHEDULED, Match.Status.CONFIRMED],
        )
        .select_related(
            'home_club', 'away_club', 'phase', 'phase__edition', 'phase__edition__competition'
        )
        .order_by('scheduled_at')[:12]
    )
    latest_by_match = {}
    for dossier in MatchDossier.objects.filter(
        tenant=tenant, match__in=matches
    ).select_related('analyzed_club').order_by('match_id', '-version'):
        latest_by_match.setdefault(dossier.match_id, dossier)
    rows = [
        {
            'match': match,
            'dossier': latest_by_match.get(match.pk),
            'clubs': (match.home_club, match.away_club),
        }
        for match in matches
    ]
    return render(request, 'futebol/intelligent_coach_center.html', {
        'title': 'Treinador Inteligente',
        'subtitle': 'Comissão Técnica Digital orientada por dados e decisão humana',
        'rows': rows,
        'lab_batch': SportsDataImportBatch.objects.filter(
            tenant=tenant, source__code='statsbomb-open',
            quality='research_sample', status=SportsDataImportBatch.Status.COMPLETED,
        ).order_by('-imported_at').first(),
        'tracking_batch': SportsDataImportBatch.objects.filter(
            tenant=tenant, source__code='skillcorner-open',
            artifacts__capability='tracking_frames', artifacts__status='ready',
            status=SportsDataImportBatch.Status.COMPLETED,
        ).order_by('-imported_at').first(),
    })


@login_required
@intelligent_coach_module_required
def intelligent_coach_generate(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    tenant = active_tenant(request)
    match = get_object_or_404(
        Match.objects.select_related('home_club', 'away_club'), tenant=tenant, pk=pk
    )
    club = get_object_or_404(Club, tenant=tenant, pk=request.POST.get('club'))
    try:
        dossier = generate_match_dossier(match=match, club=club, requested_by=request.user)
    except (ValidationError, PermissionDenied) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        messages.error(request, message)
        return redirect('intelligent-coach-center')
    messages.success(request, 'Dossiê e três Planos de Jogo gerados para revisão.')
    return redirect('intelligent-coach-dossier', pk=dossier.pk)


@login_required
@intelligent_coach_module_required
def intelligent_coach_dossier(request, pk):
    tenant = active_tenant(request)
    dossier = get_object_or_404(
        MatchDossier.objects.select_related(
            'match',
            'match__home_club',
            'match__away_club',
            'match__phase',
            'match__phase__edition',
            'match__phase__edition__competition',
            'analyzed_club',
            'generated_by',
        ),
        tenant=tenant,
        pk=pk,
    )
    plans = list(
        dossier.plans.prefetch_related('players', 'players__player').order_by('variant')
    )
    return render(request, 'futebol/intelligent_coach_dossier.html', {
        'title': 'Dossiê da Partida',
        'subtitle': str(dossier.match),
        'dossier': dossier,
        'opinions': dossier.opinions.all(),
        'plans': plans,
        'form_sequence': (
            dossier.data_snapshot.get('external_form')
            or dossier.data_snapshot.get('recent_form', {})
        ).get('sequence', []),
    })


@login_required
@intelligent_coach_module_required
def intelligent_coach_apply_draft(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    tenant = active_tenant(request)
    plan = get_object_or_404(GamePlan.objects.select_related('dossier'), tenant=tenant, pk=pk)
    if request.POST.get('confirm') != 'apply-draft':
        messages.error(
            request,
            'Confirme explicitamente a criação do rascunho antes de aplicar o Plano de Jogo.',
        )
        return redirect('intelligent-coach-dossier', pk=plan.dossier_id)
    try:
        draft = apply_game_plan_as_draft(plan=plan, applied_by=request.user)
    except (ValidationError, PermissionDenied) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        messages.error(request, message)
        return redirect('intelligent-coach-dossier', pk=plan.dossier_id)
    messages.success(request, 'Plano aplicado como rascunho; a escalação oficial não foi alterada.')
    return redirect('intelligent-coach-draft', pk=draft.pk)


@login_required
@intelligent_coach_module_required
def intelligent_coach_draft(request, pk):
    tenant = active_tenant(request)
    draft = get_object_or_404(
        LineupDraft.objects.select_related(
            'plan', 'match', 'match__home_club', 'match__away_club', 'club', 'created_by'
        ).prefetch_related('players', 'players__player'),
        tenant=tenant,
        pk=pk,
    )
    return render(request, 'futebol/intelligent_coach_draft.html', {
        'title': 'Rascunho de escalação',
        'subtitle': str(draft.match),
        'draft': draft,
        'starters': draft.players.filter(is_starter=True),
        'bench': draft.players.filter(is_starter=False),
    })


@login_required
@intelligent_coach_module_required
def intelligent_coach_review_draft(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    tenant = active_tenant(request)
    draft = get_object_or_404(LineupDraft, tenant=tenant, pk=pk)
    try:
        review_lineup_draft(
            draft=draft,
            starter_selection_ids=request.POST.getlist('starters'),
            reviewed_by=request.user,
        )
    except (ValidationError, PermissionDenied) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        messages.error(request, message)
    else:
        messages.success(
            request,
            'Rascunho revisado pela comissão; a escalação oficial continua inalterada.',
        )
    return redirect('intelligent-coach-draft', pk=draft.pk)
