from contextvars import ContextVar
import uuid

from django.shortcuts import render

request_id_var = ContextVar('request_id', default='-')

# Prefixos de URL que exigem um módulo contratado. Avaliado em ordem; o
# primeiro prefixo casado define o módulo requerido.
PATH_MODULE_RULES = (
    ('/ia/', 'ia'),
    ('/relatorios/', 'relatorios'),
    ('/integracoes/', 'integracoes'),
    ('/transferencias/', 'transferencias'),
    ('/aprovacoes/', 'aprovacoes'),
    ('/solicitacoes-aprovacao/', 'aprovacoes'),
    ('/notificacoes/', 'aprovacoes'),
    ('/auditoria/', 'auditoria'),
    ('/automacoes/', 'automacoes'),
)


class RequestIDFilter:
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.META.get('HTTP_X_REQUEST_ID', str(uuid.uuid4()))
        token = request_id_var.set(request.request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response['X-Request-ID'] = request.request_id
        return response


class ModuleAccessMiddleware:
    """Bloqueia acesso a áreas cujo módulo não foi contratado pelo tenant.

    Aplica-se apenas a usuários autenticados que não são superusuários e cujo
    tenant possui assinaturas de módulo configuradas. Tenants não-provisionados
    (sem nenhuma assinatura) mantêm acesso total — ver ``futebol.modules``.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        blocked = self._blocked_module_name(request)
        if blocked is not None:
            return render(
                request,
                'futebol/module_unavailable.html',
                {'title': 'Módulo não contratado', 'module_name': blocked},
                status=403,
            )
        return self.get_response(request)

    def _blocked_module_name(self, request):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or user.is_superuser:
            return None
        required = next((code for prefix, code in PATH_MODULE_RULES if request.path.startswith(prefix)), None)
        if required is None:
            return None
        from .modules import MODULE_NAMES, tenant_has_module

        tenant = self._active_tenant(user)
        if tenant is None:
            return None
        if tenant_has_module(tenant, required):
            return None
        return MODULE_NAMES.get(required, required)

    @staticmethod
    def _active_tenant(user):
        membership = (
            user.tenant_memberships
            .filter(active=True, tenant__active=True)
            .select_related('tenant')
            .order_by('tenant__name')
            .first()
        )
        return membership.tenant if membership else None
