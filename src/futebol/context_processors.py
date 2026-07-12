from .models import TenantBranding, TenantMembership
from .modules import ACCOUNT_GROUP, build_nav_groups, enabled_module_codes
from .services.tenancy import accessible_tenants, active_tenant


def sprint_context(request):
    memberships = []
    if request.user.is_authenticated:
        memberships = list(
            TenantMembership.objects
            .select_related('tenant')
            .filter(user=request.user, active=True, tenant__active=True)
            .order_by('tenant__name')
        )

    tenant = active_tenant(request, required=False)

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
        'tenant_options': list(accessible_tenants(request.user)) if request.user.is_authenticated else [],
        'is_authenticated': request.user.is_authenticated,
        'active_tenant': tenant,
        'branding': branding,
        'nav_groups': nav_groups,
        'account_group': ACCOUNT_GROUP,
    }
