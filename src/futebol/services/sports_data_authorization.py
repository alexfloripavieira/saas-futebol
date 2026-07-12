"""Decisões auditáveis sobre processamento de dados esportivos por IA."""

import hashlib

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from futebol.models import AIProvider, SportsDataSource, TenantMembership
from futebol.services.audit import log_audit_event


@transaction.atomic
def authorize_external_ai_processing(
    *, source: SportsDataSource, actor, provider_scope: str, note: str,
):
    allowed_actor = actor.is_superuser or TenantMembership.objects.filter(
        tenant=source.tenant, user=actor, active=True,
        role__in=[
            TenantMembership.Role.ADMIN_TENANT,
            TenantMembership.Role.GESTOR_CLUBE,
            TenantMembership.Role.ADMIN_PLATAFORMA,
        ],
    ).exists()
    if not allowed_actor:
        raise ValidationError('Usuário sem permissão para autorizar processamento externo.')
    provider_scope = (provider_scope or '').strip()
    if provider_scope not in {'any', *AIProvider.Kind.values}:
        raise ValidationError('Escopo de provider inválido.')
    note = (note or '').strip()
    if len(note) < 20:
        raise ValidationError('Registre o fundamento da autorização com ao menos 20 caracteres.')
    before = {
        'external_ai_processing_allowed': source.external_ai_processing_allowed,
        'external_ai_provider_scope': source.external_ai_provider_scope,
    }
    source.external_ai_processing_allowed = True
    source.external_ai_provider_scope = provider_scope
    source.external_ai_authorization_note = note[:500]
    source.external_ai_authorized_at = timezone.now()
    source.external_ai_authorized_by = actor
    source.save(update_fields=[
        'external_ai_processing_allowed', 'external_ai_provider_scope',
        'external_ai_authorization_note', 'external_ai_authorized_at',
        'external_ai_authorized_by', 'updated_at',
    ])
    log_audit_event(
        tenant=source.tenant, actor=actor, action='update', obj=source,
        before_state=before,
        after_state={
            'external_ai_processing_allowed': True,
            'external_ai_provider_scope': provider_scope,
            'external_ai_authorized_by': actor.pk,
            'external_ai_authorized_at': source.external_ai_authorized_at.isoformat(),
            'authorization_note_hash': hashlib.sha256(note.encode()).hexdigest(),
        },
    )
    return source
