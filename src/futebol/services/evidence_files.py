from __future__ import annotations

from futebol.models import Evidence, TenantMembership


def user_can_download_evidence(user, evidence: Evidence) -> bool:
    """Política central para a futura view de download privado."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return TenantMembership.objects.filter(
        user=user,
        tenant_id=evidence.tenant_id,
        active=True,
        tenant__active=True,
    ).exists()
