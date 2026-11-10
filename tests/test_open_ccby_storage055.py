"""Pure contracts for the reviewed optional SSD and generic PSU references."""
from array import array
import copy
import gc
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
import weakref
import zipfile

import open_ccby_components054 as components
import open_reference_models054 as common


NEW_MANIFESTS = {
    'storage': 'dbc376326f9c1b6214d2f3a398076a5a9a45e11ac3b8e60bd660ad1752475487',
    'psu': '36006f94d97e8d80d93e465bec563e36e33d1151468259ef83a1a4e89762f86a',
}
FAILED_RAM = 'f232497507390b340ad12fcdbdf3a76b527f4e97124b84c4d347e2047eeb9f6e'
CLAIMS = ('dimensions_verified', 'mechanical_fit_verified', 'telemetry_bound',
          'source_quality_accepted', 'auto_play', 'watermark_applied', 'NC_override')


def identity_document(approved):
    doc = dict(format='DesktopStats.open-CCBY-world-PN.054.1', asset=approved['asset'],
               source_license='CC-BY-4.0', attribution=approved['attribution'],
               source_urls=[approved['source_url'], components.CC_BY_URL],
               source_original_sha256=approved['source_sha256'],
               source_indexed_metadata_sha256=approved['indexed_sha256'],
               source_parent_metadata_sha256=approved['parent_sha256'],
               source_lod_indices_sha256=approved['lod_sha256'])
    doc.update({key: False for key in CLAIMS})
    return doc


class OpenCCBYStorage055Tests(unittest.TestCase):
    def test_new_allowlist_preserves_old_sources_and_excludes_failed_RAM(self):
        self.assertEqual({row['asset'] for row in components.APPROVED.values()},
                         {'cpu', 'gpu', 'storage', 'psu'})
        self.assertNotIn(FAILED_RAM, components.APPROVED)
        cpu = components.APPROVED['733bfe8d09420baabc2520a3eda3a16b32a72755fde1e9061cfbb5b53f8db426']
        gpu = components.APPROVED['bce17130167b2cfb6c2f92d991ab1342e1dbb2cec8da3e6efcb8eecaa68328f6']
        self.assertEqual((cpu['triangles'], gpu['triangles']), (426, 56742))
        self.assertEqual(gpu['lod_sha256'], '01822c53e1b74bb7fc79ce78a63b4c7d556d780703966e6ed8db823055c20394')
        self.assertEqual(common.MAX_PACKAGE_BYTES, 12 * 1024 * 1024)
        for asset, checksum in NEW_MANIFESTS.items():
            row = components.APPROVED[checksum]
            self.assertEqual(row['asset'], asset)
            self.assertIsNone(row['parent_sha256'])
            self.assertIsNone(row['lod_sha256'])
        package = Mock()
        package.read.return_value = b'{"asset":"ram","source_license":"CC-BY-4.0"}'
        with self.assertRaisesRegex(common.ModelError, '尚未纳入'):
            components.from_package(package)
        package.verify.assert_not_called()

    def test_two_authors_and_unverified_reference_claims_cannot_be_relabelled(self):
        for asset, checksum in NEW_MANIFESTS.items():
            approved = components.APPROVED[checksum]
            doc = identity_document(approved)
            components.validate_source_identity(doc, approved)
            with self.subTest(asset=asset, field='author'), self.assertRaisesRegex(common.ModelError, '署名'):
                components.validate_source_identity(dict(doc, attribution='Our exclusive retail model'), approved)
            with self.subTest(asset=asset, field='source'), self.assertRaisesRegex(common.ModelError, '来源'):
                components.validate_source_identity(dict(doc, source_original_sha256='0' * 64), approved)
            for claim in CLAIMS:
                with self.subTest(asset=asset, claim=claim), self.assertRaisesRegex(common.ModelError, '许可限制'):
                    components.validate_source_identity(dict(doc, **{claim: True}), approved)
        self.assertEqual(components.APPROVED[NEW_MANIFESTS['psu']]['attribution'],
                         'PSU Power Supply Unit · Groovex · CC BY 4.0')

    def test_complete_source_quality_and_rights_bytes_are_required(self):
        for asset in NEW_MANIFESTS:
            files = {name: (name, size, checksum) for name, size, checksum in components.FILES[asset]}
            self.assertTrue({'world-PN054.bin', 'source-original.glb', 'mesh053.json', 'geometry053.bin',
                             'source-quality053.json', 'PN-QUALITY055.json', 'CHANGES054.txt'} <= files.keys())
            self.assertTrue(set(components._NOTICES) <= set(components.FILES[asset]))
            # The package must not trust a provider returning byte-different evidence,
            # even when its advertised length is unchanged.
            for name in ('PN-QUALITY055.json', 'LICENSE-CC-BY-4.0.txt', 'source-original.glb'):
                target = files[name]
                package = Mock()
                package.verify.return_value = b'X' * target[1]
                with self.subTest(asset=asset, name=name), \
                        patch.object(components, 'FILES', {asset: (target,)}), \
                        self.assertRaisesRegex(common.ModelError, '校验不匹配'):
                    components.verify_files(package, asset)
                package.verify.assert_called_once_with(*target)

    def test_import_keeps_all_optional_models_cold(self):
        code = compile(Path(components.__file__).read_text('utf-8'), components.__file__, 'exec')
        module = ModuleType('_cold_optional_storage055')
        before = set(sys.modules)
        with patch.object(Path, 'open', side_effect=AssertionError('No model I/O')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('No preload')), \
                patch.object(zipfile, 'ZipFile', side_effect=AssertionError('No ZIP scan')):
            exec(code, module.__dict__)
        self.assertEqual(set(module.FILES), {'cpu', 'gpu', 'storage', 'psu'})
        self.assertFalse(any(name.startswith(('PySide6', 'stats_config', 'profile_paths', 'sensors'))
                             for name in set(sys.modules) - before))

    def test_PSU_and_storage_use_one_readonly_PN_owner_in_six_styles(self):
        # A tiny package exercises the production reader without private assets,
        # codec imports, a scene factory or a machine-specific hardware profile.
        packed = array('f', (0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1,
                             0, 1, 0, 0, 0, 1)).tobytes()
        for asset, checksum in NEW_MANIFESTS.items():
            approved = dict(components.APPROVED[checksum], draws=1, triangles=1)
            doc = identity_document(approved)
            identity = 'reference:' + asset + '-synthetic-control'
            doc.update(model_id='test-' + asset, label=asset, physical_draws=1, triangles=1,
                       parts=[dict(id=identity, label='Synthetic control', kind=asset)],
                       draws=[dict(name=identity, part_id=identity, component=asset, bytes=len(packed),
                                   vertex_count=3, offset=0, source_RGBA_linear=[.2, .4, .6, 1.])],
                       reference_bounds=dict(minimum=[0., 0., 0.], maximum=[1., 1., 0.]),
                       source_materials=[], changes='All source triangles retained; no repair.',
                       coordinate_convention='unverified reference units',
                       runtime_material_limit='Color factors only; textures retained in archive.')
            raw = json.dumps(doc, allow_nan=False).encode()
            approved['manifest_bytes'] = len(raw)
            package = Mock()
            package.read.return_value = raw
            with self.subTest(asset=asset), \
                    patch.object(components, 'APPROVED', {hashlib.sha256(raw).hexdigest(): approved}), \
                    patch.object(components, 'verify_files', return_value=packed):
                model = components.from_package(package)
                scenes = [common.scene_for_style(model, style) for style in common.STYLES]
                view = model.scene.meshes[0].vertices
                self.assertTrue(view.readonly)
                self.assertIs(view.obj, packed)
                self.assertEqual((view.format, view.itemsize, model.geometry_bytes), ('f', 4, 72))
                self.assertTrue(all(scene.meshes[0].vertices is view for scene in scenes))
                self.assertTrue(all(scene.meshes[0].component == asset and not scene.meshes[0].rotor for scene in scenes))
                self.assertTrue(all(scene.metadata['telemetry_bound'] is False for scene in scenes))
                refs = [weakref.ref(model), weakref.ref(model.scene), weakref.ref(model.scene.meshes[0])]
                del model, scenes, view
                gc.collect()
                self.assertTrue(all(ref() is None for ref in refs))
            wrong = copy.deepcopy(doc)
            wrong['draws'][0]['component'] = 'gpu'
            badraw = json.dumps(wrong, allow_nan=False).encode()
            approved['manifest_bytes'] = len(badraw)
            package.read.return_value = badraw
            with patch.object(components, 'APPROVED', {hashlib.sha256(badraw).hexdigest(): approved}), \
                    patch.object(components, 'verify_files', return_value=packed), \
                    self.assertRaisesRegex(common.ModelError, '部件不匹配'):
                components.from_package(package)


if __name__ == '__main__':
    unittest.main()
