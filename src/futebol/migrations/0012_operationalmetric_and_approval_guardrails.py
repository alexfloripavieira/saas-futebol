from django.conf import settings
from django.db import migrations, models
from django.db.models import Count
import django.db.models.deletion
from django.utils import timezone


def resolve_duplicate_open_requests(apps, schema_editor):
    ApprovalRequest = apps.get_model('futebol', 'ApprovalRequest')
    duplicate_targets = (
        ApprovalRequest.objects.filter(status='open')
        .values('tenant_id', 'content_type_id', 'object_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    for target in duplicate_targets.iterator():
        requests = ApprovalRequest.objects.filter(
            tenant_id=target['tenant_id'],
            content_type_id=target['content_type_id'],
            object_id=target['object_id'],
            status='open',
        ).order_by('-requested_at', '-pk')
        keep_id = requests.values_list('pk', flat=True).first()
        requests.exclude(pk=keep_id).update(status='cancelled', resolved_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ('futebol', '0011_public_api_credential'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(resolve_duplicate_open_requests, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='approvalrequest',
            constraint=models.UniqueConstraint(
                fields=('tenant', 'content_type', 'object_id'),
                condition=models.Q(status='open'),
                name='uniq_open_approval_per_target',
            ),
        ),
        migrations.CreateModel(
            name='OperationalMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(choices=[('usage', 'Uso'), ('failure', 'Falha'), ('authorization_denied', 'Autorização negada'), ('journey', 'Jornada')], max_length=32)),
                ('event', models.CharField(max_length=64)),
                ('route_name', models.CharField(blank=True, default='', max_length=120)),
                ('method', models.CharField(blank=True, default='', max_length=8)),
                ('status_code', models.PositiveSmallIntegerField(default=0)),
                ('duration_ms', models.PositiveIntegerField(default=0)),
                ('correlation_id', models.CharField(blank=True, default='', max_length=80)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='operational_metrics', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='futebol.tenant')),
            ],
            options={
                'verbose_name': 'Métrica operacional',
                'verbose_name_plural': 'Métricas operacionais',
                'ordering': ['-occurred_at'],
                'indexes': [
                    models.Index(fields=['tenant', 'kind', 'occurred_at'], name='metric_tenant_kind_idx'),
                    models.Index(fields=['tenant', 'event', 'occurred_at'], name='metric_tenant_event_idx'),
                ],
            },
        ),
    ]
