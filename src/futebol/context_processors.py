from .models import Tenant, TenantBranding, TenantMembership
from .modules import ACCOUNT_GROUP, build_nav_groups, enabled_module_codes


def _active_tenant(request, memberships):
    """Tenant ativo para branding/menu.

    Superusuário: primeiro tenant ativo (ou o selecionado via ?tenant=).
    Demais: primeiro tenant de vínculo ativo.
    """
    if not request.user.is_authenticated:
        return None
    if request.user.is_superuser:
        tenant_id = request.GET.get('tenant')
        if tenant_id:
            return Tenant.objects.filter(pk=tenant_id).first()
        return Tenant.objects.filter(active=True).first()
    membership = memberships[0] if memberships else None
    return membership.tenant if membership else None


def sprint_context(request):
    memberships = []
    if request.user.is_authenticated:
        memberships = list(
            TenantMembership.objects
            .select_related('tenant')
            .filter(user=request.user, active=True, tenant__active=True)
            .order_by('tenant__name')
        )

    tenant = _active_tenant(request, memberships)

    if tenant is not None:
        branding = getattr(tenant, 'branding', None) or TenantBranding(tenant=tenant)
        nav_groups = build_nav_groups(enabled_module_codes(tenant))
    else:
        # Anônimo ou usuário sem tenant (ex.: onboarding): sem menu operacional.
        branding = TenantBranding()
        nav_groups = []

    return {
        'sprint_name': 'Operação',
        'tenant_memberships': memberships,
        'is_authenticated': request.user.is_authenticated,
        'active_tenant': tenant,
        'branding': branding,
        'nav_groups': nav_groups,
        'account_group': ACCOUNT_GROUP,
    }
