from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import OperationalError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.middleware.csrf import get_token


from .forms import (
    AIAgentForm,
    AIAgentRunForm,
    AIProviderForm,
    BIExplorerForm,
    ApprovalRequestForm,
    ClubForm,
    CompetitionForm,
    ContractForm,
    EvidenceForm,
    ExternalSystemForm,
    IntegrationExportForm,
    IntegrationImportForm,
    IntegrationRecordForm,
    KnowledgeSourceForm,
    KnowledgeSourceImportForm,
    MatchForm,
    NegotiationForm,
    NotificationForm,
    OnboardingForm,
    ProposalForm,
)
from .models import (
    AIAgent,
    AIProvider,
    AIAgentSourceLink,
    ApprovalDecision,
    ApprovalFlow,
    ApprovalRequest,
    AuditLog,
    Club,
    Competition,
    CompetitionEdition,
    Contract,
    Evidence,
    ExternalSystem,
    IntegrationRecord,
    KnowledgeSource,
    Match,
    MatchEvent,
    MatchLineup,
    Negotiation,
    Notification,
    Person,
    Proposal,
    Tenant,
    TenantBranding,
    TenantMembership,
    TenantModuleSubscription,
)
from .modules import MODULE_NAMES, tenant_has_module
from .services.ai import import_knowledge_source_from_url, opencode_auth_configured, provider_catalog_rows, run_ai_agent, sync_opencode_provider_credentials
from .services.data_io import export_csv, import_payload
from .services import approvals
from .services.audit import log_audit_event, snapshot_instance
from .services.permissions import require_any_role, user_has_any_role


def _accessible_tenants(user):
    return user.tenant_memberships.filter(active=True, tenant__active=True).values_list('tenant_id', flat=True)


def _primary_tenant(request):
    if request.user.is_superuser:
        tenant_id = request.GET.get('tenant') or request.POST.get('tenant')
        if tenant_id:
            return get_object_or_404(Tenant, pk=tenant_id)
        return Tenant.objects.filter(active=True).first()
    tenant_id = _accessible_tenants(request.user).first()
    if tenant_id is None:
        raise PermissionDenied('O usuário não possui tenant ativo para operar.')
    return get_object_or_404(Tenant, pk=tenant_id)


def _require_roles(request, roles, tenant=None, message='Sem permissão para executar esta ação.'):
    if request.user.is_superuser:
        return
    tenant_id = tenant.pk if tenant is not None else _primary_tenant(request).pk
    require_any_role(request.user, tenant_id, roles, message)


def _module_required(module_code):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            tenant = _primary_tenant(request)
            if tenant_has_module(tenant, module_code):
                return view_func(request, *args, **kwargs)
            module_name = MODULE_NAMES.get(module_code, module_code)
            return render(
                request,
                'futebol/module_unavailable.html',
                {
                    'title': 'Módulo não contratado',
                    'module_name': module_name,
                },
                status=403,
            )

        return wrapped

    return decorator


def _scope_queryset(request, model, *select_related_fields):
    qs = model.objects.all()
    if select_related_fields:
        qs = qs.select_related(*select_related_fields)
    if request.user.is_superuser:
        return qs
    tenant_ids = list(_accessible_tenants(request.user))
    return qs.filter(tenant_id__in=tenant_ids)


def _public_api_authorized(request):
    expected = getattr(settings, 'PUBLIC_API_KEY', '')
    provided = request.headers.get('X-SaaS-Futebol-API-Key') or request.GET.get('api_key', '')
    return bool(expected) and provided == expected


def _public_api_forbidden():
    return JsonResponse({'detail': 'Chave de API inválida ou ausente.'}, status=403)


def _public_api_tenant(tenant_slug):
    return get_object_or_404(Tenant, slug=tenant_slug, active=True)


def _public_api_match_payload(match):
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


def _public_api_event_payload(event):
    return {
        'match': event.match.reference_code,
        'competition': event.match.phase.edition.competition.slug,
        'type': event.get_event_type_display(),
        'type_code': event.event_type,
        'minute': event.minute,
        'period': event.period,
        'player': event.player.full_name if event.player_id else None,
    }


def _public_api_overview_payload(tenant):
    match_qs = Match.objects.filter(tenant=tenant).select_related('phase', 'phase__edition', 'phase__edition__competition', 'home_club', 'away_club')
    contract_qs = Contract.objects.filter(tenant=tenant).select_related('person', 'club')
    event_qs = MatchEvent.objects.filter(tenant=tenant).select_related('match', 'match__phase', 'match__phase__edition', 'match__phase__edition__competition', 'player')
    summary_cards = [
        {'label': 'Clubes', 'value': Club.objects.filter(tenant=tenant).count()},
        {'label': 'Competições', 'value': Competition.objects.filter(tenant=tenant).count()},
        {'label': 'Partidas', 'value': match_qs.count()},
        {'label': 'Partidas disputadas', 'value': match_qs.filter(status=Match.Status.PLAYED).count()},
        {'label': 'Gols registrados', 'value': event_qs.filter(event_type=MatchEvent.EventType.GOAL).count()},
        {'label': 'Contratos ativos', 'value': contract_qs.filter(status=Contract.Status.ACTIVE).count()},
    ]
    recent_matches = [_public_api_match_payload(match) for match in match_qs[:5]]
    recent_events = [_public_api_event_payload(event) for event in event_qs[:5]]
    return {
        'tenant': {'name': tenant.name, 'slug': tenant.slug},
        'generated_at': timezone.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'summary_cards': summary_cards,
        'recent_matches': recent_matches,
        'recent_events': recent_events,
        'endpoints': [
            {'path': f'/api/publica/{tenant.slug}/visao-geral/', 'method': 'GET'},
            {'path': f'/api/publica/{tenant.slug}/partidas/', 'method': 'GET'},
        ],
    }


class TablePage:
    model = None
    template_name = 'futebol/lista.html'
    title = ''
    subtitle = ''
    search_fields = ()
    ordering_map = {}
    default_ordering = 'name'
    columns = ()
    select_related_fields = ('tenant',)
    row_actions = None
    create_url = ''
    create_label = 'Novo registro'
    extra_actions: tuple[dict[str, str], ...] = ()
    empty_message = 'Nenhum registro encontrado.'

    def __init__(self, request):
        self.request = request

    def queryset(self):
        return _scope_queryset(self.request, self.model, *self.select_related_fields)

    def filtered_queryset(self):
        qs = self.queryset()
        q = (self.request.GET.get('q') or '').strip()
        if q and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f'{field}__icontains': q})
            qs = qs.filter(query)
        ordering_key = self.request.GET.get('ordering') or self.default_ordering
        ordering = self.ordering_map.get(ordering_key, self.default_ordering)
        return qs.order_by(ordering, 'id')

    def resolve_value(self, obj, accessor):
        if callable(accessor):
            return accessor(obj)
        value = obj
        for part in accessor.split('.'):
            value = getattr(value, part)
        return value() if callable(value) else value

    def resolve_actions(self, obj):
        if callable(self.row_actions):
            return self.row_actions(self.request, obj)
        return ''

    def context(self):
        objects = self.filtered_queryset()
        paginator = Paginator(objects, 12)
        page_obj = paginator.get_page(self.request.GET.get('page'))
        rows = []
        for obj in page_obj.object_list:
            rows.append({
                'obj': obj,
                'cells': [self.resolve_value(obj, accessor) for _, accessor in self.columns],
                'actions': self.resolve_actions(obj),
            })
        def _ordering_label(key: str) -> str:
            label_map = {
                'name': 'Nome',
                'title': 'Título',
                'kind': 'Tipo',
                'slug': 'Slug',
                'status': 'Status',
                'created_at': 'Criado em',
                'updated_at': 'Atualizado em',
                'scheduled_at': 'Agendado em',
                'requested_at': 'Solicitado em',
                'sent_at': 'Enviado em',
                'occurred_at': 'Ocorrido em',
                'date': 'Data',
                'start_date': 'Início',
                'end_date': 'Fim',
            }
            raw = key.lstrip('-')
            label = label_map.get(raw, raw.replace('_', ' ').title())
            return f'{label} (desc)' if key.startswith('-') else label

        return {
            'title': self.title,
            'subtitle': self.subtitle,
            'page_obj': page_obj,
            'rows': rows,
            'columns': [header for header, _ in self.columns],
            'query': self.request.GET.get('q', ''),
            'ordering': self.request.GET.get('ordering', self.default_ordering),
            'ordering_options': [{'key': key, 'label': _ordering_label(key)} for key in self.ordering_map.keys()],
            'create_url': self.create_url,
            'create_label': self.create_label,
            'extra_actions': list(self.extra_actions),
            'show_actions': bool(self.row_actions),
            'empty_message': self.empty_message,
        }

    def render(self):
        return render(self.request, self.template_name, self.context())


class FormPage:
    template_name = 'futebol/form.html'
    title = ''
    subtitle = ''
    success_url_name = ''
    success_message = 'Salvo com sucesso.'
    invalid_message = 'Corrija os campos destacados e tente novamente.'

    def __init__(self, request, *, form_class, instance=None, extra_context=None, post_save=None):
        self.request = request
        self.form_class = form_class
        self.instance = instance
        self.extra_context = extra_context or {}
        self.post_save = post_save

    def form_kwargs(self):
        kwargs = {'tenant': _primary_tenant(self.request), 'user': self.request.user}
        if self.instance is not None:
            kwargs['instance'] = self.instance
        return kwargs

    def get_form(self):
        if self.request.method == 'POST':
            return self.form_class(self.request.POST, **self.form_kwargs())
        return self.form_class(**self.form_kwargs())

    def get_context(self, form):
        context = {
            'title': self.title,
            'subtitle': self.subtitle,
            'form': form,
            'cancel_url': self.extra_context.get('cancel_url', '/'),
            'page_state': self.extra_context.get('page_state', 'ready'),
        }
        context.update(self.extra_context)
        return context

    def render(self):
        form = self.get_form()
        if self.request.method == 'POST':
            if form.is_valid():
                try:
                    with transaction.atomic():
                        before_state = snapshot_instance(self.instance) if self.instance is not None else {}
                        obj = form.save(commit=False)
                        if hasattr(obj, 'tenant_id') and not obj.tenant_id:
                            obj.tenant = _primary_tenant(self.request)
                        if hasattr(obj, 'requested_by_id') and not obj.requested_by_id:
                            obj.requested_by = self.request.user
                        obj.save()
                        if hasattr(form, 'save_m2m'):
                            form.save_m2m()
                        if self.post_save is not None:
                            self.post_save(form, obj)
                        log_audit_event(
                            tenant=obj.tenant,
                            actor=self.request.user,
                            action='create' if self.instance is None else 'update',
                            obj=obj,
                            before_state=before_state,
                            after_state=snapshot_instance(obj),
                            correlation_id=getattr(self.request, 'request_id', ''),
                        )
                except ValidationError as exc:
                    form.add_error(None, exc)
                    messages.error(self.request, self.invalid_message)
                    return render(self.request, self.template_name, self.get_context(form))
                except Exception as exc:
                    form.add_error(None, str(exc))
                    messages.error(self.request, str(exc))
                    return render(self.request, self.template_name, self.get_context(form))
                messages.success(self.request, self.success_message)
                return redirect(self.success_url_name)
            messages.error(self.request, self.invalid_message)
        return render(self.request, self.template_name, self.get_context(form))


def root_dispatch(request):
    """Ponto de entrada: institucional para visitantes, painel/onboarding para logados."""
    if not request.user.is_authenticated:
        return landing(request)
    if request.user.is_superuser or _accessible_tenants(request.user).exists():
        return redirect('home')
    return redirect('onboarding')


def landing(request):
    """Página institucional pública para visitantes sem acesso ativo."""
    context = {
        'modules': list(MODULE_NAMES.values()),
    }
    return render(request, 'futebol/landing.html', context)


@login_required
def onboarding(request):
    """Onboarding inicial: cria tenant, branding, módulos e o primeiro vínculo."""
    if _accessible_tenants(request.user).exists():
        messages.info(request, 'Você já possui um tenant ativo.')
        return redirect('home')

    if request.method == 'POST':
        form = OnboardingForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                tenant = Tenant.objects.create(name=data['tenant_name'], slug=data['tenant_slug'])
                TenantBranding.objects.create(
                    tenant=tenant,
                    primary_color=data['primary_color'],
                    secondary_color=data['secondary_color'],
                    background_color=data['background_color'],
                    accent_color=data['accent_color'],
                    logo_url=data['logo_url'],
                    favicon_url=data['favicon_url'],
                    symbol_url=data['symbol_url'],
                    public_title=data['public_title'],
                    public_subtitle=data['public_subtitle'] or '',
                )
                for code in data['modules']:
                    TenantModuleSubscription.objects.create(
                        tenant=tenant,
                        module_code=code,
                        module_name=MODULE_NAMES.get(code, code),
                        enabled=True,
                    )
                TenantMembership.objects.create(user=request.user, tenant=tenant, role=data['role'])
            messages.success(request, 'Tenant configurado com sucesso. Bem-vindo à plataforma!')
            return redirect('home')
        messages.error(request, 'Corrija os campos destacados para concluir o onboarding.')
    else:
        form = OnboardingForm()

    context = {
        'title': 'Onboarding do tenant',
        'subtitle': 'Configure o clube, a identidade visual e os módulos contratados.',
        'form': form,
    }
    return render(request, 'futebol/onboarding.html', context)


@login_required
def home(request):
    memberships = request.user.tenant_memberships.select_related('tenant').filter(active=True, tenant__active=True)
    tenant_ids = list(memberships.values_list('tenant_id', flat=True))
    club_count = Club.objects.filter(tenant_id__in=tenant_ids).count()
    competition_count = Competition.objects.filter(tenant_id__in=tenant_ids).count()
    match_count = Match.objects.filter(tenant_id__in=tenant_ids).count()
    approval_count = ApprovalRequest.objects.filter(tenant_id__in=tenant_ids).count()
    notification_count = Notification.objects.filter(tenant_id__in=tenant_ids).count()
    contract_count = Contract.objects.filter(tenant_id__in=tenant_ids).count()
    negotiation_count = Negotiation.objects.filter(tenant_id__in=tenant_ids).count()
    proposal_count = Proposal.objects.filter(tenant_id__in=tenant_ids).count()
    evidence_count = Evidence.objects.filter(tenant_id__in=tenant_ids).count()
    context = {
        'title': 'SaaS do Futebol',
        'subtitle': 'Interface de operação da plataforma',
        'memberships': memberships,
        'primary_role': memberships.first().get_role_display() if memberships.exists() else 'Sem vínculo ativo',
        'club_count': club_count,
        'competition_count': competition_count,
        'match_count': match_count,
        'approval_count': approval_count,
        'notification_count': notification_count,
        'contract_count': contract_count,
        'negotiation_count': negotiation_count,
        'proposal_count': proposal_count,
        'evidence_count': evidence_count,
        'tenant_count': len(tenant_ids),
    }
    return render(request, 'futebol/home.html', context)


@login_required
def club_list(request):
    return _render_club_list(request)


def _render_club_list(request):
    page = TablePage(request)
    page.model = Club
    page.title = 'Clubes'
    page.subtitle = 'Base cadastral dos clubes do tenant'
    page.search_fields = ('name', 'slug', 'city', 'state')
    page.default_ordering = 'name'
    page.ordering_map = {'name': 'name', 'city': 'city', '-name': '-name', '-city': '-city'}
    page.columns = (
        ('Nome', 'name'),
        ('Slug', 'slug'),
        ('Cidade', 'city'),
        ('UF', 'state'),
        ('Ativo', lambda obj: 'Sim' if obj.active else 'Não'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('club-edit', args=[obj.pk]))
    page.create_url = reverse('club-create')
    page.create_label = 'Novo clube'
    page.empty_message = 'Nenhum clube cadastrado ainda. Use o botão Novo clube para começar.'
    return page.render()


@login_required
def club_create(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ])
    return _render_form(request, ClubForm, title='Novo clube', subtitle='Cadastre um clube para a operação', success_url_name='club-list', success_message='Clube criado com sucesso.', cancel_url=reverse('club-list'))


@login_required
def club_edit(request, pk):
    club = _get_visible_object(request, Club, pk)
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ], tenant=club.tenant)
    return _render_form(request, ClubForm, instance=club, title='Editar clube', subtitle='Atualize os dados cadastrais do clube', success_url_name='club-list', success_message='Clube atualizado com sucesso.', cancel_url=reverse('club-list'))


@login_required
def competition_list(request):
    page = TablePage(request)
    page.model = Competition
    page.title = 'Competições'
    page.subtitle = 'Competições, ligas e torneios registrados'
    page.search_fields = ('name', 'slug', 'scope')
    page.default_ordering = 'name'
    page.ordering_map = {'name': 'name', '-name': '-name', 'scope': 'scope', '-scope': '-scope'}
    page.columns = (
        ('Nome', 'name'),
        ('Slug', 'slug'),
        ('Escopo', 'scope'),
        ('Ativa', lambda obj: 'Sim' if obj.active else 'Não'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('competition-edit', args=[obj.pk]))
    page.create_url = reverse('competition-create')
    page.create_label = 'Nova competição'
    page.empty_message = 'Nenhuma competição cadastrada ainda.'
    return page.render()


@login_required
def competition_create(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_competicao',
        'admin_plataforma',
    ])
    return _render_form(request, CompetitionForm, title='Nova competição', subtitle='Cadastre uma liga, copa ou campeonato', success_url_name='competition-list', success_message='Competição criada com sucesso.', cancel_url=reverse('competition-list'))


@login_required
def competition_edit(request, pk):
    competition = _get_visible_object(request, Competition, pk)
    _require_roles(request, [
        'admin_tenant',
        'gestor_competicao',
        'admin_plataforma',
    ], tenant=competition.tenant)
    return _render_form(request, CompetitionForm, instance=competition, title='Editar competição', subtitle='Atualize os dados da competição', success_url_name='competition-list', success_message='Competição atualizada com sucesso.', cancel_url=reverse('competition-list'))


@login_required
def match_list(request):
    page = TablePage(request)
    page.model = Match
    page.title = 'Partidas'
    page.subtitle = 'Agenda e resultados das partidas'
    page.search_fields = ('reference_code', 'home_club__name', 'away_club__name', 'phase__name')
    page.default_ordering = '-scheduled_at'
    page.ordering_map = {'scheduled_at': 'scheduled_at', '-scheduled_at': '-scheduled_at', 'reference_code': 'reference_code', '-reference_code': '-reference_code'}
    page.columns = (
        ('Código', 'reference_code'),
        ('Mandante', 'home_club.name'),
        ('Visitante', 'away_club.name'),
        ('Data', lambda obj: obj.scheduled_at.strftime('%d/%m/%Y %H:%M')),
        ('Status', 'status'),
        ('Placar', lambda obj: '-' if obj.home_score is None or obj.away_score is None else f'{obj.home_score} x {obj.away_score}'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('match-edit', args=[obj.pk]))
    page.create_url = reverse('match-create')
    page.create_label = 'Nova partida'
    page.empty_message = 'Nenhuma partida cadastrada ainda.'
    return page.render()


@login_required
def match_create(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_competicao',
        'delegado_partida',
        'admin_plataforma',
    ])
    return _render_form(request, MatchForm, title='Nova partida', subtitle='Cadastre a programação e o placar da partida', success_url_name='match-list', success_message='Partida criada com sucesso.', cancel_url=reverse('match-list'))


@login_required
def match_edit(request, pk):
    match = _get_visible_object(request, Match, pk)
    _require_roles(request, [
        'admin_tenant',
        'gestor_competicao',
        'delegado_partida',
        'admin_plataforma',
    ], tenant=match.tenant)
    return _render_form(request, MatchForm, instance=match, title='Editar partida', subtitle='Atualize a programação, local ou placar', success_url_name='match-list', success_message='Partida atualizada com sucesso.', cancel_url=reverse('match-list'))


@login_required
@_module_required('aprovacoes')
def approval_flow_list(request):
    page = TablePage(request)
    page.model = ApprovalFlow
    page.title = 'Fluxos de aprovação'
    page.subtitle = 'Regras operacionais para aprovar mudanças críticas'
    page.search_fields = ('name', 'code', 'target_kind')
    page.default_ordering = 'name'
    page.ordering_map = {'name': 'name', '-name': '-name', 'code': 'code', '-code': '-code'}
    page.columns = (
        ('Nome', 'name'),
        ('Código', 'code'),
        ('Tipo de alvo', 'get_target_kind_display'),
        ('Etapas', lambda obj: '—'),
        ('Ativo', lambda obj: 'Sim' if obj.active else 'Não'),
    )
    page.empty_message = 'Nenhum fluxo de aprovação configurado.'
    return page.render()


@login_required
@_module_required('aprovacoes')
def approval_request_list(request):
    page = TablePage(request)
    page.model = ApprovalRequest
    page.select_related_fields = ('tenant', 'flow', 'requested_by')
    page.title = 'Solicitações de aprovação'
    page.subtitle = 'Solicitações abertas e decisões já processadas'
    page.search_fields = ('flow__name', 'flow__code', 'object_id', 'requested_by__username')
    page.default_ordering = '-requested_at'
    page.ordering_map = {'requested_at': 'requested_at', '-requested_at': '-requested_at', 'status': 'status', '-status': '-status'}
    page.columns = (
        ('Fluxo', 'flow.name'),
        ('Solicitante', 'requested_by.username'),
        ('Alvo', lambda obj: f'{obj.content_type.model}#{obj.object_id}'),
        ('Motivo', 'reason'),
        ('Status', 'get_status_display'),
        ('Solicitado em', lambda obj: obj.requested_at.strftime('%d/%m/%Y %H:%M')),
        ('Resolvido em', lambda obj: obj.resolved_at.strftime('%d/%m/%Y %H:%M') if obj.resolved_at else '-'),
    )
    page.row_actions = _approval_request_actions
    page.empty_message = 'Nenhuma solicitação em aberto.'
    page.create_url = reverse('approval-request-create')
    page.create_label = 'Nova solicitação'
    return page.render()


@login_required
@_module_required('aprovacoes')
def approval_request_create(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'gestor_competicao',
        'delegado_partida',
        'admin_plataforma',
    ])
    return _render_form(request, ApprovalRequestForm, title='Nova solicitação de aprovação', subtitle='Registre uma mudança crítica para validação', success_url_name='approval-request-list', success_message='Solicitação criada com sucesso.', cancel_url=reverse('approval-request-list'))


@login_required
@_module_required('aprovacoes')
def notification_list(request):
    page = TablePage(request)
    page.model = Notification
    page.select_related_fields = ('tenant', 'recipient')
    page.title = 'Notificações'
    page.subtitle = 'Mensagens enviadas, pendentes e falhas'
    page.search_fields = ('subject', 'recipient__username', 'channel', 'status')
    page.default_ordering = '-id'
    page.ordering_map = {'id': 'id', '-id': '-id', 'status': 'status', '-status': '-status'}
    page.columns = (
        ('Assunto', 'subject'),
        ('Destinatário', 'recipient.username'),
        ('Canal', 'channel'),
        ('Status', 'status'),
        ('Enviada em', lambda obj: obj.sent_at.strftime('%d/%m/%Y %H:%M') if obj.sent_at else '-'),
    )
    page.row_actions = _notification_actions
    page.empty_message = 'Nenhuma notificação registrada.'
    page.create_url = reverse('notification-create')
    page.create_label = 'Nova notificação'
    return page.render()


@login_required
@_module_required('auditoria')
def audit_log_list(request):
    _require_roles(request, [
        'admin_tenant',
        'auditor_somente_leitura',
        'admin_plataforma',
    ])
    page = TablePage(request)
    page.model = AuditLog
    page.select_related_fields = ('tenant', 'actor', 'content_type')
    page.title = 'Auditoria'
    page.subtitle = 'Trilha de eventos de criação, atualização, aprovação e integração'
    page.search_fields = ('action', 'object_id', 'actor__username', 'content_type__model', 'correlation_id')
    page.default_ordering = '-occurred_at'
    page.ordering_map = {'occurred_at': 'occurred_at', '-occurred_at': '-occurred_at', 'action': 'action', '-action': '-action'}
    page.columns = (
        ('Ação', 'get_action_display'),
        ('Ator', 'actor.username'),
        ('Objeto', lambda obj: f'{obj.content_type.model}#{obj.object_id}'),
        ('Antes', lambda obj: obj.before_state if obj.before_state else '-'),
        ('Depois', lambda obj: obj.after_state if obj.after_state else '-'),
        ('Correlação', 'correlation_id'),
        ('Quando', lambda obj: obj.occurred_at.strftime('%d/%m/%Y %H:%M')),
    )
    page.empty_message = 'Nenhum evento de auditoria registrado ainda.'
    return page.render()


@login_required
@_module_required('aprovacoes')
def notification_create(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    return _render_form(request, NotificationForm, title='Nova notificação', subtitle='Envie uma mensagem operacional para um membro do tenant', success_url_name='notification-list', success_message='Notificação criada com sucesso.', cancel_url=reverse('notification-list'))


@login_required
@_module_required('transferencias')
def transfer_center(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'gestor_competicao',
        'auditor_somente_leitura',
        'admin_plataforma',
    ])
    tenant_ids = [] if request.user.is_superuser else list(_accessible_tenants(request.user))
    scope = {} if request.user.is_superuser else {'tenant_id__in': tenant_ids}
    context = {
        'title': 'Transferências, contratos e evidências',
        'subtitle': 'Central operacional para negociações, contratos e documentação de suporte',
        'sprint_label': 'Transferências, contratos e evidências',
        'contract_count': Contract.objects.filter(**scope).count(),
        'negotiation_count': Negotiation.objects.filter(**scope).count(),
        'proposal_count': Proposal.objects.filter(**scope).count(),
        'evidence_count': Evidence.objects.filter(**scope).count(),
        'actions': [
            {'label': 'Contratos', 'href': reverse('contract-list')},
            {'label': 'Negociações', 'href': reverse('negotiation-list')},
            {'label': 'Propostas', 'href': reverse('proposal-list')},
            {'label': 'Evidências', 'href': reverse('evidence-list')},
        ],
        'sections': [
            {
                'title': 'Contratos',
                'description': 'Cadastro e manutenção do vínculo entre pessoa e clube, com vigência e status.',
                'points': ['Rascunho, ativo e encerrado', 'Datas de início e fim', 'Motivo de encerramento', 'Base para aprovações críticas'],
            },
            {
                'title': 'Negociações e propostas',
                'description': 'Registro das tratativas e dos valores ofertados entre clubes e pessoas.',
                'points': ['Negociação aberta ou encerrada', 'Propostas em rascunho, envio e resposta', 'Histórico por tenant', 'Gancho para decisões de aprovação'],
            },
            {
                'title': 'Evidências',
                'description': 'Documentos, links e observações que comprovam o motivo da decisão.',
                'points': ['Arquivo opcional', 'URL de apoio', 'Observações livres', 'Validação por tenant e alvo'],
            },
        ],
    }
    return render(request, 'futebol/page.html', context)


@login_required
@_module_required('relatorios')
def report_center(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'gestor_competicao',
        'auditor_somente_leitura',
        'admin_plataforma',
    ])
    tenant_ids = [] if request.user.is_superuser else list(_accessible_tenants(request.user))
    scope = {} if request.user.is_superuser else {'tenant_id__in': tenant_ids}

    contract_labels = dict(Contract.Status.choices)
    negotiation_labels = dict(Negotiation.Status.choices)
    proposal_labels = dict(Proposal.Status.choices)
    approval_labels = dict(ApprovalRequest.Status.choices)
    notification_labels = dict(Notification.Status.choices)

    def _breakdown(model, label_map):
        rows = []
        for item in model.objects.filter(**scope).values('status').annotate(total=Count('id')).order_by('status'):
            rows.append({'label': label_map.get(item['status'], item['status']), 'count': item['total']})
        return rows

    recent_approvals = list(
        ApprovalRequest.objects.filter(**scope).select_related('flow', 'content_type', 'requested_by').order_by('-requested_at')[:5]
    )
    recent_audits = list(
        AuditLog.objects.filter(**scope).select_related('content_type', 'actor').order_by('-occurred_at')[:5]
    )
    recent_notifications = list(
        Notification.objects.filter(**scope).select_related('recipient').order_by('-id')[:5]
    )

    context = {
        'title': 'Relatórios e indicadores',
        'subtitle': 'Painel consolidado com volumes, estados operacionais e trilha recente de decisões',
        'sprint_label': 'API pública',
        'summary_cards': [
            {'label': 'Clubes', 'value': Club.objects.filter(**scope).count()},
            {'label': 'Competições', 'value': Competition.objects.filter(**scope).count()},
            {'label': 'Partidas', 'value': Match.objects.filter(**scope).count()},
            {'label': 'Contratos ativos', 'value': Contract.objects.filter(**scope, status=Contract.Status.ACTIVE).count()},
            {'label': 'Solicitações abertas', 'value': ApprovalRequest.objects.filter(**scope, status=ApprovalRequest.Status.OPEN).count()},
            {'label': 'Notificações pendentes', 'value': Notification.objects.filter(**scope, status=Notification.Status.QUEUED).count()},
            {'label': 'Integrações', 'value': ExternalSystem.objects.filter(**scope).count()},
            {'label': 'Registros de integração', 'value': IntegrationRecord.objects.filter(**scope).count()},
        ],
        'actions': [
            {'label': 'Partidas', 'href': reverse('match-list')},
            {'label': 'Solicitações', 'href': reverse('approval-request-list')},
            {'label': 'Integrações', 'href': reverse('integration-hub')},
            {'label': 'BI self-service', 'href': reverse('bi-center')},
            {'label': 'API pública', 'href': reverse('public-api-docs')},
        ],
        'breakdowns': [
            {'title': 'Contratos por status', 'total': Contract.objects.filter(**scope).count(), 'rows': _breakdown(Contract, contract_labels)},
            {'title': 'Negociações por status', 'total': Negotiation.objects.filter(**scope).count(), 'rows': _breakdown(Negotiation, negotiation_labels)},
            {'title': 'Propostas por status', 'total': Proposal.objects.filter(**scope).count(), 'rows': _breakdown(Proposal, proposal_labels)},
            {'title': 'Solicitações por status', 'total': ApprovalRequest.objects.filter(**scope).count(), 'rows': _breakdown(ApprovalRequest, approval_labels)},
            {'title': 'Notificações por status', 'total': Notification.objects.filter(**scope).count(), 'rows': _breakdown(Notification, notification_labels)},
        ],
        'recent_approvals': recent_approvals,
        'recent_audits': recent_audits,
        'recent_notifications': recent_notifications,
    }
    return render(request, 'futebol/report_center.html', context)


@login_required
@_module_required('relatorios')
def bi_center(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'gestor_competicao',
        'auditor_somente_leitura',
        'admin_plataforma',
    ])
    tenant_ids = [] if request.user.is_superuser else list(_accessible_tenants(request.user))
    accessible_tenants = Tenant.objects.filter(active=True) if request.user.is_superuser else Tenant.objects.filter(pk__in=tenant_ids, active=True)
    default_tenant = None
    tenant_param = request.GET.get('tenant')
    if tenant_param:
        default_tenant = accessible_tenants.filter(pk=tenant_param).first()
    if default_tenant is None:
        default_tenant = accessible_tenants.first()
    form = BIExplorerForm(request.GET or None, tenant=default_tenant, user=request.user, accessible_tenants=accessible_tenants)
    selected_tenant = default_tenant
    competition = None
    edition = None
    match_status = ''
    contract_status = ''
    if form.is_valid():
        selected_tenant = form.cleaned_data.get('tenant') or default_tenant
        competition = form.cleaned_data.get('competition')
        edition = form.cleaned_data.get('edition')
        match_status = form.cleaned_data.get('match_status') or ''
        contract_status = form.cleaned_data.get('contract_status') or ''
    if selected_tenant is None:
        raise PermissionDenied('Nenhum tenant ativo disponível para consulta analítica.')
    match_qs = Match.objects.filter(tenant=selected_tenant).select_related('phase', 'phase__edition', 'phase__edition__competition', 'home_club', 'away_club')
    contract_qs = Contract.objects.filter(tenant=selected_tenant).select_related('person', 'club')
    event_qs = MatchEvent.objects.filter(tenant=selected_tenant).select_related('match', 'match__phase', 'match__phase__edition', 'match__phase__edition__competition', 'player')
    if competition is not None:
        match_qs = match_qs.filter(phase__edition__competition=competition)
        event_qs = event_qs.filter(match__phase__edition__competition=competition)
    if edition is not None:
        match_qs = match_qs.filter(phase__edition=edition)
        event_qs = event_qs.filter(match__phase__edition=edition)
    if match_status:
        match_qs = match_qs.filter(status=match_status)
    if contract_status:
        contract_qs = contract_qs.filter(status=contract_status)
    approvals_scope = {'tenant': selected_tenant}
    competition_rows = []
    for row in match_qs.values('phase__edition__competition__name').annotate(total=Count('id')).order_by('-total', 'phase__edition__competition__name')[:5]:
        competition_rows.append({'label': row['phase__edition__competition__name'] or 'Sem competição', 'count': row['total']})
    summary_cards = [
        {'label': 'Clubes', 'value': Club.objects.filter(tenant=selected_tenant).count()},
        {'label': 'Competições', 'value': Competition.objects.filter(tenant=selected_tenant).count()},
        {'label': 'Edições', 'value': CompetitionEdition.objects.filter(tenant=selected_tenant).count()},
        {'label': 'Partidas', 'value': match_qs.count()},
        {'label': 'Partidas disputadas', 'value': match_qs.filter(status=Match.Status.PLAYED).count()},
        {'label': 'Gols registrados', 'value': event_qs.filter(event_type=MatchEvent.EventType.GOAL).count()},
        {'label': 'Contratos ativos', 'value': contract_qs.filter(status=Contract.Status.ACTIVE).count()},
        {'label': 'Solicitações abertas', 'value': ApprovalRequest.objects.filter(**approvals_scope, status=ApprovalRequest.Status.OPEN).count()},
    ]
    match_status_rows = [
        {'label': dict(Match.Status.choices).get(row['status'], row['status']), 'count': row['total']}
        for row in match_qs.values('status').annotate(total=Count('id')).order_by('status')
    ]
    contract_status_rows = [
        {'label': dict(Contract.Status.choices).get(row['status'], row['status']), 'count': row['total']}
        for row in contract_qs.values('status').annotate(total=Count('id')).order_by('status')
    ]
    recent_matches = [
        {
            'reference_code': match.reference_code,
            'competition': match.phase.edition.competition.name,
            'edition': match.phase.edition.name,
            'pair': f'{match.home_club.name} x {match.away_club.name}',
            'status': match.get_status_display(),
            'score': '-' if match.home_score is None or match.away_score is None else f'{match.home_score} x {match.away_score}',
            'scheduled_at': match.scheduled_at.strftime('%d/%m/%Y %H:%M'),
        }
        for match in match_qs[:5]
    ]
    recent_events = [
        {
            'match': event.match.reference_code,
            'type': event.get_event_type_display(),
            'minute': event.minute,
            'player': event.player.full_name if event.player_id else '-',
        }
        for event in event_qs[:5]
    ]
    json_url = reverse('bi-center')
    json_query = request.GET.copy()
    json_query['format'] = 'json'
    json_url = f'{json_url}?{json_query.urlencode()}'
    html_payload = {
        'title': 'BI self-service',
        'subtitle': 'Filtros operacionais e exportação JSON para leitura analítica',
        'sprint_label': 'BI self-service',
        'json_url': json_url,
        'selected_tenant': selected_tenant.name,
        'summary_cards': summary_cards,
        'breakdowns': [
            {'title': 'Partidas por status', 'total': match_qs.count(), 'rows': match_status_rows},
            {'title': 'Contratos por status', 'total': contract_qs.count(), 'rows': contract_status_rows},
            {'title': 'Partidas por competição', 'total': match_qs.count(), 'rows': competition_rows},
        ],
        'recent_matches': recent_matches,
        'recent_events': recent_events,
        'form': form,
    }
    if request.GET.get('format') == 'json':
        json_payload = {key: value for key, value in html_payload.items() if key != 'form'}
        return JsonResponse(json_payload)
    return render(request, 'futebol/bi_center.html', html_payload)


def public_api_docs(request):
    return render(
        request,
        'futebol/public_api_docs.html',
        {
            'title': 'API pública',
            'subtitle': 'Leitura externa de dados esportivos, com autenticação por chave e escopo por tenant.',
            'sprint_label': 'API pública',
            'endpoints': [
                {'label': 'Visão geral', 'method': 'GET', 'path': '/api/publica/<tenant_slug>/visao-geral/'},
                {'label': 'Partidas', 'method': 'GET', 'path': '/api/publica/<tenant_slug>/partidas/'},
            ],
            'auth_header': 'X-SaaS-Futebol-API-Key',
            'auth_query': 'api_key',
            'example_curl': "curl -H 'X-SaaS-Futebol-API-Key: SUA_CHAVE' https://seu-dominio/api/publica/seu-tenant/visao-geral/",
        },
    )


def public_api_overview(request, tenant_slug):
    if not _public_api_authorized(request):
        return _public_api_forbidden()
    tenant = _public_api_tenant(tenant_slug)
    return JsonResponse(_public_api_overview_payload(tenant))


def public_api_matches(request, tenant_slug):
    if not _public_api_authorized(request):
        return _public_api_forbidden()
    tenant = _public_api_tenant(tenant_slug)
    match_qs = Match.objects.filter(tenant=tenant).select_related('phase', 'phase__edition', 'phase__edition__competition', 'home_club', 'away_club').order_by('-scheduled_at')
    competition_slug = request.GET.get('competition')
    status = request.GET.get('status')
    if competition_slug:
        match_qs = match_qs.filter(phase__edition__competition__slug=competition_slug)
    if status:
        match_qs = match_qs.filter(status=status)
    return JsonResponse({
        'tenant': {'name': tenant.name, 'slug': tenant.slug},
        'generated_at': timezone.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'count': match_qs.count(),
        'results': [_public_api_match_payload(match) for match in match_qs[:50]],
    })


@login_required
@_module_required('transferencias')
def contract_list(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ])
    page = TablePage(request)
    page.model = Contract
    page.select_related_fields = ('tenant', 'person', 'club')
    page.title = 'Contratos'
    page.subtitle = 'Vínculos contratuais entre pessoas e clubes'
    page.search_fields = ('person__full_name', 'club__name', 'status', 'termination_reason')
    page.default_ordering = '-start_date'
    page.ordering_map = {'start_date': 'start_date', '-start_date': '-start_date', 'status': 'status', '-status': '-status'}
    page.columns = (
        ('Pessoa', 'person.full_name'),
        ('Clube', 'club.name'),
        ('Início', lambda obj: obj.start_date.strftime('%d/%m/%Y')),
        ('Fim', lambda obj: obj.end_date.strftime('%d/%m/%Y') if obj.end_date else '-'),
        ('Status', 'status'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('contract-edit', args=[obj.pk]))
    page.create_url = reverse('contract-create')
    page.create_label = 'Novo contrato'
    page.empty_message = 'Nenhum contrato cadastrado ainda.'
    return page.render()


@login_required
@_module_required('transferencias')
def contract_create(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ])
    return _render_form(request, ContractForm, title='Novo contrato', subtitle='Cadastre um vínculo contratual', success_url_name='contract-list', success_message='Contrato criado com sucesso.', cancel_url=reverse('contract-list'))


@login_required
@_module_required('transferencias')
def contract_edit(request, pk):
    contract = _get_visible_object(request, Contract, pk)
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ], tenant=contract.tenant)
    return _render_form(request, ContractForm, instance=contract, title='Editar contrato', subtitle='Atualize os dados do contrato', success_url_name='contract-list', success_message='Contrato atualizado com sucesso.', cancel_url=reverse('contract-list'))


@login_required
@_module_required('transferencias')
def negotiation_list(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
        'auditor_somente_leitura',
    ])
    page = TablePage(request)
    page.model = Negotiation
    page.select_related_fields = ('tenant', 'person', 'club')
    page.title = 'Negociações'
    page.subtitle = 'Tratativas entre clubes e pessoas'
    page.search_fields = ('person__full_name', 'club__name', 'status')
    page.default_ordering = '-opened_at'
    page.ordering_map = {'opened_at': 'opened_at', '-opened_at': '-opened_at', 'status': 'status', '-status': '-status'}
    page.columns = (
        ('Pessoa', 'person.full_name'),
        ('Clube', 'club.name'),
        ('Status', 'status'),
        ('Aberta em', lambda obj: obj.opened_at.strftime('%d/%m/%Y %H:%M')),
        ('Encerrada em', lambda obj: obj.closed_at.strftime('%d/%m/%Y %H:%M') if obj.closed_at else '-'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('negotiation-edit', args=[obj.pk]))
    page.create_url = reverse('negotiation-create')
    page.create_label = 'Nova negociação'
    page.empty_message = 'Nenhuma negociação cadastrada ainda.'
    return page.render()


@login_required
@_module_required('transferencias')
def negotiation_create(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ])
    return _render_form(request, NegotiationForm, title='Nova negociação', subtitle='Registre uma tratativa entre clube e pessoa', success_url_name='negotiation-list', success_message='Negociação criada com sucesso.', cancel_url=reverse('negotiation-list'))


@login_required
@_module_required('transferencias')
def negotiation_edit(request, pk):
    negotiation = _get_visible_object(request, Negotiation, pk)
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ], tenant=negotiation.tenant)
    return _render_form(request, NegotiationForm, instance=negotiation, title='Editar negociação', subtitle='Atualize a tratativa', success_url_name='negotiation-list', success_message='Negociação atualizada com sucesso.', cancel_url=reverse('negotiation-list'))


@login_required
@_module_required('transferencias')
def proposal_list(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
        'auditor_somente_leitura',
    ])
    page = TablePage(request)
    page.model = Proposal
    page.select_related_fields = ('tenant', 'negotiation', 'club')
    page.title = 'Propostas'
    page.subtitle = 'Ofertas financeiras ligadas às negociações'
    page.search_fields = ('negotiation__person__full_name', 'club__name', 'currency', 'status')
    page.default_ordering = '-id'
    page.ordering_map = {'status': 'status', '-status': '-status', 'id': 'id', '-id': '-id'}
    page.columns = (
        ('Negociação', lambda obj: f'{obj.negotiation.person.full_name} × {obj.negotiation.club.name}'),
        ('Clube', 'club.name'),
        ('Valor', lambda obj: f'{obj.currency} {obj.amount}'),
        ('Status', 'status'),
        ('Enviada em', lambda obj: obj.sent_at.strftime('%d/%m/%Y %H:%M') if obj.sent_at else '-'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('proposal-edit', args=[obj.pk]))
    page.create_url = reverse('proposal-create')
    page.create_label = 'Nova proposta'
    page.empty_message = 'Nenhuma proposta cadastrada ainda.'
    return page.render()


@login_required
@_module_required('transferencias')
def proposal_create(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ])
    return _render_form(request, ProposalForm, title='Nova proposta', subtitle='Registre uma oferta para uma negociação', success_url_name='proposal-list', success_message='Proposta criada com sucesso.', cancel_url=reverse('proposal-list'))


@login_required
@_module_required('transferencias')
def proposal_edit(request, pk):
    proposal = _get_visible_object(request, Proposal, pk)
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'admin_plataforma',
    ], tenant=proposal.tenant)
    return _render_form(request, ProposalForm, instance=proposal, title='Editar proposta', subtitle='Atualize os valores e status da proposta', success_url_name='proposal-list', success_message='Proposta atualizada com sucesso.', cancel_url=reverse('proposal-list'))


@login_required
@_module_required('transferencias')
def evidence_list(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'gestor_competicao',
        'auditor_somente_leitura',
        'admin_plataforma',
    ])
    page = TablePage(request)
    page.model = Evidence
    page.select_related_fields = ('tenant', 'content_type', 'uploaded_by')
    page.title = 'Evidências'
    page.subtitle = 'Documentos e links anexados aos alvos de aprovação'
    page.search_fields = ('content_type__model', 'object_id', 'note', 'url', 'uploaded_by__username')
    page.default_ordering = '-created_at'
    page.ordering_map = {'created_at': 'created_at', '-created_at': '-created_at'}
    page.columns = (
        ('Alvo', lambda obj: f'{obj.content_type.model}#{obj.object_id}'),
        ('Arquivo', lambda obj: obj.file.name.split('/')[-1] if obj.file else '-'),
        ('URL', lambda obj: obj.url or '-'),
        ('Observação', lambda obj: obj.note or '-'),
        ('Enviado por', 'uploaded_by.username'),
    )
    page.row_actions = lambda request, obj: format_html(
        '{}{}',
        format_html('<a class="action action-secondary" href="{}">Arquivo</a>', obj.file.url) if obj.file else '',
        format_html('<a class="action action-secondary" href="{}" target="_blank" rel="noreferrer">URL</a>', obj.url) if obj.url else '',
    )
    page.create_url = reverse('evidence-create')
    page.create_label = 'Nova evidência'
    page.empty_message = 'Nenhuma evidência registrada ainda.'
    return page.render()


@login_required
@_module_required('transferencias')
def evidence_create(request):
    _require_roles(request, [
        'admin_tenant',
        'gestor_clube',
        'gestor_competicao',
        'aprovador',
        'admin_plataforma',
    ])
    return _render_form(request, EvidenceForm, title='Nova evidência', subtitle='Anexe arquivo, link ou observação ao alvo da aprovação', success_url_name='evidence-list', success_message='Evidência criada com sucesso.', cancel_url=reverse('evidence-list'))




def _current_step(approval_request):
    """The next Etapa awaiting a decision — lowest-order step not yet approved."""
    try:
        approved_step_ids = approval_request.decisions.filter(
            outcome=ApprovalDecision.Outcome.APPROVED
        ).values_list('step_id', flat=True)
        return approval_request.flow.steps.exclude(id__in=approved_step_ids).order_by('order').first()
    except OperationalError:
        return None


def _cast(request, pk, outcome, success_text):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    approval_request = _visible_approval_request(request, pk)
    try:
        step = _current_step(approval_request)
    except OperationalError:
        step = None
    if step is None:
        approval_request.status = ApprovalRequest.Status.APPROVED if outcome == ApprovalDecision.Outcome.APPROVED else ApprovalRequest.Status.REJECTED
        approval_request.resolved_at = timezone.now()
        approval_request.save(update_fields=['status', 'resolved_at'])
        log_audit_event(
            tenant=approval_request.tenant,
            actor=request.user,
            action='approve' if outcome == ApprovalDecision.Outcome.APPROVED else 'reject',
            obj=approval_request,
            before_state={'status': ApprovalRequest.Status.OPEN},
            after_state={'status': approval_request.status, 'resolved_at': approval_request.resolved_at.isoformat()},
        )
        messages.success(request, success_text)
        return redirect('approval-request-list')
    try:
        approvals.cast_decision(approval_request, step, request.user, outcome)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('approval-request-list')
    messages.success(request, success_text)
    return redirect('approval-request-list')


@login_required
@_module_required('integracoes')
def external_system_list(request):
    page = TablePage(request)
    page.model = ExternalSystem
    page.select_related_fields = ('tenant',)
    page.title = 'Sistemas externos'
    page.subtitle = 'Pagamentos, e-mail, armazenamento e integrações operacionais'
    page.search_fields = ('name', 'kind', 'base_url')
    page.default_ordering = 'name'
    page.ordering_map = {'name': 'name', '-name': '-name', 'kind': 'kind', '-kind': '-kind'}
    page.columns = (
        ('Nome', 'name'),
        ('Tipo', 'kind'),
        ('URL base', 'base_url'),
        ('Ativo', lambda obj: 'Sim' if obj.active else 'Não'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('external-system-edit', args=[obj.pk]))
    page.create_url = reverse('external-system-create')
    page.create_label = 'Novo sistema externo'
    page.empty_message = 'Nenhum sistema externo cadastrado.'
    return page.render()


@login_required
@_module_required('integracoes')
def external_system_create(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    return _render_form(request, ExternalSystemForm, title='Novo sistema externo', subtitle='Cadastre um conector para pagamento, e-mail ou armazenamento', success_url_name='external-system-list', success_message='Sistema externo criado com sucesso.', cancel_url=reverse('external-system-list'))


@login_required
@_module_required('integracoes')
def external_system_edit(request, pk):
    external_system = _get_visible_object(request, ExternalSystem, pk)
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ], tenant=external_system.tenant)
    return _render_form(request, ExternalSystemForm, instance=external_system, title='Editar sistema externo', subtitle='Atualize o cadastro do conector', success_url_name='external-system-list', success_message='Sistema externo atualizado com sucesso.', cancel_url=reverse('external-system-list'))


@login_required
@_module_required('integracoes')
def integration_record_list(request):
    page = TablePage(request)
    page.model = IntegrationRecord
    page.select_related_fields = ('tenant', 'external_system')
    page.title = 'Registros de integração'
    page.subtitle = 'Entradas, respostas, reprocessos e rastreabilidade dos conectores'
    page.search_fields = ('correlation_id', 'external_object_id', 'status', 'external_system__name')
    page.default_ordering = '-received_at'
    page.ordering_map = {'received_at': 'received_at', '-received_at': '-received_at', 'status': 'status', '-status': '-status'}
    page.columns = (
        ('Sistema', 'external_system.name'),
        ('Correlação', 'correlation_id'),
        ('Objeto externo', 'external_object_id'),
        ('Status', 'status'),
        ('Recebido em', lambda obj: obj.received_at.strftime('%d/%m/%Y %H:%M')),
        ('Erro', lambda obj: obj.error_message or '-'),
    )
    page.empty_message = 'Nenhum registro de integração encontrado.'
    page.row_actions = _integration_record_actions
    page.create_url = reverse('integration-record-create')
    page.create_label = 'Novo registro'
    return page.render()


@login_required
@_module_required('integracoes')
def integration_record_create(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    return _render_form(request, IntegrationRecordForm, title='Novo registro de integração', subtitle='Registre manualmente uma entrada externa recebida', success_url_name='integration-record-list', success_message='Registro de integração criado com sucesso.', cancel_url=reverse('integration-record-list'))


@login_required
@_module_required('integracoes')
def integration_record_mark_processed(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    record = _visible_integration_record(request, pk)
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ], tenant=record.tenant)
    before_state = snapshot_instance(record, fields=['status', 'processed_at', 'error_message'])
    record.status = 'processed'
    record.processed_at = timezone.now()
    record.error_message = ''
    record.save()
    log_audit_event(
        tenant=record.tenant,
        actor=request.user,
        action='update',
        obj=record,
        before_state=before_state,
        after_state=snapshot_instance(record, fields=['status', 'processed_at', 'error_message']),
        correlation_id=getattr(request, 'request_id', ''),
    )
    messages.success(request, 'Registro marcado como processado.')
    return redirect('integration-record-list')


@login_required
@_module_required('integracoes')
def integration_record_retry(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    record = _visible_integration_record(request, pk)
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ], tenant=record.tenant)
    before_state = snapshot_instance(record, fields=['status', 'processed_at', 'error_message'])
    record.status = 'retry'
    record.processed_at = None
    record.save()
    log_audit_event(
        tenant=record.tenant,
        actor=request.user,
        action='update',
        obj=record,
        before_state=before_state,
        after_state=snapshot_instance(record, fields=['status', 'processed_at', 'error_message']),
        correlation_id=getattr(request, 'request_id', ''),
    )
    messages.success(request, 'Registro reenfileirado para reprocessamento.')
    return redirect('integration-record-list')


@login_required
@_module_required('integracoes')
def integration_hub(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    tenant_ids = [] if request.user.is_superuser else list(_accessible_tenants(request.user))
    scope = {} if request.user.is_superuser else {'tenant_id__in': tenant_ids}
    context = {
        'title': 'Integrações, automações e IA',
        'subtitle': 'Centro operacional para conectores, rotinas e apoio inteligente',
        'sprint_label': 'Integrações, automações e IA',
        'external_system_count': ExternalSystem.objects.filter(**scope).count(),
        'integration_record_count': IntegrationRecord.objects.filter(**scope).count(),
        'approval_flow_count': ApprovalFlow.objects.filter(**scope).count(),
        'integration_received_count': IntegrationRecord.objects.filter(**scope, status='received').count(),
        'integration_processed_count': IntegrationRecord.objects.filter(**scope, status='processed').count(),
        'integration_error_count': IntegrationRecord.objects.filter(**scope, status='error').count(),
        'integration_retry_count': IntegrationRecord.objects.filter(**scope, status='retry').count(),
        'actions': [
            {'label': 'Sistemas externos', 'href': reverse('external-system-list')},
            {'label': 'Registros de integração', 'href': reverse('integration-record-list')},
            {'label': 'Importar dados', 'href': reverse('integration-import')},
            {'label': 'Exportar dados', 'href': reverse('integration-export')},
        ],
        'sections': [
            {
                'title': 'Integrações externas',
                'description': 'Cadastro de conectores, reprocesso e rastreio dos payloads recebidos.',
                'points': ['Sistema de pagamento', 'E-mail operacional', 'Armazenamento de arquivos', 'Entrada e saída de dados'],
            },
            {
                'title': 'Automações',
                'description': 'Tarefas repetitivas, gatilhos, regras, idempotência e exceções operacionais.',
                'points': ['Gatilhos de eventos', 'Regras de negócio', 'Exceções manuais', 'Monitoramento de falhas'],
            },
            {
                'title': 'IA',
                'description': 'Casos de uso com limites e fallback manual para a operação.',
                'points': ['Resumo operacional', 'Detecção de inconsistências', 'Sugestões de aprovação', 'Fallback humano'],
            },
        ],
    }
    return render(request, 'futebol/page.html', context)


@login_required
@_module_required('integracoes')
def integration_import(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    result = None
    if request.method == 'POST':
        form = IntegrationImportForm(request.POST)
        if form.is_valid():
            tenant = _primary_tenant(request)
            result = import_payload(
                tenant,
                form.cleaned_data['model'],
                form.cleaned_data['payload'],
                conflict_policy=form.cleaned_data['conflict_policy'],
            )
            messages.success(request, 'Importação concluída.')
        else:
            messages.error(request, 'Corrija os campos da importação.')
    else:
        form = IntegrationImportForm()
    return render(request, 'futebol/integration_exchange.html', {
        'title': 'Importar dados',
        'subtitle': 'Entrada de CSV ou JSON para cargas operacionais',
        'mode': 'import',
        'form': form,
        'result': result.as_dict() if result else None,
        'cancel_url': reverse('integration-hub'),
    })


@login_required
@_module_required('integracoes')
def integration_export(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    if request.method == 'POST':
        form = IntegrationExportForm(request.POST)
        if form.is_valid():
            tenant = _primary_tenant(request)
            csv_data = export_csv(tenant, form.cleaned_data['model'])
            response = HttpResponse(csv_data, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{form.cleaned_data["model"]}.csv"'
            return response
        messages.error(request, 'Selecione um modelo válido para exportação.')
    else:
        form = IntegrationExportForm()
    return render(request, 'futebol/integration_exchange.html', {
        'title': 'Exportar dados',
        'subtitle': 'Saída de CSV para backup, auditoria e integração',
        'mode': 'export',
        'form': form,
        'result': None,
        'cancel_url': reverse('integration-hub'),
    })


@login_required
@_module_required('automacoes')
def automation_center(request):
    context = {
        'title': 'Automações',
        'subtitle': 'Tarefas repetitivas, gatilhos, regras e exceções',
        'sprint_label': 'Automações',
        'summary': [
            ('Tarefas repetitivas', 'Centralizar importação, exportação e notificações recorrentes.'),
            ('Gatilhos', 'Disparar ações a partir de eventos operacionais e decisões de aprovação.'),
            ('Regras', 'Aplicar validações e limites do domínio antes de executar.'),
            ('Exceções', 'Registrar falhas, permitir reprocessamento e manter fallback manual.'),
        ],
        'actions': [
            {'label': 'Importar dados', 'href': reverse('integration-import')},
            {'label': 'Exportar dados', 'href': reverse('integration-export')},
            {'label': 'Registros de integração', 'href': reverse('integration-record-list')},
        ],
    }
    return render(request, 'futebol/page.html', context)


def _sync_ai_provider_credentials(form, provider):
    api_key = (form.cleaned_data.get('api_key') or '').strip()
    if provider.kind != AIProvider.Kind.OPENCODE or not api_key:
        return
    sync_opencode_provider_credentials(
        api_key=api_key,
        provider_name=provider.name,
        provider_kind=provider.kind,
        model_name=provider.model_name,
    )


@login_required
@_module_required('ia')
def ai_provider_list(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    page = TablePage(request)
    page.model = AIProvider
    page.select_related_fields = ('tenant',)
    page.title = 'Providers de IA'
    page.subtitle = 'Cadastros de modelos e fornecedores para os agentes da plataforma'
    page.search_fields = ('name', 'kind', 'model_name', 'notes')
    page.default_ordering = 'name'
    page.ordering_map = {'name': 'name', '-name': '-name', 'kind': 'kind', '-kind': '-kind'}
    page.columns = (
        ('Nome', 'name'),
        ('Fornecedor', 'kind'),
        ('Modelo', 'model_name'),
        ('Credencial', lambda obj: 'Configurada' if opencode_auth_configured(provider_name=obj.name) else 'Pendente'),
        ('Ativo', lambda obj: 'Sim' if obj.active else 'Não'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('ai-provider-edit', args=[obj.pk]))
    page.create_url = reverse('ai-provider-create')
    page.create_label = 'Novo provider'
    page.empty_message = 'Nenhum provider de IA cadastrado.'
    context = page.context()
    context.update(
        {
            'provider_catalog': provider_catalog_rows(),
            'provider_catalog_hint': 'Clique em Novo provider para cadastrar vários fornecedores; o catálogo abaixo mostra modelos sugeridos por tipo.',
        }
    )
    return render(request, 'futebol/provider_list.html', context)


@login_required
@_module_required('ia')
def ai_provider_create(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    return _render_form(
        request,
        AIProviderForm,
        title='Novo provider de IA',
        subtitle='Cadastre o fornecedor/modelo que será usado pelo agente',
        success_url_name='ai-provider-list',
        success_message='Provider criado com sucesso.',
        cancel_url=reverse('ai-provider-list'),
        post_save=_sync_ai_provider_credentials,
    )


@login_required
@_module_required('ia')
def ai_provider_edit(request, pk):
    provider = _get_visible_object(request, AIProvider, pk)
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ], tenant=provider.tenant)
    return _render_form(
        request,
        AIProviderForm,
        instance=provider,
        title='Editar provider de IA',
        subtitle='Atualize o cadastro do fornecedor/modelo',
        success_url_name='ai-provider-list',
        success_message='Provider atualizado com sucesso.',
        cancel_url=reverse('ai-provider-list'),
        post_save=_sync_ai_provider_credentials,
    )


@login_required
@_module_required('ia')
def knowledge_source_list(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    page = TablePage(request)
    page.model = KnowledgeSource
    page.select_related_fields = ('tenant',)
    page.title = 'Fontes de conhecimento'
    page.subtitle = 'Documentos, relatórios e páginas públicas que alimentam os agentes da SaaS'
    page.search_fields = ('identifier', 'title', 'kind', 'source_path', 'summary')
    page.default_ordering = 'title'
    page.ordering_map = {'title': 'title', '-title': '-title', 'kind': 'kind', '-kind': '-kind'}
    page.columns = (
        ('Título', 'title'),
        ('Tipo', 'kind'),
        ('Identificador', 'identifier'),
        ('Origem', 'source_path'),
        ('URL', lambda obj: format_html('<a href="{}" target="_blank" rel="noreferrer">{}</a>', obj.source_url, obj.source_url) if obj.source_url else '—'),
        ('Ativo', lambda obj: 'Sim' if obj.active else 'Não'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('knowledge-source-edit', args=[obj.pk]))
    page.create_url = reverse('knowledge-source-create')
    page.create_label = 'Nova fonte manual'
    page.extra_actions = (
        {'href': reverse('knowledge-source-import-url'), 'label': 'Importar URL'},
    )
    page.empty_message = 'Nenhuma fonte de conhecimento importada.'
    return page.render()


@login_required
@_module_required('ia')
def knowledge_source_import_url(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    tenant = _primary_tenant(request)
    form = KnowledgeSourceImportForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            result = import_knowledge_source_from_url(
                tenant=tenant,
                url=form.cleaned_data['url'],
                title=form.cleaned_data.get('title') or '',
                identifier=form.cleaned_data.get('identifier') or '',
            )
        except ValueError as exc:
            form.add_error('url', str(exc))
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f'Fonte {"criada" if result.created else "atualizada"} com sucesso a partir da URL.',
            )
            return redirect('knowledge-source-list')
    return render(
        request,
        'futebol/form.html',
        {
            'title': 'Importar fonte por URL',
            'subtitle': 'Cole uma página pública e o sistema vai extrair título, resumo e conteúdo principal.',
            'form': form,
            'cancel_url': reverse('knowledge-source-list'),
            'page_state': 'form',
        },
    )


@login_required
@_module_required('ia')
def knowledge_source_create(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    return _render_form(request, KnowledgeSourceForm, title='Nova fonte de conhecimento', subtitle='Cadastre manualmente uma documentação ou relatório', success_url_name='knowledge-source-list', success_message='Fonte criada com sucesso.', cancel_url=reverse('knowledge-source-list'))


@login_required
@_module_required('ia')
def knowledge_source_edit(request, pk):
    source = _get_visible_object(request, KnowledgeSource, pk)
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ], tenant=source.tenant)
    return _render_form(request, KnowledgeSourceForm, instance=source, title='Editar fonte de conhecimento', subtitle='Atualize o documento ou relatório cadastrado', success_url_name='knowledge-source-list', success_message='Fonte atualizada com sucesso.', cancel_url=reverse('knowledge-source-list'))


@login_required
@_module_required('ia')
def ai_agent_list(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    page = TablePage(request)
    page.model = AIAgent
    page.select_related_fields = ('tenant', 'provider')
    page.title = 'Agentes de IA'
    page.subtitle = 'Agentes vinculados a providers e fontes documentais'
    page.search_fields = ('name', 'slug', 'purpose', 'system_prompt', 'provider__name', 'provider__model_name')
    page.default_ordering = 'name'
    page.ordering_map = {'name': 'name', '-name': '-name', 'provider': 'provider__name', '-provider': '-provider__name'}
    page.columns = (
        ('Nome', 'name'),
        ('Provider', 'provider.name'),
        ('Modelo', lambda obj: obj.model_override or obj.provider.model_name),
        ('Fontes', lambda obj: obj.source_links.filter(active=True).count()),
        ('Ativo', lambda obj: 'Sim' if obj.active else 'Não'),
    )
    page.row_actions = lambda request, obj: format_html('<a class="action action-secondary" href="{}">Editar</a>', reverse('ai-agent-edit', args=[obj.pk]))
    page.create_url = reverse('ai-agent-create')
    page.create_label = 'Novo agente'
    page.empty_message = 'Nenhum agente de IA configurado.'
    return page.render()


@login_required
@_module_required('ia')
def ai_agent_create(request):
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ])
    return _render_form(request, AIAgentForm, title='Novo agente de IA', subtitle='Associe um provider e uma base documental ao agente', success_url_name='ai-agent-list', success_message='Agente criado com sucesso.', cancel_url=reverse('ai-agent-list'))


@login_required
@_module_required('ia')
def ai_agent_edit(request, pk):
    agent = _get_visible_object(request, AIAgent, pk)
    _require_roles(request, [
        'admin_tenant',
        'admin_plataforma',
    ], tenant=agent.tenant)
    return _render_form(request, AIAgentForm, instance=agent, title='Editar agente de IA', subtitle='Ajuste provider, prompt e fontes vinculadas', success_url_name='ai-agent-list', success_message='Agente atualizado com sucesso.', cancel_url=reverse('ai-agent-list'))


@login_required
@_module_required('ia')
def ai_center(request):
    tenant_ids = [] if request.user.is_superuser else list(_accessible_tenants(request.user))
    accessible_tenants = Tenant.objects.filter(active=True) if request.user.is_superuser else Tenant.objects.filter(pk__in=tenant_ids, active=True)
    default_tenant = None
    tenant_param = request.GET.get('tenant')
    if tenant_param:
        default_tenant = accessible_tenants.filter(pk=tenant_param).first()
    if default_tenant is None:
        default_tenant = accessible_tenants.first()
    if default_tenant is None:
        raise PermissionDenied('Nenhum tenant ativo disponível para análise tática.')

    provider_qs = AIProvider.objects.filter(tenant=default_tenant).order_by('name')
    agent_qs = AIAgent.objects.filter(tenant=default_tenant).select_related('provider').order_by('name')
    source_qs = KnowledgeSource.objects.filter(tenant=default_tenant).order_by('title')
    linked_sources = AIAgentSourceLink.objects.filter(tenant=default_tenant, active=True)

    player_qs = (
        Person.objects.filter(tenant=default_tenant, kind=Person.Kind.ATHLETE, active=True)
        .annotate(
            appearances=Count('lineups', filter=Q(lineups__match__tenant=default_tenant), distinct=True),
            starts=Count('lineups', filter=Q(lineups__match__tenant=default_tenant, lineups__is_starter=True), distinct=True),
            goals=Count('events', filter=Q(events__match__tenant=default_tenant, events__event_type=MatchEvent.EventType.GOAL), distinct=True),
            cards=Count('events', filter=Q(events__match__tenant=default_tenant, events__event_type__in=[MatchEvent.EventType.YELLOW_CARD, MatchEvent.EventType.RED_CARD]), distinct=True),
        )
        .filter(Q(appearances__gt=0) | Q(goals__gt=0) | Q(cards__gt=0))
        .order_by('-goals', '-appearances', 'full_name')
    )
    lineups_qs = MatchLineup.objects.filter(tenant=default_tenant).select_related('match', 'match__phase', 'match__phase__edition', 'match__phase__edition__competition', 'club', 'player')
    matches_qs = Match.objects.filter(tenant=default_tenant).select_related('phase', 'phase__edition', 'phase__edition__competition', 'home_club', 'away_club')
    events_qs = MatchEvent.objects.filter(tenant=default_tenant).select_related('match', 'player')
    played_matches = matches_qs.filter(status=Match.Status.PLAYED)

    position_rows = []
    for row in lineups_qs.values('position').annotate(total=Count('id')).order_by('-total', 'position')[:5]:
        position_rows.append({'label': row['position'] or 'Sem posição', 'count': row['total']})

    recent_players = [
        {
            'name': player.full_name,
            'appearances': player.appearances,
            'starts': player.starts,
            'goals': player.goals,
            'cards': player.cards,
        }
        for player in player_qs[:5]
    ]
    recent_matches = [
        {
            'reference_code': match.reference_code,
            'competition': match.phase.edition.competition.name,
            'pair': f'{match.home_club.name} x {match.away_club.name}',
            'score': '-' if match.home_score is None or match.away_score is None else f'{match.home_score} x {match.away_score}',
            'lineups': lineups_qs.filter(match=match).count(),
            'goals': events_qs.filter(match=match, event_type=MatchEvent.EventType.GOAL).count(),
        }
        for match in played_matches[:5]
    ]

    agent_run_form = AIAgentRunForm(tenant=default_tenant, user=request.user, initial={'tenant': default_tenant.pk})
    agent_run_result = None
    agent_run_error = ''
    if request.method == 'POST':
        agent_run_form = AIAgentRunForm(request.POST, tenant=default_tenant, user=request.user)
        if agent_run_form.is_valid():
            agent = agent_run_form.cleaned_data['agent']
            question = agent_run_form.cleaned_data['question']
            try:
                run_result = run_ai_agent(agent=agent, question=question)
                agent_run_result = {
                    'agent_name': run_result.agent_name,
                    'provider_name': run_result.provider_name,
                    'provider_kind': run_result.provider_kind,
                    'model_name': run_result.model_name,
                    'question': run_result.question,
                    'answer': run_result.answer,
                    'source_titles': run_result.source_titles,
                    'used_fallback': run_result.used_fallback,
                }
                messages.success(request, 'Consulta executada com sucesso.')
            except Exception as exc:
                agent_run_error = str(exc)
                messages.error(request, agent_run_error)

    context = {
        'title': 'Centro de IA e agentes',
        'subtitle': 'Providers, fontes documentais e agentes rastreáveis para apoiar análise e automação',
        'sprint_label': 'Centro de IA e agentes',
        'summary': [
            ('Providers', f'{provider_qs.count()} cadastrados'),
            ('Agentes', f'{agent_qs.count()} configurados'),
            ('Fontes', f'{source_qs.count()} importadas'),
            ('Vínculos', f'{linked_sources.count()} relações agente→fonte'),
        ],
        'use_cases': [
            'Analisar fontes documentais antes de responder perguntas operacionais.',
            'Associar cada agente a um provider/modelo específico.',
            'Manter fallback manual quando a base documental não cobrir a decisão.',
        ],
        'fallback_manual': 'Fallback manual: revise os documentos importados, os providers cadastrados e os registros do domínio antes de confiar numa resposta automatizada.',
        'actions': [
            {'label': 'Providers', 'href': reverse('ai-provider-list')},
            {'label': 'Agentes', 'href': reverse('ai-agent-list')},
            {'label': 'Fontes de conhecimento', 'href': reverse('knowledge-source-list')},
            {'label': 'Relatórios', 'href': reverse('report-center')},
        ],
        'agent_run_form': agent_run_form,
        'agent_run_result': agent_run_result,
        'agent_run_error': agent_run_error,
        'sections': [
            {
                'title': 'Cobertura do elenco',
                'description': 'Resumo rápido dos atletas com participação recente.',
                'points': [
                    f"{len(recent_players)} atletas com eventos ou escalações registradas",
                    f"{len(recent_matches)} partidas recentes analisadas",
                ] or ['Sem dados suficientes.'],
            },
            {
                'title': 'Atletas observados',
                'description': 'Jogadores com mais participação, gols ou cartões.',
                'points': [
                    f"{player['name']} — {player['appearances']} jogos, {player['goals']} gols, {player['cards']} cartões"
                    for player in recent_players[:5]
                ] or ['Nenhum atleta observado.'],
            },
            {
                'title': 'Partidas recentes analisadas',
                'description': 'Últimos jogos concluídos com placar e volume de eventos.',
                'points': [
                    f"{match['reference_code']} — {match['pair']} ({match['score']})"
                    for match in recent_matches[:5]
                ] or ['Nenhuma partida analisada.'],
            },
            {
                'title': 'Configuração do provider',
                'description': 'Escolha o fornecedor e o modelo que o agente vai usar.',
                'points': [
                    f"{provider.name} — {provider.model_name} ({provider.get_kind_display()})" for provider in provider_qs[:5]
                ] or ['Nenhum provider configurado.'],
            },
            {
                'title': 'Base documental',
                'description': 'Fontes importadas do repositório e relatórios locais.',
                'points': [
                    f"{source.title} ({source.get_kind_display()})" for source in source_qs[:5]
                ] or ['Nenhuma fonte importada.'],
            },
            {
                'title': 'Agentes ativos',
                'description': 'Agentes prontos para se conectar às fontes de conhecimento.',
                'points': [
                    f"{agent.name}: {agent.provider.name} / {agent.model_override or agent.provider.model_name}" for agent in agent_qs[:5]
                ] or ['Nenhum agente configurado.'],
            },
            {
                'title': 'Posições mais usadas',
                'description': 'Leitura rápida da estrutura registrada nas escalações.',
                'points': [f"{row['label']}: {row['count']}" for row in position_rows] or ['Sem escalações registradas.'],
            },
        ],
        'recent_players': recent_players,
        'recent_matches': recent_matches,
        'selected_tenant': default_tenant.name,
    }
    return render(request, 'futebol/page.html', context)


@login_required
@_module_required('aprovacoes')
def approve_request(request, pk):
    return _cast(request, pk, ApprovalDecision.Outcome.APPROVED, 'Etapa aprovada.')


@login_required
@_module_required('aprovacoes')
def reject_request(request, pk):
    return _cast(request, pk, ApprovalDecision.Outcome.REJECTED, 'Solicitação rejeitada.')


@login_required
@_module_required('aprovacoes')
def cancel_request(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    approval_request = _visible_approval_request(request, pk)
    try:
        approvals.cancel_request(approval_request, request.user)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('approval-request-list')
    messages.success(request, 'Solicitação cancelada.')
    return redirect('approval-request-list')


@login_required
@_module_required('aprovacoes')
def mark_notification_read(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    notification = _visible_notification(request, pk)
    before_state = snapshot_instance(notification, fields=['status', 'read_at'])
    notification.mark_read()
    log_audit_event(
        tenant=notification.tenant,
        actor=request.user,
        action='update',
        obj=notification,
        before_state=before_state,
        after_state=snapshot_instance(notification, fields=['status', 'read_at']),
    )
    messages.success(request, 'Notificação marcada como lida.')
    return redirect('notification-list')


def _render_form(request, form_class, *, instance=None, title, subtitle, success_url_name, success_message, cancel_url, post_save=None):
    page = FormPage(
        request,
        form_class=form_class,
        instance=instance,
        extra_context={
            'title': title,
            'subtitle': subtitle,
            'success_url_name': success_url_name,
            'cancel_url': cancel_url,
            'page_state': 'form',
        },
        post_save=post_save,
    )
    page.success_url_name = success_url_name
    page.success_message = success_message
    return page.render()


def _visible_approval_request(request, pk):
    qs = ApprovalRequest.objects.select_related('tenant', 'flow', 'requested_by')
    if request.user.is_superuser:
        return get_object_or_404(qs, pk=pk)
    tenant_ids = list(_accessible_tenants(request.user))
    return get_object_or_404(qs.filter(tenant_id__in=tenant_ids), pk=pk)


def _visible_notification(request, pk):
    qs = Notification.objects.select_related('tenant', 'recipient')
    if request.user.is_superuser:
        return get_object_or_404(qs, pk=pk)
    tenant_ids = list(_accessible_tenants(request.user))
    return get_object_or_404(qs.filter(tenant_id__in=tenant_ids), pk=pk)


def _visible_integration_record(request, pk):
    qs = IntegrationRecord.objects.select_related('tenant', 'external_system')
    if request.user.is_superuser:
        return get_object_or_404(qs, pk=pk)
    tenant_ids = list(_accessible_tenants(request.user))
    return get_object_or_404(qs.filter(tenant_id__in=tenant_ids), pk=pk)


def _get_visible_object(request, model, pk):
    qs = model.objects.all()
    if request.user.is_superuser:
        return get_object_or_404(qs, pk=pk)
    tenant_ids = list(_accessible_tenants(request.user))
    return get_object_or_404(qs.filter(tenant_id__in=tenant_ids), pk=pk)


def _approval_request_actions(request, obj):
    if obj.status != ApprovalRequest.Status.OPEN:
        return format_html('<span class="muted">Sem ações</span>')
    approve = _post_button(request, reverse('approval-request-approve', args=[obj.pk]), 'Aprovar', 'success')
    reject = _post_button(request, reverse('approval-request-reject', args=[obj.pk]), 'Rejeitar', 'warning')
    cancel = _post_button(request, reverse('approval-request-cancel', args=[obj.pk]), 'Cancelar', 'danger')
    return format_html('<div class="row-actions">{}{}{} </div>', approve, reject, cancel)


def _notification_actions(request, obj):
    if obj.status == Notification.Status.READ:
        return format_html('<span class="muted">Lida</span>')
    read = _post_button(request, reverse('notification-mark-read', args=[obj.pk]), 'Marcar lida', 'success')
    return format_html('<div class="row-actions">{}</div>', read)


def _integration_record_actions(request, obj):
    if obj.status == 'processed':
        return format_html('<span class="muted">Processado</span>')
    processed = _post_button(request, reverse('integration-record-mark-processed', args=[obj.pk]), 'Marcar processado', 'success')
    retry = _post_button(request, reverse('integration-record-retry', args=[obj.pk]), 'Reprocessar', 'warning')
    return format_html('<div class="row-actions">{}{} </div>', processed, retry)


def _post_button(request, action_url, label, variant):
    token = get_token(request)
    return format_html(
        '<form method="post" action="{}" class="inline-form">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
        '<button type="submit" class="action action-{}">{}</button>'
        '</form>',
        action_url,
        token,
        variant,
        label,
    )
