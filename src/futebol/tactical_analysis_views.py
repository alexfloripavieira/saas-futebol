from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from futebol.models import (
    SportsDataArtifact, SportsDataImportBatch, SportsDataRecord, TacticalInsightReview,
)
from futebol.modules import tenant_has_module
from futebol.services.spatial_analytics import build_event_analysis
from futebol.services.tactical_engine import (
    build_agent_training_insights, detect_tactical_moments,
)
from futebol.services.tracking_analytics import build_tracking_context
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
    match_id = str(batch.manifest.get('provider_match_id') or '')
    metadata_record = SportsDataRecord.objects.filter(
        tenant=tenant, source=batch.source, capability='match_metadata',
        payload__provider_match_id=match_id,
    ).order_by('-created_at').first()
    context = build_tracking_context(
        metadata_record.raw_payload if metadata_record else {},
    )
    selected_period = request.GET.get('period', '')
    if selected_period:
        preview = [
            frame for frame in preview if str(frame.get('period')) == selected_period
        ]
        detected = sum(
            player.get('detected', False) for frame in preview
            for player in frame.get('players', [])
        )
        positions = sum(len(frame.get('players', [])) for frame in preview)
        metric_team = selected_team or next(iter(context.get('teams', {})), '')
        frame_metrics = [
            (frame.get('team_metrics') or {}).get(metric_team) for frame in preview
        ]
        frame_metrics = [item for item in frame_metrics if item]
        analysis = {
            **analysis, 'frame_count': len(preview),
            'coverage': round(detected / positions * 100, 1) if positions else 0,
            'average_width': round(
                sum(item['width'] for item in frame_metrics) / len(frame_metrics), 2,
            ) if frame_metrics else None,
            'average_depth': round(
                sum(item['depth'] for item in frame_metrics) / len(frame_metrics), 2,
            ) if frame_metrics else None,
        }
    teams = [context.get('teams', {}).get(team_id, {
        'id': team_id, 'name': team_id, 'color': '#68b8ff',
    }) for team_id in sorted(analyses_by_team)]
    periods = sorted({str(frame.get('period')) for frame in analysis.get('preview', [])})
    engine = artifact.metadata.get('tactical_engine') or detect_tactical_moments(
        global_analysis.get('preview') or [],
        team_directions=context.get('directions_by_period'),
        source_context={
            'source_code': batch.source.code, 'batch_id': batch.pk,
            'artifact_id': artifact.pk, 'content_hash': artifact.content_hash,
            'schema_version': artifact.schema_version, 'quality': batch.quality,
            'license_id': batch.license_id, 'attribution': batch.attribution,
            'usage_scope': batch.manifest.get('usage_scope', 'research_only'),
            'operational_use_allowed': False,
            'detected_position_ratio': round(global_analysis.get('coverage', 0) / 100, 3),
        },
    )
    if selected_period:
        engine = {
            **engine, 'moments': [
                moment for moment in engine.get('moments', [])
                if str(moment.get('period')) == selected_period
            ],
        }
    agent_insights = build_agent_training_insights(engine)
    evidence_ids = {moment['evidence_id'] for moment in engine.get('moments', [])}
    if request.method == 'POST':
        evidence_id = request.POST.get('evidence_id', '')
        decision = request.POST.get('decision', '')
        if evidence_id not in evidence_ids or decision not in TacticalInsightReview.Decision.values:
            messages.error(request, 'Revisão tática inválida ou fora da janela selecionada.')
        else:
            TacticalInsightReview.objects.update_or_create(
                tenant=tenant, artifact=artifact, evidence_id=evidence_id,
                defaults={
                    'decision': decision, 'note': request.POST.get('note', '')[:500],
                    'reviewed_by': request.user,
                },
            )
            messages.success(
                request, 'Decisão humana registrada apenas no ambiente de treinamento.',
            )
        query = urlencode({
            key: value for key, value in {
                'team': selected_team, 'period': selected_period,
            }.items() if value
        })
        url = request.path + (f'?{query}' if query else '')
        return redirect(url)
    reviews = {
        review.evidence_id: review for review in artifact.tactical_reviews.filter(
            tenant=tenant, evidence_id__in=evidence_ids,
        )
    }
    engine = {
        **engine,
        'moments': [{
            **moment,
            'review_decision': (
                reviews[moment['evidence_id']].get_decision_display()
                if moment['evidence_id'] in reviews else ''
            ),
        } for moment in engine.get('moments', [])],
    }
    playback = {
        'schema_version': 'tracking-playback-v1',
        'teams': teams, 'players': context.get('players', {}), 'frames': preview,
        'directions_by_period': context.get('directions_by_period', {}),
        'selected_team': selected_team, 'selected_period': selected_period,
        'limits': {'preview_frames': len(preview)},
        'caveats': {
            'performance_metrics': False,
            'research_only': batch.quality == 'research_sample',
        },
    }
    return render(request, 'futebol/tracking_analysis_lab.html', {
        'title': 'Tracking posicional', 'batch': batch, 'artifact': artifact,
        'analysis': analysis, 'preview': preview, 'teams': teams,
        'selected_team': selected_team, 'selected_period': selected_period,
        'periods': periods, 'playback': playback, 'engine': engine,
        'player_context': context.get('players', {}),
        'agent_insights': agent_insights,
    })
