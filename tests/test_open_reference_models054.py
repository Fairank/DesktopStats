"""Pure controls for explicit reviewed-model opening, without private assets."""
from array import array
import importlib.util
import math
from pathlib import Path
import stat
import struct
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import open_reference_models054 as models


class OpenReferenceModel054Tests(unittest.TestCase):
    def test_cold_adapter_import_does_not_open_or_discover_any_model(self):
        code = compile(Path(models.__file__).read_text('utf-8'), models.__file__, 'exec')
        probe = ModuleType('_cold_open_reference_probe054')
        before = set(sys.modules)
        with patch.dict(sys.modules, {probe.__name__: probe}), \
                patch.object(Path, 'open', side_effect=AssertionError('No model I/O')), \
                patch.object(zipfile, 'ZipFile', side_effect=AssertionError('No archive discovery')):
            exec(code, probe.__dict__)
            self.assertTrue(callable(probe.load_reference))
        self.assertFalse(any(name.startswith(('PySide6', 'stats_config', 'profile_paths', 'sensors'))
                             for name in set(sys.modules) - before))

    def test_affine_positions_and_inverse_transpose_normals_are_packed_readonly(self):
        position = array('f', (1, 0, 0, 0, 1, 0, 0, 0, 0))
        normal = array('f', (math.sqrt(.5), math.sqrt(.5), 0) * 3)
        matrix = (2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 4, 0, 5, 7, 11, 1)
        result = models._expanded(position, normal, (0, 1, 2), matrix, 10)
        self.assertEqual(tuple(result[:3]), (70, 70, 110))
        self.assertEqual(tuple(result[6:9]), (50, 100, 110))
        expected = (3/math.sqrt(13), 2/math.sqrt(13), 0)
        for actual, value in zip(result[3:6], expected):
            self.assertAlmostEqual(actual, value, places=6)
        self.assertTrue(result.readonly)
        self.assertTrue(result.c_contiguous)
        self.assertEqual((result.format, result.itemsize, result.ndim), ('f', 4, 1))
        self.assertIsInstance(result.obj, bytes)
        with self.assertRaises(TypeError): result[0] = 99
        with self.assertRaises(models.ModelError):
            models._expanded(position, normal, (0, 1, 3), matrix, 10)
        with self.assertRaises(models.ModelError):
            models._normal_basis((0,) * 15 + (1,))

    def test_trs_parent_composition_keeps_authored_pose_and_independent_normal(self):
        local = models._local_matrix(dict(translation=[5, 7, 11], scale=[2, 3, 4],
                                         rotation=[0, 0, math.sqrt(.5), math.sqrt(.5)]))
        parent = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 0, 0, 1)
        position = (1, 0, 0, 0, 0, 0, 0, 1, 0)
        normal = (1, 0, 0) * 3
        packed = models._expanded(position, normal, (0, 1, 2), models._multiply(parent, local), 1)
        for actual, expected in zip(packed[:6], (15, 9, 11, 0, 1, 0)):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_six_styles_share_exact_geometry_and_reference_identity(self):
        from assembly_geometry import Mesh
        vertices = memoryview(struct.pack('<18f', 0, 0, 0, 0, 0, 1,
                                           1, 0, 0, 0, 0, 1,
                                           0, 1, 0, 0, 0, 1)).cast('f')
        meshes = [Mesh('frame', vertices, (.04, .04, .04, 1), component='fans', part_id='reference:frame'),
                  Mesh('blade', vertices, (.05, .05, .05, 1), component='fans', part_id='reference:impeller')]
        reference = models._finish('synthetic-control', 'Synthetic geometry control', meshes,
                    [dict(id='reference:frame', label='Frame', kind='fans'),
                     dict(id='reference:impeller', label='Blade', kind='fans')], 'control', ('', 'blade'))
        original = vertices.tobytes()
        for style in models.STYLES:
            scene = models.scene_for_style(reference, style)
            self.assertEqual(scene.metadata['visual_style'], style)
            self.assertFalse(scene.metadata['telemetry_bound'])
            self.assertFalse(scene.metadata['mechanical_fit_verified'])
            self.assertEqual(scene.dimensions, (1, 1, .01))
            for old, new in zip(reference.scene.meshes, scene.meshes):
                self.assertIs(new.vertices, old.vertices)
                self.assertIs(new.vertices.obj, old.vertices.obj)
                self.assertEqual(new.vertices.tobytes(), original)
                self.assertEqual((new.position, new.part_id), (old.position, old.part_id))
            if style in ('cartoon', 'notebook_color', 'sticker', 'papercut'):
                self.assertNotEqual(scene.meshes[0].color, scene.meshes[1].color)
        self.assertEqual(reference.geometry_bytes, 144)
        self.assertIs(models.scene_for_style(reference, 'miniature'), reference.scene)
        with self.assertRaises(TypeError): reference.parts[0]['label'] = 'Changed'
        with self.assertRaises(models.ModelError): models.scene_for_style(reference, 'invented-style')

    def test_zip_paths_duplicates_symlinks_and_declared_bombs_fail_before_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number, names in enumerate((('../escape',), ('file', 'FILE'), ('dir\\escape',))):
                path = root / ('bad-'+str(number)+'.zip')
                with zipfile.ZipFile(path, 'w') as archive:
                    for name in names: archive.writestr(name, b'not executable')
                with self.assertRaises(models.ModelError): models.load_reference(path)
            linked = root / 'linked.zip'
            info = zipfile.ZipInfo('component053.json')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(linked, 'w') as archive: archive.writestr(info, b'/outside')
            with self.assertRaises(models.ModelError): models.load_reference(linked)
            bomb = root / 'declared-bomb.zip'
            with zipfile.ZipFile(bomb, 'w') as archive: archive.writestr('component053.json', b'{}')
            raw = bytearray(bomb.read_bytes())
            at = raw.index(b'PK\x01\x02')
            struct.pack_into('<I', raw, at+24, models.MAX_PACKAGE_BYTES+1)
            bomb.write_bytes(raw)
            with self.assertRaises(models.ModelError): models.load_reference(bomb)

    def test_unreviewed_source_and_reparse_or_escape_paths_cannot_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'component053.json').write_bytes(b'{"format":"pretend","source":{"license":"MIT"}}')
            with self.assertRaisesRegex(models.ModelError, '尚未纳入'):
                models.load_reference(root)
            package = models._Package(root)
            try:
                with patch.object(Path, 'lstat', return_value=SimpleNamespace(
                        st_mode=stat.S_IFREG, st_file_attributes=0x400)):
                    with self.assertRaisesRegex(models.ModelError, '重解析点'):
                        package.read('component053.json')
                with patch.object(Path, 'resolve', return_value=root.parent/'outside.json'):
                    with self.assertRaisesRegex(models.ModelError, '目录之外'):
                        package.read('component053.json')
                with self.assertRaises(models.ModelError): package.read('../outside.json')
            finally: package.close()


if __name__ == '__main__':
    unittest.main()
