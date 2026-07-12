from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError


EVIDENCE_SIGNATURES = {
    '.pdf': (b'%PDF-',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
}

EVIDENCE_MIME_TYPES = {
    '.pdf': {'application/pdf'},
    '.png': {'image/png'},
    '.jpg': {'image/jpeg', 'image/pjpeg'},
    '.jpeg': {'image/jpeg', 'image/pjpeg'},
}


def evidence_upload_path(instance, filename: str) -> str:
    """Gera um caminho não adivinhável e segregado pelo tenant."""
    suffix = Path(filename).suffix.lower()
    tenant_id = instance.tenant_id or 'sem-tenant'
    return f'evidencias/{tenant_id}/{uuid4().hex}{suffix}'


def validate_evidence_file(uploaded_file) -> None:
    max_size = getattr(settings, 'EVIDENCE_MAX_UPLOAD_SIZE', 10 * 1024 * 1024)
    if uploaded_file.size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValidationError(f'O arquivo de evidência deve ter no máximo {max_mb:g} MB.')

    suffix = Path(uploaded_file.name).suffix.lower()
    allowed_extensions = set(
        getattr(settings, 'EVIDENCE_ALLOWED_EXTENSIONS', EVIDENCE_SIGNATURES.keys())
    )
    if suffix not in allowed_extensions or suffix not in EVIDENCE_SIGNATURES:
        raise ValidationError('Tipo de arquivo não permitido. Envie PDF, PNG ou JPEG.')

    content_type = getattr(uploaded_file, 'content_type', None)
    allowed_mimes = set(
        getattr(
            settings,
            'EVIDENCE_ALLOWED_CONTENT_TYPES',
            {'application/pdf', 'image/png', 'image/jpeg', 'image/pjpeg'},
        )
    )
    if content_type and (
        content_type not in allowed_mimes or content_type not in EVIDENCE_MIME_TYPES[suffix]
    ):
        raise ValidationError('O conteúdo do arquivo não corresponde ao tipo informado.')

    position = uploaded_file.tell() if hasattr(uploaded_file, 'tell') else None
    try:
        header = uploaded_file.read(16)
    finally:
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(position or 0)
    if not any(header.startswith(signature) for signature in EVIDENCE_SIGNATURES[suffix]):
        raise ValidationError('O conteúdo do arquivo não corresponde à extensão informada.')
