from django.db import migrations
from django.utils import timezone


TRUSTED_PLATFORM_SOURCES = {
    'football-data-org': {
        'kind': 'football_data_org',
        'license_id': 'football-data-org-terms',
        'attribution': 'Dados fornecidos por football-data.org.',
        'quality': 'production_basic',
        'adapter_version': '1.0',
        'schema_version': 'football-data-v4',
        'provider': 'football-data.org',
        'dataset_prefix': 'competition-',
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
        'dataset_prefix': 'competition-',
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
        'dataset_prefix': 'a-league-2024-25-controlled-sample',
        'capabilities': {'match_catalog', 'match_metadata'},
        'source_url_prefix': (
            'https://raw.githubusercontent.com/SkillCorner/opendata/master/data/'
        ),
    },
}


def _trusted_sources(LegacySource, code, contract):
    """Somente conectores com o contrato exato publicado pela plataforma.

    Nome/código isolados não bastam: um Tenant pode ter criado ou enriquecido
    uma fonte homônima e esse dado precisa continuar privado.
    """
    return LegacySource.objects.filter(
        code=code,
        kind=contract['kind'],
        license_id=contract['license_id'],
        attribution=contract['attribution'],
        quality=contract['quality'],
        adapter_version=contract['adapter_version'],
        schema_version=contract['schema_version'],
    ).order_by('-last_sync_at', '-id')


def _is_trusted_batch(batch, contract):
    manifest = batch.manifest if isinstance(batch.manifest, dict) else {}
    declared_capabilities = manifest.get('capabilities')
    if not isinstance(declared_capabilities, list):
        return False
    if (
        batch.license_id != contract['license_id']
        or batch.attribution != contract['attribution']
        or batch.quality != contract['quality']
        or manifest.get('provider') != contract['provider']
        or not batch.dataset_id.startswith(contract['dataset_prefix'])
        or not set(declared_capabilities).issubset(contract['capabilities'])
    ):
        return False
    records = batch.records.all()
    if records.exclude(capability__in=contract['capabilities']).exists():
        return False
    if records.exclude(source_url__startswith=contract['source_url_prefix']).exists():
        return False
    return batch.record_count == records.count()


def backfill_global_catalog(apps, schema_editor):
    # Dados tenant-scoped nunca são promovidos automaticamente. Metadados e
    # URLs não conseguem provar que um payload não foi enriquecido pelo clube.
    # A Base Global nasce exclusivamente dos sincronizadores da plataforma.
    return None


class Migration(migrations.Migration):
    dependencies = [('futebol', '0031_globalsportsdatabatch_globalsportsdatasource_and_more')]

    operations = [
        migrations.RunPython(backfill_global_catalog, migrations.RunPython.noop),
    ]
