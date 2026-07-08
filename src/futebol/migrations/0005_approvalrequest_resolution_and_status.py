from django.db import migrations, models


STATUS_MAP = {
    'pending': 'open',
}
REVERSE_STATUS_MAP = {v: k for k, v in STATUS_MAP.items()}


def forwards(apps, schema_editor):
    ApprovalRequest = apps.get_model('futebol', 'ApprovalRequest')
    for request in ApprovalRequest.objects.all():
        if request.status in STATUS_MAP:
            request.status = STATUS_MAP[request.status]
            request.save(update_fields=['status'])


def backwards(apps, schema_editor):
    ApprovalRequest = apps.get_model('futebol', 'ApprovalRequest')
    for request in ApprovalRequest.objects.all():
        if request.status in REVERSE_STATUS_MAP:
            request.status = REVERSE_STATUS_MAP[request.status]
            request.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('futebol', '0004_approvalrequest_to_generic_target'),
    ]

    operations = [
        migrations.RenameField(
            model_name='approvalrequest',
            old_name='decided_at',
            new_name='resolved_at',
        ),
        migrations.AlterField(
            model_name='approvalrequest',
            name='status',
            field=models.CharField(choices=[('open', 'Aberta'), ('approved', 'Aprovada'), ('rejected', 'Rejeitada'), ('cancelled', 'Cancelada')], default='open', max_length=16),
        ),
        migrations.RunPython(forwards, backwards),
    ]
