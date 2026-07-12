from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from futebol.models import PublicAPICredential


API_KEY_HEADER = 'X-SaaS-Futebol-API-Key'


@dataclass
class PublicAPIAuthenticationError(Exception):
    detail: str = 'Chave de API inválida ou ausente.'
    status_code: int = 403


@dataclass
class PublicAPIRateLimitExceeded(PublicAPIAuthenticationError):
    detail: str = 'Limite de requisições excedido.'
    status_code: int = 429
    retry_after: int = 60


@transaction.atomic
def _apply_rate_limit(credential):
    """Limite global por credencial, compartilhado entre todos os workers."""
    limit = int(getattr(settings, 'PUBLIC_API_RATE_LIMIT', 120))
    window = int(getattr(settings, 'PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS', 60))
    if limit <= 0:
        return
    locked = PublicAPICredential.objects.select_for_update().get(pk=credential.pk)
    now = timezone.now()
    elapsed = now - locked.rate_window_started_at
    if elapsed >= timedelta(seconds=window):
        locked.rate_window_started_at = now
        locked.rate_request_count = 0
        elapsed = timedelta(0)
    if locked.rate_request_count >= limit:
        retry_after = max(1, window - int(elapsed.total_seconds()))
        raise PublicAPIRateLimitExceeded(retry_after=retry_after)
    locked.rate_request_count += 1
    locked.save(update_fields=['rate_window_started_at', 'rate_request_count', 'updated_at'])
    credential.rate_window_started_at = locked.rate_window_started_at
    credential.rate_request_count = locked.rate_request_count


def authenticate_public_api_request(request, tenant):
    """Autentica a credencial do tenant exclusivamente pelo header oficial."""
    raw_key = (request.headers.get(API_KEY_HEADER) or '').strip()
    if not raw_key:
        raise PublicAPIAuthenticationError()

    credential = PublicAPICredential.objects.filter(
        tenant=tenant,
        active=True,
        revoked_at__isnull=True,
    ).first()
    if not credential:
        raise PublicAPIAuthenticationError()

    expected_prefix = f'sf_pub_{credential.key_prefix}_'
    if not raw_key.startswith(expected_prefix) or not credential.matches(raw_key):
        raise PublicAPIAuthenticationError()
    _apply_rate_limit(credential)
    PublicAPICredential.objects.filter(pk=credential.pk).update(last_used_at=timezone.now())
    return credential
