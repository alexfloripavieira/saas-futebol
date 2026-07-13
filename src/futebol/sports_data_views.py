import os
import logging
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from futebol.models import SportsDataSource
from futebol.modules import tenant_has_module
from futebol.services.permissions import require_any_role
from futebol.services.sports_data_providers import (
    sync_football_data_org,
    sync_skillcorner_open,
    sync_statsbomb_open,
)
from futebol.services.tenancy import active_tenant

logger = logging.getLogger(__name__)


def sports_data_module_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        tenant = active_tenant(request)
        if request.user.is_superuser or tenant_has_module(tenant, 'integracoes'):
            return view_func(request, *args, **kwargs)
        return render(
            request,
            'futebol/module_unavailable.html',
            {'title': 'Módulo não contratado', 'module_name': 'Integrações'},
            status=403,
        )

    return wrapped


def _source_summary(source, now):
    latest_batch = source.import_batches.order_by('-imported_at', '-created_at').first()
    records = latest_batch.records.all() if latest_batch else source.records.none()
    freshness_age = now - source.last_sync_at if source.last_sync_at else None
    if source.kind == SportsDataSource.Kind.CLUB_INTERNAL:
        freshness_status, freshness_label = 'live', 'Atualização transacional'
    elif source.operational_status == SportsDataSource.OperationalStatus.CONTRACT_REQUIRED:
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
    sources = SportsDataSource.objects.filter(tenant=tenant).order_by('name')
    rows = [_source_summary(source, now) for source in sources]
    return render(
        request,
        'futebol/sports_data_center.html',
        {
            'title': 'Fontes Esportivas',
            'subtitle': 'Cobertura, atualidade e proveniência dos dados usados pelo Treinador Inteligente',
            'rows': rows,
            'active_count': sum(1 for row in rows if row['source'].active),
            'record_count': sum(row['record_count'] for row in rows),
            'expired_count': sum(row['expired_record_count'] for row in rows),
        },
    )


@login_required
@sports_data_module_required
def sports_data_source_sync(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    tenant = active_tenant(request)
    require_any_role(
        request.user,
        tenant.pk,
        ('admin_tenant', 'gestor_clube', 'admin_plataforma'),
        'Sem permissão para sincronizar fontes esportivas.',
    )
    source = get_object_or_404(SportsDataSource, tenant=tenant, pk=pk)
    if source.code not in {'football-data-org', 'statsbomb-open', 'skillcorner-open'}:
        messages.warning(
            request,
            'Esta fonte aguarda dataset autorizado ou contrato comercial para sincronização.',
        )
        return redirect('sports-data-source-detail', pk=source.pk)
    try:
        if source.code == 'football-data-org':
            batch = sync_football_data_org(
                tenant=tenant,
                imported_by=request.user,
                api_key=os.getenv('FOOTBALL_DATA_ORG_API_KEY', ''),
                competition_code=request.POST.get('competition', 'BSA'),
            )
        elif source.code == 'statsbomb-open':
            batch = sync_statsbomb_open(
                tenant=tenant,
                imported_by=request.user,
                competition_id=request.POST.get('competition_id', '43'),
                season_id=request.POST.get('season_id', '106'),
                max_matches=1,
                max_events=5000,
            )
        else:
            batch = sync_skillcorner_open(
                tenant=tenant, imported_by=request.user, max_matches=2
            )
    except Exception:
        logger.exception(
            'Falha ao sincronizar fonte esportiva',
            extra={'request_id': getattr(request, 'request_id', '-')},
        )
        messages.error(request, 'Falha ao sincronizar a fonte. Consulte o registro operacional.')
    else:
        messages.success(request, f'Sincronização concluída: {batch.record_count} registros.')
    return redirect('sports-data-source-detail', pk=source.pk)


@login_required
@sports_data_module_required
def sports_data_source_detail(request, pk):
    tenant = active_tenant(request)
    source = get_object_or_404(SportsDataSource, tenant=tenant, pk=pk)
    batches = source.import_batches.select_related('imported_by').order_by(
        '-imported_at', '-created_at'
    )[:30]
    return render(
        request,
        'futebol/sports_data_source_detail.html',
        {
            'title': source.name,
            'subtitle': 'Histórico de importações e proveniência',
            'summary': _source_summary(source, timezone.now()),
            'batches': batches,
        },
    )
