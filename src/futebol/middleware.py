from contextvars import ContextVar
from time import perf_counter
import uuid

request_id_var = ContextVar('request_id', default='-')


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


class OperationalMetricsMiddleware:
    """Registra uso, falha e 403 por rota para usuários autenticados."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = perf_counter()
        response = self.get_response(request)
        duration_ms = round((perf_counter() - started_at) * 1000)

        user = getattr(request, 'user', None)
        if not getattr(user, 'is_authenticated', False):
            return response

        from futebol.models import OperationalMetric
        from futebol.services.metrics import record_metric
        from futebol.services.tenancy import active_tenant

        tenant = active_tenant(request, required=False)
        route_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
        if not route_name:
            return response
        if response.status_code == 403:
            kind = OperationalMetric.Kind.AUTHORIZATION_DENIED
            event = 'authorization_denied'
        elif response.status_code >= 400:
            kind = OperationalMetric.Kind.FAILURE
            event = 'request_failed'
        else:
            kind = OperationalMetric.Kind.USAGE
            event = 'request_completed'
        record_metric(
            tenant=tenant,
            kind=kind,
            event=event,
            route_name=route_name,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
            actor=user,
            correlation_id=getattr(request, 'request_id', ''),
        )
        return response
