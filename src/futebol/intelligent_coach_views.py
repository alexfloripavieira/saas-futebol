from functools import wraps
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseNotAllowed
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from futebol.models import (
    AIAgent, AIProvider, Club, Contract, GamePlan, LineupDraft, Match, MatchDossier,
    SpecialistOpinion, SportsDataImportBatch,
    TacticalBoard, TacticalBoardVersion,
)
from futebol.modules import tenant_has_module
from futebol.services.intelligent_coach import (
    apply_game_plan_as_draft,
    eligible_player_count,
    generate_match_dossier,
    review_lineup_draft,
)
from futebol.services.real_coach_journey import (
    SEEDED_MATCH_REFERENCES, build_public_rehearsal, public_squad_players,
)
from futebol.services.sports_catalog import latest_records_for
from futebol.services.tenancy import active_tenant
from futebol.services.tactical_board import (
    get_or_create_board, restore_board_version, save_and_publish_board, save_board,
)


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
    clubs = list(
        Club.objects.filter(tenant=tenant, active=True)
        .order_by('name')
    )
    selected_club = None
    requested_club_id = request.GET.get('club')
    if requested_club_id:
        selected_club = next(
            (club for club in clubs if str(club.pk) == requested_club_id), None,
        )
    if selected_club is None:
        selected_club = next(
            (club for club in clubs if club.registration_code.startswith('football-data:')),
            None,
        )
    if selected_club is None:
        selected_club = next(
            (
                club for club in clubs
                if Contract.objects.filter(
                    tenant=tenant, club=club, status=Contract.Status.ACTIVE,
                ).exists()
            ),
            clubs[0] if clubs else None,
        )
    match_filters = Q()
    if selected_club:
        match_filters = Q(home_club=selected_club) | Q(away_club=selected_club)
    matches = list(
        Match.objects.filter(
            match_filters,
            tenant=tenant,
            scheduled_at__gte=timezone.now(),
            status__in=[Match.Status.SCHEDULED, Match.Status.CONFIRMED],
        )
        .exclude(reference_code__in=SEEDED_MATCH_REFERENCES)
        .select_related(
            'home_club', 'away_club', 'phase', 'phase__edition', 'phase__edition__competition'
        )
        .order_by('scheduled_at')[:12]
    )
    requested_match_id = request.GET.get('match')
    if requested_match_id:
        matches.sort(key=lambda item: str(item.pk) != requested_match_id)
    latest_by_match = {}
    for dossier in MatchDossier.objects.filter(
        tenant=tenant, match__in=matches, analyzed_club=selected_club,
    ).select_related('analyzed_club').order_by('match_id', '-version'):
        latest_by_match.setdefault(dossier.match_id, dossier)
    public_squad_count = (
        len(public_squad_players(tenant=tenant, club=selected_club))
        if selected_club else 0
    )
    rows = [
        {
            'match': match,
            'dossier': latest_by_match.get(match.pk),
            'club': selected_club,
            'opponent': (
                match.away_club if match.home_club_id == selected_club.pk else match.home_club
            ),
            'eligible_player_count': eligible_player_count(match=match, club=selected_club),
            'public_squad_count': public_squad_count,
        }
        for match in matches
    ]
    global_lab_record = latest_records_for(
        tenant, provider_code='statsbomb-open', capability='event_stream',
    ).select_related('batch').order_by('-batch__published_at').first()
    return render(request, 'futebol/intelligent_coach_center.html', {
        'title': 'Treinador Inteligente',
        'subtitle': 'Do dado disponível à decisão da comissão técnica',
        'clubs': clubs,
        'selected_club': selected_club,
        'active_roster_count': rows[0]['eligible_player_count'] if rows else 0,
        'played_match_count': Match.objects.filter(
            Q(home_club=selected_club) | Q(away_club=selected_club),
            tenant=tenant, status=Match.Status.PLAYED,
        ).count() if selected_club else 0,
        'provider_count': AIProvider.objects.filter(tenant=tenant, active=True).count(),
        'agent_count': AIAgent.objects.filter(tenant=tenant, active=True).count(),
        'provider_was_used': SpecialistOpinion.objects.filter(
            tenant=tenant,
            dossier__analyzed_club=selected_club,
            execution_mode=SpecialistOpinion.ExecutionMode.PROVIDER,
        ).exists() if selected_club else False,
        'rows': rows,
        'operational_ready': bool(rows and rows[0]['eligible_player_count'] >= 11),
        'global_lab_batch': global_lab_record.batch if global_lab_record else None,
        'tracking_batch': SportsDataImportBatch.objects.filter(
            tenant=tenant, source__code='skillcorner-open',
            artifacts__capability='tracking_frames', artifacts__status='ready',
            status=SportsDataImportBatch.Status.COMPLETED,
        ).order_by('-imported_at').first(),
    })


@login_required
@intelligent_coach_module_required
def intelligent_coach_public_rehearsal(request, pk):
    tenant = active_tenant(request)
    match = get_object_or_404(
        Match.objects.select_related('home_club', 'away_club', 'phase__edition__competition'),
        tenant=tenant, pk=pk,
    )
    club = get_object_or_404(Club, tenant=tenant, pk=request.GET.get('club'))
    try:
        rehearsal = build_public_rehearsal(match=match, club=club)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect(f'{reverse("intelligent-coach-center")}?club={club.pk}&match={match.pk}')
    return render(request, 'futebol/intelligent_coach_public_rehearsal.html', {
        'title': 'Ensaio com elenco público',
        'subtitle': str(match),
        'rehearsal': rehearsal,
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


@login_required
@intelligent_coach_module_required
def intelligent_coach_board_open(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    tenant = active_tenant(request)
    draft = get_object_or_404(
        LineupDraft.objects.prefetch_related('players'), tenant=tenant, pk=pk,
    )
    try:
        board = get_or_create_board(draft=draft, actor=request.user)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('intelligent-coach-draft', pk=draft.pk)
    return redirect('intelligent-coach-board', pk=board.pk)


@login_required
@intelligent_coach_module_required
def intelligent_coach_board(request, pk):
    tenant = active_tenant(request)
    board = get_object_or_404(
        TacticalBoard.objects.select_related(
            'draft', 'draft__plan', 'draft__match', 'draft__club', 'updated_by',
        ).prefetch_related('draft__players', 'draft__players__player', 'versions'),
        tenant=tenant, pk=pk,
    )
    return render(request, 'futebol/intelligent_coach_board.html', {
        'title': 'Prancheta tática', 'subtitle': str(board.draft.match),
        'board': board, 'draft': board.draft,
        'players': board.draft.players.select_related('player').all(),
        'player_labels': {
            str(item.player_id): {
                'name': item.player.full_name, 'position': item.position,
            }
            for item in board.draft.players.select_related('player').all()
        },
        'versions': board.versions.select_related('created_by').all(),
    })


@login_required
@intelligent_coach_module_required
def intelligent_coach_board_save(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    tenant = active_tenant(request)
    board = get_object_or_404(TacticalBoard, tenant=tenant, pk=pk)
    try:
        document = json.loads(request.POST.get('document') or '{}')
        save_board(
            board=board, document=document,
            expected_revision=int(request.POST.get('expected_revision') or 0),
            actor=request.user,
        )
        messages.success(request, 'Prancheta salva como estado editável.')
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Documento da prancheta inválido.'
        messages.error(request, message)
    return redirect('intelligent-coach-board', pk=board.pk)


@login_required
@intelligent_coach_module_required
def intelligent_coach_board_publish(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    tenant = active_tenant(request)
    board = get_object_or_404(TacticalBoard, tenant=tenant, pk=pk)
    try:
        document = json.loads(request.POST.get('document') or '{}')
        version = save_and_publish_board(
            board=board, document=document,
            expected_revision=int(request.POST.get('expected_revision') or 0), actor=request.user,
            change_note=request.POST.get('change_note', ''),
        )
        if getattr(version, 'already_existed', False):
            messages.info(request, f'O mesmo conteúdo já estava preservado na versão v{version.version}.')
        else:
            messages.success(request, f'Versão imutável v{version.version} criada.')
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Documento da prancheta inválido.'
        messages.error(request, message)
    return redirect('intelligent-coach-board', pk=board.pk)


@login_required
@intelligent_coach_module_required
def intelligent_coach_board_restore(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    tenant = active_tenant(request)
    version = get_object_or_404(
        TacticalBoardVersion.objects.select_related('board'), tenant=tenant, pk=pk,
    )
    try:
        restore_board_version(
            version=version, actor=request.user,
            expected_revision=int(request.POST.get('expected_revision') or 0),
        )
        messages.success(request, f'Versão v{version.version} restaurada como novo estado editável.')
    except (ValueError, ValidationError) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Revisão inválida.'
        messages.error(request, message)
    return redirect('intelligent-coach-board', pk=version.board_id)
