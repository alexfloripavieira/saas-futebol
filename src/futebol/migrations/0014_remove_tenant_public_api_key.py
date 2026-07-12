from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('futebol', '0013_public_api_rate_limit_state')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE futebol_tenant DROP COLUMN IF EXISTS public_api_key',
                    reverse_sql=(
                        "ALTER TABLE futebol_tenant ADD COLUMN IF NOT EXISTS "
                        "public_api_key varchar(64) NOT NULL DEFAULT ''"
                    ),
                ),
            ],
            state_operations=[
                migrations.RemoveField(model_name='tenant', name='public_api_key'),
            ],
        ),
    ]
