from __future__ import annotations

from django.core.exceptions import PermissionDenied

from futebol.models import TenantMembership


ROLE_PRIORITY = {
    TenantMembership.Role.ADMIN_PLATAFORMA,
    TenantMembership.Role.ADMIN_TENANT,
}


def user_has_any_role(user, tenant_id, roles) -> bool:
    if user.is_superuser:
        return True
    return user.tenant_memberships.filter(
        tenant_id=tenant_id,
        active=True,
        role__in=roles,
        tenant__active=True,
    ).exists()


def require_any_role(user, tenant_id, roles, message='Sem permissão para executar esta ação.'):
    if not user_has_any_role(user, tenant_id, roles):
        raise PermissionDenied(message)
