"""Gate registrations — the football-specific side of the approval engine.

Each gate declares its target model, proponent role, and the atomic
`on_approved` / `on_rejected` effects. Imported once from FutebolConfig.ready()
so the registry is populated at startup. See docs/adr/0001.
"""
from __future__ import annotations

from django.utils import timezone

from futebol.models import Contract, Match, Negotiation
from futebol.services.approvals import GateSpec, register
from futebol.services.audit import log_audit_event, snapshot_instance


# ─── G-1: Contrato ──────────────────────────────────────────────────────────

def contract_approved(request):
    contract = request.content_object
    contract.status = Contract.Status.ACTIVE
    if not contract.signed_at:
        contract.signed_at = timezone.now()
    contract.save()


def contract_rejected(request):
    contract = request.content_object
    contract.status = Contract.Status.TERMINATED
    contract.termination_reason = 'Rejeitado na aprovação.'
    contract.save()


# ─── G-5: Transferência (two-step + evidence) ────────────────────────────────

def transfer_approved(request):
    negotiation = request.content_object
    today = timezone.now().date()
    actor = request.decisions.order_by('-decided_at', '-id').first().decided_by
    negotiation_before = snapshot_instance(negotiation)
    # Rescind the athlete's current active contracts (origin).
    origin_contracts = list(Contract.objects.select_for_update().filter(
        tenant_id=negotiation.tenant_id,
        person_id=negotiation.person_id,
        status=Contract.Status.ACTIVE,
    ))
    for contract in origin_contracts:
        before_state = snapshot_instance(contract)
        contract.status = Contract.Status.TERMINATED
        contract.end_date = today
        contract.termination_reason = 'Transferência.'
        contract.save()
        log_audit_event(
            tenant=contract.tenant,
            actor=actor,
            action='update',
            obj=contract,
            before_state=before_state,
            after_state=snapshot_instance(contract),
        )
    # Create the destination contract already active — this approval is its approval.
    destination_contract = Contract.objects.create(
        tenant=negotiation.tenant,
        person=negotiation.person,
        club=negotiation.club,
        start_date=today,
        signed_at=timezone.now(),
        status=Contract.Status.ACTIVE,
    )
    log_audit_event(
        tenant=destination_contract.tenant,
        actor=actor,
        action='create',
        obj=destination_contract,
        after_state=snapshot_instance(destination_contract),
    )
    negotiation.status = Negotiation.Status.ACCEPTED
    negotiation.closed_at = timezone.now()
    negotiation.save()
    log_audit_event(
        tenant=negotiation.tenant,
        actor=actor,
        action='update',
        obj=negotiation,
        before_state=negotiation_before,
        after_state=snapshot_instance(negotiation),
    )


def transfer_rejected(request):
    negotiation = request.content_object
    negotiation.status = Negotiation.Status.OPEN
    negotiation.save()


# ─── G-3: Reabertura de partida ──────────────────────────────────────────────

def match_reopen_approved(request):
    match = request.content_object
    match.events.all().delete()
    match.status = Match.Status.SCHEDULED
    match.home_score = None
    match.away_score = None
    match.save()


def match_reopen_rejected(request):
    # No-op on the target; the attempt is audited elsewhere.
    return None


def register_gates():
    register(GateSpec(
        target_kind='contrato',
        target_model=Contract,
        proponent_role='gestor_clube',
        on_approved=contract_approved,
        on_rejected=contract_rejected,
    ))
    register(GateSpec(
        target_kind='transferencia',
        target_model=Negotiation,
        proponent_role='gestor_clube',
        on_approved=transfer_approved,
        on_rejected=transfer_rejected,
    ))
    register(GateSpec(
        target_kind='partida',
        target_model=Match,
        proponent_role='gestor_competicao',
        on_approved=match_reopen_approved,
        on_rejected=match_reopen_rejected,
    ))
