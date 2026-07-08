from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseNotAllowed
from django.db import OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.middleware.csrf import get_token


from .forms import (
    ApprovalRequestForm,
    ClubForm,
    CompetitionForm,
    ExternalSystemForm,
    IntegrationExportForm,
    IntegrationImportForm,
    IntegrationRecordForm,
    MatchForm,
    NotificationForm,
)
from .models import (
    ApprovalDecision,
    ApprovalFlow,
    ApprovalRequest,
    Club,
    Competition,
    ExternalSystem,
    IntegrationRecord,
    Match,
    Notification,
    Tenant,
)
from .services.data_io import export_csv, import_payload
from .services import approvals


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


def _scope_queryset(request, model, *select_related_fields):
    qs = model.objects.all()
    if select_related_fields:
        qs = qs.select_related(*select_related_fields)
    if request.user.is_superuser:
        return qs
    tenant_ids = list(_accessible_tenants(request.user))
    return qs.filter(tenant_id__in=tenant_ids)


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
        return {
            'title': self.title,
            'subtitle': self.subtitle,
            'page_obj': page_obj,
            'rows': rows,
            'columns': [header for header, _ in self.columns],
            'query': self.request.GET.get('q', ''),
            'ordering': self.request.GET.get('ordering', self.default_ordering),
            'ordering_options': list(self.ordering_map.items()),
            'create_url': self.create_url,
            'create_label': self.create_label,
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

    def __init__(self, request, *, form_class, instance=None, extra_context=None):
        self.request = request
        self.form_class = form_class
        self.instance = instance
        self.extra_context = extra_context or {}

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
                obj = form.save(commit=False)
                if hasattr(obj, 'tenant_id') and not obj.tenant_id:
                    obj.tenant = _primary_tenant(self.request)
                if hasattr(obj, 'requested_by_id') and not obj.requested_by_id:
                    obj.requested_by = self.request.user
                obj.save()
                if hasattr(form, 'save_m2m'):
                    form.save_m2m()
                messages.success(self.request, self.success_message)
                return redirect(self.success_url_name)
            messages.error(self.request, self.invalid_message)
        return render(self.request, self.template_name, self.get_context(form))


@login_required
def home(request):
    memberships = request.user.tenant_memberships.select_related('tenant').filter(active=True, tenant__active=True)
    tenant_ids = list(memberships.values_list('tenant_id', flat=True))
    club_count = Club.objects.filter(tenant_id__in=tenant_ids).count()
    competition_count = Competition.objects.filter(tenant_id__in=tenant_ids).count()
    match_count = Match.objects.filter(tenant_id__in=tenant_ids).count()
    approval_count = ApprovalRequest.objects.filter(tenant_id__in=tenant_ids).count()
    notification_count = Notification.objects.filter(tenant_id__in=tenant_ids).count()
    context = {
        'title': 'SaaS do Futebol',
        'subtitle': 'Interface de operação da Sprint 5',
        'memberships': memberships,
        'primary_role': memberships.first().get_role_display() if memberships.exists() else 'Sem vínculo ativo',
        'club_count': club_count,
        'competition_count': competition_count,
        'match_count': match_count,
        'approval_count': approval_count,
        'notification_count': notification_count,
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
    return _render_form(request, ClubForm, title='Novo clube', subtitle='Cadastre um clube para a operação', success_url_name='club-list', success_message='Clube criado com sucesso.', cancel_url=reverse('club-list'))


@login_required
def club_edit(request, pk):
    club = _get_visible_object(request, Club, pk)
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
    return _render_form(request, CompetitionForm, title='Nova competição', subtitle='Cadastre uma liga, copa ou campeonato', success_url_name='competition-list', success_message='Competição criada com sucesso.', cancel_url=reverse('competition-list'))


@login_required
def competition_edit(request, pk):
    competition = _get_visible_object(request, Competition, pk)
    return _render_form(request, CompetitionForm, instance=competition, title='Editar competição', subtitle='Atualize o cadastro da competição', success_url_name='competition-list', success_message='Competição atualizada com sucesso.', cancel_url=reverse('competition-list'))


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
    return _render_form(request, MatchForm, title='Nova partida', subtitle='Cadastre a programação e o placar da partida', success_url_name='match-list', success_message='Partida criada com sucesso.', cancel_url=reverse('match-list'))


@login_required
def match_edit(request, pk):
    match = _get_visible_object(request, Match, pk)
    return _render_form(request, MatchForm, instance=match, title='Editar partida', subtitle='Atualize a programação, o placar ou as observações', success_url_name='match-list', success_message='Partida atualizada com sucesso.', cancel_url=reverse('match-list'))


@login_required
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
def approval_request_create(request):
    return _render_form(request, ApprovalRequestForm, title='Nova solicitação de aprovação', subtitle='Registre uma mudança crítica para validação', success_url_name='approval-request-list', success_message='Solicitação criada com sucesso.', cancel_url=reverse('approval-request-list'))


@login_required
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
def notification_create(request):
    return _render_form(request, NotificationForm, title='Nova notificação', subtitle='Envie uma mensagem operacional para um membro do tenant', success_url_name='notification-list', success_message='Notificação criada com sucesso.', cancel_url=reverse('notification-list'))


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
def external_system_create(request):
    return _render_form(request, ExternalSystemForm, title='Novo sistema externo', subtitle='Cadastre um conector para pagamento, e-mail ou armazenamento', success_url_name='external-system-list', success_message='Sistema externo criado com sucesso.', cancel_url=reverse('external-system-list'))


@login_required
def external_system_edit(request, pk):
    external_system = _get_visible_object(request, ExternalSystem, pk)
    return _render_form(request, ExternalSystemForm, instance=external_system, title='Editar sistema externo', subtitle='Atualize os dados de integração', success_url_name='external-system-list', success_message='Sistema externo atualizado com sucesso.', cancel_url=reverse('external-system-list'))


@login_required
def integration_record_list(request):
    page = TablePage(request)
    page.model = IntegrationRecord
    page.select_related_fields = ('tenant', 'external_system')
    page.title = 'Registros de integração'
    page.subtitle = 'Entradas, respostas e rastreabilidade dos conectores'
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
    page.create_url = reverse('integration-record-create')
    page.create_label = 'Novo registro'
    return page.render()


@login_required
def integration_record_create(request):
    return _render_form(request, IntegrationRecordForm, title='Novo registro de integração', subtitle='Registre manualmente uma entrada externa recebida', success_url_name='integration-record-list', success_message='Registro de integração criado com sucesso.', cancel_url=reverse('integration-record-list'))


@login_required
def integration_hub(request):
    tenant_ids = [] if request.user.is_superuser else list(_accessible_tenants(request.user))
    scope = {} if request.user.is_superuser else {'tenant_id__in': tenant_ids}
    context = {
        'title': 'Integrações, automações e IA',
        'subtitle': 'Centro operacional para conectores, rotinas e apoio inteligente',
        'sprint_label': 'Sprint 5 · Integrações, automações e IA',
        'external_system_count': ExternalSystem.objects.filter(**scope).count(),
        'integration_record_count': IntegrationRecord.objects.filter(**scope).count(),
        'approval_flow_count': ApprovalFlow.objects.filter(**scope).count(),
        'actions': [
            {'label': 'Sistemas externos', 'href': reverse('external-system-list')},
            {'label': 'Registros de integração', 'href': reverse('integration-record-list')},
            {'label': 'Importar dados', 'href': reverse('integration-import')},
            {'label': 'Exportar dados', 'href': reverse('integration-export')},
        ],
        'sections': [
            {
                'title': 'Integrações externas',
                'description': 'Cadastro de conectores e rastreio dos payloads recebidos.',
                'points': ['Sistema de pagamento', 'E-mail operacional', 'Armazenamento de arquivos', 'Entrada e saída de dados'],
            },
            {
                'title': 'Automações',
                'description': 'Tarefas repetitivas, gatilhos, regras e exceções operacionais.',
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
def integration_import(request):
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
def integration_export(request):
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
def automation_center(request):
    context = {
        'title': 'Automações',
        'subtitle': 'Tarefas repetitivas, gatilhos, regras e exceções',
        'sprint_label': 'Sprint 5 · Automações',
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


@login_required
def ai_center(request):
    context = {
        'title': 'IA',
        'subtitle': 'Casos de uso, limites e fallback manual para a operação',
        'sprint_label': 'Sprint 5 · IA',
        'summary': [
            ('Casos de uso', 'Resumo operacional, priorização de trabalho e leitura de inconsistências.'),
            ('Limites', 'IA não altera dados sem validação humana e não substitui regras do domínio.'),
            ('Fallback manual', 'Toda sugestão tem rota de revisão humana e ação tradicional equivalente.'),
        ],
        'actions': [
            {'label': 'Centro de integrações', 'href': reverse('integration-hub')},
            {'label': 'Automações', 'href': reverse('automation-center')},
            {'label': 'Solicitações de aprovação', 'href': reverse('approval-request-list')},
        ],
    }
    return render(request, 'futebol/page.html', context)


@login_required
def approve_request(request, pk):
    return _cast(request, pk, ApprovalDecision.Outcome.APPROVED, 'Etapa aprovada.')


@login_required
def reject_request(request, pk):
    return _cast(request, pk, ApprovalDecision.Outcome.REJECTED, 'Solicitação rejeitada.')


@login_required
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
def mark_notification_read(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    notification = _visible_notification(request, pk)
    notification.mark_read()
    messages.success(request, 'Notificação marcada como lida.')
    return redirect('notification-list')


def _render_form(request, form_class, *, instance=None, title, subtitle, success_url_name, success_message, cancel_url):
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
