"""Fila durável e máquina de estados da Comissão Técnica Digital."""

from datetime import timedelta
import logging
import uuid

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from futebol.models import (
    AIAgent, MatchDossier, Notification, SpecialistOpinion, SportsDataArtifact,
    TacticalAgentOpinion, TacticalCommissionRun, TacticalCommissionTask, Tenant,
    TenantMembership,
)
from futebol.services.audit import log_audit_event
from futebol.services.dossier_ai import (
    AGENT_SLUGS,
    persist_dossier_coordinator_decision,
    persist_dossier_specialist_opinion,
    prepare_dossier_coordinator_decision,
    prepare_dossier_specialist_opinion,
)
from futebol.services.tactical_ai import generate_tactical_agent_opinions
from futebol.services.tactical_engine import build_agent_training_insights


COORDINATOR = 'coordinator'
logger = logging.getLogger(__name__)
TERMINAL_TASK_STATUSES = {
    TacticalCommissionTask.Status.COMPLETED,
    TacticalCommissionTask.Status.FAILED,
    TacticalCommissionTask.Status.CANCELLED,
}


def _can_manage(actor, tenant):
    return actor.is_superuser or TenantMembership.objects.filter(
        tenant=tenant, user=actor, active=True,
        role__in=[
            TenantMembership.Role.ADMIN_TENANT,
            TenantMembership.Role.GESTOR_CLUBE,
            TenantMembership.Role.ADMIN_PLATAFORMA,
        ],
    ).exists()


def _validate_source(artifact):
    source = artifact.batch.source
    if not (
        source.external_ai_processing_allowed and source.external_ai_authorized_by_id and
        source.external_ai_authorized_at and source.external_ai_authorization_note.strip() and
        source.external_ai_provider_scope
    ):
        raise ValidationError('A fonte não autoriza processamento por provider de IA externo.')


@transaction.atomic
def enqueue_commission(
    *, artifact, actor, specialties=None, idempotency_key='', max_provider_calls=8,
):
    """Registra uma execução e suas tarefas sem chamar o provider na request."""
    artifact = SportsDataArtifact.objects.select_for_update().select_related(
        'batch__source', 'tenant',
    ).get(pk=artifact.pk)
    if not _can_manage(actor, artifact.tenant):
        raise ValidationError('Usuário sem permissão para executar a comissão técnica.')
    _validate_source(artifact)
    daily_limit = int(getattr(settings, 'TACTICAL_COMMISSION_DAILY_CALL_LIMIT', 40))
    used_today = TacticalCommissionRun.objects.filter(
        tenant=artifact.tenant,
        created_at__gte=timezone.now() - timedelta(hours=24),
    ).aggregate(total=Sum('provider_calls_used'))['total'] or 0
    remaining = max(0, daily_limit - used_today)
    if max_provider_calls < 1 or max_provider_calls > 50 or remaining < 1:
        raise ValidationError('Limite de chamadas do provider inválido.')
    max_provider_calls = min(max_provider_calls, remaining)
    available = [
        item['agent'] for item in build_agent_training_insights(
            artifact.metadata.get('tactical_engine') or {},
        ) if item.get('agent') != COORDINATOR
    ]
    requested = list(dict.fromkeys(specialties or available))
    if not requested or not set(requested).issubset(set(available)):
        raise ValidationError('Seleção de personas inválida para este artefato.')
    key = (idempotency_key or f'artifact-{artifact.pk}-{uuid.uuid4().hex}')[:120]
    existing = TacticalCommissionRun.objects.filter(
        tenant=artifact.tenant, idempotency_key=key,
    ).first()
    if existing:
        return existing
    run = TacticalCommissionRun.objects.create(
        tenant=artifact.tenant, artifact=artifact, requested_by=actor,
        idempotency_key=key, requested_specialties=requested,
        max_provider_calls=max_provider_calls,
        correlation_id=uuid.uuid4(),
    )
    now = timezone.now()
    for specialty in requested:
        TacticalCommissionTask.objects.create(
            tenant=artifact.tenant, run=run, specialty=specialty,
            available_at=now,
        )
    TacticalCommissionTask.objects.create(
        tenant=artifact.tenant, run=run, specialty=COORDINATOR,
        available_at=now + timedelta(days=3650),
    )
    log_audit_event(
        tenant=artifact.tenant, actor=actor, action='create', obj=run,
        after_state={
            'artifact_id': artifact.pk, 'specialties': requested,
            'max_provider_calls': max_provider_calls,
            'correlation_id': str(run.correlation_id),
        },
    )
    return run


@transaction.atomic
def enqueue_dossier_commission(
    *, dossier, actor, specialties=None, idempotency_key='', max_provider_calls=8,
):
    """Enfileira a decisão operacional sem chamar o provider na requisição."""
    dossier = MatchDossier.objects.select_for_update().select_related('tenant').get(
        pk=dossier.pk,
    )
    if not _can_manage(actor, dossier.tenant):
        raise ValidationError('Usuário sem permissão para executar a comissão técnica.')
    key = (idempotency_key or f'dossier-{dossier.pk}-v{dossier.version}')[:120]
    existing = TacticalCommissionRun.objects.filter(
        tenant=dossier.tenant, idempotency_key=key,
    ).first()
    if existing:
        if existing.dossier_id != dossier.pk:
            raise ValidationError('Chave idempotente já pertence a outro Dossiê.')
        return existing
    active_slugs = set(AIAgent.objects.filter(
        tenant=dossier.tenant,
        active=True,
        provider__active=True,
        provider__operational_data_processing_allowed=True,
        provider__operational_data_authorized_at__isnull=False,
        provider__operational_data_authorized_by__isnull=False,
        slug__in=AGENT_SLUGS.values(),
    ).values_list('slug', flat=True))
    if AGENT_SLUGS[SpecialistOpinion.Specialty.COORDINATOR] not in active_slugs:
        raise ValidationError('Coordenador Técnico sem provider ativo.')
    available = [
        specialty for specialty, slug in AGENT_SLUGS.items()
        if specialty != COORDINATOR and slug in active_slugs
    ]
    required_specialties = [
        specialty for specialty in AGENT_SLUGS if specialty != COORDINATOR
    ]
    if specialties is None and set(available) != set(required_specialties):
        missing = [
            dict(SpecialistOpinion.Specialty.choices)[specialty]
            for specialty in required_specialties if specialty not in available
        ]
        raise ValidationError(
            'Comissão Técnica Digital incompleta; configure provider ativo para: '
            + ', '.join(missing)
            + '.'
        )
    requested = list(dict.fromkeys(specialties or available))
    if not requested or not set(requested).issubset(set(available)):
        raise ValidationError('Seleção de personas inválida para o Dossiê.')
    required_calls = len(requested) + 1
    if max_provider_calls < required_calls:
        raise ValidationError('Limite de chamadas insuficiente para especialistas e Coordenador.')
    daily_limit = int(getattr(settings, 'TACTICAL_COMMISSION_DAILY_CALL_LIMIT', 40))
    used_today = TacticalCommissionRun.objects.filter(
        tenant=dossier.tenant,
        created_at__gte=timezone.now() - timedelta(hours=24),
    ).aggregate(total=Sum('provider_calls_used'))['total'] or 0
    remaining = max(0, daily_limit - used_today)
    if remaining < required_calls:
        raise ValidationError('Limite diário do provider insuficiente para o Dossiê.')
    run = TacticalCommissionRun.objects.create(
        tenant=dossier.tenant,
        dossier=dossier,
        requested_by=actor,
        idempotency_key=key,
        requested_specialties=requested,
        max_provider_calls=min(max_provider_calls, remaining),
        correlation_id=uuid.uuid4(),
    )
    now = timezone.now()
    for specialty in requested:
        TacticalCommissionTask.objects.create(
            tenant=dossier.tenant,
            run=run,
            specialty=specialty,
            available_at=now,
        )
    TacticalCommissionTask.objects.create(
        tenant=dossier.tenant,
        run=run,
        specialty=COORDINATOR,
        available_at=now + timedelta(days=3650),
    )
    dossier.status = MatchDossier.Status.PROCESSING
    dossier.save(update_fields=['status', 'updated_at'])
    log_audit_event(
        tenant=dossier.tenant,
        actor=actor,
        action='create',
        obj=run,
        after_state={
            'dossier_id': dossier.pk,
            'specialties': requested,
            'max_provider_calls': run.max_provider_calls,
            'correlation_id': str(run.correlation_id),
        },
    )
    return run


@transaction.atomic
def claim_next_task(*, worker_id, lease_seconds=300):
    """Reivindica uma tarefa sem manter lock durante a chamada externa."""
    now = timezone.now()
    TacticalCommissionTask.objects.filter(
        status=TacticalCommissionTask.Status.RUNNING,
        lease_expires_at__lt=now,
        run__status__in=[
            TacticalCommissionRun.Status.QUEUED,
            TacticalCommissionRun.Status.RUNNING,
            TacticalCommissionRun.Status.PARTIAL,
        ],
    ).update(
        status=TacticalCommissionTask.Status.QUEUED,
        lease_owner='', lease_expires_at=None, available_at=now,
        error_code='lease_expired',
    )
    task = (
        TacticalCommissionTask.objects.select_for_update(skip_locked=True)
        .select_related('run')
        .filter(
            status=TacticalCommissionTask.Status.QUEUED,
            available_at__lte=now,
            run__status__in=[
                TacticalCommissionRun.Status.QUEUED,
                TacticalCommissionRun.Status.RUNNING,
                TacticalCommissionRun.Status.PARTIAL,
            ],
        )
        .order_by('available_at', 'created_at')
        .first()
    )
    if not task:
        return None
    task.status = TacticalCommissionTask.Status.RUNNING
    task.lease_owner = str(worker_id)[:100]
    task.lease_expires_at = now + timedelta(seconds=max(30, lease_seconds))
    task.started_at = task.started_at or now
    task.error_code = ''
    task.save(update_fields=[
        'status', 'lease_owner', 'lease_expires_at', 'started_at',
        'error_code', 'updated_at',
    ])
    if task.run.status == TacticalCommissionRun.Status.QUEUED:
        task.run.status = TacticalCommissionRun.Status.RUNNING
        task.run.started_at = task.run.started_at or now
        task.run.save(update_fields=['status', 'started_at', 'updated_at'])
    return task


def _latest_tasks(run, *, exclude_coordinator=False):
    queryset = run.tasks.all().order_by('specialty', '-attempt', '-id')
    if exclude_coordinator:
        queryset = queryset.exclude(specialty=COORDINATOR)
    latest = {}
    for task in queryset:
        latest.setdefault(task.specialty, task)
    return list(latest.values())


def _build_consolidation(run):
    opinions = [
        task.opinion for task in _latest_tasks(run, exclude_coordinator=True)
        if task.opinion_id
    ]
    recommendations = []
    evidence_ids = []
    for opinion in opinions:
        recommendations.extend(opinion.recommendations[:2])
        evidence_ids.extend(opinion.evidence_ids)
    recommendations = list(dict.fromkeys(recommendations))[:8]
    evidence_ids = list(dict.fromkeys(evidence_ids))
    strengths = [op.summary for op in opinions if op.confidence >= 50][:4]
    conflicts = [
        {
            'topic': 'prioridade do plano',
            'perspectives': [op.specialty for op in opinions[:4]],
            'requires_human_decision': True,
        },
    ] if len(opinions) > 1 else []
    base = recommendations or ['Manter a hipótese em treinamento até ampliar a amostra.']
    plans = [
        {'variant': 'balanced', 'label': 'Equilibrado', 'recommendations': base[:4], 'requires_human_review': True},
        {'variant': 'offensive', 'label': 'Ofensivo', 'recommendations': base[1:5] or base[:3], 'requires_human_review': True},
        {'variant': 'conservative', 'label': 'Conservador', 'recommendations': list(reversed(base[:4])), 'requires_human_review': True},
    ]
    return {
        'summary': 'Síntese da Comissão Técnica Digital para treinamento.',
        'strengths': strengths,
        'evidence_ids': evidence_ids,
        'requires_human_review': True,
    }, conflicts, plans


def _reconcile_dossier_run(run):
    specialist_tasks = _latest_tasks(run, exclude_coordinator=True)
    coordinator = next(
        (task for task in _latest_tasks(run) if task.specialty == COORDINATOR), None,
    )
    specialists_complete = specialist_tasks and all(
        task.status == TacticalCommissionTask.Status.COMPLETED
        and task.execution_mode == SpecialistOpinion.ExecutionMode.PROVIDER
        for task in specialist_tasks
    )
    specialists_terminal = specialist_tasks and all(
        task.status in TERMINAL_TASK_STATUSES for task in specialist_tasks
    )
    if specialists_complete:
        if coordinator and coordinator.status == TacticalCommissionTask.Status.QUEUED:
            coordinator.available_at = timezone.now()
            coordinator.save(update_fields=['available_at', 'updated_at'])
    elif specialists_terminal:
        if coordinator and coordinator.status == TacticalCommissionTask.Status.QUEUED:
            coordinator.status = TacticalCommissionTask.Status.CANCELLED
            coordinator.error_code = 'specialist_dependency_failed'
            coordinator.finished_at = timezone.now()
            coordinator.save(update_fields=[
                'status', 'error_code', 'finished_at', 'updated_at',
            ])
        successful = sum(
            task.status == TacticalCommissionTask.Status.COMPLETED
            and task.execution_mode == SpecialistOpinion.ExecutionMode.PROVIDER
            for task in specialist_tasks
        )
        run.status = (
            TacticalCommissionRun.Status.PARTIAL
            if successful else TacticalCommissionRun.Status.FAILED
        )
        run.dossier.status = (
            MatchDossier.Status.PARTIAL if successful else MatchDossier.Status.FAILED
        )
        run.dossier.save(update_fields=['status', 'updated_at'])
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'finished_at', 'updated_at'])

    tasks = _latest_tasks(run)
    if not tasks or not all(task.status in TERMINAL_TASK_STATUSES for task in tasks):
        return run
    if all(task.status == TacticalCommissionTask.Status.COMPLETED for task in tasks):
        run.status = TacticalCommissionRun.Status.COMPLETED
    elif run.status not in {
        TacticalCommissionRun.Status.PARTIAL, TacticalCommissionRun.Status.FAILED,
    }:
        run.status = TacticalCommissionRun.Status.PARTIAL
        run.dossier.status = MatchDossier.Status.PARTIAL
        run.dossier.save(update_fields=['status', 'updated_at'])
    run.finished_at = run.finished_at or timezone.now()
    run.save(update_fields=['status', 'finished_at', 'updated_at'])
    if not run.notification_sent:
        Notification.objects.create(
            tenant=run.tenant,
            recipient=run.requested_by,
            subject='Comissão Técnica Digital concluída',
            body=(
                'A IA concluiu a Sala da Próxima Partida.'
                if run.status == TacticalCommissionRun.Status.COMPLETED
                else 'A IA não concluiu todas as análises. Revise as falhas e tente novamente.'
            ),
            metadata={'commission_run_id': run.pk, 'dossier_id': run.dossier_id},
        )
        run.notification_sent = True
        run.save(update_fields=['notification_sent', 'updated_at'])
    return run


@transaction.atomic
def reconcile_run(run_id):
    # Bloqueia somente a execução. ``dossier`` é anulável porque esta fila também
    # atende os ensaios de P&D; incluir o LEFT JOIN no FOR UPDATE quebra no Postgres.
    run = TacticalCommissionRun.objects.select_for_update().get(pk=run_id)
    if run.status == TacticalCommissionRun.Status.CANCELLED:
        return run
    if run.dossier_id:
        return _reconcile_dossier_run(run)
    specialist_tasks = _latest_tasks(run, exclude_coordinator=True)
    if specialist_tasks and all(task.status in TERMINAL_TASK_STATUSES for task in specialist_tasks):
        coordinator = next(
            (task for task in _latest_tasks(run) if task.specialty == COORDINATOR), None,
        )
        if coordinator and coordinator.status == TacticalCommissionTask.Status.QUEUED:
            coordinator.available_at = timezone.now()
            coordinator.save(update_fields=['available_at', 'updated_at'])
        has_issue = any(
            task.status == TacticalCommissionTask.Status.FAILED or
            task.execution_mode == TacticalAgentOpinion.ExecutionMode.FALLBACK
            for task in specialist_tasks
        )
        if has_issue and run.status != TacticalCommissionRun.Status.PARTIAL:
            run.status = TacticalCommissionRun.Status.PARTIAL
            run.save(update_fields=['status', 'updated_at'])
    tasks = _latest_tasks(run)
    if not tasks or not all(task.status in TERMINAL_TASK_STATUSES for task in tasks):
        return run
    useful = [task for task in tasks if task.status == TacticalCommissionTask.Status.COMPLETED]
    failed = [task for task in tasks if task.status == TacticalCommissionTask.Status.FAILED]
    fallback = [
        task for task in useful
        if task.specialty != COORDINATOR and
        task.execution_mode == TacticalAgentOpinion.ExecutionMode.FALLBACK
    ]
    if not useful:
        status = TacticalCommissionRun.Status.FAILED
    elif failed or fallback:
        status = TacticalCommissionRun.Status.PARTIAL
    else:
        status = TacticalCommissionRun.Status.COMPLETED
    synthesis, conflicts, plans = _build_consolidation(run)
    run.status = status
    run.synthesis = synthesis
    run.conflicts = conflicts
    run.plan_variants = plans
    run.finished_at = timezone.now()
    run.save(update_fields=[
        'status', 'synthesis', 'conflicts', 'plan_variants', 'finished_at', 'updated_at',
    ])
    if not run.notification_sent:
        Notification.objects.create(
            tenant=run.tenant, recipient=run.requested_by,
            subject='Comissão Técnica Digital concluída',
            body='A análise terminou. Revise os pareceres e cenários antes de qualquer decisão.',
            metadata={'commission_run_id': run.pk, 'status': status},
        )
        run.notification_sent = True
        run.save(update_fields=['notification_sent', 'updated_at'])
    return run


def execute_claimed_task(*, task_id, worker_id):
    task = TacticalCommissionTask.objects.select_related(
        'run', 'run__artifact', 'run__dossier', 'run__requested_by',
    ).get(pk=task_id)
    if (
        task.status != TacticalCommissionTask.Status.RUNNING
        or task.lease_owner != str(worker_id)[:100]
        or not task.lease_expires_at
        or task.lease_expires_at <= timezone.now()
    ):
        raise ValidationError('Lease da tarefa não pertence mais a este worker.')
    run = task.run
    with transaction.atomic():
        locked = TacticalCommissionRun.objects.select_for_update().get(pk=run.pk)
        current_task = TacticalCommissionTask.objects.select_for_update().get(pk=task.pk)
        if not (
            current_task.status == TacticalCommissionTask.Status.RUNNING and
            current_task.lease_owner == str(worker_id)[:100] and
            current_task.lease_expires_at and
            current_task.lease_expires_at > timezone.now()
        ):
            raise ValidationError('Lease da tarefa não pertence mais a este worker.')
        if locked.status == TacticalCommissionRun.Status.CANCELLED:
            current_task.status = TacticalCommissionTask.Status.CANCELLED
            current_task.finished_at = timezone.now()
            current_task.lease_expires_at = None
            current_task.save(update_fields=[
                'status', 'finished_at', 'lease_expires_at', 'updated_at',
            ])
            return current_task
        if task.specialty == COORDINATOR and locked.artifact_id:
            synthesis, conflicts, plans = _build_consolidation(locked)
            locked.synthesis = synthesis
            locked.conflicts = conflicts
            locked.plan_variants = plans
            locked.save(update_fields=['synthesis', 'conflicts', 'plan_variants', 'updated_at'])
            current_task.status = TacticalCommissionTask.Status.COMPLETED
            current_task.execution_mode = TacticalAgentOpinion.ExecutionMode.FALLBACK
            current_task.finished_at = timezone.now()
            current_task.lease_expires_at = None
            current_task.save(update_fields=[
                'status', 'execution_mode', 'finished_at', 'lease_expires_at', 'updated_at',
            ])
            reconcile_run(run.pk)
            return current_task
        Tenant.objects.select_for_update().get(pk=locked.tenant_id)
        daily_limit = int(getattr(settings, 'TACTICAL_COMMISSION_DAILY_CALL_LIMIT', 40))
        tenant_calls = TacticalCommissionRun.objects.filter(
            tenant_id=locked.tenant_id,
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).aggregate(total=Sum('provider_calls_used'))['total'] or 0
        if (
            locked.provider_calls_used >= locked.max_provider_calls or
            tenant_calls >= daily_limit
        ):
            current_task.status = TacticalCommissionTask.Status.FAILED
            current_task.error_code = 'tenant_provider_budget_exhausted'
            current_task.finished_at = timezone.now()
            current_task.lease_expires_at = None
            current_task.save(update_fields=[
                'status', 'error_code', 'finished_at', 'lease_expires_at', 'updated_at',
            ])
            reconcile_run(run.pk)
            return current_task
        locked.provider_calls_used += 1
        locked.save(update_fields=['provider_calls_used', 'updated_at'])
    try:
        if run.dossier_id:
            if task.specialty == COORDINATOR:
                prepared_decision = prepare_dossier_coordinator_decision(
                    dossier=run.dossier,
                )
            else:
                prepared_decision = prepare_dossier_specialist_opinion(
                    dossier=run.dossier,
                    specialty=task.specialty,
                )
        else:
            opinions = generate_tactical_agent_opinions(
                artifact=run.artifact, actor=run.requested_by,
                specialties=[task.specialty],
            )
            if not opinions:
                raise ValidationError('Persona sem agente ativo ou evidência compatível.')
            opinion = opinions[0]
            specialist_opinion = None
            execution_mode = opinion.execution_mode
        with transaction.atomic():
            locked_run = TacticalCommissionRun.objects.select_for_update().get(
                pk=run.pk,
            )
            current = TacticalCommissionTask.objects.select_for_update().get(pk=task.pk)
            if not (
                current.status == TacticalCommissionTask.Status.RUNNING and
                current.lease_owner == str(worker_id)[:100] and
                current.lease_expires_at and
                current.lease_expires_at > timezone.now()
            ):
                return current
            if locked_run.status == TacticalCommissionRun.Status.CANCELLED:
                current.status = TacticalCommissionTask.Status.CANCELLED
            else:
                if run.dossier_id:
                    if task.specialty == COORDINATOR:
                        specialist_opinion = persist_dossier_coordinator_decision(
                            dossier=run.dossier,
                            prepared=prepared_decision,
                            actor=run.requested_by,
                        )
                    else:
                        specialist_opinion = persist_dossier_specialist_opinion(
                            dossier=run.dossier,
                            prepared=prepared_decision,
                            actor=run.requested_by,
                        )
                    opinion = None
                    execution_mode = SpecialistOpinion.ExecutionMode.PROVIDER
                current.status = TacticalCommissionTask.Status.COMPLETED
                current.opinion = opinion
                current.specialist_opinion = specialist_opinion
                current.execution_mode = execution_mode
            current.finished_at = timezone.now()
            current.lease_expires_at = None
            current.save(update_fields=[
                'status', 'opinion', 'specialist_opinion', 'execution_mode', 'finished_at',
                'lease_expires_at', 'updated_at',
            ])
            task = current
    except Exception as exc:
        log_context = {
            'commission_run_id': run.pk,
            'commission_task_id': task.pk,
            'specialty': task.specialty,
        }
        if isinstance(exc, ValidationError):
            logger.warning(
                'Resposta do agente rejeitada pela validação da Comissão Técnica Digital',
                extra=log_context,
            )
        else:
            logger.exception(
                'Falha inesperada ao executar agente da Comissão Técnica Digital',
                extra=log_context,
            )
        with transaction.atomic():
            locked_run = TacticalCommissionRun.objects.select_for_update().get(pk=run.pk)
            current = TacticalCommissionTask.objects.select_for_update().get(pk=task.pk)
            if not (
                current.status == TacticalCommissionTask.Status.RUNNING and
                current.lease_owner == str(worker_id)[:100] and
                current.lease_expires_at and
                current.lease_expires_at > timezone.now()
            ):
                return current
            current.status = (
                TacticalCommissionTask.Status.CANCELLED
                if locked_run.status == TacticalCommissionRun.Status.CANCELLED
                else TacticalCommissionTask.Status.FAILED
            )
            current.error_code = (
                '' if current.status == TacticalCommissionTask.Status.CANCELLED
                else 'validation_error' if isinstance(exc, ValidationError)
                else 'provider_execution_failed'
            )
            current.finished_at = timezone.now()
            current.lease_expires_at = None
            current.save(update_fields=[
                'status', 'error_code', 'finished_at', 'lease_expires_at', 'updated_at',
            ])
            task = current
    reconcile_run(run.pk)
    return task


@transaction.atomic
def cancel_commission(*, run, actor):
    run = TacticalCommissionRun.objects.select_for_update().get(pk=run.pk)
    if not _can_manage(actor, run.tenant):
        raise ValidationError('Usuário sem permissão para cancelar a comissão.')
    if run.status in {
        TacticalCommissionRun.Status.COMPLETED, TacticalCommissionRun.Status.FAILED,
    }:
        raise ValidationError('Execução já encerrada não pode ser cancelada.')
    if run.status != TacticalCommissionRun.Status.CANCELLED:
        run.status = TacticalCommissionRun.Status.CANCELLED
        run.cancelled_at = timezone.now()
        run.cancelled_by = actor
        run.finished_at = run.cancelled_at
        run.save(update_fields=[
            'status', 'cancelled_at', 'cancelled_by', 'finished_at', 'updated_at',
        ])
        run.tasks.filter(status=TacticalCommissionTask.Status.QUEUED).update(
            status=TacticalCommissionTask.Status.CANCELLED,
            finished_at=run.cancelled_at,
        )
        if run.dossier_id:
            snapshot = dict(run.dossier.data_snapshot)
            decision_engine = dict(snapshot.get('decision_engine') or {})
            decision_engine['status'] = 'cancelled'
            snapshot['decision_engine'] = decision_engine
            run.dossier.status = MatchDossier.Status.FAILED
            run.dossier.data_snapshot = snapshot
            run.dossier.save(update_fields=['status', 'data_snapshot', 'updated_at'])
        log_audit_event(
            tenant=run.tenant, actor=actor, action='update', obj=run,
            after_state={'status': run.status},
        )
    return run


@transaction.atomic
def retry_task(*, task, actor):
    task = TacticalCommissionTask.objects.select_for_update().select_related('run').get(pk=task.pk)
    run = TacticalCommissionRun.objects.select_for_update().get(pk=task.run_id)
    if not _can_manage(actor, run.tenant):
        raise ValidationError('Usuário sem permissão para repetir a persona.')
    if task.status != TacticalCommissionTask.Status.FAILED and not (
        task.status == TacticalCommissionTask.Status.COMPLETED and
        task.execution_mode == TacticalAgentOpinion.ExecutionMode.FALLBACK
    ):
        raise ValidationError('Apenas falhas ou fallbacks podem ser repetidos.')
    if task.attempt >= task.max_attempts:
        raise ValidationError('Limite de tentativas atingido para esta persona.')
    new_task, _ = TacticalCommissionTask.objects.get_or_create(
        tenant=run.tenant, run=run, specialty=task.specialty,
        attempt=task.attempt + 1,
        defaults={
            'max_attempts': task.max_attempts, 'available_at': timezone.now(),
        },
    )
    if task.specialty != COORDINATOR:
        coordinator = next(
            (item for item in _latest_tasks(run) if item.specialty == COORDINATOR), None,
        )
        if coordinator and coordinator.status in TERMINAL_TASK_STATUSES:
            TacticalCommissionTask.objects.create(
                tenant=run.tenant, run=run, specialty=COORDINATOR,
                attempt=coordinator.attempt + 1, max_attempts=coordinator.max_attempts,
                available_at=timezone.now() + timedelta(days=3650),
            )
    run.status = TacticalCommissionRun.Status.RUNNING
    run.finished_at = None
    run.notification_sent = False
    run.save(update_fields=['status', 'finished_at', 'notification_sent', 'updated_at'])
    if run.dossier_id:
        run.dossier.status = MatchDossier.Status.PROCESSING
        run.dossier.save(update_fields=['status', 'updated_at'])
    log_audit_event(
        tenant=run.tenant, actor=actor, action='update', obj=run,
        after_state={'retry_specialty': task.specialty, 'attempt': new_task.attempt},
    )
    return new_task


@transaction.atomic
def review_commission(*, run, actor, decision, note=''):
    run = TacticalCommissionRun.objects.select_for_update().get(pk=run.pk)
    if not _can_manage(actor, run.tenant):
        raise ValidationError('Usuário sem permissão para revisar a comissão.')
    if run.status not in {
        TacticalCommissionRun.Status.COMPLETED,
        TacticalCommissionRun.Status.PARTIAL,
    } or not run.finished_at:
        raise ValidationError('A comissão precisa estar concluída para revisão.')
    if decision not in {'approved_training', 'rejected'}:
        raise ValidationError('Decisão humana inválida.')
    run.review_decision = decision
    run.review_note = (note or '').strip()[:500]
    run.reviewed_by = actor
    run.reviewed_at = timezone.now()
    run.save(update_fields=[
        'review_decision', 'review_note', 'reviewed_by', 'reviewed_at', 'updated_at',
    ])
    log_audit_event(
        tenant=run.tenant, actor=actor, action='update', obj=run,
        after_state={'review_decision': decision, 'reviewed_at': run.reviewed_at.isoformat()},
    )
    return run


def serialize_run_status(run):
    tasks = _latest_tasks(run)
    total = len(tasks)
    terminal = sum(task.status in TERMINAL_TASK_STATUSES for task in tasks)
    has_active_tasks = terminal < total
    error_labels = {
        'provider_execution_failed': 'O provider não respondeu corretamente.',
        'validation_error': 'A resposta da IA não passou pela validação de segurança.',
        'tenant_provider_budget_exhausted': 'O limite de chamadas do provider foi atingido.',
        'specialist_dependency_failed': 'O Coordenador aguardará a correção dos especialistas.',
    }
    return {
        'id': run.pk,
        'status': run.status,
        'status_label': run.get_status_display(),
        'progress': round(terminal * 100 / total) if total else 0,
        'provider_calls': {
            'used': run.provider_calls_used, 'limit': run.max_provider_calls,
        },
        'tasks': [{
            'id': task.pk, 'specialty': task.specialty,
            'specialty_label': task.get_specialty_display(),
            'status': task.status, 'status_label': task.get_status_display(),
            'attempt': task.attempt,
            'execution_mode': task.execution_mode,
            'execution_mode_label': dict(
                TacticalAgentOpinion.ExecutionMode.choices,
            ).get(task.execution_mode, ''),
            'error_code': task.error_code,
            'error_label': error_labels.get(task.error_code, 'Falha na execução do agente.'),
            'can_retry': (
                (task.specialty != COORDINATOR or bool(run.dossier_id))
                and task.attempt < task.max_attempts and (
                    task.status == TacticalCommissionTask.Status.FAILED or
                    task.execution_mode == TacticalAgentOpinion.ExecutionMode.FALLBACK
                )
            ),
        } for task in tasks],
        'dossier': ({
            'id': run.dossier_id,
            'status': run.dossier.status,
            'status_label': run.dossier.get_status_display(),
        } if run.dossier_id else None),
        'synthesis': run.synthesis,
        'conflicts': run.conflicts,
        'plan_variants': run.plan_variants,
        'can_cancel': has_active_tasks and run.status in {
            TacticalCommissionRun.Status.QUEUED,
            TacticalCommissionRun.Status.RUNNING,
            TacticalCommissionRun.Status.PARTIAL,
        },
        'updated_at': run.updated_at.isoformat(),
    }
