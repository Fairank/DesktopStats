"""Real controller rows must carry each chosen device's changing raw activity."""

import copy
import time
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import native_controller as controls
from external_sensor import PROVIDER, SENSOR_TYPES
from stats_config import DEFAULT, validate
from top_bar_feedback import CHANNELS


class TopBarActivityIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Activity integration tests require offscreen QPA")

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        value = copy.deepcopy(DEFAULT)
        value['top_bar']['items'] = [dict(id='b_activity', metric='ram_percent', prefs={})]
        with patch.object(controls, 'load', return_value=validate(value)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)
        self.ui._data = dict(time=time.time())

    def select(self, metric, **prefs):
        item = dict(id='b_activity', metric=metric, prefs={'icon_effect': 'auto'} | prefs)
        self.ui._saved['top_bar']['items'] = [item]
        return self.ui.topBarRows()[0]

    def test_live_cpu_and_memory_ramps_reach_the_view_without_rounding(self):
        for metric in ('cpu_usage', 'ram_percent'):
            observed = []
            for value in (1.25, 35.5, 89.75):
                self.ui._data[metric] = value
                row = self.select(metric, precision='0')
                self.assertTrue(row['available'])
                self.assertEqual(row['numeric_value'], value)
                observed.append(row['effect_level'])
            self.assertEqual(observed, [.0125, .355, .8975])

    def test_heat_power_and_fan_ramps_use_their_own_quantity_scale(self):
        examples = (
            ('cpu_temp', (25, 62.5, 112.5), (.2, .5, .9)),
            ('cpu_power', (4, 50, 160), (.02, .25, .8)),
            ('cpu_fan_rpm', (1200, 6000, 10800), (.1, .5, .9)),
            ('cpu_frequency', (.8, 4, 7.2), (.1, .5, .9)),
        )
        for metric, values, expected in examples:
            observed = []
            for value in values:
                self.ui._data[metric] = value
                row = self.select(metric)
                observed.append(row['effect_level'])
                self.assertEqual(row['numeric_value'], value)
            self.assertEqual(observed, list(expected), metric)
        self.ui._data['cpu_temp'] = 62.5
        c = self.select('cpu_temp', temperature_unit='C')
        f = self.select('cpu_temp', temperature_unit='F')
        self.assertNotEqual(c['numeric_value'], f['numeric_value'])
        self.assertEqual(c['effect_level'], f['effect_level'])

    def test_duplex_updates_independently_on_the_selected_adapter(self):
        self.ui._data.update(net_download=99, net_upload=99, networks={
            'unused': dict(label='Other', net_download=99, net_upload=99),
            'selected': dict(label='Chosen', net_download=.001, net_upload=70),
        })
        first = self.select('net_download', network_target='selected', style='duplex', precision='2')
        self.assertGreater(first['paired_rows'][0]['effect_level'], 0)
        self.assertEqual(first['paired_rows'][0]['numeric_value'], .001)
        self.assertEqual(first['paired_rows'][1]['effect_level'], .7)
        self.ui._data['networks']['selected'].update(net_download=60, net_upload=0)
        second = self.ui.topBarRows()[0]
        self.assertEqual([row['effect_level'] for row in second['paired_rows']], [.6, 0])
        converted = self.select('net_download', network_target='selected', style='duplex', network_unit='Mbps')
        self.assertNotEqual(second['numeric_value'], converted['numeric_value'])
        self.assertEqual([row['effect_level'] for row in second['paired_rows']],
                         [row['effect_level'] for row in converted['paired_rows']])
        del self.ui._data['networks']['selected']
        self.assertTrue(all(row['effect_level'] is None for row in self.ui.topBarRows()[0]['paired_rows']))

    def test_group_members_keep_separate_activity_and_device_identity(self):
        self.ui._data['gpus'] = {
            'other': dict(label='Other', gpu_usage=99, gpu_temp=120, gpu_power=290),
            'chosen': dict(label='Chosen', gpu_usage=10, gpu_temp=62.5, gpu_power=240),
        }
        first = self.select('gpu_usage', gpu_target='chosen',
                            metrics=['gpu_usage', 'gpu_temp', 'gpu_power'])
        self.assertEqual([row['effect_level'] for row in first['group_rows']], [.1, .5, .8])
        self.ui._data['gpus']['chosen'].update(gpu_usage=85, gpu_temp=25, gpu_power=30)
        second = self.ui.topBarRows()[0]
        self.assertEqual([row['effect_level'] for row in second['group_rows']], [.85, .2, .1])
        self.assertEqual(first['id'], second['id'])

    def test_missing_stale_zero_and_recovery_have_distinct_activity(self):
        self.ui._data['ram_percent'] = 80
        self.assertEqual(self.select('ram_percent')['effect_level'], .8)
        for value, expected in ((0, 0), (None, None), (float('nan'), None), (60, .6)):
            self.ui._data['ram_percent'] = value
            self.assertEqual(self.ui.topBarRows()[0]['effect_level'], expected)
        self.ui._data['time'] = time.time() - 100
        self.assertIsNone(self.ui.topBarRows()[0]['effect_level'])
        self.ui._data['time'] = time.time()
        self.assertEqual(self.ui.topBarRows()[0]['effect_level'], .6)
        self.assertEqual(self.select('ram_percent', icon_effect='off')['icon_effect'], 'off')
        self.assertIsNone(self.ui.topBarRows()[0]['effect_level'])

    def test_processor_layers_remain_real_when_the_primary_is_zero_or_missing(self):
        self.ui._data.update(cpu_usage=0, cpu_temp=100, cpu_power=160)
        first = self.select('cpu_usage')
        self.assertEqual(first['hardware_state']['profile'], 'processor')
        self.assertEqual([first['hardware_state'][key] for key in ('load', 'thermal', 'energy')],
                         [0, .8, .8])
        del self.ui._data['cpu_usage']
        second = self.ui.topBarRows()[0]
        self.assertFalse(second['available'])
        self.assertTrue(second['hardware_state']['available'])
        self.assertIsNone(second['hardware_state']['load'])
        self.assertEqual(second['hardware_state']['thermal'], .8)
        self.assertEqual(second['hardware_state']['energy'], .8)
        converted = self.select('cpu_usage', temperature_unit='F', precision='0')
        self.assertEqual(second['hardware_state'], converted['hardware_state'])

    def test_ten_processor_states_are_not_quantized_and_raw_numbers_stay_exact(self):
        states = []
        for index in range(10):
            fraction = (index + .5) / 10
            self.ui._data.update(cpu_usage=100*fraction, cpu_temp=125*fraction,
                                 cpu_power=200*fraction)
            row = self.select('cpu_usage')
            self.assertEqual(row['numeric_value'], 100*fraction)
            self.assertAlmostEqual(row['hardware_state']['load'], fraction)
            self.assertAlmostEqual(row['hardware_state']['thermal'], fraction)
            self.assertAlmostEqual(row['hardware_state']['energy'], fraction)
            states.append(row['hardware_state']['load'])
        self.assertEqual(len(set(states)), 10)
        self.ui._data['cpu_usage'] = 37.12345
        self.assertAlmostEqual(self.ui.topBarRows()[0]['hardware_state']['load'], .3712345, places=12)

    def test_gpu_layers_never_borrow_the_default_adapter_or_asic_sensor(self):
        self.ui._data.update(gpu_usage=99, gpu_temp=120, gpu_power=290, gpu_asic_power=299,
                            gpus={'chosen': dict(gpu_usage=None, gpu_temp=50, gpu_power=60)})
        row = self.select('gpu_usage', gpu_target='chosen')
        self.assertFalse(row['available'])
        state = row['hardware_state']
        self.assertTrue(state['available'])
        self.assertEqual([state[key] for key in ('load', 'thermal', 'energy')], [None, .4, .2])
        del self.ui._data['gpus']['chosen']
        missing = self.ui.topBarRows()[0]['hardware_state']
        self.assertFalse(missing['available'])
        self.assertTrue(all(missing[key] is None for key in CHANNELS))
        self.assertEqual(self.select('gpu_asic_power')['hardware_state'], {})

    def test_memory_and_fan_do_not_invent_temperature_or_power(self):
        self.ui._data.update(ram_percent=72, cpu_temp=110, cpu_power=180, cpu_fan_rpm=6000)
        memory = self.select('ram_percent')['hardware_state']
        self.assertEqual((memory['profile'], memory['load']), ('memory', .72))
        self.assertIsNone(memory['thermal'])
        self.assertIsNone(memory['energy'])
        fan = self.select('cpu_fan_rpm')['hardware_state']
        self.assertEqual((fan['profile'], fan['spin']), ('fan', .5))
        self.assertIsNone(fan['thermal'])
        self.ui._data['gpus'] = {'chosen': dict(vram_gb=4, vram_total_gb=8,
                                              gpu_temp=110, gpu_power=270)}
        vram = self.select('vram_gb', gpu_target='chosen')['hardware_state']
        self.assertEqual((vram['profile'], vram['load']), ('memory', .5))
        self.assertIsNone(vram['thermal'])
        self.assertIsNone(vram['energy'])

    def test_network_disk_and_battery_preserve_each_real_direction(self):
        self.ui._data.update(net_download=99, net_upload=99,
                            networks={'chosen': dict(net_download=20, net_upload=70)},
                            disks={'chosen': dict(disk_read=125, disk_write=400)},
                            battery_percent=80, battery_charge_watts=30, battery_discharge_watts=0)
        network = self.select('net_download', network_target='chosen', style='duplex')['hardware_state']
        self.assertEqual((network['profile'], network['inbound'], network['outbound']),
                         ('network', .2, .7))
        disk = self.select('disk_read', disk_target='chosen')['hardware_state']
        self.assertEqual((disk['profile'], disk['inbound'], disk['outbound']), ('disk', .25, .8))
        battery = self.select('battery_percent')['hardware_state']
        self.assertEqual((battery['profile'], battery['load'], battery['inbound'], battery['outbound']),
                         ('battery', .8, .3, 0))
        self.ui._data.update(battery_charge_watts=None, battery_discharge_watts=25)
        changed = self.ui.topBarRows()[0]['hardware_state']
        self.assertIsNone(changed['inbound'])
        self.assertEqual(changed['outbound'], .25)

    def test_storage_health_is_not_a_capacity_or_unrelated_io_gauge(self):
        self.ui._data.update(disk_read=500, disk_write=500, disk_percent=99,
                            volumes={'chosen': dict(disk_percent=40)},
                            storages={'chosen': dict(storage_temp=65, storage_wear_percent=90)})
        volume = self.select('disk_percent', volume_target='chosen')['hardware_state']
        self.assertEqual((volume['profile'], volume['load']), ('volume', .4))
        storage = self.select('storage_wear_percent', storage_target='chosen')['hardware_state']
        self.assertEqual((storage['profile'], storage['thermal']), ('storage', .65))
        self.assertIsNone(storage['load'])
        self.assertIsNone(storage['inbound'])
        self.assertIsNone(storage['outbound'])

    def test_battery_power_glyph_uses_its_own_quantity_not_the_charge_level(self):
        self.ui._data.update(battery_percent=90, battery_charge_watts=20,
                             battery_discharge_watts=None, battery_watts=-30)
        charge = self.select('battery_charge_watts')
        self.assertEqual(charge['icon'], 'power')
        self.assertEqual(charge['hardware_state']['energy'], .2)
        discharge = self.select('battery_discharge_watts')
        self.assertEqual(discharge['icon'], 'power')
        self.assertIsNone(discharge['hardware_state']['energy'])
        signed = self.select('battery_watts')
        self.assertEqual(signed['hardware_state']['energy'], .3)
        self.assertEqual(signed['hardware_state']['inbound'], .2)
        self.assertIsNone(signed['hardware_state']['outbound'])

    def test_frequency_only_devices_keep_their_own_scalar_response(self):
        self.ui._data.update(cpu_frequency=4, gpus={'chosen': dict(gpu_clock=2000,
                                                                 gpu_memory_clock=6000)})
        for metric, prefs, expected in (
            ('cpu_frequency', {}, .5),
            ('gpu_clock', {'gpu_target': 'chosen'}, .5),
            ('gpu_memory_clock', {'gpu_target': 'chosen'}, .5),
        ):
            row = self.select(metric, **prefs)
            self.assertEqual(row['icon'], 'frequency')
            self.assertTrue(row['available'])
            self.assertEqual(row['effect_level'], expected)
            self.assertEqual(row['hardware_state'], {})

    def test_external_sensor_types_route_without_guessing_a_name_or_device(self):
        expected = {
            'Temperature': ('temperature', 'heat'), 'Fan': ('fan', 'spin'),
            'Voltage': ('voltage', 'flow'), 'Current': ('voltage', 'flow'),
            'Power': ('power', 'flow'), 'Clock': ('frequency', 'pulse'),
            'Load': ('grid', 'pulse'), 'Level': ('grid', 'pulse'),
            'Throughput': ('sensors', 'pulse'),
        }
        for kind, meta in SENSOR_TYPES.items():
            binding = dict(provider=PROVIDER, sensor_id='/chosen/exact/channel',
                           sensor_type=kind, name='CPU Fan Power Temperature Download',
                           hardware_name='Unclassified hardware')
            self.ui._data['external_sensors'] = {
                binding['sensor_id']: dict(id=binding['sensor_id'], type=kind,
                                           unit=meta['unit'], value=meta['maximum']*.5,
                                           available=True),
            }
            row = self.select('external_1', sensor_bindings={'external_1': binding})
            self.assertEqual((row['icon'], row['auto_effect']),
                             expected.get(kind, ('sensors', 'off')), kind)
            self.assertEqual(row['effect_level'], .5)
            self.assertTrue(row['available'])
            self.assertEqual(row['hardware_state'], {})
            self.ui._data['external_sensors'][binding['sensor_id']]['type'] = 'invalid'
            invalid = self.ui.topBarRows()[0]
            self.assertFalse(invalid['available'])
            self.assertIsNone(invalid['effect_level'])

    def test_cold_and_invalid_negative_activity_do_not_fabricate_heat_or_rotation(self):
        self.ui._data.update(cpu_temp=-10, cpu_fan_rpm=-500, cpu_usage=-3,
                             cpu_frequency=-1, cpu_power=-20, battery_watts=-30)
        cold = self.select('cpu_temp', temperature_unit='F')
        self.assertEqual(cold['effect_level'], 0)
        for metric in ('cpu_fan_rpm', 'cpu_usage', 'cpu_frequency', 'cpu_power'):
            row = self.select(metric)
            self.assertIsNone(row['effect_level'], metric)
            state = row['hardware_state']
            self.assertFalse(state and any(state.get(key, 0) and state[key] > 0 for key in CHANNELS))
        self.assertEqual(self.select('battery_watts')['effect_level'], .3)

    def test_auto_channels_stop_on_stale_and_manual_modes_stay_independent(self):
        self.ui._data.update(cpu_usage=0, cpu_temp=0, cpu_power=0)
        zero = self.select('cpu_usage')['hardware_state']
        self.assertTrue(zero['available'])
        self.assertEqual([zero[key] for key in ('load', 'thermal', 'energy')], [0, 0, 0])
        self.ui._data['time'] = time.time() - 100
        stale = self.ui.topBarRows()[0]['hardware_state']
        self.assertFalse(stale['available'])
        self.assertTrue(all(stale[key] is None for key in CHANNELS))
        self.ui._data['time'] = time.time()
        for effect in ('off', 'pulse', 'heat', 'flow', 'spin'):
            self.assertEqual(self.select('cpu_usage', icon_effect=effect)['hardware_state'], {})


if __name__ == '__main__':
    unittest.main()
