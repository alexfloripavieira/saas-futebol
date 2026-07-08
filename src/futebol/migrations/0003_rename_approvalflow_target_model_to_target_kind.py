from django.db import migrations


TARGET_KIND_MAP = {
    'futebol.Contract': 'contrato',
    'futebol.Negotiation': 'transferencia',
    'futebol.Match': 'partida',
}
REVERSE_TARGET_KIND_MAP = {v: k for k, v in TARGET_KIND_MAP.items()}


def forwards(apps, schema_editor):
    ApprovalFlow = apps.get_model('futebol', 'ApprovalFlow')
    for flow in ApprovalFlow.objects.all():
        if flow.target_kind in TARGET_KIND_MAP:
            flow.target_kind = TARGET_KIND_MAP[flow.target_kind]
            flow.save(update_fields=['target_kind'])


def backwards(apps, schema_editor):
    ApprovalFlow = apps.get_model('futebol', 'ApprovalFlow')
    for flow in ApprovalFlow.objects.all():
        if flow.target_kind in REVERSE_TARGET_KIND_MAP:
            flow.target_kind = REVERSE_TARGET_KIND_MAP[flow.target_kind]
            flow.save(update_fields=['target_kind'])


class Migration(migrations.Migration):

    dependencies = [
        ('futebol', '0002_approvalflow_club_competition_competitionedition_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='approvalflow',
            old_name='target_model',
            new_name='target_kind',
        ),
        migrations.RunPython(forwards, backwards),
    ]
