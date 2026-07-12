from django.db import migrations, models

import futebol.validators


class Migration(migrations.Migration):
    dependencies = [
        ('futebol', '0009_tenant_public_api_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evidence',
            name='file',
            field=models.FileField(
                blank=True,
                upload_to=futebol.validators.evidence_upload_path,
                validators=[futebol.validators.validate_evidence_file],
            ),
        ),
    ]
