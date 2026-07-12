import hashlib
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from futebol.models import SportsDataImportBatch, SportsDataRecord, SportsDataSource, Tenant
from futebol.services.sports_data import import_local_sports_dataset


class LocalSportsDatasetContractTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Dados Esportivos', slug='dados-esportivos')
        self.user = get_user_model().objects.create_user('importador-esportivo', password='x')
        self.dataset_root = Path(__file__).resolve().parent / 'data' / 'sports'

    def _dataset_with_record_times(self, root, **times):
        dataset = root / 'demo-treinador-sintetico-v1'
        shutil.copytree(self.dataset_root / dataset.name, dataset)
        records_path = dataset / 'matches.json'
        records = json.loads(records_path.read_text(encoding='utf-8'))
        records[0].update(times)
        raw = json.dumps(records, ensure_ascii=False, indent=2).encode('utf-8')
        records_path.write_bytes(raw)
        manifest_path = dataset / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['files']['fixtures_results']['sha256'] = hashlib.sha256(raw).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        return dataset

    def test_importa_dataset_com_proveniencia_e_sem_duplicar(self):
        first = import_local_sports_dataset(
            tenant=self.tenant,
            dataset_slug='demo-treinador-sintetico-v1',
            imported_by=self.user,
            root=self.dataset_root,
        )
        second = import_local_sports_dataset(
            tenant=self.tenant,
            dataset_slug='demo-treinador-sintetico-v1',
            imported_by=self.user,
            root=self.dataset_root,
        )

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(first.status, SportsDataImportBatch.Status.COMPLETED)
        self.assertEqual(first.quality, 'synthetic')
        self.assertEqual(first.license_id, 'internal-demo')
        self.assertGreater(first.content_hash, '')
        self.assertEqual(SportsDataImportBatch.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(SportsDataRecord.objects.filter(tenant=self.tenant).count(), 4)
        self.assertEqual(
            set(SportsDataRecord.objects.values_list('capability', flat=True)),
            {'fixtures_results', 'standings_form'},
        )

    def test_rejeita_caminho_fora_da_raiz_configurada(self):
        with self.assertRaisesMessage(ValidationError, 'identificador seguro'):
            import_local_sports_dataset(
                tenant=self.tenant,
                dataset_slug='../segredo',
                imported_by=self.user,
                root=self.dataset_root,
            )

    def test_rejeita_arquivo_adulterado_pelo_hash_do_manifesto(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / 'adulterado'
            dataset.mkdir()
            (dataset / 'manifest.json').write_text(
                '{"dataset_id":"adulterado","version":"1","license_id":"internal-demo",'
                '"attribution":"Projeto","quality":"synthetic","files":'
                '{"fixtures_results":{"path":"matches.json","sha256":"0000"}}}',
                encoding='utf-8',
            )
            (dataset / 'matches.json').write_text('[]', encoding='utf-8')

            with self.assertRaisesMessage(ValidationError, 'hash não confere'):
                import_local_sports_dataset(
                    tenant=self.tenant,
                    dataset_slug='adulterado',
                    imported_by=self.user,
                    root=root,
                )

    def test_rejeita_observed_at_fornecido_e_invalido(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = self._dataset_with_record_times(root, observed_at='data-invalida')

            with self.assertRaisesMessage(ValidationError, 'observed_at inválido'):
                import_local_sports_dataset(
                    tenant=self.tenant,
                    dataset_slug=dataset.name,
                    imported_by=self.user,
                    root=root,
                )

    def test_rejeita_expires_at_fornecido_e_invalido(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = self._dataset_with_record_times(root, expires_at='data-invalida')

            with self.assertRaisesMessage(ValidationError, 'expires_at inválido'):
                import_local_sports_dataset(
                    tenant=self.tenant,
                    dataset_slug=dataset.name,
                    imported_by=self.user,
                    root=root,
                )

    def test_rejeita_expires_at_anterior_ao_observed_at(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = self._dataset_with_record_times(
                root,
                observed_at='2026-07-02T10:00:00Z',
                expires_at='2026-07-01T10:00:00Z',
            )

            with self.assertRaisesMessage(ValidationError, 'anterior a observed_at'):
                import_local_sports_dataset(
                    tenant=self.tenant,
                    dataset_slug=dataset.name,
                    imported_by=self.user,
                    root=root,
                )

    def test_preserva_registros_de_cada_versao_importada(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / 'demo-treinador-sintetico-v1'
            shutil.copytree(self.dataset_root / dataset.name, dataset)

            first = import_local_sports_dataset(
                tenant=self.tenant,
                dataset_slug=dataset.name,
                imported_by=self.user,
                root=root,
            )
            manifest_path = dataset / 'manifest.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['version'] = '2'
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
            second = import_local_sports_dataset(
                tenant=self.tenant,
                dataset_slug=dataset.name,
                imported_by=self.user,
                root=root,
            )

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(SportsDataImportBatch.objects.filter(tenant=self.tenant).count(), 2)
        self.assertEqual(first.records.count(), 4)
        self.assertEqual(second.records.count(), 4)
        self.assertEqual(SportsDataRecord.objects.filter(tenant=self.tenant).count(), 8)

    def test_rejeita_registro_cuja_fonte_diverge_do_lote(self):
        batch = import_local_sports_dataset(
            tenant=self.tenant,
            dataset_slug='demo-treinador-sintetico-v1',
            imported_by=self.user,
            root=self.dataset_root,
        )
        other_source = SportsDataSource.objects.create(
            tenant=self.tenant,
            code='outra-fonte',
            name='Outra fonte',
            kind=SportsDataSource.Kind.LOCAL_DATASET,
            capabilities=['fixtures_results'],
            license_id='internal-demo',
            attribution='Projeto',
            quality='synthetic',
        )

        with self.assertRaisesMessage(ValidationError, 'fonte do registro diverge'):
            SportsDataRecord.objects.create(
                tenant=self.tenant,
                source=other_source,
                batch=batch,
                capability='fixtures_results',
                provider_record_id='registro-invalido',
                payload={},
                content_hash='0' * 64,
            )
