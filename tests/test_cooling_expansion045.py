"""Pure-data regressions for the optional 0.45 cooling library.

No Qt, hardware collection, renderer, application or installed profile is used.
"""
import importlib.util
import json
from pathlib import Path
import unittest

import cooling_expansion045 as catalog


class CoolingExpansion045Tests(unittest.TestCase):
    def setUp(self):
        self.fans = catalog.fan_records()
        self.coolers = catalog.cooler_records()

    def test_exact_ids_counts_and_base_catalog_disjoint(self):
        import cooling_catalog as base
        self.assertEqual((len(self.fans), len(self.coolers)), (40, 23))
        self.assertEqual(set(catalog.fan_ids), set(self.fans))
        self.assertEqual(set(catalog.cooler_ids), set(self.coolers))
        self.assertEqual(len(catalog.fan_ids), len(set(catalog.fan_ids)))
        self.assertEqual(len(catalog.cooler_ids), len(set(catalog.cooler_ids)))
        self.assertFalse(set(self.fans) & {r['id'] for r in base._FANS})
        self.assertFalse(set(self.coolers) & {r['id'] for r in base._COOLERS})
        self.assertGreaterEqual(len({r['brand'] for r in self.fans.values()}), 12)

    def test_json_only_authoring_api_and_detached_nested_values(self):
        encoded = json.dumps(dict(fans=self.fans, coolers=self.coolers), allow_nan=False)
        self.assertEqual(json.loads(encoded)['fans'], self.fans)
        self.fans['arctic-p14-max']['foil_profile']['sweep_deg'] = -999
        self.fans['arctic-p14-max']['sources'].append('fake')
        self.coolers['noctua-nh-u9s']['dimensions_mm']['depth'] = -99
        self.assertEqual(catalog.fan_records()['arctic-p14-max']['foil_profile']['sweep_deg'], 42)
        self.assertNotIn('fake', catalog.fan_records()['arctic-p14-max']['sources'])
        self.assertEqual(catalog.cooler_records()['noctua-nh-u9s']['dimensions_mm']['depth'], 93.5)

    def test_separate_lazy_categories_and_no_imported_runtime(self):
        path = Path(catalog.__file__)
        spec = importlib.util.spec_from_file_location('_cooling_045_fresh', path)
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        self.assertIsNone(fresh._FANS)
        self.assertIsNone(fresh._COOLERS)
        self.assertEqual(set(fresh.fan_records()), set(fresh.fan_ids))
        self.assertIsNone(fresh._COOLERS)
        source = path.read_text(encoding='utf8')
        for forbidden in ('import PySide', 'import psutil', 'import cooling_catalog',
                          'import native_', 'urllib', 'threading', 'QTimer', 'subprocess'):
            self.assertNotIn(forbidden, source)

    def test_provenance_and_reference_geometry_are_separate(self):
        official_hosts = ('noctua.at', 'arctic.de', 'bequiet.com', 'deepcool.com', 'lian-li.com',
                          'thermaltakeusa.com', 'phanteks.com', 'coolermaster.com',
                          'fractal-design.com', 'montechpc.com', 'antec.com', 'apnx.com',
                          'corsair.com', 'nzxt.com', 'thermalright.com')
        from urllib.parse import urlparse
        for row in (*self.fans.values(), *self.coolers.values()):
            with self.subTest(id=row['id']):
                self.assertEqual(row['geometry_accuracy'], 'original_reference')
                self.assertTrue(row['brand'] and row['series'] and row['reviewed'])
                self.assertTrue(row['sources'])
                for url in row['sources']:
                    host = urlparse(url).hostname or ''
                    self.assertTrue(any(host == h or host.endswith('.'+h) for h in official_hosts), url)
                    self.assertEqual(urlparse(url).scheme, 'https')
                self.assertNotIn('data:image', json.dumps(row))
                self.assertFalse(any(k in row for k in ('rpm', 'current_rpm', 'rotation_rpm')))

    def test_observed_foils_bounded_not_random_motor_or_rpm_facts(self):
        foils = [r for r in self.fans.values() if 'foil_profile' in r]
        self.assertEqual(len(foils), 22)
        self.assertGreaterEqual(len({tuple(r['foil_profile'].values()) for r in foils}), 18)
        for row in foils:
            with self.subTest(id=row['id']):
                self.assertTrue(row['blade_count_verified'])
                self.assertTrue(row['blade_geometry_reviewed'])
                self.assertTrue(row['photo_observations'])
                self.assertEqual(row['foil_profile_accuracy'], 'qualitative_reference')
                for key, low, high in (('sweep_deg', -35, 55), ('leading', .05, .5),
                                       ('trailing', .05, .5), ('root', .15, .5)):
                    self.assertGreaterEqual(row['foil_profile'][key], low)
                    self.assertLessEqual(row['foil_profile'][key], high)
        for row in self.fans.values():
            self.assertFalse(row['rotation_direction_verified'])
            if not row['blade_count_verified']:
                self.assertIn('blade_count', row['unknown'])
                self.assertNotIn('foil_profile', row)
        self.assertEqual(sum(r['blade_count_verified'] for r in self.fans.values()), 29)

    def test_nonstandard_mount_axes_are_not_square_105mm(self):
        row = self.fans['noctua-nf-a12x25r-pwm']
        self.assertEqual(row['frame'], 'round')
        self.assertEqual(row['mount_pitch_axes_mm'], [93, 83])
        self.assertTrue(row['mount_pitch_axes_verified'])
        self.assertFalse(row['mount_pitch_axes_orientation_verified'])
        self.assertIsNone(row['mount_pitch_mm'])
        self.assertFalse(row['mount_pitch_verified'])
        self.assertEqual(self.coolers['noctua-nh-d12l']['fan_model'], row['id'])
        self.assertEqual(self.fans['lian-li-tl120']['width_mm'], 124)
        self.assertEqual(self.fans['lian-li-slinf120-reverse']['width_mm'], 122)
        self.assertEqual(self.fans['lian-li-tl120']['size_mm'], 120)

    def test_distinct_thin_thick_ring_reverse_and_fixed_white_window(self):
        self.assertEqual(self.fans['arctic-p14-max']['depth_mm'], 27)
        self.assertTrue(self.fans['arctic-p14-max']['outer_ring'])
        self.assertEqual(self.fans['arctic-p14-slim-pwm-pst']['depth_mm'], 16)
        self.assertEqual(self.fans['arctic-p14-pro']['blades'], 7)
        self.assertFalse(self.fans['arctic-p14-pro']['outer_ring'])
        self.assertTrue(self.fans['montech-rx120-pwm']['reverse_blade'])
        self.assertFalse(self.fans['montech-rx120-pwm']['rotation_direction_verified'])
        window = self.fans['deepcool-ft14']
        self.assertEqual((window['depth_mm'], window['blades']), (25, 9))
        self.assertFalse(window['rgb'])
        self.assertTrue(window['fixed_white_hub_window'])
        self.assertEqual(window['hub_window_face'], 'front')
        self.assertEqual(window['switch_face'], 'rear')
        self.assertEqual(window['fixed_led_color'], '#ffffff')
        for row in self.fans.values():
            if row['brand'] == 'Noctua':
                self.assertFalse(row['rgb'])
                self.assertFalse(row.get('fixed_white_hub_window', False))
                self.assertFalse(row.get('frame_rgb_ring', False))
        apnx = self.fans['apnx-fp2-120']
        self.assertTrue(apnx['replaceable_reverse_impeller'])
        self.assertFalse(apnx['reverse_blade'])

    def test_central_single_fan_and_under_fan_factory_layouts(self):
        for id in ('noctua-nh-d12l', 'deepcool-assassin4s',
                   'thermalright-pa120-mini-black', 'thermalright-silver-soul135'):
            with self.subTest(id=id):
                self.assertEqual(self.coolers[id]['fan_layout'], 'center')
                self.assertEqual(self.coolers[id]['kind'], 'dual_tower')
                self.assertEqual(self.coolers[id]['fan_count'], 1)
        low = self.coolers['noctua-nh-l12sx77']
        self.assertTrue(low['c_shape'])
        self.assertEqual(low['fan_placement'], 'under')
        self.assertEqual(low['dimensions_mm'], dict(width=128, height=77, depth=131))
        self.assertEqual(low['fan_model'], 'noctua-nf-a12x15-pwm')
        self.assertEqual(self.coolers['deepcool-assassin4s']['dimensions_mm']['depth'], 116)

    def test_dimension_conflicts_not_promoted_to_exact_fitment(self):
        for id in ('noctua-nh-u9s', 'bequiet-pure-rock2', 'bequiet-shadow-rock3'):
            row = self.coolers[id]
            self.assertFalse(row['dimensions_verified'])
            self.assertFalse(row['dimension_axes_verified']['depth'])
            self.assertTrue(row['notes'])
        for id in ('corsair-h170i-elite-lcd-xt', 'corsair-h150i-elite-lcd-xt'):
            row = self.coolers[id]
            self.assertFalse(row['radiator_dimensions_verified'])
            self.assertFalse(row['radiator_axes_verified']['thickness'])
        self.assertEqual(self.coolers['noctua-nh-u14s']['dimensions_mm']['depth'], 78)
        an400 = self.coolers['deepcool-an400']
        self.assertNotIn('fixed_white_hub_window', an400)
        self.assertFalse(an400['dimensions_verified'])

    def test_verified_hole_measurements_have_independent_sources(self):
        for row in self.fans.values():
            if row.get('mount_pitch_verified') or row.get('mount_pitch_axes_verified'):
                self.assertIn(row['mounting_source'], row['sources'])
        self.assertEqual(self.fans['arctic-p9-pwm-pst']['mount_pitch_mm'], 82.5)
        self.assertEqual(self.fans['fractal-aspect12-pwm']['mount_pitch_mm'], 105)
        self.assertEqual(self.fans['fractal-prisma-al14-pwm']['mount_pitch_mm'], 125)

    def test_sealed_aio_all_six_size_classes_and_correct_factory_fans(self):
        rows = [r for r in self.coolers.values() if r['kind'] == 'aio']
        self.assertEqual(len(rows), 8)
        self.assertEqual({r['radiator_size'] for r in rows}, {120, 140, 240, 280, 360, 420})
        for row in rows:
            self.assertTrue(row['sealed_aio'])
            self.assertEqual(row['radiator_size'], row['fan_count']*row['fan_reference_mm'])
            self.assertGreater(row['radiator_mm']['length'], row['radiator_size'])
        self.assertEqual(self.coolers['nzxt-kraken-x42']['radiator_mm'], dict(length=175, width=143, thickness=30))
        self.assertFalse(self.coolers['nzxt-kraken-x42']['pump_lcd'])
        self.assertEqual(self.coolers['nzxt-kraken-x42']['pump_style'], 'nzxt_infinity')
        self.assertFalse(self.coolers['corsair-h60-2018']['pump_rgb_ring'])
        self.assertTrue(self.coolers['corsair-h60-2018']['pump_fixed_white'])
        self.assertEqual(self.coolers['corsair-h170i-elite-lcd-xt']['fan_model'], 'corsair-af140-rgb-elite')
        self.assertEqual(self.coolers['nzxt-kraken-elite240-rgb-2023']['fan_model'], 'nzxt-f120-rgb-core-2023')
        self.assertEqual(self.coolers['nzxt-kraken-elite240-rgb-2023']['pump_reference_mm'], dict(width=81.9, height=59.5, depth=81.9))


if __name__ == '__main__':
    unittest.main()
