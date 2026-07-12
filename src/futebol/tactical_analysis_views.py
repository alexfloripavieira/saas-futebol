from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from futebol.models import SportsDataArtifact, SportsDataImportBatch
from futebol.modules import tenant_has_module
from futebol.services.spatial_analytics import build_event_analysis
from futebol.services.tenancy import active_tenant


def _ia_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        tenant = active_tenant(request)
        if request.user.is_superuser or tenant_has_module(tenant, 'ia'):
            return view(request, *args, **kwargs)
        return render(
            request, 'futebol/module_unavailable.html',
            {'title': 'Módulo não contratado', 'module_name': 'IA'}, status=403,
        )
    return wrapped


@login_required
@_ia_required
def tactical_analysis_lab(request, batch_pk):
    tenant = active_tenant(request)
    batch = get_object_or_404(
        SportsDataImportBatch.objects.select_related('source', 'imported_by'),
        tenant=tenant, pk=batch_pk, status=SportsDataImportBatch.Status.COMPLETED,
        quality='research_sample',
    )
    event_records = batch.records.filter(capability='event_stream').order_by('id')
    match_ids = list(dict.fromkeys(
        str(payload.get('provider_match_id'))
        for payload in event_records.values_list('payload', flat=True)
        if payload.get('provider_match_id')
    ))
    selected_match = request.GET.get('match') or (match_ids[0] if match_ids else '')
    records = list(event_records.filter(payload__provider_match_id=selected_match))
    unfiltered = build_event_analysis(records)
    selected_team = request.GET.get('team', '')
    selected_period = request.GET.get('period', '')
    analysis = build_event_analysis(
        records, team=selected_team, period=selected_period,
    )
    analysis['teams'] = unfiltered['teams']
    event_limit = (batch.manifest.get('limits') or {}).get('max_events_per_match')
    analysis['partial'] = bool(event_limit and len(records) >= int(event_limit))
    return render(request, 'futebol/tactical_analysis_lab.html', {
        'title': 'Laboratório Tático',
        'subtitle': 'Analytics espacial validado com dados abertos de P&D',
        'batch': batch,
        'analysis': analysis,
        'match_ids': match_ids,
        'selected_match': selected_match,
        'periods': sorted({
            str(record.payload.get('period')) for record in records
            if record.payload.get('period')
        }),
    })


@login_required
@_ia_required
def tracking_analysis_lab(request, batch_pk):
    tenant = active_tenant(request)
    batch = get_object_or_404(
        SportsDataImportBatch.objects.select_related('source'),
        tenant=tenant, pk=batch_pk, status=SportsDataImportBatch.Status.COMPLETED,
        quality='research_sample', source__code='skillcorner-open',
    )
    artifact = get_object_or_404(
        SportsDataArtifact, tenant=tenant, batch=batch,
        capability='tracking_frames', status=SportsDataArtifact.Status.READY,
    )
    global_analysis = artifact.metadata.get('analysis') or {}
    analyses_by_team = artifact.metadata.get('analyses_by_team') or {}
    selected_team = request.GET.get('team', '')
    analysis = analyses_by_team.get(selected_team, global_analysis)
    preview = analysis.get('preview') or []
    teams = sorted(analyses_by_team)
    return render(request, 'futebol/tracking_analysis_lab.html', {
        'title': 'Tracking posicional', 'batch': batch, 'artifact': artifact,
        'analysis': analysis, 'preview': preview, 'teams': teams,
        'selected_team': selected_team,
    })
