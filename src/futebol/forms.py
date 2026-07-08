from __future__ import annotations

from django import forms
from django.contrib.contenttypes.models import ContentType

from .models import (
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
    Match,
    Negotiation,
    Notification,
    Person,
    Proposal,
    Tenant,
)
from .services.data_io import MODEL_REGISTRY


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


class BIExplorerForm(forms.Form):
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.none(), required=False, label='Tenant')
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
        choices=[(key, key.title()) for key in MODEL_REGISTRY],
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
        choices=[(key, key.title()) for key in MODEL_REGISTRY],
        label='Modelo',
    )
