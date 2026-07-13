from django.db import migrations


def purge_tenant_promoted_batches(apps, schema_editor):
    GlobalBatch = apps.get_model('futebol', 'GlobalSportsDataBatch')
    # Reaplica a contração em bancos que já executaram a versão antiga da 0033.
    # Lotes nativos globais possuem ao menos uma GlobalSportsSyncRun vinculada.
    GlobalBatch.objects.filter(sync_runs__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [('futebol', '0033_remove_unsafe_global_sports_backfill')]

    operations = [
        migrations.RunPython(
            purge_tenant_promoted_batches,
            migrations.RunPython.noop,
        ),
    ]
