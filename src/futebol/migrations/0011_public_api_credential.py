from django.contrib.auth.hashers import make_password
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def secure_legacy_keys(apps, schema_editor):
    Tenant = apps.get_model('futebol', 'Tenant')
    PublicAPICredential = apps.get_model('futebol', 'PublicAPICredential')
    for tenant in Tenant.objects.exclude(public_api_key='').iterator():
        raw_key = tenant.public_api_key.strip()
        if raw_key:
            PublicAPICredential.objects.create(
                tenant=tenant,
                key_prefix=f'leg{tenant.pk:08x}'[-11:],
                key_hash=make_password(raw_key),
                active=True,
            )
        tenant.public_api_key = ''
        tenant.save(update_fields=['public_api_key'])


class Migration(migrations.Migration):
    dependencies = [
        ('futebol', '0010_alter_evidence_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublicAPICredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('key_prefix', models.CharField(max_length=12, unique=True)),
                ('key_hash', models.CharField(max_length=128)),
                ('active', models.BooleanField(default=True)),
                ('rotated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='public_api_credential', to='futebol.tenant')),
            ],
            options={
                'verbose_name': 'Credencial da API pública',
                'verbose_name_plural': 'Credenciais da API pública',
            },
        ),
        migrations.RunPython(secure_legacy_keys, migrations.RunPython.noop),
    ]
