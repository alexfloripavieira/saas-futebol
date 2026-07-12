"""Registro resiliente das métricas operacionais mínimas do piloto."""

from __future__ import annotations

import logging

from django.db import DatabaseError

from futebol.models import OperationalMetric


logger = logging.getLogger(__name__)


def record_metric(
    *,
    tenant,
    kind: str,
    event: str,
    route_name: str = '',
    method: str = '',
    status_code: int = 0,
    duration_ms: int = 0,
    actor=None,
    correlation_id: str = '',
    metadata: dict | None = None,
):
    """Persiste um evento sem permitir que observabilidade derrube a operação."""
    if tenant is None:
        return None
    try:
        return OperationalMetric.objects.create(
            tenant=tenant,
            kind=kind,
            event=event[:64],
            route_name=(route_name or '')[:120],
            method=(method or '')[:8],
            status_code=max(0, int(status_code or 0)),
            duration_ms=max(0, int(duration_ms or 0)),
            actor=actor if getattr(actor, 'is_authenticated', False) else None,
            correlation_id=(correlation_id or '')[:80],
            metadata=metadata or {},
        )
    except DatabaseError:
        logger.exception('Falha ao persistir métrica operacional event=%s', event)
        return None
