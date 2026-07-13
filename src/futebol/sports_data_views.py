from datetime import timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from futebol.models import GlobalSportsDataSource
from futebol.services.sports_catalog import (
    capabilities_for_source,
    latest_records_for,
    sources_for,
    tenant_has_sports_intelligence,
)
from futebol.services.tenancy import active_tenant


def sports_data_module_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        tenant = active_tenant(request)
        if request.user.is_superuser or tenant_has_sports_intelligence(tenant):
            return view_func(request, *args, **kwargs)
        return render(
            request,
            'futebol/module_unavailable.html',
            {'title': 'Módulo não contratado', 'module_name': 'Inteligência Esportiva'},
            status=403,
        )

    return wrapped


def _source_summary(source, now, tenant):
    latest_run = source.sync_runs.filter(
        status='completed', batch__isnull=False,
    ).select_related('batch').order_by('-finished_at', '-created_at').first()
    latest_batch = (
        latest_run.batch if latest_run
        else source.batches.order_by('-published_at', '-created_at').first()
    )
    records = latest_records_for(
        tenant,
        provider_code=source.code,
        include_expired=True,
    )
    freshness_age = now - source.last_success_at if source.last_success_at else None
    if source.operational_status == GlobalSportsDataSource.OperationalStatus.CONTRACT_REQUIRED:
        freshness_status, freshness_label = 'disconnected', 'Não conectada'
    elif freshness_age is None:
        freshness_status, freshness_label = 'pending', 'Nunca sincronizada'
    elif freshness_age <= timedelta(hours=8):
        freshness_status, freshness_label = 'fresh', 'Atualizada'
    elif freshness_age <= timedelta(hours=24):
        freshness_status, freshness_label = 'attention', 'Atualização próxima do limite'
    else:
        freshness_status, freshness_label = 'stale', 'Desatualizada'
    return {
        'source': source,
        'latest_batch': latest_batch,
        'record_count': records.count(),
        'dataset_count': records.values('batch__dataset_id').distinct().count(),
        'valid_record_count': records.filter(expires_at__gt=now).count()
        + records.filter(expires_at__isnull=True).count(),
        'expired_record_count': records.filter(expires_at__lte=now).count(),
        'freshness_status': freshness_status,
        'freshness_label': freshness_label,
    }


@login_required
@sports_data_module_required
def sports_data_source_list(request):
    tenant = active_tenant(request)
    now = timezone.now()
    sources = (
        GlobalSportsDataSource.objects.all()
        if request.user.is_superuser else sources_for(tenant)
    ).order_by('name')
    rows = [_source_summary(source, now, tenant) for source in sources]
    return render(
        request,
        'futebol/sports_data_center.html',
        {
            'title': 'Cobertura e atualidade dos dados',
            'subtitle': 'Base Esportiva Global mantida pela plataforma e usada pelo Treinador Inteligente',
            'rows': rows,
            'connected_count': sum(
                1 for row in rows if row['source'].last_success_at is not None
            ),
            'record_count': sum(row['record_count'] for row in rows),
            'expired_count': sum(row['expired_record_count'] for row in rows),
        },
    )


@login_required
@sports_data_module_required
def sports_data_source_detail(request, pk):
    tenant = active_tenant(request)
    sources = GlobalSportsDataSource.objects.all() if request.user.is_superuser else sources_for(tenant)
    source = get_object_or_404(sources, pk=pk)
    allowed_capabilities = (
        set(source.capabilities or [])
        if request.user.is_superuser
        else capabilities_for_source(tenant, source)
    )
    entitled_records = latest_records_for(
        tenant, provider_code=source.code, include_expired=True,
    ).filter(capability__in=allowed_capabilities)
    batches = source.batches.filter(
        records__in=entitled_records,
    ).distinct().order_by('-published_at', '-created_at')[:30]
    return render(
        request,
        'futebol/sports_data_source_detail.html',
        {
            'title': source.name,
            'subtitle': 'Histórico de importações e proveniência',
            'summary': _source_summary(source, timezone.now(), tenant),
            'batches': batches,
            'allowed_capabilities': sorted(allowed_capabilities),
        },
    )
