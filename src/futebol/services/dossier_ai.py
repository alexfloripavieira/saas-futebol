"""Execução operacional da Comissão Técnica Digital para um Dossiê."""

from __future__ import annotations

import hashlib
import json
import time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from futebol.models import (
    AIAgent,
    GamePlan,
    GamePlanPlayer,
    MatchDossier,
    OperationalMetric,
    Person,
    SpecialistOpinion,
)
from futebol.services.ai import run_ai_agent_prompt
from futebol.services.audit import log_audit_event


SPECIALIST_SCHEMA = 'coach-dossier-specialist-v1'
COORDINATOR_SCHEMA = 'coach-dossier-decision-v1'
AGENT_SLUGS = {
    SpecialistOpinion.Specialty.COORDINATOR: 'coach-coordinator',
    SpecialistOpinion.Specialty.TACTICAL: 'coach-tactical',
    SpecialistOpinion.Specialty.PHYSICAL: 'coach-physical',
    SpecialistOpinion.Specialty.DEFENSE: 'coach-defense',
    SpecialistOpinion.Specialty.ATTACK: 'coach-attack',
    SpecialistOpinion.Specialty.SCOUT: 'coach-scout',
    SpecialistOpinion.Specialty.SET_PIECES: 'coach-set-pieces',
    SpecialistOpinion.Specialty.ENVIRONMENT: 'coach-environment',
}


def _evidence_package(dossier, specialty):
    snapshot = dossier.data_snapshot
    evidence = [{
        'evidence_id': f'match:{dossier.match_id}',
        'kind': 'match_context',
        'match_id': dossier.match_id,
        'scheduled_at': dossier.match.scheduled_at.isoformat(),
        'analyzed_club_id': dossier.analyzed_club_id,
        'opponent_club_id': (
            dossier.match.away_club_id
            if dossier.analyzed_club_id == dossier.match.home_club_id
            else dossier.match.home_club_id
        ),
        'recent_form': snapshot.get('recent_form') or {},
        'external_form': snapshot.get('external_form'),
        'opponent_external_form': snapshot.get('opponent_external_form'),
        'opponent_prediction': snapshot.get('opponent_prediction') or {},
    }]
    for player in snapshot.get('availability') or []:
        evidence.append({
            'evidence_id': f'player:{player["player_id"]}',
            'kind': 'eligible_player',
            'player_id': player['player_id'],
            'primary_position': player.get('primary_position') or '',
            'secondary_positions': player.get('secondary_positions') or [],
            'status': player.get('status'),
            'readiness': player.get('readiness'),
            'max_minutes': player.get('max_minutes'),
        })
    for item in snapshot.get('external_evidence') or []:
        evidence.append({
            'evidence_id': f'record:{item["record_id"]}',
            'kind': 'external_record',
            'record_id': item['record_id'],
            'capability': item.get('capability'),
            'source_code': item.get('source_code'),
            'observed_at': item.get('observed_at'),
            'validity': item.get('validity'),
        })
    return {
        'schema_version': 'coach-dossier-evidence-v1',
        'specialty': specialty,
        'requires_human_review': True,
        'evidence': evidence,
    }


def _json_payload(text, schema):
    content = (text or '').strip()
    if len(content) > 60_000:
        raise ValidationError('Resposta do provider excede o limite permitido.')
    if content.startswith('```'):
        content = content.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationError('Provider retornou JSON inválido.') from exc
    if not isinstance(payload, dict) or payload.get('schema_version') != schema:
        raise ValidationError('Schema da resposta do provider é inválido.')
    if payload.get('requires_human_review') is not True:
        raise ValidationError('Provider tentou dispensar a revisão humana.')
    return payload


def _string_list(payload, key, *, minimum=1, maximum=8):
    items = payload.get(key)
    if not isinstance(items, list) or not minimum <= len(items) <= maximum:
        raise ValidationError(f'Campo {key} inválido na resposta do provider.')
    if any(not isinstance(item, str) or not item.strip() or len(item) > 600 for item in items):
        raise ValidationError(f'Campo {key} inválido na resposta do provider.')
    return [item.strip() for item in items]


def _base_opinion(payload, *, specialty, allowed_evidence_ids):
    if payload.get('specialty') != specialty:
        raise ValidationError('Especialidade divergente na resposta do provider.')
    summary = payload.get('summary')
    confidence = payload.get('confidence')
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 1600:
        raise ValidationError('Resumo inválido na resposta do provider.')
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        raise ValidationError('Confiança inválida na resposta do provider.')
    evidence_ids = payload.get('evidence_ids')
    if (
        not isinstance(evidence_ids, list) or not evidence_ids
        or any(
            not isinstance(evidence_id, str) or not evidence_id.strip()
            for evidence_id in evidence_ids
        )
        or not set(evidence_ids).issubset(allowed_evidence_ids)
    ):
        raise ValidationError('Provider citou evidência inexistente.')
    return {
        'summary': summary.strip(),
        'recommendations': _string_list(payload, 'recommendations'),
        'limitations': _string_list(payload, 'limitations', minimum=0, maximum=8),
        'confidence': min(confidence, 85),
        'evidence_ids': evidence_ids,
    }


def _agent_for(dossier, specialty):
    slug = AGENT_SLUGS[specialty]
    agent = AIAgent.objects.select_related('provider').filter(
        tenant=dossier.tenant,
        slug=slug,
        active=True,
        provider__active=True,
        provider__operational_data_processing_allowed=True,
        provider__operational_data_authorized_at__isnull=False,
        provider__operational_data_authorized_by__isnull=False,
    ).first()
    if not agent:
        raise ValidationError(
            f'Agente {dict(SpecialistOpinion.Specialty.choices)[specialty]} sem provider ativo '
            'e autorizado para dados operacionais.'
        )
    return agent


def _run_provider(*, agent, prompt):
    started = time.monotonic()
    result = run_ai_agent_prompt(agent=agent, prompt=prompt)
    duration_ms = round((time.monotonic() - started) * 1000)
    if result.used_fallback:
        raise ValidationError('Provider indisponível; nenhuma opinião foi fabricada.')
    return result, duration_ms


def _provider_usage(result):
    raw = result.provider_response if isinstance(result.provider_response, dict) else {}
    usage = raw.get('usage') if isinstance(raw.get('usage'), dict) else {}
    return {
        key: value for key, value in usage.items()
        if key in {'prompt_tokens', 'completion_tokens', 'total_tokens'}
        and isinstance(value, int) and value >= 0
    }


def _specialist_prompt(package):
    return (
        'Analise somente o pacote JSON. Responda exclusivamente JSON no schema '
        '{"schema_version":"coach-dossier-specialist-v1","specialty":"...",'
        '"summary":"...","recommendations":["..."],"limitations":["..."],'
        '"confidence":0,"evidence_ids":["..."],"requires_human_review":true}. '
        'Não invente dados ou evidence_ids.\n<EVIDENCE>\n'
        f'{json.dumps(package, ensure_ascii=False, sort_keys=True)}\n</EVIDENCE>'
    )


def prepare_dossier_specialist_opinion(*, dossier, specialty):
    """Chama e valida o provider sem persistir qualquer decisão operacional."""
    dossier = MatchDossier.objects.select_related('match', 'analyzed_club').get(pk=dossier.pk)
    existing = dossier.opinions.filter(specialty=specialty).first()
    if existing:
        if existing.execution_mode != SpecialistOpinion.ExecutionMode.PROVIDER:
            raise ValidationError('Dossiê contém parecer incompatível com execução provider-first.')
        return {'existing_id': existing.pk}
    agent = _agent_for(dossier, specialty)
    package = _evidence_package(dossier, specialty)
    allowed_ids = {item['evidence_id'] for item in package['evidence']}
    prompt = _specialist_prompt(package)
    result, duration_ms = _run_provider(agent=agent, prompt=prompt)
    payload = _json_payload(result.answer, SPECIALIST_SCHEMA)
    parsed = _base_opinion(payload, specialty=specialty, allowed_evidence_ids=allowed_ids)
    evidence_by_id = {item['evidence_id']: item for item in package['evidence']}
    return {
        'agent_id': agent.pk,
        'provider_id': agent.provider_id,
        'specialty': specialty,
        'parsed': parsed,
        'evidence': [evidence_by_id[item] for item in parsed['evidence_ids']],
        'provider_name': result.provider_name,
        'model_name': result.model_name,
        'prompt_version': SPECIALIST_SCHEMA,
        'prompt_hash': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'duration_ms': max(0, duration_ms),
        'provider_usage': _provider_usage(result),
    }


@transaction.atomic
def persist_dossier_specialist_opinion(*, dossier, prepared, actor):
    """Persiste somente depois de o worker revalidar lease e cancelamento."""
    dossier = MatchDossier.objects.select_for_update().get(pk=dossier.pk)
    if prepared.get('existing_id'):
        return SpecialistOpinion.objects.get(
            tenant=dossier.tenant, dossier=dossier, pk=prepared['existing_id'],
        )
    existing = dossier.opinions.filter(specialty=prepared['specialty']).first()
    if existing:
        if existing.execution_mode != SpecialistOpinion.ExecutionMode.PROVIDER:
            raise ValidationError('Dossiê contém parecer incompatível com execução provider-first.')
        return existing
    agent = AIAgent.objects.select_related('provider').filter(
        tenant=dossier.tenant,
        pk=prepared['agent_id'],
        provider_id=prepared['provider_id'],
        active=True,
        provider__active=True,
        provider__operational_data_processing_allowed=True,
        provider__operational_data_authorized_at__isnull=False,
        provider__operational_data_authorized_by__isnull=False,
    ).first()
    if not agent:
        raise ValidationError('Autorização operacional do provider foi revogada durante a execução.')
    parsed = prepared['parsed']
    opinion = SpecialistOpinion.objects.create(
        tenant=dossier.tenant,
        dossier=dossier,
        agent=agent,
        specialty=prepared['specialty'],
        summary=parsed['summary'],
        recommendations=parsed['recommendations'],
        limitations=parsed['limitations'],
        confidence=parsed['confidence'],
        evidence=prepared['evidence'],
        execution_mode=SpecialistOpinion.ExecutionMode.PROVIDER,
        model_name=prepared['model_name'],
        provider_name=prepared['provider_name'],
        prompt_version=prepared['prompt_version'],
        prompt_hash=prepared['prompt_hash'],
        duration_ms=prepared['duration_ms'],
        provider_usage=prepared['provider_usage'],
    )
    OperationalMetric.objects.create(
        tenant=dossier.tenant,
        kind=OperationalMetric.Kind.USAGE,
        event='dossier_ai_provider',
        duration_ms=prepared['duration_ms'],
        actor=actor,
        metadata={
            'dossier_id': dossier.pk,
            'agent_id': agent.pk,
            'specialty': prepared['specialty'],
            'provider': prepared['provider_name'],
            'model': prepared['model_name'],
            'prompt_version': prepared['prompt_version'],
            'prompt_hash': prepared['prompt_hash'],
            'execution_mode': 'provider',
        },
    )
    return opinion


def _coordinator_prompt(dossier, opinions, package):
    safe_opinions = [{
        'specialty': item.specialty,
        'summary': item.summary,
        'recommendations': item.recommendations,
        'limitations': item.limitations,
        'confidence': item.confidence,
        'evidence_ids': [entry['evidence_id'] for entry in item.evidence],
    } for item in opinions]
    roster = [item for item in package['evidence'] if item['kind'] == 'eligible_player']
    context = {
        'schema_version': 'coach-dossier-coordination-input-v1',
        'match_id': dossier.match_id,
        'opinions': safe_opinions,
        'eligible_roster': roster,
        'allowed_evidence_ids': [item['evidence_id'] for item in package['evidence']],
    }
    schema = (
        '{"schema_version":"coach-dossier-decision-v1","specialty":"coordinator",'
        '"summary":"...","recommendations":["..."],"limitations":["..."],'
        '"confidence":0,"evidence_ids":["..."],"requires_human_review":true,'
        '"plans":[{"variant":"balanced|offensive|conservative","formation":"...",'
        '"summary":"...","attacking_plan":["..."],"defensive_plan":["..."],'
        '"transitions":["..."],"set_pieces":["..."],"risks":["..."],'
        '"confidence":0,"starters":[{"player_id":1,"position":"...",'
        '"pitch_x":50,"pitch_y":50,"tactical_role":"...","rationale":"..."}]}],'
        '"training_microcycle":{"summary":"...","sessions":[{"day":"D-1",'
        '"focus":"...","load":"...","objectives":["..."],'
        '"staff_decision":"..."}],"limitations":["..."]}}'
    )
    return (
        f'Consolide a comissão. Responda somente JSON neste schema: {schema}. '
        'Gere exatamente três planos e exatamente onze titulares elegíveis em cada plano. '
        'Não invente evidências ou atletas.\n<COORDINATION_DATA>\n'
        f'{json.dumps(context, ensure_ascii=False, sort_keys=True)}\n</COORDINATION_DATA>'
    )


def _validate_plan(item, *, eligible_ids, goalkeeper_ids):
    variant = item.get('variant')
    if variant not in GamePlan.Variant.values:
        raise ValidationError('Variante inválida na decisão do Coordenador.')
    starters = item.get('starters')
    if not isinstance(starters, list) or len(starters) != 11:
        raise ValidationError('Cada Plano de Jogo precisa ter exatamente 11 titulares.')
    if any(not isinstance(entry, dict) for entry in starters):
        raise ValidationError('Titular inválido no Plano de Jogo.')
    player_ids = [entry.get('player_id') for entry in starters]
    if any(
        isinstance(player_id, bool) or not isinstance(player_id, int)
        for player_id in player_ids
    ):
        raise ValidationError('Identificador de atleta inválido no Plano de Jogo.')
    if len(set(player_ids)) != 11 or not set(player_ids).issubset(eligible_ids):
        raise ValidationError('Coordenador selecionou atleta inelegível ou duplicado.')
    if not set(player_ids).intersection(goalkeeper_ids):
        raise ValidationError('Plano do Coordenador não contém goleiro apto.')
    normalized_starters = []
    for entry in starters:
        if not isinstance(entry.get('position'), str) or not entry['position'].strip():
            raise ValidationError('Posição inválida no Plano de Jogo.')
        x, y = entry.get('pitch_x'), entry.get('pitch_y')
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int):
            raise ValidationError('Coordenadas inválidas no Plano de Jogo.')
        if not 0 <= x <= 100 or not 0 <= y <= 100:
            raise ValidationError('Coordenadas fora do campo no Plano de Jogo.')
        for key, limit in (('tactical_role', 80), ('rationale', 1000)):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValidationError(f'Campo {key} inválido no Plano de Jogo.')
        normalized_starters.append(entry)
    confidence = item.get('confidence')
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        raise ValidationError('Confiança inválida no Plano de Jogo.')
    formation = item.get('formation')
    summary = item.get('summary')
    if not isinstance(formation, str) or not formation.strip() or len(formation) > 16:
        raise ValidationError('Formação inválida no Plano de Jogo.')
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 1600:
        raise ValidationError('Resumo inválido no Plano de Jogo.')
    return {
        'variant': variant,
        'formation': formation.strip(),
        'summary': summary.strip(),
        'attacking_plan': _string_list(item, 'attacking_plan'),
        'defensive_plan': _string_list(item, 'defensive_plan'),
        'transitions': _string_list(item, 'transitions'),
        'set_pieces': _string_list(item, 'set_pieces'),
        'risks': _string_list(item, 'risks', minimum=0),
        'confidence': min(confidence, 85),
        'starters': normalized_starters,
    }


def _validate_microcycle(payload):
    if not isinstance(payload, dict):
        raise ValidationError('Microciclo inválido na decisão do Coordenador.')
    summary = payload.get('summary')
    sessions = payload.get('sessions')
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 1600:
        raise ValidationError('Resumo do microciclo inválido.')
    if not isinstance(sessions, list) or not 1 <= len(sessions) <= 7:
        raise ValidationError('Sessões do microciclo inválidas.')
    normalized_sessions = []
    for session in sessions:
        if not isinstance(session, dict):
            raise ValidationError('Sessão do microciclo inválida.')
        normalized = {}
        for key, limit in (('day', 16), ('focus', 180), ('load', 80), ('staff_decision', 600)):
            value = session.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValidationError(f'Campo {key} inválido no microciclo.')
            normalized[key] = value.strip()
        normalized['objectives'] = _string_list(session, 'objectives', maximum=6)
        normalized_sessions.append(normalized)
    return {
        'summary': summary.strip(),
        'sessions': normalized_sessions,
        'limitations': _string_list(payload, 'limitations', minimum=0, maximum=8),
    }


def prepare_dossier_coordinator_decision(*, dossier):
    """Obtém a decisão do Coordenador sem abrir transação durante a rede."""
    dossier = MatchDossier.objects.select_related(
        'match', 'analyzed_club',
    ).get(pk=dossier.pk)
    existing = dossier.opinions.filter(
        specialty=SpecialistOpinion.Specialty.COORDINATOR,
        execution_mode=SpecialistOpinion.ExecutionMode.PROVIDER,
    ).first()
    if existing and dossier.status == MatchDossier.Status.READY and dossier.plans.count() == 3:
        return {'existing_id': existing.pk}
    opinions = list(dossier.opinions.exclude(
        specialty=SpecialistOpinion.Specialty.COORDINATOR,
    ))
    if not opinions or any(
        item.execution_mode != SpecialistOpinion.ExecutionMode.PROVIDER for item in opinions
    ):
        raise ValidationError('Coordenador exige pareceres válidos produzidos pelo provider.')
    agent = _agent_for(dossier, SpecialistOpinion.Specialty.COORDINATOR)
    package = _evidence_package(dossier, SpecialistOpinion.Specialty.COORDINATOR)
    allowed_ids = {item['evidence_id'] for item in package['evidence']}
    prompt = _coordinator_prompt(dossier, opinions, package)
    result, duration_ms = _run_provider(agent=agent, prompt=prompt)
    payload = _json_payload(result.answer, COORDINATOR_SCHEMA)
    parsed_opinion = _base_opinion(
        payload,
        specialty=SpecialistOpinion.Specialty.COORDINATOR,
        allowed_evidence_ids=allowed_ids,
    )
    roster = dossier.data_snapshot.get('availability') or []
    roster_by_player_id = {item['player_id']: item for item in roster}
    eligible_ids = {item['player_id'] for item in roster}
    goalkeeper_ids = {
        item['player_id'] for item in roster
        if item.get('primary_position') == 'GOL'
        or 'GOL' in (item.get('secondary_positions') or [])
    }
    plans_payload = payload.get('plans')
    if not isinstance(plans_payload, list) or len(plans_payload) != 3:
        raise ValidationError('Coordenador precisa produzir exatamente três Planos de Jogo.')
    plans = [
        _validate_plan(item, eligible_ids=eligible_ids, goalkeeper_ids=goalkeeper_ids)
        for item in plans_payload
    ]
    if {item['variant'] for item in plans} != set(GamePlan.Variant.values):
        raise ValidationError('Coordenador não produziu as três variantes obrigatórias.')
    microcycle = _validate_microcycle(payload.get('training_microcycle'))
    evidence_by_id = {item['evidence_id']: item for item in package['evidence']}
    return {
        'agent_id': agent.pk,
        'provider_id': agent.provider_id,
        'parsed_opinion': parsed_opinion,
        'roster': roster,
        'plans': plans,
        'microcycle': microcycle,
        'evidence': [evidence_by_id[item] for item in parsed_opinion['evidence_ids']],
        'provider_name': result.provider_name,
        'model_name': result.model_name,
        'prompt_version': COORDINATOR_SCHEMA,
        'prompt_hash': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'duration_ms': max(0, duration_ms),
        'provider_usage': _provider_usage(result),
    }


@transaction.atomic
def persist_dossier_coordinator_decision(*, dossier, prepared, actor):
    dossier = MatchDossier.objects.select_for_update().select_related(
        'match', 'analyzed_club',
    ).get(pk=dossier.pk)
    if prepared.get('existing_id'):
        return SpecialistOpinion.objects.get(
            tenant=dossier.tenant, dossier=dossier, pk=prepared['existing_id'],
        )
    existing = dossier.opinions.filter(
        specialty=SpecialistOpinion.Specialty.COORDINATOR,
        execution_mode=SpecialistOpinion.ExecutionMode.PROVIDER,
    ).first()
    if existing and dossier.status == MatchDossier.Status.READY and dossier.plans.count() == 3:
        return existing
    opinions = list(dossier.opinions.exclude(
        specialty=SpecialistOpinion.Specialty.COORDINATOR,
    ))
    if not opinions or any(
        item.execution_mode != SpecialistOpinion.ExecutionMode.PROVIDER for item in opinions
    ):
        raise ValidationError('Coordenador exige pareceres válidos produzidos pelo provider.')
    agent = AIAgent.objects.select_related('provider').filter(
        tenant=dossier.tenant,
        pk=prepared['agent_id'],
        provider_id=prepared['provider_id'],
        active=True,
        provider__active=True,
        provider__operational_data_processing_allowed=True,
        provider__operational_data_authorized_at__isnull=False,
        provider__operational_data_authorized_by__isnull=False,
    ).first()
    if not agent:
        raise ValidationError('Autorização operacional do provider foi revogada durante a execução.')
    parsed_opinion = prepared['parsed_opinion']
    roster = prepared['roster']
    roster_by_player_id = {item['player_id']: item for item in roster}
    eligible_ids = set(roster_by_player_id)
    plans = prepared['plans']
    microcycle = prepared['microcycle']
    coordinator_opinion = SpecialistOpinion.objects.create(
        tenant=dossier.tenant,
        dossier=dossier,
        agent=agent,
        specialty=SpecialistOpinion.Specialty.COORDINATOR,
        summary=parsed_opinion['summary'],
        recommendations=parsed_opinion['recommendations'],
        limitations=parsed_opinion['limitations'],
        confidence=parsed_opinion['confidence'],
        evidence=prepared['evidence'],
        execution_mode=SpecialistOpinion.ExecutionMode.PROVIDER,
        model_name=prepared['model_name'],
        provider_name=prepared['provider_name'],
        prompt_version=prepared['prompt_version'],
        prompt_hash=prepared['prompt_hash'],
        duration_ms=prepared['duration_ms'],
        provider_usage=prepared['provider_usage'],
    )
    players = {item.pk: item for item in Person.objects.filter(
        tenant=dossier.tenant, pk__in=eligible_ids,
    )}
    for item in plans:
        plan = GamePlan.objects.create(
            tenant=dossier.tenant,
            dossier=dossier,
            **{key: value for key, value in item.items() if key != 'starters'},
        )
        starter_ids = set()
        for order, selection in enumerate(item['starters'], start=1):
            player_id = selection['player_id']
            starter_ids.add(player_id)
            GamePlanPlayer.objects.create(
                tenant=dossier.tenant,
                plan=plan,
                player=players[player_id],
                club=dossier.analyzed_club,
                position=selection['position'],
                pitch_x=selection['pitch_x'],
                pitch_y=selection['pitch_y'],
                tactical_role=str(selection.get('tactical_role') or '')[:80],
                rationale=str(selection.get('rationale') or '')[:1000],
                is_starter=True,
                order=order,
                minute_limit=roster_by_player_id[player_id].get('max_minutes'),
            )
        for order, player_id in enumerate(sorted(eligible_ids - starter_ids), start=12):
            roster_item = roster_by_player_id[player_id]
            GamePlanPlayer.objects.create(
                tenant=dossier.tenant,
                plan=plan,
                player=players[player_id],
                club=dossier.analyzed_club,
                position=roster_item.get('primary_position') or 'NI',
                pitch_x=5,
                pitch_y=95,
                rationale='Reserva elegível; não selecionado entre os 11 pelo Coordenador de IA.',
                is_starter=False,
                order=order,
                minute_limit=roster_item.get('max_minutes'),
            )
    snapshot = dict(dossier.data_snapshot)
    snapshot['training_microcycle'] = {
        **microcycle,
        'status': 'provider_generated_for_staff_review',
        'method': COORDINATOR_SCHEMA,
        'restricted_players': sum(
            item.get('status') in {'limited', 'doubt'} for item in roster
        ),
    }
    snapshot['lineup_recommendation'] = {
        'method': COORDINATOR_SCHEMA,
        'status': 'provider_generated_for_staff_review',
        'provider': prepared['provider_name'],
        'model': prepared['model_name'],
        'requires_human_review': True,
    }
    snapshot['decision_engine'] = {
        'mode': 'provider',
        'provider': prepared['provider_name'],
        'model': prepared['model_name'],
        'schema_version': COORDINATOR_SCHEMA,
        'generated_at': timezone.now().isoformat(),
        'requires_human_review': True,
    }
    dossier.data_snapshot = snapshot
    dossier.status = MatchDossier.Status.READY
    dossier.confidence = parsed_opinion['confidence']
    dossier.generated_at = timezone.now()
    dossier.save(update_fields=[
        'data_snapshot', 'status', 'confidence', 'generated_at', 'updated_at',
    ])
    OperationalMetric.objects.create(
        tenant=dossier.tenant,
        kind=OperationalMetric.Kind.USAGE,
        event='dossier_ai_coordinator',
        duration_ms=prepared['duration_ms'],
        actor=actor,
        metadata={
            'dossier_id': dossier.pk,
            'agent_id': agent.pk,
            'provider': prepared['provider_name'],
            'model': prepared['model_name'],
            'prompt_version': prepared['prompt_version'],
            'prompt_hash': prepared['prompt_hash'],
            'execution_mode': 'provider',
        },
    )
    log_audit_event(
        tenant=dossier.tenant,
        actor=actor,
        action='update',
        obj=dossier,
        after_state={
            'status': dossier.status,
            'provider': prepared['provider_name'],
            'model': prepared['model_name'],
            'schema_version': COORDINATOR_SCHEMA,
        },
    )
    return coordinator_opinion
