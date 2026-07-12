"""Approval engine — generic, multi-step, data-driven (see docs/adr/0001).

The engine knows nothing about football. Each gate is defined once in the
registry (see gates.py): its target type, the proponent role and creation
trigger, and the `on_approved` / `on_rejected` effect handlers. Terms are
canonical (Fluxo de Aprovação, Solicitação, Decisão, Etapa) — see CONTEXT.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from futebol.models import (
    AuditLog,
    ApprovalDecision,
    ApprovalFlow,
    ApprovalRequest,
    TenantMembership,
)
from futebol.services.audit import log_audit_event, snapshot_instance


@dataclass(frozen=True)
class GateSpec:
    """One gate: how a target kind is approved and what approval/rejection does."""

    target_kind: str
    target_model: type[models.Model]
    proponent_role: str
    on_approved: Callable[[ApprovalRequest], None]
    on_rejected: Callable[[ApprovalRequest], None]


REGISTRY: dict[str, GateSpec] = {}


def register(spec: GateSpec) -> None:
    REGISTRY[spec.target_kind] = spec


def get(target_kind: str) -> GateSpec:
    try:
        return REGISTRY[target_kind]
    except KeyError as exc:
        raise ValidationError(f'Nenhum gate registrado para "{target_kind}".') from exc


def spec_for_model(model: type[models.Model]) -> GateSpec:
    for spec in REGISTRY.values():
        if spec.target_model is model:
            return spec
    raise ValidationError(f'Modelo {model.__name__} não é aprovável.')


def approvable_models() -> set[type[models.Model]]:
    """The allow-list of target models — drives ApprovalRequest.clean()."""
    return {spec.target_model for spec in REGISTRY.values()}


@transaction.atomic
def open_request(target: models.Model, requested_by, reason: str = '') -> ApprovalRequest:
    """Auto-open a Solicitação over `target` (ADR-0001, decision 9)."""
    if target.pk is None:
        raise ValidationError('O alvo precisa estar salvo antes de solicitar aprovação.')
    spec = spec_for_model(type(target))
    flow = ApprovalFlow.objects.get(
        tenant=target.tenant, target_kind=spec.target_kind, active=True
    )
    if not flow.steps.exists():
        raise ValidationError('O fluxo precisa ter ao menos uma etapa antes de receber solicitações.')

    if not requested_by.is_superuser:
        allowed_roles = {
            spec.proponent_role,
            TenantMembership.Role.ADMIN_TENANT,
            TenantMembership.Role.ADMIN_PLATAFORMA,
        }
        can_propose = TenantMembership.objects.filter(
            user=requested_by,
            tenant=target.tenant,
            role__in=allowed_roles,
            active=True,
            tenant__active=True,
        ).exists()
        if not can_propose:
            raise ValidationError('O usuário não possui o papel exigido para solicitar esta aprovação.')

    content_type = ContentType.objects.get_for_model(type(target))
    if ApprovalRequest.objects.select_for_update().filter(
        tenant=target.tenant,
        content_type=content_type,
        object_id=str(target.pk),
        status=ApprovalRequest.Status.OPEN,
    ).exists():
        raise ValidationError('Já existe uma solicitação aberta para este alvo.')

    request = ApprovalRequest(
        tenant=target.tenant,
        flow=flow,
        requested_by=requested_by,
        content_type=content_type,
        object_id=str(target.pk),
        reason=reason,
    )
    request.save()
    log_audit_event(
        tenant=request.tenant,
        actor=requested_by,
        action='create',
        obj=request,
        after_state={
            'flow_id': request.flow_id,
            'target_kind': request.flow.target_kind,
            'object_id': request.object_id,
            'reason': request.reason,
            'status': request.status,
        },
    )
    return request


@transaction.atomic
def cast_decision(request: ApprovalRequest, step, user, outcome: str, note: str = '') -> ApprovalDecision:
    """Record one Decisão on one Etapa; resolve the case if it ends here.

    A rejection is terminal (ADR-0001, decision 8): it resolves the whole
    Solicitação and runs the gate's on_rejected. An approval resolves the case
    only once every Etapa of the flow has an approving Decisão.
    """
    if not request.flow.steps.exists():
        raise ValidationError('Não é possível decidir uma solicitação cujo fluxo não possui etapas.')
    if step is None:
        raise ValidationError('Não há etapa pendente para esta solicitação.')

    decision = ApprovalDecision(
        tenant=request.tenant,
        request=request,
        step=step,
        decided_by=user,
        outcome=outcome,
        note=note,
    )
    decision.save()  # full_clean() enforces the invariants (self-approval, role, order, evidence, open)

    spec = get(request.flow.target_kind)

    if outcome == ApprovalDecision.Outcome.REJECTED:
        _resolve(request, ApprovalRequest.Status.REJECTED)
        spec.on_rejected(request)
        log_audit_event(
            tenant=request.tenant,
            actor=user,
            action='reject',
            obj=request,
            before_state={'status': ApprovalRequest.Status.OPEN},
            after_state={
                'status': request.status,
                'decision_id': decision.pk,
                'step_id': step.pk,
                'outcome': outcome,
            },
        )
        return decision

    total_steps = request.flow.steps.count()
    approved_steps = request.decisions.filter(outcome=ApprovalDecision.Outcome.APPROVED).count()
    if approved_steps >= total_steps:
        _resolve(request, ApprovalRequest.Status.APPROVED)
        spec.on_approved(request)
        log_audit_event(
            tenant=request.tenant,
            actor=user,
            action='approve',
            obj=request,
            before_state={'status': ApprovalRequest.Status.OPEN},
            after_state={
                'status': request.status,
                'decision_id': decision.pk,
                'step_id': step.pk,
                'outcome': outcome,
            },
        )
    return decision


@transaction.atomic
def cancel_request(request: ApprovalRequest, user) -> ApprovalRequest:
    """Cancel a still-open case — requester or admin_tenant only, no side-effect."""
    if request.status != ApprovalRequest.Status.OPEN:
        raise ValidationError('Só é possível cancelar solicitações abertas.')
    is_requester = request.requested_by_id == user.id
    is_admin = TenantMembership.objects.filter(
        user=user,
        tenant_id=request.tenant_id,
        role=TenantMembership.Role.ADMIN_TENANT,
        active=True,
    ).exists()
    if not (is_requester or is_admin or user.is_superuser):
        raise ValidationError('Sem permissão para cancelar a solicitação.')
    _resolve(request, ApprovalRequest.Status.CANCELLED)
    log_audit_event(
        tenant=request.tenant,
        actor=user,
        action='update',
        obj=request,
        before_state={'status': ApprovalRequest.Status.OPEN},
        after_state={'status': request.status},
    )
    return request


def _resolve(request: ApprovalRequest, status: str) -> None:
    request.status = status
    request.resolved_at = timezone.now()
    request.save(update_fields=['status', 'resolved_at'])
