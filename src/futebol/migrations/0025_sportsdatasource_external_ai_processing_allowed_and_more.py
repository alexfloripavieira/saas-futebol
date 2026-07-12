from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('futebol', '0024_tacticalinsightreview_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sportsdatasource',
            name='external_ai_processing_allowed',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='TacticalAgentOpinion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('specialty', models.CharField(max_length=32)),
                ('summary', models.TextField()),
                ('recommendations', models.JSONField(default=list)),
                ('limitations', models.JSONField(default=list)),
                ('confidence', models.PositiveSmallIntegerField(default=0)),
                ('evidence_ids', models.JSONField(default=list)),
                ('execution_mode', models.CharField(choices=[('provider', 'Provider de IA'), ('fallback', 'Fallback determinístico')], max_length=16)),
                ('provider_name', models.CharField(max_length=160)),
                ('model_name', models.CharField(max_length=120)),
                ('prompt_version', models.CharField(default='tactical-agent-v1', max_length=32)),
                ('prompt_hash', models.CharField(max_length=64)),
                ('generated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('requires_human_review', models.BooleanField(default=True)),
                ('eligible_for_operational_use', models.BooleanField(default=False)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tactical_opinions', to='futebol.aiagent')),
                ('artifact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agent_opinions', to='futebol.sportsdataartifact')),
                ('generated_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='generated_tactical_opinions', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='futebol.tenant')),
            ],
        ),
        migrations.AddConstraint(
            model_name='tacticalagentopinion',
            constraint=models.UniqueConstraint(fields=('tenant', 'artifact', 'agent'), name='uniq_tactical_agent_opinion'),
        ),
    ]
