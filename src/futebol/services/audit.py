from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from futebol.middleware import request_id_var
from futebol.models import AuditLog


_JSON_TYPES = (str, int, float, bool, type(None))


def current_correlation_id() -> str:
    try:
        return request_id_var.get()
    except LookupError:
        return '-'


def _jsonable(value):
    if isinstance(value, _JSON_TYPES):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, models.Model):
        return value.pk
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return str(value)


def snapshot_instance(instance: models.Model, fields: Iterable[str] | None = None) -> dict:
    if instance is None:
        return {}
    chosen = set(fields) if fields is not None else None
    data: dict[str, object] = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key:
            continue
        if chosen is not None and field.name not in chosen and field.attname not in chosen:
            continue
        value = getattr(instance, field.attname)
        data[field.name] = _jsonable(value)
    return data


def log_audit_event(
    *,
    tenant,
    action: str,
    obj: models.Model,
    actor=None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    correlation_id: str | None = None,
):
    if obj is None:
        return None
    return AuditLog.objects.create(
        tenant=tenant,
        actor=actor,
        action=action,
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=str(obj.pk),
        before_state=before_state or {},
        after_state=after_state or {},
        correlation_id=correlation_id or current_correlation_id(),
    )
