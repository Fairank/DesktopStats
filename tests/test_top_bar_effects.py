"""Opt-in decoration must not invent telemetry or change a selected device."""
import copy
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import native_controller as controls
from stats_config import DEFAULT, validate
from top_bar_config import validate_top_bar
from top_bar_profiles import ICON_EFFECTS, effect_strength
from top_bar_runtime import BarViewState, TopBarManager


class EffectConfigTests(unittest.TestCase):
    def test_legacy_default_is_static_and_round_trip_is_lossless(self):
        legacy = validate_top_bar({'items': [dict(id='b_cpu', metric='cpu_usage', prefs={})]})
        self.assertNotIn('icon_effect', legacy['items'][0]['prefs'])
        self.assertEqual(validate_top_bar(legacy), legacy)
        for effect in ICON_EFFECTS:
            legacy['items'][0]['prefs']['icon_effect'] = effect
            self.assertEqual(validate_top_bar(legacy), legacy)

    def test_unknown_or_structured_effect_is_rejected(self):
        for effect in ('blink', '', True, None, [], {}):
            with self.subTest(effect=effect), self.assertRaises(ValueError):
                validate_top_bar({'items': [dict(id='b_cpu', metric='cpu_usage',
                                               prefs=dict(icon_effect=effect))]})

    def test_strength_is_bounded_and_invalid_data_stays_missing(self):
        self.assertEqual(effect_strength(0, 100), 0)
        self.assertEqual(effect_strength(50, 100), .5)
        self.assertEqual(effect_strength(-20, 100), .2)
        self.assertEqual(effect_strength(200, 100), 1)
        for value in (None, True, '4', float('nan'), float('inf'), 10**1000):
            self.assertIsNone(effect_strength(value, 100))
        for limit in (0, -1, True, None, float('nan'), float('inf'), 10**1000):
            self.assertIsNone(effect_strength(1, limit))


class EffectControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        value = copy.deepcopy(DEFAULT)
        value['top_bar']['items'] = [dict(id='b_test', metric='cpu_temp', prefs={})]
        with patch.object(controls, 'load', return_value=validate(value)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)
        self.ui._data = dict(time=time.time(), cpu_temp=50, net_download=5, net_upload=0)

    def select(self, metric, **prefs):
        item = dict(id='b_test', metric=metric, prefs=dict(icon_effect='auto', **prefs))
        self.ui._saved['top_bar']['items'] = [item]
        return self.ui.topBarRows()[0]

    def test_strength_uses_canonical_units_and_independent_pair_channels(self):
        c = self.select('cpu_temp', temperature_unit='C')
        f = self.select('cpu_temp', temperature_unit='F')
        self.assertNotEqual(c['numeric_value'], f['numeric_value'])
        self.assertEqual(c['effect_level'], f['effect_level'])
        a = self.select('net_download', network_unit='MBps', style='duplex')
        b = self.select('net_download', network_unit='Mbps', style='duplex')
        self.assertEqual(a['effect_level'], b['effect_level'])
        self.assertEqual([row['effect_level'] for row in b['paired_rows']], [.05, 0])
        del self.ui._data['net_upload']
        self.assertIsNone(self.ui.topBarRows()[0]['paired_rows'][1]['effect_level'])

    def test_grouped_gpu_never_borrows_a_different_device_or_quantity(self):
        self.ui._data.update(gpu_usage=99, gpu_temp=100, gpu_power=200, gpus={
            '0': dict(gpu_usage=99, gpu_temp=100, gpu_power=200),
            '1': dict(gpu_usage=0, gpu_temp=50, gpu_power=20),
        })
        row = self.select('gpu_usage', gpu_target='1',
                          metrics=['gpu_usage', 'gpu_temp', 'gpu_power'])
        self.assertEqual(row['group_rows'][0]['effect_level'], 0)
        self.assertEqual(row['group_rows'][1]['effect_level'], .4)
        self.assertNotEqual(row['group_rows'][1]['effect_level'], row['group_rows'][2]['effect_level'])
        del self.ui._data['gpus']['1']
        self.assertTrue(all(member['effect_level'] is None
                            for member in self.ui.topBarRows()[0]['group_rows']))

    def test_missing_and_stale_readings_never_drive_effects(self):
        self.select('cpu_temp')
        self.ui._data['cpu_temp'] = float('nan')
        self.assertIsNone(self.ui.topBarRows()[0]['effect_level'])
        self.ui._data.update(cpu_temp=50, time=time.time()-100)
        self.assertIsNone(self.ui.topBarRows()[0]['effect_level'])

    def test_default_off_does_not_compute_activity_and_draft_does_not_leak(self):
        with patch.object(controls, 'effect_strength', side_effect=AssertionError('off')):
            self.assertEqual(self.ui.topBarRows()[0]['icon_effect'], 'off')
        self.ui.changeTopBarItem('b_test', 'icon_effect', 'heat')
        self.assertEqual(self.ui.topBarDraftRows()[0]['icon_effect'], 'heat')
        self.assertEqual(self.ui.topBarRows()[0]['icon_effect'], 'off')
        before = copy.deepcopy(self.ui._draft)
        self.ui.changeTopBarItem('b_test', 'icon_effect', 'invalid')
        self.assertEqual(self.ui._draft, before)
        with patch.object(controls, 'save'):
            self.assertTrue(self.ui.applyTopBar())
        self.assertEqual(self.ui.topBarRows()[0]['icon_effect'], 'heat')

    def test_reduced_motion_signal_reaches_host_and_default_self_check_is_static(self):
        parent = QObject()
        state = BarViewState(parent, 'self-check')
        self.assertFalse(state.motionEnabled)

        class Policy(QObject):
            motionChanged = Signal()
            motionEnabled = True

        parent.controller = Policy()
        self.assertTrue(state.motionEnabled)
        notifications = []
        state.motionChanged.connect(lambda: notifications.append(state.motionEnabled))
        manager = type('Manager', (), dict(closed=False,
            hosts={'fake': type('Host', (), dict(state=state))()}))()
        parent.controller.motionEnabled = False
        TopBarManager._motion_changed(manager)
        self.assertEqual(notifications, [False])
        manager.closed = True
        TopBarManager._motion_changed(manager)
        self.assertEqual(notifications, [False])

    def test_motion_notify_can_synchronously_close_or_replace_a_host(self):
        parent = QObject()
        states = [BarViewState(parent, str(index)) for index in range(3)]
        hosts = {str(index): type('Host', (), dict(state=state))()
                 for index, state in enumerate(states)}
        manager = type('Manager', (), dict(closed=False, hosts=hosts))()
        emitted = []
        states[0].motionChanged.connect(lambda: manager.hosts.pop('1'))
        states[1].motionChanged.connect(lambda: emitted.append('removed'))
        states[2].motionChanged.connect(lambda: emitted.append('retained'))
        TopBarManager._motion_changed(manager)
        self.assertEqual(emitted, ['retained'])
        states[0].motionChanged.disconnect()
        states[0].motionChanged.connect(lambda: setattr(manager, 'closed', True))
        TopBarManager._motion_changed(manager)
        self.assertEqual(emitted, ['retained'])


if __name__ == '__main__':
    unittest.main()
