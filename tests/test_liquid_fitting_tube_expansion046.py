"""Pure authoring facts: per-end mating, measured scope and lazy loading."""
import ast
import copy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import liquid_fitting_tube_expansion046 as catalog


class FittingTubing046Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL', 'subprocess.Popen', 'threading.Thread.start', 'socket.socket'):
            self.enterContext(patch(target, side_effect=AssertionError('Authoring catalog must perform no I/O')))

    def test_fresh_import_invalid_filters_and_lookups_do_not_allocate(self):
        source = Path(catalog.__file__).read_text(encoding='utf8')
        isolated = {}
        exec(compile(source, catalog.__file__, 'exec'), isolated)
        self.assertIsNone(isolated['_ROWS'])
        for invalid in (None, False, 0, [], {}, 'unknown', '../private', 'x' * 200):
            self.assertIsNone(isolated['get_record'](invalid))
            self.assertIsNone(isolated['_ROWS'])
        for invalid in (False, 0, [], {}, 'radiator', 'loop'):
            self.assertEqual(isolated['records'](invalid), ())
            self.assertIsNone(isolated['_ROWS'])
        rows = isolated['records']()
        self.assertIsInstance(rows, tuple)
        self.assertIs(rows, isolated['records']())
        self.assertEqual(tuple(r['id'] for r in rows), catalog.IDS)
        imports = [n for n in ast.walk(ast.parse(source)) if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual([(n.module, tuple(a.name for a in n.names)) for n in imports], [('copy', ('deepcopy',))])

    def test_detached_lookup_and_kind_filter_keep_authoritative_data(self):
        for identity in catalog.IDS:
            row = catalog.get_record(identity)
            before = copy.deepcopy(row)
            row['dimensions_mm']['width'] = -1
            row['geometry_features'].clear()
            row['ports'][0]['position_normalized'][0] = 50
            self.assertEqual(catalog.get_record(identity), before)
        fitting = catalog.records('fitting')
        tubing = catalog.records('tubing')
        self.assertEqual(len(fitting), 20)
        self.assertEqual(len(tubing), 11)
        self.assertTrue(all(r['part_kind'] == 'fitting' for r in fitting))
        self.assertTrue(all(r['part_kind'] == 'tubing' for r in tubing))
        self.assertEqual({r['id'] for r in fitting + tubing}, set(catalog.IDS))

    def test_named_units_specs_and_sources_not_color_or_quantity_padding(self):
        rows = catalog.records()
        self.assertEqual(len(rows), 31)
        self.assertEqual(len(set(catalog.IDS)), 31)
        self.assertEqual({r['brand'] for r in rows}, {'Alphacool', 'CORSAIR', 'Thermaltake'})
        signatures = set()
        for row in rows:
            json.dumps(row, allow_nan=False)
            signature = (row['brand'], row['series'], row['form'], row['geometry_family'], row['fitting_angle_deg'], row['tube_inner_mm'], row['tube_outer_mm'])
            self.assertNotIn(signature, signatures, row['id'])
            signatures.add(signature)
            self.assertTrue(row['sources'])
            self.assertTrue(all(u.startswith(('https://download.alphacool.com/', 'https://www.corsair.com/', 'https://thermaltake.com/', 'https://www.thermaltake.com/')) for u in row['sources']))
            self.assertTrue(row['notes'])
            self.assertEqual(row['selection_source'], 'manual')
            self.assertTrue(row['photo_reviewed'])
            self.assertEqual(row['source_authority'], 'manufacturer')
            self.assertEqual(row['ports_count'], len(row['ports']))
            self.assertTrue(row['ports_geometry_complete'])
            self.assertEqual(row['geometry_accuracy'], 'original_reference')
            self.assertEqual(row['geometry_features_basis'], 'observed_reference')
            for key in ('live_temperature_available', 'live_flow_available', 'installed_hardware_inferred'):
                self.assertFalse(row[key])

    def test_unknown_envelope_axes_remain_null_with_separate_reference(self):
        for row in catalog.records():
            dims = row['dimensions_mm']
            axes = row['axis_verified']
            self.assertEqual(set(dims), {'width', 'height', 'depth'})
            self.assertEqual(set(axes), set(dims))
            for name, value in dims.items():
                if value is None:
                    self.assertFalse(axes[name])
                else:
                    self.assertIs(type(axes[name]), bool)
                    self.assertGreater(value, 0)
            self.assertEqual(row['dimensions_verified'], all(axes.values()))
            self.assertEqual(set(row['reference_envelope_mm']), set(dims))
            self.assertTrue(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in row['reference_envelope_mm'].values()))
            self.assertIn(row['dimensions_scope'], ('overall', 'publisher_unspecified', 'supplied_tube'))
        partial = catalog.get_record('alphacool-eiszapfen-hard-90-13')
        self.assertEqual(partial['dimensions_mm'], dict(width=21, height=None, depth=42.5))
        self.assertFalse(partial['dimensions_verified'])
        for identity in ('corsair-xf-soft-10-13', 'corsair-xf-hard-14', 'corsair-xf-rotary-90', 'corsair-xf-ball-valve'):
            row = catalog.get_record(identity)
            self.assertEqual(set(row['dimensions_mm'].values()), {None})
            self.assertFalse(any(row['axis_verified'].values()))

    def test_each_port_has_separate_thread_gender_tube_and_reference_pose(self):
        coordinates = {'front': (2, .5), 'rear': (2, -.5), 'top': (1, .5), 'bottom': (1, -.5), 'left': (0, -.5), 'right': (0, .5)}
        for row in catalog.records():
            self.assertEqual(len({p['id'] for p in row['ports']}), len(row['ports']))
            for port in row['ports']:
                self.assertIn(port['thread_gender'], ('male', 'female', 'none', 'unknown'))
                self.assertIn(port['thread'], ('G1/4', None))
                self.assertEqual(port['thread'] is None, port['thread_gender'] == 'none')
                self.assertFalse(port['position_verified'])
                self.assertIs(type(port['role_verified']), bool)
                self.assertIn(port['source'], row['sources'])
                point = port['position_normalized']
                self.assertEqual(len(point), 3)
                self.assertTrue(all(math.isfinite(v) and -.5 <= v <= .5 for v in point))
                self.assertIn(port['role'], ('connection', 'closure'))
                if port['face'] == 'angled':
                    normal = port['normal_reference']
                    self.assertEqual(len(normal), 3)
                    self.assertAlmostEqual(sum(v*v for v in normal), 1, places=12)
                    self.assertFalse(port['normal_verified'])
                else:
                    axis, edge = coordinates[port['face']]
                    self.assertEqual(point[axis], edge)
                if port['thread_gender'] == 'none':
                    self.assertIn(port['tube_type'], ('soft', 'hard'))
                    self.assertGreater(port['tube_outer_mm'], 0)
                else:
                    self.assertIsNone(port['tube_outer_mm'])
                    self.assertIsNone(port['tube_inner_mm'])
                self.assertNotIn('inlet', port['id'])
                self.assertNotIn('outlet', port['id'])

    def test_known_conflict_and_dual_compression_do_not_become_threaded_mates(self):
        conflict = catalog.get_record('alphacool-eiszapfen-static-45')
        self.assertEqual([p['thread_gender'] for p in conflict['ports']], ['unknown', 'unknown'])
        self.assertFalse(any(p['role_verified'] for p in conflict['ports']))
        self.assertEqual(conflict['fitting_angle_deg'], 45)
        self.assertIn('conflicts', conflict['notes'])
        dual = catalog.get_record('thermaltake-pacific-dual-hard-90-16')
        self.assertIsNone(dual['thread_standard'])
        self.assertEqual(dual['geometry_family'], 'dual_compression_elbow')
        self.assertEqual([p['thread'] for p in dual['ports']], [None, None])
        self.assertEqual([p['tube_type'] for p in dual['ports']], ['hard', 'hard'])
        self.assertTrue(all(p['tube_outer_mm'] == 16 for p in dual['ports']))
        self.assertNotIn('rotary_collar', dual['geometry_features'])
        plug = catalog.get_record('alphacool-eiszapfen-plug')
        self.assertEqual([p['role'] for p in plug['ports']], ['closure'])
        self.assertFalse(plug['requires_tube'])

    def test_source_specific_sizes_and_body_total_scopes(self):
        first = catalog.get_record('alphacool-eiszapfen-soft-90-16-10')
        self.assertEqual(first['dimensions_mm'], dict(width=22, height=34.5, depth=35.5))
        self.assertEqual((first['tube_inner_mm'], first['tube_outer_mm']), (10, 16))
        self.assertEqual(first['ports'][0]['thread_gender'], 'male')
        plug = catalog.get_record('alphacool-eiszapfen-plug')
        self.assertEqual(plug['dimensions_mm']['height'], 9.5)
        self.assertEqual(plug['dimensions_scope'], 'overall')
        self.assertIn('4.5mm', plug['notes'])
        extender = catalog.get_record('thermaltake-pacific-mm-ext20')
        self.assertEqual(extender['dimensions_mm'], dict(width=22, height=30, depth=22))
        self.assertEqual([p['thread_gender'] for p in extender['ports']], ['male', 'male'])
        self.assertIn('not total height', extender['notes'])
        fpro = catalog.get_record('thermaltake-f-pro-hard-16')
        self.assertEqual(fpro['dimensions_mm'], dict(width=24, height=23.6, depth=24))
        self.assertEqual(fpro['material'], 'copper')
        self.assertEqual(fpro['compatible_materials'], ['PCTG', 'PETG', 'PMMA', 'glass'])

    def test_tube_material_wall_and_per_unit_lengths_are_real_separate_specs(self):
        expected = {
            'alphacool-alphatube-hf-13-10': (13, 10, 3000, 'PVC'),
            'alphacool-alphatube-hf-16-10': (16, 10, 3000, 'PVC'),
            'alphacool-epdm-13-10': (13, 10, 3000, 'EPDM'),
            'alphacool-epdm-16-10': (16, 10, 1000, 'EPDM'),
            'alphacool-alphatube-tpv-16-10': (16, 10, 3300, 'TPV (EPDM/PP)'),
            'alphacool-acryl-13-10': (13, 10, 600, 'PMMA'),
            'alphacool-acryl-16-13': (16, 13, 800, 'PMMA'),
            'alphacool-carbon-13-10': (13, 10, 800, 'CFRP'),
            'alphacool-carbon-16-13': (16, 13, 800, 'CFRP'),
            'corsair-xt-hardline-14-10': (14, 10, 1000, 'PMMA'),
            'thermaltake-v-tubler-petg-16-12': (16, 12, 500, 'PETG'),
        }
        for identity, values in expected.items():
            row = catalog.get_record(identity)
            self.assertEqual((row['tube_outer_mm'], row['tube_inner_mm'], row['length_mm'], row['material']), values)
            self.assertGreater(row['tube_outer_mm'], row['tube_inner_mm'])
            self.assertEqual(row['reference_envelope_mm']['height'], 80)
            self.assertEqual(row['dimensions_scope'], 'supplied_tube')
            self.assertIsNone(row['min_bend_radius_mm'])
            self.assertIsNone(row['thread_standard'])
            self.assertFalse(row['requires_tube'])
            self.assertTrue(all(p['thread'] is None and p['thread_gender'] == 'none' for p in row['ports']))
        self.assertIn('not exact5/8', catalog.get_record('thermaltake-v-tubler-petg-16-12')['notes'])

    def test_finite_geometry_families_encode_actual_structural_differences(self):
        families = {'knurled_soft_compression', 'knurled_hard_compression', 'smooth_hard_compression', 'silicone_grip_hard_compression', 'rotary_compression_elbow', 'static_thread_elbow', 'rotary_thread_adapter', 'low_profile_plug', 'clear_soft_tube', 'opaque_soft_tube', 'clear_hard_tube', 'carbon_hard_tube', 'ball_drain', 'dual_compression_elbow', 'knurled_extension'}
        features = {'diamond_knurl', 'compression_ring', 'stepped_base', 'silicone_grip', 'axial_grip_flutes', 'beveled_lip', 'rotary_collar', 'smooth_elbow', 'low_profile_elbow', 'slotted_cap', 'lever_handle', 'smooth_sleeve', 'transparent_wall', 'matte_wall', 'hollow_ends', 'carbon_weave_reference', 'dual_compression_rings', 'ring_seam'}
        self.assertEqual({r['geometry_family'] for r in catalog.records()}, families)
        for row in catalog.records():
            self.assertTrue(set(row['geometry_features']) <= features)
            self.assertEqual(len(row['geometry_features']), len(set(row['geometry_features'])))
        apex = catalog.get_record('alphacool-apex-grip-hard-13')
        smooth = catalog.get_record('thermaltake-f-pro-hard-16')
        self.assertIn('silicone_grip', apex['geometry_features'])
        self.assertNotIn('diamond_knurl', smooth['geometry_features'])
        self.assertNotEqual(apex['geometry_family'], smooth['geometry_family'])

    def test_selected_sku_palette_tracks_reviewed_finish_without_color_duplicates(self):
        def brightness(row):
            color = row['body_color']
            self.assertEqual(len(color), 7)
            self.assertTrue(color.startswith('#'))
            return sum(int(color[n:n+2], 16)/255 for n in (1, 3, 5))/3
        for row in catalog.records():
            self.assertTrue(0 <= brightness(row) <= 1)
            self.assertIn('not measured factory paint', row['notes'])
        self.assertGreater(brightness(catalog.get_record('alphacool-eiszapfen-soft-13-10')), .8)
        self.assertLess(brightness(catalog.get_record('corsair-xf-hard-14')), .25)
        self.assertGreater(brightness(catalog.get_record('thermaltake-f-pro-hard-16')), .65)
        self.assertGreater(brightness(catalog.get_record('thermaltake-pacific-dual-hard-90-16')), .65)
        self.assertLess(brightness(catalog.get_record('thermaltake-pacific-mm-ext20')), .25)
        self.assertLess(brightness(catalog.get_record('alphacool-carbon-16-13')), .25)
        self.assertEqual(len(catalog.IDS), 31)


if __name__ == '__main__':
    unittest.main()
