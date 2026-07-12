from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404

from .models import Evidence
from .services.evidence_files import user_can_download_evidence
from .services.tenancy import active_tenant


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return JsonResponse({'status': 'unhealthy'}, status=503)
    return JsonResponse({'status': 'ok'})


@login_required
def evidence_download(request, pk):
    evidence = get_object_or_404(Evidence.objects.select_related('tenant'), pk=pk, tenant=active_tenant(request))
    if not evidence.file or not user_can_download_evidence(request.user, evidence):
        return JsonResponse({'detail': 'Arquivo não encontrado.'}, status=404)
    return FileResponse(
        evidence.file.open('rb'),
        as_attachment=True,
        filename=Path(evidence.file.name).name,
    )
