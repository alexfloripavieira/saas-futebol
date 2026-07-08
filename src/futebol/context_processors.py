from .models import TenantMembership


def sprint_context(request):
    memberships = []
    if request.user.is_authenticated:
        memberships = (
            TenantMembership.objects
            .select_related('tenant')
            .filter(user=request.user, active=True, tenant__active=True)
            .order_by('tenant__name')
        )
    return {
        'sprint_name': 'Sprint 12 — Análise tática e scouting',
        'tenant_memberships': memberships,
        'is_authenticated': request.user.is_authenticated,
    }
