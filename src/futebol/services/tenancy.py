"""Resolução do contexto operacional de tenant por requisição."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied

from futebol.models import Tenant


ACTIVE_TENANT_SESSION_KEY = 'active_tenant_id'


def accessible_tenants(user):
    if user.is_superuser:
        return Tenant.objects.filter(active=True).order_by('name')
    return Tenant.objects.filter(
        active=True,
        memberships__user=user,
        memberships__active=True,
    ).distinct().order_by('name')


def active_tenant(request, *, required=True):
    """Retorna o tenant ativo autorizado e estabiliza sua seleção na sessão."""
    if not request.user.is_authenticated:
        if required:
            raise PermissionDenied('Autenticação necessária para selecionar um tenant.')
        return None

    tenants = accessible_tenants(request.user)
    tenant_id = request.session.get(ACTIVE_TENANT_SESSION_KEY)
    tenant = tenants.filter(pk=tenant_id).first() if tenant_id else None
    if tenant is None:
        tenant = tenants.first()
    if tenant is None:
        if required:
            raise PermissionDenied('O usuário não possui tenant ativo para operar.')
        return None
    if request.session.get(ACTIVE_TENANT_SESSION_KEY) != tenant.pk:
        request.session[ACTIVE_TENANT_SESSION_KEY] = tenant.pk
    return tenant


def select_active_tenant(request, tenant_id):
    tenant = accessible_tenants(request.user).filter(pk=tenant_id).first()
    if tenant is None:
        raise PermissionDenied('Sem acesso ao tenant selecionado.')
    request.session[ACTIVE_TENANT_SESSION_KEY] = tenant.pk
    return tenant
