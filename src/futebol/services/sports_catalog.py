"""Interface de leitura da Base Esportiva Global com entitlement comercial."""

import hashlib

from django.core.exceptions import PermissionDenied
from django.db.models import Exists, F, OuterRef, Q, Subquery
from django.utils import timezone

from futebol.models import (
    GlobalSportsDataRecord,
    GlobalSportsDataSource,
    GlobalSportsSyncRun,
    TenantModuleSubscription,
)
from futebol.modules import tenant_has_module


SOURCE_ENTITLEMENT_PREFIX = 'ia-fonte:'
CAPABILITY_ENTITLEMENT_PREFIX = 'ia-cap:'


def source_entitlement_code(source_code):
    """Código comercial para liberar uma fonte global específica."""
    return _bounded_entitlement_code(SOURCE_ENTITLEMENT_PREFIX, source_code)


def capability_entitlement_code(capability):
    """Código comercial para liberar uma capacidade em qualquer fonte."""
    return _bounded_entitlement_code(CAPABILITY_ENTITLEMENT_PREFIX, capability)


def _bounded_entitlement_code(prefix, value):
    value = str(value or '').strip()
    if not value:
        raise ValueError('O identificador do entitlement não pode ser vazio.')
    readable = f'{prefix}{value}'
    if len(readable) <= 40:
        return readable
    digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
    return f'{prefix}#{digest[:40 - len(prefix) - 1]}'


def tenant_has_sports_intelligence(tenant):
    # Usa a mesma compatibilidade do menu: Tenant ainda não provisionado tem
    # acesso legado; assim o catálogo e a navegação nunca divergem.
    return bool(tenant and tenant_has_module(tenant, 'ia'))


def _require_entitlement(tenant):
    if not tenant_has_sports_intelligence(tenant):
        raise PermissionDenied(
            'O Tenant não possui o serviço de Inteligência Esportiva contratado.'
        )


def _granular_entitlements(tenant):
    """Política granular ou ``None`` para o contrato legado irrestrito de IA.

    A existência de qualquer linha granular ativa o modo restritivo, mesmo se
    todas estiverem desabilitadas. Isso permite revogar explicitamente acesso
    sem que a ausência de linhas ativas seja confundida com o contrato legado.
    """
    subscriptions = TenantModuleSubscription.objects.filter(tenant=tenant).filter(
        Q(module_code__startswith=SOURCE_ENTITLEMENT_PREFIX)
        | Q(module_code__startswith=CAPABILITY_ENTITLEMENT_PREFIX)
    )
    if not subscriptions.exists():
        return None
    enabled_codes = set(
        subscriptions.filter(enabled=True).values_list('module_code', flat=True)
    )
    source_codes = set()
    capabilities = set()
    for source in GlobalSportsDataSource.objects.only('code', 'capabilities'):
        if source_entitlement_code(source.code) in enabled_codes:
            source_codes.add(source.code)
        for capability in source.capabilities or []:
            if capability_entitlement_code(capability) in enabled_codes:
                capabilities.add(capability)
    return source_codes, capabilities


def _entitled_source_ids(policy):
    if policy is None:
        return None
    source_codes, capabilities = policy
    return [
        source.pk
        for source in GlobalSportsDataSource.objects.only('pk', 'code', 'capabilities')
        if source.code in source_codes
        or set(source.capabilities or []).intersection(capabilities)
    ]


def sources_for(tenant):
    """Fontes globais que um Tenant contratante pode consultar."""
    _require_entitlement(tenant)
    source_ids = _entitled_source_ids(_granular_entitlements(tenant))
    sources = GlobalSportsDataSource.objects.exclude(
        operational_status=GlobalSportsDataSource.OperationalStatus.DISABLED,
    )
    return sources if source_ids is None else sources.filter(pk__in=source_ids)


def capabilities_for_source(tenant, source):
    """Capacidades da fonte que o contrato atual permite revelar e consumir."""
    _require_entitlement(tenant)
    if source.operational_status == GlobalSportsDataSource.OperationalStatus.DISABLED:
        return set()
    policy = _granular_entitlements(tenant)
    declared = set(source.capabilities or [])
    if policy is None:
        return declared
    source_codes, capabilities = policy
    return declared if source.code in source_codes else declared.intersection(capabilities)


def latest_records_for(
    tenant, *, capability=None, provider_code=None, valid_at=None,
    include_expired=False,
):
    """Registros canônicos mais recentes, sem criar cópias por Tenant."""
    _require_entitlement(tenant)
    valid_at = valid_at or timezone.now()
    records = GlobalSportsDataRecord.objects.filter(
        batch__status='completed',
    ).exclude(
        source__operational_status=GlobalSportsDataSource.OperationalStatus.DISABLED,
    )
    policy = _granular_entitlements(tenant)
    if policy is not None:
        source_codes, capabilities = policy
        records = records.filter(
            Q(source__code__in=source_codes) | Q(capability__in=capabilities)
        )
    if capability:
        records = records.filter(capability=capability)
    if not include_expired:
        records = records.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=valid_at)
        )
    if provider_code:
        records = records.filter(source__code=provider_code)
    newer = GlobalSportsDataRecord.objects.filter(
        source_id=OuterRef('source_id'),
        capability=OuterRef('capability'),
        provider_record_id=OuterRef('provider_record_id'),
        batch__status='completed',
        batch__published_at__gt=OuterRef('batch__published_at'),
    )
    latest_successful_run = GlobalSportsSyncRun.objects.filter(
        source_id=OuterRef('source_id'),
        dataset_id=OuterRef('batch__dataset_id'),
        status=GlobalSportsSyncRun.Status.COMPLETED,
        batch__isnull=False,
        finished_at__isnull=False,
    ).order_by('-finished_at', '-pk')
    return records.annotate(
        has_newer=Exists(newer),
        latest_run_batch_id=Subquery(latest_successful_run.values('batch_id')[:1]),
    ).filter(
        Q(latest_run_batch_id=F('batch_id'))
        | Q(latest_run_batch_id__isnull=True, has_newer=False)
    )
