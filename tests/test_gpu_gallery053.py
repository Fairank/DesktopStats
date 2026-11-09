"""Prepared API tests for real catalog identities, with no artwork generation."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import gpu_gallery053 as gallery
import hardware_appearance as appearance

ROOT = Path(__file__).resolve().parents[1]


class GpuGalleryReference053Tests(unittest.TestCase):
    def test_real_148_index_is_detached_and_does_not_resolve_models(self):
        with patch.object(appearance, 'appearance_for', side_effect=AssertionError('Discovery must not resolve models')) as resolver:
            rows = gallery.choices()
        self.assertEqual(resolver.call_count, 0)
        source = [row for row in appearance.CATALOG if row[1] == 'gpu']
        self.assertEqual(len(rows), 148)
        self.assertEqual([(r['id'], r['label'], r['brand']) for r in rows],
                         [(r[0], r[4], appearance.BRANDS[r[3]][0]) for r in source])
        self.assertEqual(len({r['id'] for r in rows}), 148)
        self.assertTrue(all(set(r) == {'id', 'label', 'brand', 'fidelity'} for r in rows))
        self.assertTrue(all(r['fidelity'] == 'two_dimensional_reference' for r in rows))
        pristine = copy.deepcopy(rows)
        rows[0]['label'] = 'changed'; rows.pop()
        self.assertEqual(gallery.choices(), pristine)

    def test_each_of_the_148_real_ids_resolves_to_its_own_existing_appearance(self):
        for row in appearance.CATALOG:
            if row[1] != 'gpu':
                continue
            with self.subTest(model=row[0]):
                selected = gallery.reference(row[0])
                self.assertTrue(selected, 'A listed reference must not silently resolve another model')
                self.assertEqual((selected['id'], selected['label'], selected['source_url']),
                                 (row[0], row[4], row[8]))
                actual = selected['appearance']
                self.assertEqual((actual['id'], actual['kind'], actual['confidence']),
                                 (row[0], 'gpu', 'model'))
                self.assertEqual(actual, appearance.appearance_for('gpu', row[-1][0]))
                self.assertTrue(selected['reference_only'])
                self.assertFalse(selected['telemetry_bound'])
                self.assertFalse(selected['installed_model_verified'])
                self.assertFalse(selected['mechanical_fit_verified'])

    def test_partial_and_unknown_fans_and_nested_provenance_are_not_completed(self):
        partial = gallery.reference('leadtek-hurricane-4090-24g')
        self.assertEqual(partial['appearance']['fan_profile']['blade_counts'], [9, None, 9])
        self.assertFalse(partial['appearance']['fan_profile']['render_ready'])
        unknown = gallery.reference('gigabyte-aorus-4090-master')
        self.assertIsNone(unknown['appearance']['fan_profile']['blades'])
        self.assertEqual(unknown['appearance']['fan_profile']['artwork_status'], 'pending')
        self.assertTrue(partial['appearance']['fan_profile']['source_url'].startswith('https://'))
        pristine = copy.deepcopy(partial)
        partial['appearance']['fan_profile']['blade_counts'][1] = 9
        partial['appearance']['board_details'].clear()
        self.assertEqual(gallery.reference('leadtek-hurricane-4090-24g'), pristine)

    def test_bad_non_gpu_or_ambiguous_identity_fails_closed(self):
        with patch.object(appearance, 'appearance_for', side_effect=AssertionError('Invalid requests must not resolve')) as resolver:
            for value in ('', None, True, [], {}, 7, 'x' * 65, '../gpu', 'intel-13700kf', 'not-a-gpu', 'ASUS-DUAL-4060-OC'):
                with self.subTest(value=value):
                    self.assertEqual(gallery.reference(value), {})
        self.assertEqual(resolver.call_count, 0)
        for result in ({}, dict(id='other', kind='gpu', confidence='model'),
                       dict(id='asus-dual-4060-oc', kind='gpu', confidence='series')):
            with patch.object(appearance, 'appearance_for', return_value=result):
                self.assertEqual(gallery.reference('asus-dual-4060-oc'), {})

    def test_actual_controller_slot_is_inactive_gated_and_gpu_is_not_an_art_job(self):
        tree = ast.parse((ROOT / 'assembly_tools.py').read_text(encoding='utf8'))
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AssemblyTools')
        method = copy.deepcopy(next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == 'accessoryGpuReference'))
        method.decorator_list = []
        scope = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     'actual-candidate-assembly_tools-slot', 'exec'), scope)
        target = SimpleNamespace(_accessory_gallery_active=False)
        with patch.object(gallery, 'reference', wraps=gallery.reference) as resolve:
            self.assertEqual(scope['accessoryGpuReference'](target, 'leadtek-hurricane-4090-24g'), {})
            self.assertEqual(resolve.call_count, 0)
            target._accessory_gallery_active = True
            result = scope['accessoryGpuReference'](target, 'leadtek-hurricane-4090-24g')
            resolve.assert_called_once_with('leadtek-hurricane-4090-24g')
            self.assertEqual(result['id'], 'leadtek-hurricane-4090-24g')
        import accessory_art
        self.assertNotIn('gpu', accessory_art._ASYNC_KINDS)
        self.assertNotIn('gpu', accessory_art._KINDS)
        self.assertIsNone(accessory_art.model_key('gpu', 'asus-dual-4060-oc', 'miniature'))
        self.assertEqual(accessory_art.cache_info(), dict(entries=0, max_entries=16))


if __name__ == '__main__':
    unittest.main()
