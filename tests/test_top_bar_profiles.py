"""Module identity and paired readouts, without live collectors or native windows."""
import copy
import time
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import native_controller as controls
from metrics import METRICS
from stats_config import DEFAULT
from top_bar_config import validate_top_bar
from top_bar_profiles import can_gauge, detail_profile, paired_channels


class ModulePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(controls, 'load', return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.ui._data = dict(time=time.time())

    def tearDown(self):
        self.ui.close()
        self.ui.deleteLater()

    def select(self, metric, **prefs):
        self.ui._saved['top_bar']['items'] = [dict(id='b_pair', metric=metric, prefs=prefs)]
        self.ui._draft = copy.deepcopy(self.ui._saved)
        return self.ui.topBarDetailRow('b_pair')

    def test_every_fixed_reading_has_a_hardware_profile(self):
        for key in METRICS:
            if not key.startswith('external_'):
                self.assertNotEqual(detail_profile(key)[0], 'external', key)
        self.assertEqual(detail_profile('external_1')[2], ())

    def test_network_pair_preserves_selected_device_zero_and_units(self):
        self.ui._data.update(net_download=999, net_upload=999, networks={
            'wifi': dict(label='Wi-Fi', net_download=1.25, net_upload=0)})
        row = self.select('net_upload', style='duplex', network_target='wifi', network_unit='Mbps', precision='1')
        self.assertEqual([v['metric'] for v in row['paired_rows']], ['net_download', 'net_upload'])
        self.assertEqual([v['value'] for v in row['paired_rows']], ['10.0 Mbps', '0.0 Mbps'])
        self.assertTrue(all(v['available'] for v in row['paired_rows']))
        self.assertEqual(row['hardware_name'], 'Wi-Fi')

    def test_absent_direction_is_unavailable_not_zero(self):
        self.ui._data.update(networks={'wifi': dict(net_download=2)})
        row = self.select('net_download', style='duplex', network_target='wifi')
        self.assertTrue(row['paired_rows'][0]['available'])
        self.assertEqual(row['paired_rows'][1]['number_text'], '—')
        self.assertFalse(row['paired_rows'][1]['available'])
        self.assertIn('↓ 2.00 MB/s', row['value'])
        self.assertIn('↑ —', row['value'])

    def test_pair_retains_both_histories_in_display_units_and_breaks_gaps(self):
        for sample in (dict(net_download=1, net_upload=2), dict(net_download=3),
                       dict(net_download=4, net_upload=0)):
            self.ui._history.append(dict(time=time.time(), networks={'wifi': sample}))
        self.ui._data['networks'] = {'wifi': dict(net_download=4, net_upload=0)}
        row = self.select('net_download', style='duplex', network_target='wifi', network_unit='Mbps')
        down, up = row['paired_rows']
        self.assertEqual(down['trend'], [8, 24, 32])
        self.assertEqual(up['trend'], [16, None, 0])
        self.assertIsNone(up['trend_points'][1])
        self.assertEqual(down['trend_maximum'], up['trend_maximum'])
        self.assertEqual(down['trend_minimum'], 0)
        self.assertEqual(down['trend_points'][-1]['y'], 0)
        self.assertEqual(up['trend_points'][-1]['y'], 1)

    def test_real_timestamp_spacing_is_not_inferred_from_refresh_setting(self):
        stamp = time.time()-4
        for offset, value in ((0, 1), (1, 2), (4, 3)):
            self.ui._history.append(dict(time=stamp+offset, net_download=value, net_upload=value))
        self.ui._data.update(net_download=3, net_upload=3)
        row = self.select('net_download', style='duplex')
        self.assertEqual(row['history_elapsed_s'], 4)
        self.assertEqual([p['x'] for p in row['trend_points']], [0, .25, 1])
        self.assertEqual([p['x'] for p in row['paired_rows'][0]['trend_points']], [0, .25, 1])
        self.ui._history[1]['time'] = stamp-1
        row = self.select('net_download')
        self.assertIsNone(row['history_elapsed_s'])
        self.assertEqual(row['history_axis'], 'samples')

    def test_equal_and_missing_timestamps_do_not_invent_a_time_window(self):
        for stamp in (time.time(), None):
            self.ui._history.clear()
            self.ui._history.extend([dict(time=stamp, cpu_usage=10)]*3)
            self.ui._data.update(cpu_usage=10)
            row = self.select('cpu_usage')
            self.assertIsNone(row['history_elapsed_s'])
            self.assertEqual(row['history_min'], 10)
            self.assertEqual(row['history_mean'], 10)

    def test_disconnected_pair_never_substitutes_other_interface(self):
        self.ui._data.update(net_download=30, net_upload=20,
                             networks={'other': dict(net_download=30, net_upload=20)})
        row = self.select('net_download', network_target='removed', style='duplex')
        self.assertFalse(any(v['available'] for v in row['paired_rows']))

    def test_stale_pair_and_capacity_stay_unavailable(self):
        self.ui._data.update(time=time.time()-60, net_download=2, net_upload=1,
                             ram_used_gb=20, ram_total_gb=32)
        self.assertFalse(any(v['available'] for v in self.select('net_download')['paired_rows']))
        self.assertEqual(self.select('ram_percent')['capacity_summary'], {})

    def test_disk_io_and_volume_details_do_not_mix_targets(self):
        self.ui._data.update(disks={'1': dict(disk_read=12, disk_write=3)},
                             volumes={'C:': dict(disk_percent=40, disk_used_gb=40,
                                                 disk_free_gb=60, disk_total_gb=100)})
        row = self.select('disk_read', disk_target='1', style='duplex')
        self.assertEqual([r['metric'] for r in row['related']], ['disk_write'])
        self.assertEqual(row['capacity_summary'], {})
        row = self.select('disk_percent', volume_target='C:')
        self.assertEqual(row['capacity_summary']['fraction'], .4)
        self.assertEqual({r['metric'] for r in row['related']},
                         {'disk_used_gb', 'disk_free_gb', 'disk_total_gb'})

    def test_gpu_related_and_capacity_use_the_selected_gpu(self):
        self.ui._data.update(gpus={
            '0': dict(gpu_usage=99, gpu_power=300, vram_gb=16, vram_total_gb=24),
            '1': dict(label='Second GPU', gpu_usage=20, gpu_power=9, vram_gb=2, vram_total_gb=8)})
        row = self.select('gpu_usage', gpu_target='1')
        self.assertEqual(row['capacity_summary']['fraction'], .25)
        power = next(r for r in row['related'] if r['metric'] == 'gpu_power')
        self.assertEqual(power['value'], '9.0 W')
        self.assertNotIn('cpu_power', [r['metric'] for r in row['related']])

    def test_memory_capacity_never_calls_occupancy_pressure(self):
        self.ui._data.update(ram_percent=50, ram_used_gb=16, ram_total_gb=32)
        row = self.select('ram_percent')
        self.assertEqual(row['capacity_summary']['fraction'], .5)
        self.assertNotIn('压力', row['label'])
        self.ui._data['ram_total_gb'] = 0
        self.assertEqual(self.select('ram_percent')['capacity_summary'], {})

    def test_battery_pair_is_battery_side_without_fabricated_adapter_input(self):
        self.ui._data.update(battery_charge_watts=0, battery_discharge_watts=0)
        row = self.select('battery_discharge_watts', style='duplex')
        self.assertTrue(all(r['available'] for r in row['paired_rows']))
        self.assertNotIn('adapter_input_watts', [r['metric'] for r in row['related']])

    def test_duplex_schema_roundtrip_and_rejects_unpaired_metrics(self):
        for metric in ('net_download', 'net_upload', 'disk_read', 'disk_write',
                       'battery_charge_watts', 'battery_discharge_watts'):
            bar = copy.deepcopy(DEFAULT['top_bar'])
            for style in ('duplex', 'duplex_inline'):
                bar['items'] = [dict(id='b_pair', metric=metric, prefs=dict(style=style))]
                normalized = validate_top_bar(bar)
                self.assertEqual(validate_top_bar(normalized), normalized)
                self.assertTrue(paired_channels(metric))
        bar['items'][0]['metric'] = 'cpu_usage'
        with self.assertRaises(ValueError):
            validate_top_bar(bar)

    def test_unbounded_lifetime_is_not_an_occupancy_gauge(self):
        self.assertTrue(can_gauge(METRICS['ram_percent']))
        self.assertFalse(can_gauge(METRICS['storage_wear_percent']))
        self.assertFalse(can_gauge(METRICS['cpu_fan_rpm']))
        self.ui._data['storages'] = {'0': dict(storage_wear_percent=40)}
        row = self.select('storage_wear_percent', style='ring_value')
        self.assertFalse(row['gauge_available'])
        self.assertEqual(row['value'], '40 %')


if __name__ == '__main__':
    unittest.main()
