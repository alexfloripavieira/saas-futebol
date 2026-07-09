from django.db import migrations, models


TARGET_MODEL_MAP = {
    'futebol.Contract': ('futebol', 'contract'),
    'futebol.Negotiation': ('futebol', 'negotiation'),
    'futebol.Match': ('futebol', 'match'),
}


def forwards(apps, schema_editor):
    ApprovalRequest = apps.get_model('futebol', 'ApprovalRequest')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    content_type_cache = {}
    for request in ApprovalRequest.objects.all():
        key = TARGET_MODEL_MAP.get(getattr(request, 'target_model', ''))
        if not key:
            continue
        if key not in content_type_cache:
            content_type_cache[key] = ContentType.objects.get(app_label=key[0], model=key[1]).pk
        request.content_type_id = content_type_cache[key]
        request.object_id = getattr(request, 'target_object_id', '') or ''
        request.save(update_fields=['content_type', 'object_id'])


def backwards(apps, schema_editor):
    ApprovalRequest = apps.get_model('futebol', 'ApprovalRequest')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    reverse_map = {v: k for k, v in TARGET_MODEL_MAP.items()}
    for request in ApprovalRequest.objects.all():
        content_type = ContentType.objects.get_for_id(request.content_type_id)
        key = (content_type.app_label, content_type.model)
        if key not in reverse_map:
            continue
        request.target_model = reverse_map[key]
        request.target_object_id = request.object_id
        request.save(update_fields=['target_model', 'target_object_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('futebol', '0003_rename_approvalflow_target_model_to_target_kind'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalrequest',
            name='content_type',
            field=models.ForeignKey(null=True, blank=True, on_delete=models.PROTECT, to='contenttypes.contenttype'),
        ),
        migrations.AddField(
            model_name='approvalrequest',
            name='object_id',
            field=models.CharField(max_length=64, null=True, blank=True),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name='approvalrequest',
            name='content_type',
            field=models.ForeignKey(on_delete=models.PROTECT, to='contenttypes.contenttype'),
        ),
        migrations.AlterField(
            model_name='approvalrequest',
            name='object_id',
            field=models.CharField(max_length=64),
        ),
        migrations.RemoveField(
            model_name='approvalrequest',
            name='target_model',
        ),
        migrations.RemoveField(
            model_name='approvalrequest',
            name='target_object_id',
        ),
    ]
