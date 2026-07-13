from django.db import migrations


TRUSTED_PUBLIC_CONTRACTS = {
    'football-data-org': {
        'kind': 'football_data_org',
        'license_id': 'football-data-org-terms',
        'attribution': 'Dados fornecidos por football-data.org.',
        'quality': 'production_basic',
        'adapter_version': '1.0',
        'schema_version': 'football-data-v4',
        'provider': 'football-data.org',
        'capabilities': {'fixtures_results', 'standings_form'},
        'source_url_prefix': 'https://api.football-data.org/v4/',
    },
    'statsbomb-open': {
        'kind': 'statsbomb_open',
        'license_id': 'statsbomb-open-data',
        'attribution': 'StatsBomb Open Data — uso restrito ao laboratório autorizado.',
        'quality': 'research_sample',
        'adapter_version': '1.0',
        'schema_version': 'statsbomb-open-v1.1',
        'provider': 'StatsBomb Open Data',
        'capabilities': {'fixtures_results', 'event_stream'},
        'source_url_prefix': (
            'https://raw.githubusercontent.com/statsbomb/open-data/master/data/'
        ),
    },
    'skillcorner-open': {
        'kind': 'skillcorner_open',
        'license_id': 'skillcorner-open-data',
        'attribution': 'SkillCorner Open Data — amostra para pesquisa.',
        'quality': 'research_sample',
        'adapter_version': '1.0',
        'schema_version': 'skillcorner-open-2024-25',
        'provider': 'SkillCorner Open Data',
        'capabilities': {'match_catalog', 'match_metadata'},
        'source_url_prefix': (
            'https://raw.githubusercontent.com/SkillCorner/opendata/master/data/'
        ),
    },
}

# A migração 0032 antiga promovia também cópias tenant-scoped destes
# providers sem existir contrato global verificável. Nenhum lote pode sobreviver
# à contração; a fonte vazia pode permanecer como prospecto comercial.
CONTRACT_REQUIRED_CODES = {'hudl-wyscout', 'opta', 'fmdb-pro'}


def _source_matches(source, contract):
    return all(
        getattr(source, field) == contract[field]
        for field in (
            'kind', 'license_id', 'attribution', 'quality', 'adapter_version',
            'schema_version',
        )
    )


def _batch_matches(batch, contract):
    manifest = batch.manifest if isinstance(batch.manifest, dict) else {}
    declared = manifest.get('capabilities')
    if (
        not isinstance(declared, list)
        or batch.license_id != contract['license_id']
        or batch.quality != contract['quality']
        or manifest.get('provider') != contract['provider']
        or not set(declared).issubset(contract['capabilities'])
    ):
        return False
    records = batch.records.all()
    return (
        batch.record_count == records.count()
        and not records.exclude(capability__in=contract['capabilities']).exists()
        and not records.exclude(
            source_url__startswith=contract['source_url_prefix']
        ).exists()
    )


def remove_unsafe_backfill(apps, schema_editor):
    GlobalSource = apps.get_model('futebol', 'GlobalSportsDataSource')
    GlobalBatch = apps.get_model('futebol', 'GlobalSportsDataBatch')

    GlobalBatch.objects.filter(source__code__in=CONTRACT_REQUIRED_CODES).delete()
    # O sincronizador global sempre cria uma execução ligada ao lote. Um lote
    # sem execução só pode ter vindo do backfill tenant-scoped anterior.
    GlobalBatch.objects.filter(sync_runs__isnull=True).delete()
    for code, contract in TRUSTED_PUBLIC_CONTRACTS.items():
        source = GlobalSource.objects.filter(code=code).first()
        if source is None:
            continue
        if not _source_matches(source, contract):
            source.batches.all().delete()
            continue
        unsafe_ids = [
            batch.pk for batch in source.batches.all()
            if not _batch_matches(batch, contract)
        ]
        GlobalBatch.objects.filter(pk__in=unsafe_ids).delete()


class Migration(migrations.Migration):
    dependencies = [('futebol', '0032_backfill_global_sports_catalog')]

    operations = [
        migrations.RunPython(remove_unsafe_backfill, migrations.RunPython.noop),
    ]
