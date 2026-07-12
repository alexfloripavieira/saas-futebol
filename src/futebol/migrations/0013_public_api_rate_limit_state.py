from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('futebol', '0012_operationalmetric_and_approval_guardrails')]

    operations = [
        migrations.AddField(
            model_name='publicapicredential',
            name='rate_request_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='publicapicredential',
            name='rate_window_started_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
