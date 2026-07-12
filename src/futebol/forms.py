from __future__ import annotations

from urllib.parse import urlparse

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from .models import (
    AIAgent,
    AIAgentSourceLink,
    AIProvider,
    ApprovalFlow,
    ApprovalRequest,
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    Contract,
    Evidence,
    ExternalSystem,
    IntegrationRecord,
    KnowledgeSource,
    Match,
    Negotiation,
    Notification,
    Person,
    Proposal,
    Tenant,
    TenantBranding,
    TenantMembership,
    TenantModuleSubscription,
)
from .modules import BASE_MODULE, MODULE_CATALOG, MODULE_CODES
from .services.ai import provider_allowed_hosts, provider_model_catalog_flat, provider_model_options
from .services.data_io import MODEL_REGISTRY

MODEL_LABELS = {
    'club': 'Clube',
    'competition': 'Competição',
    'edition': 'Edição',
    'phase': 'Fase',
    'match': 'Partida',
}


class TenantScopedForm(forms.ModelForm):
    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        self.tenant = tenant
        self.user = user
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            attrs = widget.attrs.setdefault('class', '')
            classes = [c for c in attrs.split() if c]
            for candidate in ('form-control', 'field-input'):
                if candidate not in classes:
                    classes.append(candidate)
            widget.attrs['class'] = ' '.join(classes).strip()


class OnboardingForm(forms.Form):
    """Formulário de onboarding inicial do tenant (dados, branding e módulos)."""

    _color_attrs = {'type': 'color', 'class': 'form-control field-input'}

    # Papéis auto-atribuíveis no onboarding: apenas papéis internos ao tenant.
    # ``admin_plataforma`` é reservado ao fornecedor (ver PRD §4.1 e Risco 2).
    _self_service_roles = [
        (value, label)
        for value, label in TenantMembership.Role.choices
        if value != TenantMembership.Role.ADMIN_PLATAFORMA
    ]

    tenant_name = forms.CharField(label='Nome do clube', max_length=120)
    tenant_slug = forms.SlugField(label='Identificador (slug)', max_length=120)
    role = forms.ChoiceField(
        label='Seu papel inicial',
        choices=_self_service_roles,
        initial=TenantMembership.Role.ADMIN_TENANT,
    )
    modules = forms.MultipleChoiceField(
        label='Módulos contratados',
        choices=[(m['code'], m['name']) for m in MODULE_CATALOG],
        widget=forms.CheckboxSelectMultiple,
        initial=list(MODULE_CODES),
    )
    public_title = forms.CharField(label='Título público', max_length=120, initial='SaaS do Futebol')
    public_subtitle = forms.CharField(label='Subtítulo público', max_length=200, required=False, initial='Operação multi-tenant')
    primary_color = forms.CharField(label='Cor primária', max_length=9, initial='#1d6fe8', widget=forms.TextInput(attrs=_color_attrs))
    secondary_color = forms.CharField(label='Cor secundária', max_length=9, initial='#0c274a', widget=forms.TextInput(attrs=_color_attrs))
    background_color = forms.CharField(label='Cor de fundo', max_length=9, initial='#06162d', widget=forms.TextInput(attrs=_color_attrs))
    accent_color = forms.CharField(label='Cor de destaque', max_length=9, initial='#55a7ff', widget=forms.TextInput(attrs=_color_attrs))
    logo_url = forms.URLField(label='URL do logo', required=False)
    favicon_url = forms.URLField(label='URL do favicon', required=False)
    symbol_url = forms.URLField(label='URL do símbolo', required=False)

    def clean_tenant_slug(self):
        slug = self.cleaned_data['tenant_slug']
        if Tenant.objects.filter(slug=slug).exists():
            raise ValidationError('Já existe um tenant com este identificador.')
        return slug

    def clean_tenant_name(self):
        name = self.cleaned_data['tenant_name']
        if Tenant.objects.filter(name=name).exists():
            raise ValidationError('Já existe um tenant com este nome.')
        return name


class TenantBrandingForm(forms.ModelForm):
    class Meta:
        model = TenantBranding
        fields = [
            'primary_color',
            'secondary_color',
            'background_color',
            'accent_color',
            'logo_url',
            'favicon_url',
            'symbol_url',
            'public_title',
            'public_subtitle',
        ]
        labels = {
            'primary_color': 'Cor primária',
            'secondary_color': 'Cor secundária',
            'background_color': 'Cor de fundo',
            'accent_color': 'Cor de destaque',
            'logo_url': 'URL do logo',
            'favicon_url': 'URL do favicon',
            'symbol_url': 'URL do símbolo',
            'public_title': 'Título público',
            'public_subtitle': 'Subtítulo público',
        }
        widgets = {
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color'}),
            'background_color': forms.TextInput(attrs={'type': 'color'}),
            'accent_color': forms.TextInput(attrs={'type': 'color'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            attrs = widget.attrs.setdefault('class', '')
            classes = [c for c in attrs.split() if c]
            for candidate in ('form-control', 'field-input'):
                if candidate not in classes:
                    classes.append(candidate)
            widget.attrs['class'] = ' '.join(classes).strip()


class TenantModulesForm(forms.Form):
    modules = forms.MultipleChoiceField(
        label='Módulos contratados',
        choices=[(m['code'], m['name']) for m in MODULE_CATALOG],
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, tenant: Tenant | None = None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        self.fields['modules'].initial = self.initial_codes()

    def initial_codes(self):
        if self.tenant is None:
            return []
        subscriptions = self.tenant.tenantmodulesubscriptions.all()
        if not subscriptions.exists():
            return list(MODULE_CODES)
        return list(subscriptions.filter(enabled=True).values_list('module_code', flat=True))

    def save(self):
        selected_codes = set(self.cleaned_data.get('modules') or [])
        selected_codes.add(BASE_MODULE)
        if self.tenant is None:
            return
        for module in MODULE_CATALOG:
            TenantModuleSubscription.objects.update_or_create(
                tenant=self.tenant,
                module_code=module['code'],
                defaults={
                    'module_name': module['name'],
                    'enabled': module['code'] in selected_codes,
                },
            )


class TenantUserCreateForm(forms.Form):
    username = forms.CharField(label='Usuário', max_length=150)
    first_name = forms.CharField(label='Nome', max_length=150, required=False)
    last_name = forms.CharField(label='Sobrenome', max_length=150, required=False)
    email = forms.EmailField(label='E-mail', required=False)
    password1 = forms.CharField(label='Senha', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar senha', widget=forms.PasswordInput)
    role = forms.ChoiceField(label='Papel inicial', choices=OnboardingForm._self_service_roles)
    active = forms.BooleanField(label='Vínculo ativo', required=False, initial=True)

    def __init__(self, *args, tenant: Tenant | None = None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            attrs = widget.attrs.setdefault('class', '')
            classes = [c for c in attrs.split() if c]
            for candidate in ('form-control', 'field-input'):
                if candidate not in classes:
                    classes.append(candidate)
            widget.attrs['class'] = ' '.join(classes).strip()

    def clean_username(self):
        username = self.cleaned_data['username']
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise ValidationError('Já existe um usuário com este login.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            raise ValidationError('As senhas informadas não conferem.')
        return cleaned_data

    def save(self):
        User = get_user_model()
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data.get('email') or '',
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data.get('first_name') or '',
            last_name=self.cleaned_data.get('last_name') or '',
        )
        TenantMembership.objects.create(
            user=user,
            tenant=self.tenant,
            role=self.cleaned_data['role'],
            active=self.cleaned_data.get('active', False),
        )
        return user


class TenantUserEditForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = {
            'username': 'Usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail',
            'is_active': 'Usuário ativo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            attrs = widget.attrs.setdefault('class', '')
            classes = [c for c in attrs.split() if c]
            for candidate in ('form-control', 'field-input'):
                if candidate not in classes:
                    classes.append(candidate)
            widget.attrs['class'] = ' '.join(classes).strip()

    def clean_username(self):
        username = self.cleaned_data['username']
        User = get_user_model()
        qs = User.objects.filter(username=username)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Já existe um usuário com este login.')
        return username


class TenantMembershipForm(forms.ModelForm):
    class Meta:
        model = TenantMembership
        fields = ['role', 'active']
        labels = {
            'role': 'Papel',
            'active': 'Vínculo ativo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = OnboardingForm._self_service_roles
        for field in self.fields.values():
            widget = field.widget
            attrs = widget.attrs.setdefault('class', '')
            classes = [c for c in attrs.split() if c]
            for candidate in ('form-control', 'field-input'):
                if candidate not in classes:
                    classes.append(candidate)
            widget.attrs['class'] = ' '.join(classes).strip()


class BIExplorerForm(forms.Form):
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.none(), required=False, label='Unidade')
    competition = forms.ModelChoiceField(queryset=Competition.objects.none(), required=False, label='Competição')
    edition = forms.ModelChoiceField(queryset=CompetitionEdition.objects.none(), required=False, label='Edição')
    match_status = forms.ChoiceField(required=False, choices=[('', 'Todos')] + list(Match.Status.choices), label='Status da partida')
    contract_status = forms.ChoiceField(required=False, choices=[('', 'Todos')] + list(Contract.Status.choices), label='Status contratual')

    def __init__(self, *args, tenant: Tenant | None = None, user=None, accessible_tenants=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            attrs = widget.attrs.setdefault('class', '')
            classes = [c for c in attrs.split() if c]
            for candidate in ('form-control', 'field-input'):
                if candidate not in classes:
                    classes.append(candidate)
            widget.attrs['class'] = ' '.join(classes).strip()
        accessible_tenants = accessible_tenants or Tenant.objects.none()
        if user is not None and getattr(user, 'is_superuser', False):
            self.fields['tenant'].queryset = Tenant.objects.filter(active=True)
        else:
            self.fields['tenant'].queryset = accessible_tenants
        tenant_value = None
        if self.is_bound:
            tenant_value = self.data.get('tenant') or None
        if tenant_value:
            selected_tenant = Tenant.objects.filter(pk=tenant_value).first()
        else:
            selected_tenant = tenant
        competition_qs = Competition.objects.none()
        edition_qs = CompetitionEdition.objects.none()
        if selected_tenant is not None:
            competition_qs = Competition.objects.filter(tenant=selected_tenant)
            edition_qs = CompetitionEdition.objects.filter(tenant=selected_tenant).select_related('competition')
            competition_value = None
            if self.is_bound:
                competition_value = self.data.get('competition') or None
            if competition_value:
                edition_qs = edition_qs.filter(competition_id=competition_value)
        self.fields['competition'].queryset = competition_qs
        self.fields['edition'].queryset = edition_qs
        if tenant is not None:
            self.fields['tenant'].initial = tenant


class ClubForm(TenantScopedForm):
    class Meta:
        model = Club
        fields = ['name', 'slug', 'registration_code', 'city', 'state', 'active']
        labels = {
            'name': 'Nome do clube',
            'slug': 'Slug',
            'registration_code': 'Código de registro',
            'city': 'Cidade',
            'state': 'UF',
            'active': 'Ativo',
        }
        help_texts = {
            'slug': 'Usado na URL e na integração.',
            'registration_code': 'Identificador opcional do cadastro externo.',
        }


class PersonForm(TenantScopedForm):
    class Meta:
        model = Person
        fields = ['full_name', 'document_id', 'kind', 'birth_date', 'active']
        labels = {
            'full_name': 'Nome completo',
            'document_id': 'Documento',
            'kind': 'Tipo de pessoa',
            'birth_date': 'Data de nascimento',
            'active': 'Ativa',
        }
        widgets = {'birth_date': forms.DateInput(attrs={'type': 'date'})}


class CompetitionForm(TenantScopedForm):
    class Meta:
        model = Competition
        fields = ['name', 'slug', 'scope', 'active']
        labels = {
            'name': 'Nome da competição',
            'slug': 'Slug',
            'scope': 'Escopo',
            'active': 'Ativa',
        }


class MatchForm(TenantScopedForm):
    class Meta:
        model = Match
        fields = [
            'phase',
            'home_club',
            'away_club',
            'reference_code',
            'scheduled_at',
            'venue',
            'status',
            'home_score',
            'away_score',
            'notes',
        ]
        labels = {
            'phase': 'Fase',
            'home_club': 'Mandante',
            'away_club': 'Visitante',
            'reference_code': 'Código de referência',
            'scheduled_at': 'Data e hora',
            'venue': 'Local',
            'status': 'Status',
            'home_score': 'Placar do mandante',
            'away_score': 'Placar do visitante',
            'notes': 'Observações',
        }
        widgets = {
            'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'reference_code': 'Código único para o tenant.',
            'scheduled_at': 'Use o horário local da operação.',
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        if tenant is not None:
            self.fields['phase'].queryset = CompetitionPhase.objects.filter(tenant=tenant).select_related('edition', 'edition__competition')
            self.fields['home_club'].queryset = Club.objects.filter(tenant=tenant)
            self.fields['away_club'].queryset = Club.objects.filter(tenant=tenant)


class ContractForm(TenantScopedForm):
    class Meta:
        model = Contract
        fields = ['person', 'club', 'start_date', 'end_date', 'signed_at', 'status', 'termination_reason']
        labels = {
            'person': 'Pessoa',
            'club': 'Clube',
            'start_date': 'Data de início',
            'end_date': 'Data de fim',
            'signed_at': 'Assinado em',
            'status': 'Status',
            'termination_reason': 'Motivo do encerramento',
        }
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'signed_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'termination_reason': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        if tenant is not None:
            self.fields['person'].queryset = Person.objects.filter(tenant=tenant)
            self.fields['club'].queryset = Club.objects.filter(tenant=tenant)


class NegotiationForm(TenantScopedForm):
    class Meta:
        model = Negotiation
        fields = ['club', 'person', 'status', 'closed_at']
        labels = {
            'club': 'Clube',
            'person': 'Pessoa',
            'status': 'Status',
            'closed_at': 'Encerrada em',
        }
        widgets = {
            'closed_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        if tenant is not None:
            self.fields['club'].queryset = Club.objects.filter(tenant=tenant)
            self.fields['person'].queryset = Person.objects.filter(tenant=tenant)


class ProposalForm(TenantScopedForm):
    class Meta:
        model = Proposal
        fields = ['negotiation', 'club', 'amount', 'currency', 'status', 'sent_at']
        labels = {
            'negotiation': 'Negociação',
            'club': 'Clube',
            'amount': 'Valor',
            'currency': 'Moeda',
            'status': 'Status',
            'sent_at': 'Enviada em',
        }
        widgets = {
            'sent_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        if tenant is not None:
            self.fields['negotiation'].queryset = Negotiation.objects.filter(tenant=tenant).select_related('person', 'club')
            self.fields['club'].queryset = Club.objects.filter(tenant=tenant)


class EvidenceForm(TenantScopedForm):
    class Meta:
        model = Evidence
        fields = ['content_type', 'object_id', 'file', 'url', 'note']
        labels = {
            'content_type': 'Tipo de alvo',
            'object_id': 'ID do alvo',
            'file': 'Arquivo',
            'url': 'URL de apoio',
            'note': 'Observação',
        }
        widgets = {
            'note': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'content_type': 'A evidência precisa ficar no mesmo alvo usado na aprovação.',
            'object_id': 'Use o ID do objeto para localizar o alvo.',
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        if tenant is not None:
            from .services import approvals
            allowed_models = approvals.approvable_models()
            self.fields['content_type'].queryset = ContentType.objects.filter(
                app_label='futebol',
                model__in=[model._meta.model_name for model in allowed_models],
            )

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.user is not None and not obj.uploaded_by_id:
            obj.uploaded_by = self.user
        if self.tenant is not None and not obj.tenant_id:
            obj.tenant = self.tenant
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class ApprovalRequestForm(TenantScopedForm):
    class Meta:
        model = ApprovalRequest
        fields = ['flow', 'content_type', 'object_id', 'reason']
        labels = {
            'flow': 'Fluxo',
            'content_type': 'Modelo de destino',
            'object_id': 'ID do objeto de destino',
            'reason': 'Motivo',
        }
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'content_type': 'Selecione o tipo de objeto que será aprovado.',
            'object_id': 'Informe o identificador textual ou numérico do objeto alvo.',
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        if tenant is not None:
            self.fields['flow'].queryset = ApprovalFlow.objects.filter(tenant=tenant, active=True)
            from .services import approvals
            allowed_models = approvals.approvable_models()
            allowed_content_types = ContentType.objects.filter(
                app_label='futebol',
                model__in=[model._meta.model_name for model in allowed_models],
            )
            self.fields['content_type'].queryset = allowed_content_types

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.user is not None and not obj.requested_by_id:
            obj.requested_by = self.user
        if self.tenant is not None and not obj.tenant_id:
            obj.tenant = self.tenant
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class NotificationForm(TenantScopedForm):
    class Meta:
        model = Notification
        fields = ['recipient', 'channel', 'subject', 'body']
        labels = {
            'recipient': 'Destinatário',
            'channel': 'Canal',
            'subject': 'Assunto',
            'body': 'Mensagem',
        }
        widgets = {
            'body': forms.Textarea(attrs={'rows': 5}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant is not None and 'recipient' in cleaned_data:
            recipient = cleaned_data['recipient']
            if recipient and not recipient.is_superuser:
                has_membership = recipient.tenant_memberships.filter(
                    tenant=self.tenant,
                    active=True,
                    tenant__active=True,
                ).exists()
                if not has_membership:
                    self.add_error('recipient', 'O destinatário precisa ter vínculo ativo com o tenant.')
        return cleaned_data


class ExternalSystemForm(TenantScopedForm):
    class Meta:
        model = ExternalSystem
        fields = ['name', 'kind', 'base_url', 'active']
        labels = {
            'name': 'Nome do sistema externo',
            'kind': 'Tipo',
            'base_url': 'URL base',
            'active': 'Ativo',
        }
        help_texts = {
            'base_url': 'URL principal ou endpoint de referência.',
        }


class AIProviderForm(TenantScopedForm):
    api_key = forms.CharField(
        required=False,
        label='Chave da API',
        widget=forms.PasswordInput(render_value=False),
        help_text='Opcional. Preencha para gravar a credencial no OpenCode e atualizar o provider local.',
    )
    api_base_url = forms.CharField(
        required=False,
        label='URL base da API',
        help_text='Deixe em branco para OpenCode Go; preencha apenas em providers com endpoint HTTP.',
    )

    class Meta:
        model = AIProvider
        fields = ['name', 'kind', 'model_name', 'api_base_url', 'active', 'notes']
        labels = {
            'name': 'Nome do provider',
            'kind': 'Fornecedor',
            'model_name': 'Modelo padrão',
            'active': 'Ativo',
            'notes': 'Observações',
        }
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
            'model_name': forms.TextInput(attrs={'list': 'provider-model-suggestions'}),
            'api_base_url': forms.TextInput(attrs={'placeholder': 'https://...'}),
        }
        help_texts = {
            'notes': 'Guarde aqui o contexto operacional do provider.',
            'model_name': 'Use uma das sugestões do catálogo; você também pode digitar um modelo customizado.',
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        kind = None
        if self.is_bound:
            kind = self.data.get('kind')
        elif self.instance and getattr(self.instance, 'kind', None):
            kind = self.instance.kind
        self.model_suggestions = provider_model_options(kind or '')
        self.model_catalog = provider_model_catalog_flat()
        self.fields['kind'].widget.attrs['data-model-options'] = 'provider-model-map'
        self.fields['model_name'].widget.attrs['data-model-input'] = 'true'
        if kind == AIProvider.Kind.OPENCODE:
            self.fields['api_base_url'].widget.attrs['placeholder'] = 'Não usado no OpenCode Go'
            self.fields['api_base_url'].widget.attrs['disabled'] = True

    def clean_api_base_url(self):
        api_base_url = (self.cleaned_data.get('api_base_url') or '').strip()
        kind = self.cleaned_data.get('kind')
        if kind == AIProvider.Kind.OPENCODE:
            return ''
        if api_base_url:
            URLValidator(schemes=['http', 'https'])(api_base_url)
            host = (urlparse(api_base_url).hostname or '').lower()
            allowed = provider_allowed_hosts(kind)
            if host not in allowed:
                raise ValidationError(
                    'Host não permitido para este fornecedor. Permitidos: '
                    f'{", ".join(sorted(allowed)) or "nenhum"}. '
                    'Fale com o administrador da plataforma para liberar um endpoint próprio.'
                )
        return api_base_url

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get('kind')
        if kind == AIProvider.Kind.OPENCODE:
            cleaned['api_base_url'] = ''
        return cleaned


class KnowledgeSourceForm(TenantScopedForm):
    class Meta:
        model = KnowledgeSource
        fields = ['identifier', 'title', 'kind', 'source_path', 'source_url', 'summary', 'content', 'active']
        labels = {
            'identifier': 'Identificador',
            'title': 'Título',
            'kind': 'Tipo',
            'source_path': 'Caminho da fonte',
            'source_url': 'URL da fonte',
            'summary': 'Resumo',
            'content': 'Conteúdo',
            'active': 'Ativo',
        }
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 4}),
            'content': forms.Textarea(attrs={'rows': 12}),
        }
        help_texts = {
            'identifier': 'Use um identificador estável, como o caminho relativo do arquivo.',
            'source_path': 'Opcional para rastrear a origem física do documento.',
            'source_url': 'Preencha quando a fonte vier de uma URL pública.',
        }


class KnowledgeSourceImportForm(forms.Form):
    url = forms.URLField(label='URL pública', help_text='Cole a URL do artigo, página ou documento que deseja importar.')
    identifier = forms.CharField(label='Identificador', required=False, max_length=240, help_text='Opcional: se vazio, a aplicação gera um identificador estável a partir da URL.')
    title = forms.CharField(label='Título', required=False, max_length=255, help_text='Opcional: se vazio, usamos o título encontrado na página.')

    def clean_url(self):
        url = (self.cleaned_data.get('url') or '').strip()
        validator = URLValidator(schemes=['http', 'https'])
        try:
            validator(url)
        except ValidationError as exc:
            raise ValidationError('Informe uma URL pública válida com http ou https.') from exc
        return url


class AIAgentForm(TenantScopedForm):
    knowledge_sources = forms.ModelMultipleChoiceField(
        queryset=KnowledgeSource.objects.none(),
        required=False,
        label='Fontes de conhecimento',
        help_text='Selecione os documentos que alimentam este agente.',
    )

    class Meta:
        model = AIAgent
        fields = ['name', 'slug', 'provider', 'purpose', 'system_prompt', 'model_override', 'temperature', 'active']
        labels = {
            'name': 'Nome do agente',
            'slug': 'Slug',
            'provider': 'Provider',
            'purpose': 'Objetivo',
            'system_prompt': 'Prompt do sistema',
            'model_override': 'Modelo específico',
            'temperature': 'Temperatura',
            'active': 'Ativo',
        }
        widgets = {
            'purpose': forms.Textarea(attrs={'rows': 3}),
            'system_prompt': forms.Textarea(attrs={'rows': 10}),
        }
        help_texts = {
            'model_override': 'Opcional: substitui o modelo padrão do provider.',
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        if tenant is not None:
            self.fields['provider'].queryset = AIProvider.objects.filter(tenant=tenant).order_by('name')
            self.fields['knowledge_sources'].queryset = KnowledgeSource.objects.filter(tenant=tenant, active=True).order_by('title')

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.tenant is not None and not obj.tenant_id:
            obj.tenant = self.tenant
        if commit:
            obj.save()
            selected_sources = list(self.cleaned_data.get('knowledge_sources', []))
            existing_source_ids = set(
                AIAgentSourceLink.objects.filter(tenant=obj.tenant, agent=obj).values_list('source_id', flat=True)
            )
            selected_source_ids = set(source.pk for source in selected_sources)
            AIAgentSourceLink.objects.filter(tenant=obj.tenant, agent=obj, source_id__in=(existing_source_ids - selected_source_ids)).delete()
            for index, source in enumerate(selected_sources):
                AIAgentSourceLink.objects.update_or_create(
                    tenant=obj.tenant,
                    agent=obj,
                    source=source,
                    defaults={'order': index, 'active': True},
                )
            self.save_m2m()
        return obj


class AIAgentRunForm(forms.Form):
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.none(), widget=forms.HiddenInput)
    agent = forms.ModelChoiceField(queryset=AIAgent.objects.none(), label='Agente')
    question = forms.CharField(label='Pergunta', widget=forms.Textarea(attrs={'rows': 4}), max_length=2000)

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            attrs = widget.attrs.setdefault('class', '')
            classes = [c for c in attrs.split() if c]
            for candidate in ('form-control', 'field-input'):
                if candidate not in classes:
                    classes.append(candidate)
            widget.attrs['class'] = ' '.join(classes).strip()
        if user is not None and getattr(user, 'is_superuser', False):
            tenant_qs = Tenant.objects.filter(active=True)
        else:
            tenant_qs = Tenant.objects.filter(active=True, pk=tenant.pk) if tenant is not None else Tenant.objects.none()
        self.fields['tenant'].queryset = tenant_qs
        if tenant is not None:
            self.fields['tenant'].initial = tenant
            self.fields['agent'].queryset = AIAgent.objects.filter(tenant=tenant, active=True).select_related('provider').order_by('name')
        elif self.is_bound:
            tenant_id = self.data.get('tenant')
            if tenant_id:
                self.fields['agent'].queryset = AIAgent.objects.filter(tenant_id=tenant_id, active=True).select_related('provider').order_by('name')


class IntegrationRecordForm(TenantScopedForm):
    status = forms.ChoiceField(
        choices=[
            ('received', 'Recebido'),
            ('processed', 'Processado'),
            ('error', 'Erro'),
            ('retry', 'Reprocessar'),
        ],
        initial='received',
        label='Status',
    )

    class Meta:
        model = IntegrationRecord
        fields = ['external_system', 'correlation_id', 'external_object_id', 'payload', 'status', 'error_message']
        labels = {
            'external_system': 'Sistema externo',
            'correlation_id': 'ID de correlação',
            'external_object_id': 'ID externo',
            'payload': 'Payload',
            'error_message': 'Mensagem de erro',
        }
        widgets = {
            'payload': forms.Textarea(attrs={'rows': 8}),
            'error_message': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, tenant: Tenant | None = None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, user=user, **kwargs)
        if tenant is not None:
            self.fields['external_system'].queryset = ExternalSystem.objects.filter(tenant=tenant, active=True)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.tenant is not None and not obj.tenant_id:
            obj.tenant = self.tenant
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class IntegrationImportForm(forms.Form):
    model = forms.ChoiceField(
        choices=[(key, MODEL_LABELS.get(key, key.title())) for key in MODEL_REGISTRY],
        label='Modelo',
    )
    conflict_policy = forms.ChoiceField(
        choices=[
            ('skip', 'Ignorar conflitos'),
            ('overwrite', 'Sobrescrever dados'),
            ('error', 'Falhar no conflito'),
        ],
        label='Política de conflito',
    )
    payload = forms.CharField(
        label='Conteúdo CSV ou JSON',
        widget=forms.Textarea(attrs={'rows': 12}),
        help_text='Cole um CSV com cabeçalho ou um JSON em formato de lista.',
    )


class IntegrationExportForm(forms.Form):
    model = forms.ChoiceField(
        choices=[(key, MODEL_LABELS.get(key, key.title())) for key in MODEL_REGISTRY],
        label='Modelo',
    )
