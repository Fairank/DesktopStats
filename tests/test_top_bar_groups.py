"""Grouped readouts keep one device, transaction and physical hit region."""
import copy
import time
import unittest
from unittest.mock import patch

import test_top_bar_runtime as runtime_fixture
from PySide6.QtWidgets import QApplication

import native_controller as controls
from stats_config import DEFAULT, validate
from top_bar_config import validate_top_bar
from top_bar_layout import DISPLAY_STYLES, PixelRect


def grouped(metric='cpu_usage', metrics=None, **prefs):
    return dict(id='b_group', metric=metric,
                prefs=dict(style='icon_value', placement='right', sensor_bindings={},
                           metrics=metrics or [metric, 'cpu_temp', 'cpu_power'], **prefs))


class GroupConfigTests(unittest.TestCase):
    def config(self, item):
        value = copy.deepcopy(DEFAULT)
        value['top_bar']['items'] = [item]
        return value

    def test_group_round_trip_keeps_primary_order_and_device(self):
        source = self.config(grouped('gpu_usage', ['gpu_usage', 'gpu_power', 'gpu_temp'],
                                     gpu_target='1', temperature_unit='F'))
        before = copy.deepcopy(source)
        result = validate(source)
        self.assertEqual(result['top_bar']['items'], before['top_bar']['items'])
        self.assertEqual(validate(result), result)
        self.assertEqual(source, before)

    def test_invalid_group_never_silently_changes_primary_or_hardware(self):
        for selection in ([], ['cpu_temp', 'cpu_usage'], ['cpu_usage', 'gpu_temp'],
                          ['cpu_usage', 'cpu_usage'], ['cpu_usage', 'external_1'],
                          ['cpu_usage', 'cpu_temp', 'cpu_power', 'cpu_cores', 'cpu_threads'],
                          'cpu_usage', ['cpu_usage', 1], ['cpu_usage', ['cpu_temp']]):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                value = self.config(grouped())
                value['top_bar']['items'][0]['prefs']['metrics'] = selection
                validate(value)
        with self.assertRaises(ValueError):
            validate(self.config(grouped('net_download', ['net_download', 'net_upload'])))

    def test_mixed_units_cannot_be_misrepresented_as_gauges(self):
        for style in ('bar_value', 'ring_value', 'duplex', 'duplex_inline'):
            with self.subTest(style=style), self.assertRaises(ValueError):
                value = self.config(grouped())
                value['top_bar']['items'][0]['prefs']['style'] = style
                validate(value)

    def test_legacy_single_items_keep_all_existing_styles_and_no_group_field(self):
        for style in DISPLAY_STYLES:
            metric = 'net_download' if style in ('duplex', 'duplex_inline') else 'cpu_usage'
            value = dict(items=[dict(id='b_single', metric=metric, prefs=dict(style=style))])
            item = validate_top_bar(value)['items'][0]
            self.assertEqual(item['prefs']['style'], style)
            self.assertNotIn('metrics', item['prefs'])


class GroupControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        value = copy.deepcopy(DEFAULT)
        value['top_bar']['items'] = [grouped()]
        with patch.object(controls, 'load', return_value=validate(value)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)
        self.ui._data = dict(time=time.time(), cpu_usage=0, cpu_temp=50, cpu_power=12.5)

    def test_grouped_zero_units_icons_and_missing_values_are_independent(self):
        row = self.ui.topBarRows()[0]
        self.assertTrue(row['grouped'])
        self.assertEqual([child['metric'] for child in row['group_rows']],
                         ['cpu_usage', 'cpu_temp', 'cpu_power'])
        self.assertEqual([child['value'] for child in row['group_rows']], ['0 %', '50 °C', '12.5 W'])
        self.assertEqual([child['icon'] for child in row['group_rows']], ['cpu', 'temperature', 'power'])
        self.assertEqual(row['value'], '0 %')
        self.assertTrue(all('group_rows' not in child for child in row['group_rows']))
        self.ui._data.pop('cpu_temp')
        row = self.ui.topBarRows()[0]
        self.assertEqual(row['group_rows'][1]['value'], '—')
        self.assertFalse(row['group_rows'][1]['available'])
        self.assertTrue(row['group_rows'][0]['available'])
        self.assertIn('12.5 W', row['group_value'])

    def test_gpu_group_never_borrows_another_gpu_and_applies_temperature_unit(self):
        item = grouped('gpu_usage', ['gpu_usage', 'gpu_power', 'gpu_temp'],
                       gpu_target='1', temperature_unit='F')
        self.ui._saved['top_bar']['items'] = [item]
        self.ui._data.update(gpu_usage=99, gpu_power=999, gpu_temp=99, gpus={
            '0': dict(label='GPU zero', gpu_usage=90, gpu_power=80, gpu_temp=70),
            '1': dict(label='GPU one', gpu_usage=0, gpu_power=20, gpu_temp=50),
        })
        row = self.ui.topBarRows()[0]
        self.assertEqual([child['value'] for child in row['group_rows']], ['0 %', '20.0 W', '122 °F'])
        self.assertTrue(all(child['hardware_name'] == 'GPU one' for child in row['group_rows']))
        del self.ui._data['gpus']['1']
        self.assertTrue(all(child['value'] == '—' for child in self.ui.topBarRows()[0]['group_rows']))

    def test_stale_frame_never_leaves_live_group_members(self):
        self.ui._data['time'] = time.time()-100
        row = self.ui.topBarRows()[0]
        self.assertFalse(row['group_available'])
        self.assertTrue(all(child['value'] == '—' for child in row['group_rows']))

    def test_selected_group_style_previews_have_real_histories_without_charging_all_rows(self):
        for index in range(3):
            self.ui._history.append(dict(time=time.time()-3+index, cpu_usage=index,
                                         cpu_temp=50+index, cpu_power=10+index))
        self.assertTrue(all(child['history'] == [] for child in self.ui.topBarRows()[0]['group_rows']))
        row = self.ui.topBarStylePreviewRow('b_group')
        self.assertEqual([child['history'] for child in row['group_rows']],
                         [[0, 1, 2], [50, 51, 52], [10, 11, 12]])
        self.assertTrue(all(child['trend_available'] for child in row['group_rows']))

    def test_edit_is_atomic_undoable_and_rejects_invalid_members(self):
        before = copy.deepcopy(self.ui._draft)
        self.assertFalse(self.ui.setTopBarGroupMetrics('b_group', ['cpu_usage', 'gpu_temp']))
        self.assertEqual(self.ui._draft, before)
        self.assertTrue(self.ui.setTopBarGroupMetrics('b_group', ['cpu_usage', 'cpu_power', 'cpu_temp']))
        self.assertEqual(self.ui._draft['top_bar']['items'][0]['prefs']['metrics'],
                         ['cpu_usage', 'cpu_power', 'cpu_temp'])
        self.ui.undoDraft()
        self.assertEqual(self.ui._draft, before)
        self.ui.redoDraft()
        self.assertEqual(self.ui._draft['top_bar']['items'][0]['prefs']['metrics'][1], 'cpu_power')

    def test_reapplying_group_preset_is_success_without_an_undo_step(self):
        before = copy.deepcopy(self.ui._draft)
        self.assertTrue(self.ui.setTopBarGroupMetrics('b_group', ['cpu_usage', 'cpu_temp', 'cpu_power']))
        self.assertEqual(self.ui._draft, before)
        self.assertFalse(self.ui.undoDraft())

    def test_first_group_edit_converts_incompatible_gauge_and_can_return_to_single(self):
        self.ui._draft['top_bar']['items'][0]['prefs'] = dict(style='ring_value', sensor_bindings={})
        self.assertTrue(self.ui.setTopBarGroupMetrics('b_group', ['cpu_usage', 'cpu_temp']))
        self.assertEqual(self.ui._draft['top_bar']['items'][0]['prefs']['style'], 'icon_value')
        self.assertTrue(self.ui.setTopBarGroupMetrics('b_group', ['cpu_usage']))
        self.assertNotIn('metrics', self.ui._draft['top_bar']['items'][0]['prefs'])
        self.assertFalse(self.ui.topBarDraftRows()[0]['grouped'])

    def test_failed_save_keeps_applied_group_and_pending_preferences(self):
        old = copy.deepcopy(self.ui._saved)
        self.ui.change('refresh', .1)
        self.ui.setTopBarGroupMetrics('b_group', ['cpu_usage', 'cpu_temp'])
        draft = copy.deepcopy(self.ui._draft)
        with patch.object(controls, 'save', side_effect=OSError(13, 'synthetic read-only')):
            self.assertFalse(self.ui.applyTopBar())
        self.assertEqual(self.ui._saved, old)
        self.assertEqual(self.ui._draft, draft)

    def test_live_drag_commits_one_group_preserving_members_and_preference_draft(self):
        self.ui._saved['top_bar']['items'].append(dict(id='b_peer', metric='ram_percent',
            prefs=dict(style='value', placement='right', sensor_bindings={})))
        self.ui._draft = copy.deepcopy(self.ui._saved)
        self.ui.change('refresh', .1)
        with patch.object(controls, 'save') as save:
            self.assertTrue(self.ui.placeLiveTopBarMetric('b_group', '', 'left'))
        self.assertEqual(save.call_count, 1)
        item = next(item for item in self.ui._saved['top_bar']['items'] if item['id'] == 'b_group')
        self.assertEqual(item['prefs']['metrics'], ['cpu_usage', 'cpu_temp', 'cpu_power'])
        self.assertEqual(self.ui._draft['refresh'], .1)
        self.assertNotEqual(self.ui._saved['refresh'], .1)

    def test_runtime_group_is_one_measured_hit_region_and_overflows_whole(self):
        fixture = runtime_fixture.TopBarRuntimeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        row = self.ui.topBarRows()[0]
        fixture.controller.rows = [row]
        settings = runtime_fixture.config()
        settings['top_bar']['items'] = [copy.deepcopy(self.ui._saved['top_bar']['items'][0])]
        fixture.manager.apply(settings)
        host = fixture.manager.hosts['DISPLAY1']
        self.assertEqual([item.id for item in host.geometry.items], ['b_group'])
        width = host.geometry.items[0].rect.width
        self.assertGreater(width, 150)
        self.assertEqual([item['id'] for item in host.state._rows], ['b_group'])
        fixture.a.physical = PixelRect(0, 0, 140, 1080)
        fixture.manager.apply(settings)
        host = fixture.manager.hosts['DISPLAY1']
        self.assertEqual(host.geometry.overflow_ids, ('b_group',))
        self.assertEqual(host.geometry.items, ())


if __name__ == '__main__':
    unittest.main()
