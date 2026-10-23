"""Whole-bar treatments and effect sliders preserve material and draft ownership."""
import copy
import time
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import native_controller as controls
from stats_config import DEFAULT, validate
from top_bar_config import BAR_DESIGNS, top_bar_style, validate_top_bar


class DesignConfigTests(unittest.TestCase):
    def test_legacy_is_classic_without_adding_effect_preferences(self):
        old = copy.deepcopy(DEFAULT)
        old['top_bar']['appearance'].pop('design', None)
        value = validate(old)
        self.assertEqual(value['top_bar']['appearance']['design'], 'classic')
        self.assertNotIn('effect_intensity', value['top_bar']['items'][0]['prefs'])
        self.assertNotIn('effect_speed', value['top_bar']['items'][0]['prefs'])
        self.assertEqual(validate(value), value)

    def test_treatment_is_independent_of_material_inheritance(self):
        for follow in (True, False):
            for design in BAR_DESIGNS:
                value = copy.deepcopy(DEFAULT)
                value['skin'], value['glass_transparency'] = 'tint', 61.125
                value['top_bar']['appearance'].update(
                    follow_global=follow, skin='graphite', glass_transparency=12.375,
                    design=design)
                before = copy.deepcopy(value)
                style = top_bar_style(validate(value))
                self.assertEqual(style['bar_design'], design)
                self.assertEqual(style['skin'], 'tint' if follow else 'graphite')
                self.assertEqual(style['glass_transparency'], 61.125 if follow else 12.375)
                self.assertEqual(value, before)

    def test_bad_design_and_nonfinite_or_structured_effect_values_rejected(self):
        for selected in ('', 'liquid', None, True, [], {}):
            value = copy.deepcopy(DEFAULT['top_bar'])
            value['appearance']['design'] = selected
            with self.subTest(design=selected), self.assertRaises(ValueError):
                validate_top_bar(value)
        for field, values in (
            ('effect_intensity', (-.001, 1.001)),
            ('effect_speed', (.499, 2.001)),
        ):
            for selected in (*values, True, None, '1', [], {}, float('nan'),
                             float('inf'), -float('inf'), 10**5000):
                value = copy.deepcopy(DEFAULT['top_bar'])
                value['items'][0]['prefs'][field] = selected
                with self.subTest(field=field, kind=type(selected)), self.assertRaises(ValueError):
                    validate_top_bar(value)

    def test_fractional_effect_settings_roundtrip_at_boundaries(self):
        for intensity in (0, .125, .5, 1):
            for speed in (.5, .875, 1, 2):
                value = copy.deepcopy(DEFAULT['top_bar'])
                value['items'][0]['prefs'].update(effect_intensity=intensity, effect_speed=speed)
                normalized = validate_top_bar(value)
                self.assertEqual(validate_top_bar(normalized), normalized)
                self.assertEqual(normalized['items'][0]['prefs']['effect_intensity'], intensity)
                self.assertEqual(normalized['items'][0]['prefs']['effect_speed'], speed)


class DesignControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(controls, 'load', return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)
        self.identifier = self.ui._draft['top_bar']['items'][0]['id']

    def test_design_only_edit_undo_and_branch_apply_preserve_other_pending_inputs(self):
        self.ui.change('glass_transparency', 31.125)
        desktop = copy.deepcopy(self.ui._draft)
        self.ui.changeTopBarAppearance('design', 'capsule')
        appearance = self.ui._draft['top_bar']['appearance']
        self.assertTrue(appearance['follow_global'])
        self.assertEqual(appearance['design'], 'capsule')
        self.assertEqual(self.ui._saved['top_bar']['appearance']['design'], 'classic')
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, desktop)
        self.assertTrue(self.ui.redoDraft())
        with patch.object(controls, 'save'):
            self.assertTrue(self.ui.applyTopBar())
        self.assertEqual(self.ui._saved['top_bar']['appearance']['design'], 'capsule')
        self.assertNotEqual(self.ui._saved['glass_transparency'], 31.125)
        self.assertEqual(self.ui._draft['glass_transparency'], 31.125)
        self.assertTrue(self.ui.dirty)

    def test_effect_slider_moves_coalesce_and_invalid_edits_do_not_mutate(self):
        before = copy.deepcopy(self.ui._draft)
        for level in (.1, .2, .325):
            self.ui.changeTopBarEffect(self.identifier, 'effect_intensity', level)
        self.assertEqual(self.ui._draft['top_bar']['items'][0]['prefs']['effect_intensity'], .325)
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, before)
        for field, selected in (('effect_speed', float('nan')), ('effect_intensity', -1),
                                ('effect_speed', 3), ('other', 1)):
            self.ui.changeTopBarEffect(self.identifier, field, selected)
            self.assertEqual(self.ui._draft, before)
        self.ui.changeTopBarEffect('b_unknown', 'effect_speed', 1.5)
        self.assertEqual(self.ui._draft, before)

    def test_group_and_pair_rows_get_same_controls_but_independent_activity(self):
        self.ui._data = dict(time=time.time(), cpu_usage=40, cpu_temp=60,
                             net_download=5, net_upload=0)
        for metric, extra in (
            ('cpu_usage', {'metrics': ['cpu_usage', 'cpu_temp']}),
            ('net_download', {'style': 'duplex'}),
        ):
            value = copy.deepcopy(DEFAULT)
            value['top_bar']['items'] = [dict(id='b_group', metric=metric, prefs=dict(
                icon_effect='auto', effect_intensity=.375, effect_speed=1.75, **extra))]
            self.ui._saved = validate(value)
            row = self.ui.topBarRows()[0]
            children = row['group_rows'] if row['grouped'] else row['paired_rows']
            self.assertEqual(len(children), 2)
            for child in [row, *children]:
                self.assertEqual(child['effect_intensity'], .375)
                self.assertEqual(child['effect_speed'], 1.75)
            self.assertNotEqual(children[0]['effect_level'], children[1]['effect_level'])

    def test_cancel_bar_restores_design_effects_and_leaves_global_draft(self):
        self.ui.change('refresh', .25)
        self.ui.changeTopBarAppearance('design', 'instrument')
        self.ui.changeTopBarEffect(self.identifier, 'effect_speed', 1.75)
        self.assertTrue(self.ui.revertTopBarDraft())
        self.assertEqual(self.ui._draft['top_bar'], self.ui._saved['top_bar'])
        self.assertEqual(self.ui._draft['refresh'], .25)


if __name__ == '__main__':
    unittest.main()
