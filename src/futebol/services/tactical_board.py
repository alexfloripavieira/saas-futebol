"""Prancheta tática editável com snapshots imutáveis e auditáveis."""

import hashlib
import json
import math

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from futebol.models import (
    LineupDraft, TacticalBoard, TacticalBoardVersion, TenantMembership,
)
from futebol.services.audit import log_audit_event


ELEMENT_TYPES = {'position', 'arrow', 'line', 'zone', 'annotation'}
CLASSIFICATIONS = {'observed', 'calculated', 'recommended', 'hypothesis'}


def _can_edit(actor, tenant):
    return actor.is_superuser or TenantMembership.objects.filter(
        tenant=tenant, user=actor, active=True,
        role__in=[
            TenantMembership.Role.ADMIN_TENANT,
            TenantMembership.Role.GESTOR_CLUBE,
            TenantMembership.Role.ADMIN_PLATAFORMA,
        ],
    ).exists()


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f'Coordenada {field} inválida.')
    value = round(float(value), 2)
    if not 0 <= value <= 100:
        raise ValidationError(f'Coordenada {field} precisa estar entre 0 e 100.')
    return value


def validate_board_document(document, board):
    if not isinstance(document, dict) or document.get('schema_version') != 1:
        raise ValidationError('Schema da prancheta é inválido.')
    elements = document.get('elements')
    if not isinstance(elements, list) or len(elements) > 200:
        raise ValidationError('A prancheta aceita no máximo 200 elementos.')
    player_ids = set(board.draft.players.values_list('player_id', flat=True))
    seen = set()
    clean = []
    for index, raw in enumerate(elements):
        if not isinstance(raw, dict):
            raise ValidationError('Elemento da prancheta inválido.')
        element_id = str(raw.get('id') or f'element-{index + 1}')[:80]
        if element_id in seen:
            raise ValidationError('IDs dos elementos precisam ser únicos.')
        seen.add(element_id)
        kind = raw.get('type')
        classification = raw.get('classification')
        if kind not in ELEMENT_TYPES or classification not in CLASSIFICATIONS:
            raise ValidationError('Tipo ou classificação do elemento é inválido.')
        item = {'id': element_id, 'type': kind, 'classification': classification}
        if kind == 'position':
            player_id = raw.get('player_id')
            if isinstance(player_id, bool) or not isinstance(player_id, int) or player_id not in player_ids:
                raise ValidationError('Atleta da posição não pertence ao rascunho.')
            item.update({
                'player_id': player_id,
                'x': _number(raw.get('x'), 'x'), 'y': _number(raw.get('y'), 'y'),
            })
        elif kind in {'arrow', 'line'}:
            item.update({key: _number(raw.get(key), key) for key in ('x1', 'y1', 'x2', 'y2')})
        elif kind == 'zone':
            item.update({key: _number(raw.get(key), key) for key in ('x', 'y', 'width', 'height')})
            if item['x'] + item['width'] > 100 or item['y'] + item['height'] > 100:
                raise ValidationError('A zona precisa permanecer dentro do campo.')
        else:
            text = str(raw.get('text') or '').strip()
            if not text or len(text) > 240:
                raise ValidationError('Anotação precisa ter entre 1 e 240 caracteres.')
            item.update({
                'x': _number(raw.get('x'), 'x'), 'y': _number(raw.get('y'), 'y'),
                'text': text,
            })
        clean.append(item)
    return {'schema_version': 1, 'elements': clean}


@transaction.atomic
def get_or_create_board(*, draft, actor):
    if not _can_edit(actor, draft.tenant):
        raise PermissionDenied('Usuário sem permissão para editar a prancheta.')
    # Serializa a criação pela raiz compartilhada. Um lock somente em
    # TacticalBoard não protege quando a linha ainda não existe.
    draft = LineupDraft.objects.select_for_update().select_related('tenant').get(pk=draft.pk)
    existing = TacticalBoard.objects.select_for_update().filter(
        tenant=draft.tenant, draft=draft,
    ).first()
    if existing:
        return existing
    elements = [{
        'id': f'player-{player.player_id}', 'type': 'position',
        'classification': 'recommended', 'player_id': player.player_id,
        'x': float(player.pitch_x), 'y': float(player.pitch_y),
    } for player in draft.players.select_related('player').order_by('order')]
    board = TacticalBoard.objects.create(
        tenant=draft.tenant, draft=draft,
        document={'schema_version': 1, 'elements': elements},
        revision=1, updated_by=actor,
    )
    log_audit_event(
        tenant=draft.tenant, actor=actor, action='create', obj=board,
        after_state={'draft_id': draft.pk, 'revision': 1, 'elements': len(elements)},
    )
    return board


@transaction.atomic
def save_board(*, board, document, expected_revision, actor):
    board = TacticalBoard.objects.select_for_update().select_related('draft').get(pk=board.pk)
    if not _can_edit(actor, board.tenant):
        raise PermissionDenied('Usuário sem permissão para editar a prancheta.')
    if expected_revision != board.revision:
        raise ValidationError('A prancheta foi alterada por outro usuário. Recarregue antes de salvar.')
    clean = validate_board_document(document, board)
    board.document = clean
    board.revision += 1
    board.updated_by = actor
    board.save(update_fields=['document', 'revision', 'updated_by', 'updated_at'])
    digest = hashlib.sha256(
        json.dumps(clean, sort_keys=True, separators=(',', ':')).encode(),
    ).hexdigest()
    log_audit_event(
        tenant=board.tenant, actor=actor, action='update', obj=board,
        after_state={'revision': board.revision, 'content_hash': digest, 'elements': len(clean['elements'])},
    )
    return board


@transaction.atomic
def publish_board_version(*, board, actor, change_note=''):
    board = TacticalBoard.objects.select_for_update().get(pk=board.pk)
    if not _can_edit(actor, board.tenant):
        raise PermissionDenied('Usuário sem permissão para versionar a prancheta.')
    document = validate_board_document(board.document, board)
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    existing = board.versions.filter(tenant=board.tenant, content_hash=digest).first()
    if existing:
        existing.already_existed = True
        return existing
    number = (board.versions.order_by('-version').values_list('version', flat=True).first() or 0) + 1
    version = TacticalBoardVersion.objects.create(
        tenant=board.tenant, board=board, version=number, document=document,
        content_hash=digest, change_note=(change_note or '').strip()[:500],
        created_by=actor,
    )
    log_audit_event(
        tenant=board.tenant, actor=actor, action='create', obj=version,
        after_state={'board_id': board.pk, 'version': number, 'content_hash': digest},
    )
    return version


@transaction.atomic
def save_and_publish_board(*, board, document, expected_revision, actor, change_note=''):
    board = save_board(
        board=board, document=document, expected_revision=expected_revision, actor=actor,
    )
    return publish_board_version(board=board, actor=actor, change_note=change_note)


def restore_board_version(*, version, actor, expected_revision):
    return save_board(
        board=version.board, document=version.document,
        expected_revision=expected_revision, actor=actor,
    )
