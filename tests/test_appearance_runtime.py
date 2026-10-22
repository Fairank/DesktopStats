"""Appearance preview must not run the normal desktop apply/placement path."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from native_runtime import Runtime
from stats_config import DEFAULT


class RuntimeAppearanceTests(unittest.TestCase):
    def runtime(self):
        saved = copy.deepcopy(DEFAULT)
        saved["widgets"]["cpu"]["skin"] = "minimal"
        draft = copy.deepcopy(saved)
        draft["widgets"]["cpu"].update(skin="glass", glass_transparency=24.5)
        draft["widgets"]["cpu"]["content"] = ["cpu_power"]
        window = Mock()
        runtime = SimpleNamespace(
            headless=False, shutting_down=False,
            controller=SimpleNamespace(_saved=saved, _draft=draft, set_window_materials=Mock()),
            settings=Mock(), widgets={"cpu": window},
            _spec_by_id={"cpu": {"id": "cpu", "cells": [{"key": "cpu"}]}},
            composition={"cpu": {"renderer": "Software", "fallback_reason": "material-disabled",
                                   "desktop_level_error": "known placement diagnostic"}},
            apply=Mock(), arrange=Mock(), position=Mock(), compose=Mock(),
        )
        runtime.settings.isVisible.return_value = True
        return runtime, window

    def test_only_appearance_reaches_existing_window_no_geometry_native_or_commit(self):
        runtime, window = self.runtime()
        before = copy.deepcopy(runtime.controller._saved)
        with patch("native_runtime.widget_material", return_value={"coating_translucent": True}) as coating:
            Runtime.refresh_appearance(runtime)
        props = dict(call.args for call in window.setProperty.call_args_list)
        self.assertEqual(props["appearanceConfig"]["widgets"]["cpu"]["skin"], "glass")
        self.assertEqual(props["appearanceConfig"]["widgets"]["cpu"]["glass_transparency"], 24.5)
        self.assertEqual(props["appearanceConfig"]["widgets"]["cpu"]["content"], before["widgets"]["cpu"]["content"])
        self.assertEqual(runtime.controller._saved, before)
        self.assertEqual(props["composition"]["desktop_level_error"], "known placement diagnostic")
        self.assertNotIn("fallback_reason", props["composition"])
        coating.assert_called_once_with(True)
        for method in (runtime.apply, runtime.arrange, runtime.position, runtime.compose,
                       window.show, window.hide, window.resize, window.setPosition, window.setFlags):
            method.assert_not_called()

    def test_hidden_settings_and_revert_restore_saved_coating(self):
        runtime, window = self.runtime()
        with patch("native_runtime.widget_material", side_effect=lambda enabled: {"coating_translucent": enabled}):
            Runtime.refresh_appearance(runtime)
            runtime.settings.isVisible.return_value = False
            Runtime.refresh_appearance(runtime)
            props = dict(call.args for call in window.setProperty.call_args_list)
            self.assertEqual(props["appearanceConfig"], runtime.controller._saved)
            self.assertFalse(props["composition"]["coating_translucent"])
            runtime.settings.isVisible.return_value = True
            runtime.controller._draft = copy.deepcopy(runtime.controller._saved)
            Runtime.refresh_appearance(runtime)
            props = dict(call.args for call in window.setProperty.call_args_list)
            self.assertEqual(props["appearanceConfig"], runtime.controller._saved)

    def test_duplicate_and_nonappearance_edits_do_not_repaint(self):
        runtime, window = self.runtime()
        with patch("native_runtime.widget_material", return_value={"coating_translucent": True}) as coating:
            Runtime.refresh_appearance(runtime)
            calls = window.setProperty.call_count
            Runtime.refresh_appearance(runtime)
            runtime.controller._draft["refresh"] = .01
            runtime.controller._draft["widgets"]["cpu"]["width"] = 1111
            Runtime.refresh_appearance(runtime)
            self.assertEqual(window.setProperty.call_count, calls)
            self.assertEqual(coating.call_count, 1)

    def test_new_window_same_id_receives_preview_and_removed_window_leaves_cache(self):
        runtime, window = self.runtime()
        with patch("native_runtime.widget_material", return_value={}):
            Runtime.refresh_appearance(runtime)
            replacement = Mock()
            runtime.widgets["cpu"] = replacement
            Runtime.refresh_appearance(runtime)
            self.assertEqual(replacement.setProperty.call_count, 3)
            runtime.widgets.clear()
            Runtime.refresh_appearance(runtime)
            self.assertEqual(runtime._appearance_states, {})

    def test_headless_and_shutdown_have_no_effect(self):
        runtime, window = self.runtime()
        for headless, shutdown in ((True, False), (False, True)):
            runtime.headless, runtime.shutting_down = headless, shutdown
            Runtime.refresh_appearance(runtime)
        window.setProperty.assert_not_called()


if __name__ == "__main__":
    unittest.main()
