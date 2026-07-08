from __future__ import annotations

from django import forms
from django.contrib.contenttypes.models import ContentType

from .models import (
    ApprovalFlow,
    ApprovalRequest,
    Club,
    Competition,
    CompetitionPhase,
    ExternalSystem,
    IntegrationRecord,
    Match,
    Notification,
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
