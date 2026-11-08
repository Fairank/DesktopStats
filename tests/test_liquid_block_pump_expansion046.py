"""Offline authoring contracts for retail liquid blocks, pumps and reservoirs."""
import ast
import json
import math
from pathlib import Path
import unittest
from urllib.parse import urlsplit

import liquid_block_pump_expansion046 as catalog


ROOT = Path(__file__).resolve().parents[1]
AXES = ('width', 'height', 'depth')
PRIMARY_DOMAINS = ('alphacool.com', 'corsair.com', 'watercool.de',
                   'aquacomputer.de', 'thermaltake.com', 'koolance.com',
                   'xs-pc.com', 'phanteks.com', 'phanteks.com.tw')


class LiquidBlockPumpExpansion046Tests(unittest.TestCase):
    def test_fresh_module_is_lazy_and_unknown_lookup_does_not_allocate_records(self):
        namespace = {}
        exec(compile((ROOT / 'liquid_block_pump_expansion046.py').read_text(encoding='utf-8'),
                     'liquid_block_pump_expansion046.py', 'exec'), namespace)
        self.assertIsNone(namespace['_ROWS'])
        self.assertIsNone(namespace['_BY_ID'])
        for identity in (None, False, 7, [], {}, '../pump', 'D5', 'ALPHACOOL-CORE1-BLACK'):
            self.assertEqual(namespace['get_record'](identity), {})
        with self.assertRaises(ValueError):
            namespace['records']('radiator')
        self.assertIsNone(namespace['_ROWS'])
        self.assertIsNone(namespace['_BY_ID'])
        self.assertEqual(len(namespace['records']('pump')), 8)
        self.assertEqual(len(namespace['_ROWS']), 32)

    def test_inventory_is_exact_products_not_colors_or_runtime_styles(self):
        rows = catalog.records()
        self.assertIsInstance(rows, tuple)
        self.assertIsInstance(catalog.IDS, tuple)
        self.assertEqual(len(rows), 32)
        self.assertEqual(len(catalog.IDS), len(set(catalog.IDS)))
        self.assertEqual(set(catalog.IDS), {r['id'] for r in rows})
        self.assertEqual(len({r['brand'] for r in rows}), 8)
        self.assertEqual({kind: len(catalog.records(kind)) for kind in catalog.KINDS},
                         {'cpu_block': 10, 'pump': 8, 'reservoir': 4, 'pump_reservoir': 10})
        self.assertEqual(len({r['geometry_family'] for r in rows}), 14)
        self.assertNotEqual(len({r['geometry_family'] for r in rows}), len(rows))
        for row in rows:
            self.assertTrue(row['label'] and row['series'] and row['geometry_features'])
            self.assertNotIn('style', row)

    def test_getter_and_filtered_records_are_deep_detached(self):
        identity = catalog.IDS[0]
        before = catalog.get_record(identity)
        changed = catalog.get_record(identity)
        changed['ports'][0]['position_normalized'][0] = 999
        changed['geometry_features'].append('mutation')
        changed['reference_envelope_mm']['width'] = 999
        changed['sources'].clear()
        self.assertEqual(catalog.get_record(identity), before)
        all_rows = catalog.records()
        all_rows[0]['factory_bracket']['description'] = 'mutation'
        self.assertEqual(catalog.get_record(identity), before)

    def test_dimensions_distinguish_source_axes_body_and_reference_envelope(self):
        for row in catalog.records():
            with self.subTest(identity=row['id']):
                self.assertEqual(set(row['axis_verified']), set(AXES))
                self.assertEqual(set(row['dimensions_mm']), set(AXES))
                self.assertEqual(set(row['reference_envelope_mm']), set(AXES))
                for axis in AXES:
                    reference = row['reference_envelope_mm'][axis]
                    self.assertIs(type(reference) in (int, float), True)
                    self.assertTrue(math.isfinite(reference) and 0 < reference < 1000)
                    actual = row['dimensions_mm'][axis]
                    self.assertIsInstance(row['axis_verified'][axis], bool)
                    self.assertEqual(row['axis_verified'][axis], actual is not None)
                    if actual is not None:
                        self.assertTrue(math.isfinite(actual) and actual > 0)
                self.assertEqual(row['dimensions_verified'], all(row['axis_verified'].values()))
                self.assertIn(row['dimensions_scope'], ('complete', 'partial', 'unknown', 'body_only'))
                if row['dimensions_scope'] == 'body_only':
                    self.assertFalse(row['dimensions_verified'])
                    self.assertTrue(all(v is None for v in row['dimensions_mm'].values()))
                    self.assertTrue(row.get('body_dimensions_verified'))
                if row['port_position_scope'] == 'body':
                    self.assertTrue(row.get('body_dimensions_verified'))
                    self.assertTrue(all(row['body_dimensions_mm'].get(axis, 0) > 0 for axis in AXES))
                else:
                    self.assertEqual(row['port_position_scope'], 'overall')

    def test_sources_are_primary_https_and_json_has_no_nonfinite_or_executable_payload(self):
        for row in catalog.records():
            with self.subTest(identity=row['id']):
                self.assertTrue(row['sources'])
                for source in row['sources'] + [p['source'] for p in row['ports']]:
                    url = urlsplit(source)
                    self.assertEqual(url.scheme, 'https')
                    self.assertTrue(any(url.hostname == d or url.hostname.endswith('.' + d)
                                        for d in PRIMARY_DOMAINS), source)
                self.assertEqual(json.loads(json.dumps(row, allow_nan=False)), row)
                raw = json.dumps(row).casefold()
                for forbidden in ('data:image', '<script', 'qa-private', 'c:\\users', 'powershell'):
                    self.assertNotIn(forbidden, raw)

    def test_ports_are_reference_positions_with_independent_thread_role_and_hose_data(self):
        face_axes = {'right': (0, .5), 'left': (0, -.5), 'top': (1, .5),
                     'bottom': (1, -.5), 'front': (2, .5), 'rear': (2, -.5)}
        roles = {'inlet', 'outlet', 'connection', 'fill', 'drain', 'auxiliary'}
        for row in catalog.records():
            with self.subTest(identity=row['id']):
                ids = [p['id'] for p in row['ports']]
                self.assertEqual(len(ids), len(set(ids)))
                if row['ports_count'] is not None:
                    self.assertGreaterEqual(row['ports_count'], len(row['ports']))
                    if row['ports_geometry_complete']:
                        self.assertEqual(row['ports_count'], len(row['ports']))
                else:
                    self.assertFalse(row['ports_geometry_complete'])
                for port in row['ports']:
                    self.assertFalse(port['position_verified'])
                    self.assertIsInstance(port['role_verified'], bool)
                    self.assertIn(port['role'], roles)
                    self.assertIn(port['thread_gender'], ('male', 'female', 'none', 'unknown'))
                    xyz = port['position_normalized']
                    self.assertEqual(len(xyz), 3)
                    self.assertTrue(all(type(v) in (int, float) and math.isfinite(v) and -.5 <= v <= .5
                                        for v in xyz))
                    index, limit = face_axes[port['face']]
                    self.assertEqual(xyz[index], limit)

    def test_bare_motors_have_no_fabricated_hydraulic_threads(self):
        raw_ids = ('aquacomputer-d5-next', 'watercool-wcp-d5-pwm',
                   'alphacool-vpp655-pwm', 'alphacool-vpp-apex', 'alphacool-dc-lt2-2600')
        for identity in raw_ids:
            row = catalog.get_record(identity)
            self.assertEqual((row['part_kind'], row['form']), ('pump', 'pump_body'))
            self.assertTrue(row['contains_motor'])
            self.assertFalse(row['requires_motor'])
            self.assertEqual(row['ports_count'], 0)
            self.assertEqual(row['ports'], [])
            self.assertTrue(row['ports_geometry_complete'])
        self.assertEqual(catalog.get_record('alphacool-vpp-apex')['label'],
                         'Alphacool VPP Apex Pump ·13339')

    def test_pump_tops_and_motorless_combo_bodies_do_not_acquire_a_motor_or_oled(self):
        for identity in ('alphacool-eisstation-dclt-solotop',
                         'aquacomputer-ultitube-d5-150-pro-body', 'xspc-d5-argb-mini-tank'):
            row = catalog.get_record(identity)
            self.assertFalse(row['contains_motor'])
            self.assertTrue(row['requires_motor'])
            self.assertNotIn('oled_window', row['observed_lighting'])
            self.assertNotIn('ips_lcd_window', row['observed_lighting'])
        top = catalog.get_record('alphacool-eisstation-dclt-solotop')
        self.assertEqual((top['part_kind'], top['form']), ('pump', 'pump_top'))
        qx5 = catalog.get_record('xspc-qx5-argb-mini')
        self.assertEqual((qx5['part_kind'], qx5['form']), ('pump', 'pump_complete'))
        self.assertIn('QX5', qx5['motor_type'])
        self.assertNotEqual(qx5['motor_type'], 'DDC')

    def test_body_measurement_and_mounting_exclusions_are_not_complete_fit_certificates(self):
        hk = catalog.get_record('watercool-heatkiller-iv-pro-amd-acetal')
        self.assertEqual(hk['body_dimensions_mm'], {'width': 66, 'height': 17, 'depth': 59})
        self.assertFalse(hk['dimensions_verified'])
        self.assertEqual(hk['port_position_scope'], 'body')
        for identity in ('aquacomputer-ultitube-d5-150-pro-next',
                         'aquacomputer-ultitube-d5-150-pro-body', 'aquacomputer-ultitube-d5-50-pro-next'):
            self.assertEqual(catalog.get_record(identity)['dimensions_scope'], 'body_only')
        w9 = catalog.get_record('thermaltake-pacific-w9')
        self.assertFalse(w9['dimensions_verified'])
        self.assertEqual(w9['port_position_scope'], 'overall')
        self.assertIn('90 x 90 x 29', ' '.join(w9['notes']))

    def test_source_conflict_and_partial_views_remain_explicit(self):
        tube = catalog.get_record('watercool-heatkiller-tube150')
        self.assertIsNone(tube['ports_count'])
        self.assertFalse(tube['ports_geometry_complete'])
        self.assertGreaterEqual(len(tube['sources']), 2)
        self.assertIn('german', ' '.join(tube['notes']).casefold())
        lcd = catalog.get_record('corsair-xd5-rgb-elite-lcd')
        self.assertIsNone(lcd['ports_count'])
        self.assertFalse(lcd['ports_geometry_complete'])
        self.assertTrue(all(not p['role_verified'] for p in lcd['ports']))
        self.assertFalse(catalog.get_record('alphacool-eisbecher-aurora250-apex')['ports_geometry_complete'])

    def test_ports_of_distinct_hardware_do_not_borrow_wrong_topology(self):
        lcd = catalog.get_record('corsair-xc7-rgb-elite-lcd')
        self.assertEqual({p['face'] for p in lcd['ports']}, {'right'})
        pro = catalog.get_record('corsair-xc7-rgb-pro')
        self.assertEqual({p['face'] for p in pro['ports']}, {'top'})
        self.assertTrue(all(p['role_verified'] for p in pro['ports']))
        xd5 = catalog.get_record('corsair-xd5-rgb-gen2')
        self.assertEqual(xd5['ports_count'], 6)
        self.assertNotIn('bottom', {p['face'] for p in xd5['ports']})
        self.assertIn('rear', {p['face'] for p in xd5['ports']})

    def test_barbed_pump_and_large_fill_openings_do_not_turn_into_gquarter(self):
        pump = catalog.get_record('koolance-pmp450')
        self.assertTrue(pump['contains_motor'])
        self.assertEqual(pump['dimensions_mm'], {'width': 88, 'height': 107, 'depth': 90})
        self.assertEqual(len(pump['ports']), 2)
        for port in pump['ports']:
            self.assertIsNone(port['thread'])
            self.assertEqual(port['thread_gender'], 'none')
            self.assertEqual((port['tube_type'], port['tube_inner_mm'], port['tube_outer_mm']),
                             ('soft', 13, 16))
        photon = catalog.get_record('xspc-photon-v4-black')
        self.assertEqual(photon['ports_count'], 4)
        self.assertEqual(sum(p['thread'] == 'G1/4' for p in photon['ports']), 3)
        self.assertEqual(sum(p['thread'] == 'M20' for p in photon['ports']), 1)

    def test_socket_specific_brackets_and_unknown_thread_sizes_stay_conservative(self):
        for identity in ('koolance-cpu-400a', 'koolance-cpu-400a-s', 'phanteks-glacier-c370i'):
            self.assertNotIn('AM5', catalog.get_record(identity)['supported_sockets'])
        self.assertEqual(catalog.get_record('phanteks-glacier-c370i')['supported_sockets'],
                         ['LGA1700', 'LGA1200'])
        xpx = catalog.get_record('alphacool-xpx-pro-aurora-brass')
        self.assertNotIn('LGA4677', xpx['supported_sockets'])
        self.assertIn('corner_argb_windows', xpx['geometry_features'])
        for identity in ('phanteks-glacier-c370i', 'phanteks-glacier-r260c-d5'):
            self.assertTrue(all(p['thread'] is None for p in catalog.get_record(identity)['ports']))
        flat = catalog.get_record('phanteks-glacier-r260c-d5')
        self.assertTrue(flat['contains_motor'])
        self.assertEqual(flat['ports_count'], 7)
        self.assertEqual(sum(p['role'] == 'inlet' for p in flat['ports']), 4)
        self.assertEqual(sum(p['role'] == 'outlet' for p in flat['ports']), 2)

    def test_ultitube_ports_use_actual_body_not_unverified_mounting_frame(self):
        for identity in ('aquacomputer-ultitube-d5-150-pro-next',
                         'aquacomputer-ultitube-d5-150-pro-body', 'aquacomputer-ultitube-d5-50-pro-next'):
            row = catalog.get_record(identity)
            self.assertEqual(row['port_position_scope'], 'body')
            self.assertEqual(row['body_dimensions_mm']['width'], 72)
            self.assertEqual(row['body_dimensions_mm']['depth'], 72)
            self.assertGreater(row['reference_envelope_mm']['width'], 72)
            self.assertTrue(all(not port['position_verified'] for port in row['ports']))
        body = catalog.get_record('aquacomputer-ultitube-d5-150-pro-body')
        short = catalog.get_record('aquacomputer-ultitube-d5-50-pro-next')
        tall = catalog.get_record('aquacomputer-ultitube-d5-150-pro-next')
        self.assertLess(body['ports'][0]['position_normalized'][1], tall['ports'][0]['position_normalized'][1])
        self.assertGreater(short['ports'][0]['position_normalized'][1], tall['ports'][0]['position_normalized'][1])

    def test_flat_reservoir_side_and_top_ports_follow_front_plate_not_rear_motor(self):
        row = catalog.get_record('phanteks-glacier-r260c-d5')
        for port in row['ports']:
            self.assertFalse(port['position_verified'])
            if port['face'] in ('top', 'left'):
                self.assertGreater(port['position_normalized'][2], .3)
            elif port['face'] == 'front':
                self.assertEqual(port['position_normalized'][2], .5)

    def test_no_runtime_sampling_clocks_network_qt_or_photograph_assets(self):
        source = (ROOT / 'liquid_block_pump_expansion046.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(imports, ['copy'])
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))
        forbidden_fields = {'rpm', 'pump_rpm', 'temperature', 'coolant_temperature', 'flow_rate',
                            'sensor_id', 'device_id', 'animation_clock', 'live_reading', 'photo'}
        for row in catalog.records():
            self.assertFalse(forbidden_fields.intersection(row))
            self.assertNotIn('smile', ' '.join(row['geometry_features']).casefold())
        self.assertNotIn('https://images.', source)
        self.assertNotIn('base64', source)


if __name__ == '__main__':
    unittest.main()
