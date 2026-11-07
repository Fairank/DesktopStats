"""Meaningful untrusted-archive, retained-memory and runtime isolation contracts."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch
import zipfile

import hardware_packs as packs


def model(number=0):
    return dict(id='intel-test-' + str(number), label='Intel Test ' + str(number), vendor='intel', series='Test series',
                aliases=['Intel Test ' + str(number)], sources=['https://www.intel.com/test'],
                cpu_package=dict(id='intel_lga115x_1200', model_id='intel-test-' + str(number),vendor='intel',socket='LGA1151', width_mm=37.5, length_mm=37.5,
                    substrate_mm=None, ihs_kind='intel_square', contacts='lga', pin_count=1151,
                    notch_profile='intel_square', label_ascii='INTEL TEST ' + str(number), status='unverified_reference',
                    source_urls=['https://www.intel.com/test'], topology_map_verified=False))


class HardwarePackTests(unittest.TestCase):
    def test_lifecycle_is_atomic_detached_and_releases_selected_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.dspack'; target = root / 'installed'
            raw = packs.make_pack('intel-desktop', 'Intel Desktop', [model(i) for i in range(16)])
            self.assertEqual(raw, packs.make_pack('intel-desktop', 'Intel Desktop', [model(i) for i in range(16)]))
            source.write_bytes(raw); store = packs.PackStore(target)
            self.assertEqual(store.memory_status()['selected_records'], 0)
            self.assertFalse(target.exists())
            store.install(source)
            self.assertEqual(len(store.choices()), 16)
            for index in range(16):
                row = store.get_cpu('intel-test-' + str(index)); row['cpu_package']['width_mm'] = 1
            self.assertEqual(store.memory_status()['selected_records'], 8)
            self.assertEqual(store.get_cpu('intel-test-15')['cpu_package']['width_mm'], 37.5)
            self.assertEqual(store.memory_status()['persistent_meshes'], 0)
            self.assertEqual(store.memory_status()['background_workers'], 0)
            self.assertTrue(store.remove('intel-desktop')); self.assertEqual(store.choices(), [])
            self.assertEqual(store.memory_status()['selected_records'], 0)
            self.assertTrue(source.exists())

    def test_rejects_scripts_paths_duplicates_encryption_and_corruption(self):
        raw = packs.make_pack('intel-test', 'Intel Test', [model()])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            manifest = archive.read('manifest.json'); models = archive.read('models.json')
        for bad_name in ('../manifest.json', 'C:/models.json', 'code.py', 'models.json/child'):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr('manifest.json', manifest); archive.writestr('models.json', models)
                archive.writestr(bad_name, b'forbidden')
            with self.assertRaises(packs.PackError): packs._archive(buffer.getvalue())
        with self.assertRaises(packs.PackError): packs._archive(raw[:-40])
        encrypted=bytearray(raw)
        for signature,offset in ((b'PK\x03\x04',6),(b'PK\x01\x02',8)):
            at=encrypted.find(signature)
            value=struct.unpack_from('<H',encrypted,at+offset)[0]
            struct.pack_into('<H',encrypted,at+offset,value|1)
        with self.assertRaises(packs.PackError):packs._archive(bytes(encrypted))
        duplicate=io.BytesIO()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(duplicate,'w') as archive:
                archive.writestr('manifest.json',manifest);archive.writestr('models.json',models)
                archive.writestr('models.json',models)
        with self.assertRaises(packs.PackError):packs._archive(duplicate.getvalue())
        with self.assertRaises(packs.PackError): packs._json(b'{"a":1,"a":2}')
        with self.assertRaises(packs.PackError): packs._json(b'{"a":NaN}')
        with self.assertRaises(packs.PackError):packs.make_pack('intel-test','Intel Test',[model()],version='1'*190000+'.0.0')

    def test_invalid_data_never_overwrites_valid_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.dspack'; store = packs.PackStore(root / 'installed')
            source.write_bytes(packs.make_pack('intel-test', 'Intel Test', [model()]))
            store.install(source); before = (store.directory / 'intel-test.dspack').read_bytes()
            source.write_bytes(b'corrupt')
            with self.assertRaises(packs.PackError): store.install(source)
            self.assertEqual((store.directory / 'intel-test.dspack').read_bytes(), before)

    def test_all_untrusted_generator_fields_are_bounded(self):
        mutations = [lambda row: row.update(code='bad'), lambda row: row.update(id='amd-9950x'),
                     lambda row: row.update(label='<img src="https://example.invalid/track">'),
                     lambda row: row['cpu_package'].update(width_mm=float('inf')),
                     lambda row: row['cpu_package'].update(width_mm=10**400),
                     lambda row: row['cpu_package'].update(width_mm=True),
                     lambda row: row['cpu_package'].update(pin_count=100000000),
                     lambda row: row['cpu_package'].update(socket='AM5'),
                     lambda row: row['cpu_package'].update(id='arbitrary_renderer'),
                     lambda row: row['cpu_package'].update(id=[]),
                     lambda row: row['cpu_package'].update(package_family=[]),
                     lambda row: row['cpu_package'].update(cooler_inferred=True),
                     lambda row: row['cpu_package'].update(label_ascii='X' * 10000),
                     lambda row: row['sources'].__setitem__(0, 'file:///private')]
        for mutate in mutations:
            row = model(); mutate(row)
            with self.assertRaises(packs.PackError): packs.make_pack('intel-test', 'Intel Test', [row])

    def test_ids_collisions_and_manifest_inventory_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.dspack'; store = packs.PackStore(root / 'installed')
            source.write_bytes(packs.make_pack('intel-one', 'One', [model()])); store.install(source)
            source.write_bytes(packs.make_pack('intel-two', 'Two', [model()]))
            with self.assertRaises(packs.PackError): store.install(source)
            self.assertEqual(len(store.choices()), 1)
            for identity in ('../outside', '/outside', 'x/y', 'C:\\outside'):
                with self.assertRaises(packs.PackError): store.remove(identity)

    def test_no_polling_or_directory_reads_after_initial_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = packs.PackStore(Path(tmp)); store.reload()
            with patch.object(Path, 'iterdir', side_effect=AssertionError('rescan')), patch.object(Path, 'open', side_effect=AssertionError('IO')):
                for _ in range(20):
                    self.assertEqual(store.choices(), []); self.assertIsNone(store.get_cpu('unknown'))

    def test_cached_remove_refuses_a_replaced_pack_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.dspack';store=packs.PackStore(root/'installed')
            source.write_bytes(packs.make_pack('intel-test','Intel Test',[model()]))
            store.install(source)
            store.directory.rename(root/'original')
            store.directory.mkdir()
            sentinel=store.directory/'intel-test.dspack';sentinel.write_bytes(b'keep replacement file')
            with self.assertRaises(packs.PackError):store.remove('intel-test')
            self.assertEqual(sentinel.read_bytes(),b'keep replacement file')

    def test_runtime_matching_does_not_import_authoring_catalog_or_borrow_readings(self):
        import cpu_package_runtime as runtime
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.dspack'; store = packs.PackStore(root / 'installed')
            source.write_bytes(packs.make_pack('intel-test', 'Intel Test', [model()])); store.install(source)
            with patch.object(packs, '_store', store):
                self.assertEqual(runtime.match_model('Intel(R) Test 0 CPU')['id'], 'intel-test-0')
                self.assertIsNone(runtime.match_model('AMD Ryzen Intel Test 0'))
                self.assertIsNone(runtime.match_model('Intel Test 0 laptop'))
                self.assertEqual(runtime.reference_choices()[0]['pack_id'], 'intel-test')
                self.assertEqual(runtime.get_package('amd-9950x')['socket'], 'AM5')


if __name__ == '__main__': unittest.main()
