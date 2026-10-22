"""User-facing customization contracts without showing or changing desktop windows."""

import copy
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/customization-unit-data"),
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from native_card import HardwareCard
from native_controller import Controller
from native_platform import glass
from skin_styles import SKINS, effective_skin, palette
from stats_config import DEFAULT, validate


class CustomizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.initial = copy.deepcopy(DEFAULT)
        self.loader = patch("native_controller.load", return_value=self.initial)
        self.loader.start()
        self.ui = Controller()

    def tearDown(self):
        self.loader.stop()

    def test_missing_title_visibility_defaults_on_and_hidden_title_is_retained(self):
        old = {"version": 5, "widgets": {"cpu": {"title": "My title"}}}
        cfg = validate(old)
        self.assertTrue(cfg["widgets"]["cpu"]["show_title"])
        cfg["widgets"]["cpu"]["show_title"] = False
        saved = validate(cfg)
        self.assertFalse(saved["widgets"]["cpu"]["show_title"])
        self.assertEqual(saved["widgets"]["cpu"]["title"], "My title")
        for bad in (0, 1, "false", None):
            cfg["widgets"]["cpu"]["show_title"] = bad
            with self.assertRaises(ValueError):
                validate(cfg)

    def test_global_skin_does_not_overwrite_explicit_widget_choice(self):
        cfg = copy.deepcopy(DEFAULT)
        cfg["skin"] = "card"
        cfg["widgets"]["cpu"]["skin"] = "glass"
        self.assertEqual(effective_skin(cfg, "cpu"), "glass")
        cfg["widgets"]["cpu"]["skin"] = None
        self.assertEqual(effective_skin(cfg, "cpu"), "card")

    def test_six_distinct_materials_and_minimal_has_no_fallback_box(self):
        self.assertEqual(len(SKINS), 6)
        self.assertEqual(len({palette(s)["top"] for s in SKINS}), 6)
        minimal = palette("minimal", frosted=False)
        self.assertTrue(minimal["transparent"])
        self.assertEqual(minimal["border"], "#00000000")
        self.assertGreater(
            int(palette("frost")["top"][1:3], 16), int(palette("glass")["top"][1:3], 16)
        )
        self.assertEqual(palette("graphite")["ink"], palette("graphite", dark=True)["ink"])

    def test_quick_action_commits_only_its_field_and_preserves_editor_work(self):
        self.ui.changeWidget("cpu", "title", "Unsaved")
        self.ui.change("theme", "dark")
        with patch("native_controller.save") as save:
            self.assertTrue(self.ui.quickWidget("cpu", "show_title", False))
        persisted = save.call_args.args[0]
        self.assertEqual(persisted["theme"], "light")
        self.assertEqual(persisted["widgets"]["cpu"]["title"], "")
        self.assertFalse(persisted["widgets"]["cpu"]["show_title"])
        self.assertEqual(self.ui._draft["theme"], "dark")
        self.assertEqual(self.ui._draft["widgets"]["cpu"]["title"], "Unsaved")
        self.assertFalse(self.ui._draft["widgets"]["cpu"]["show_title"])

    def test_quick_write_failure_leaves_saved_and_draft_unchanged(self):
        self.ui.changeWidget("cpu", "title", "Pending")
        saved, draft = copy.deepcopy(self.ui._saved), copy.deepcopy(self.ui._draft)
        with patch("native_controller.save", side_effect=OSError("Disk full")):
            self.assertFalse(self.ui.quickWidget("cpu", "skin", "frost"))
        self.assertEqual(self.ui._saved, saved)
        self.assertEqual(self.ui._draft, draft)
        self.assertFalse(self.ui.quickWidget("cpu", "skin", "unknown"))

    def test_reset_overrides_remains_a_draft_until_apply(self):
        self.ui.changeWidget("cpu", "skin", "graphite")
        self.ui.useGlobalSkin()
        self.assertIsNone(self.ui._draft["widgets"]["cpu"]["skin"])
        self.assertEqual(self.ui._saved, self.initial)

    def test_title_off_removes_the_header_ink_and_keeps_the_reading(self):
        config = copy.deepcopy(DEFAULT)
        config["widgets"]["cpu"].update(skin="minimal", title="TITLE", chart=False)

        def render(enabled, title, temperature=65):
            config["widgets"]["cpu"]["show_title"] = enabled
            config["widgets"]["cpu"]["title"] = title
            card = HardwareCard()
            card.setWidth(160)
            card.setHeight(160)
            card.set_config(copy.deepcopy(config))
            card.set_key("cpu")
            card.set_data({"time": time.time(), "cpu_temp": temperature, "cpu_usage": 15})
            image = QImage(160, 160, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            card.paint(painter)
            painter.end()
            return image

        # Hidden titles must not affect pixels; content may reclaim their space.
        hidden = render(False, "FIRST")
        self.assertEqual(hidden, render(False, "SECOND"))
        self.assertNotEqual(render(True, "FIRST"), render(True, "SECOND"))
        self.assertNotEqual(hidden, render(True, "FIRST"))
        self.assertNotEqual(hidden, render(False, "FIRST", temperature=95))

    def test_dwm_alpha_is_version_guarded_and_never_claims_visible_verification(self):
        for build in (22621, 26100):
            dwm, user = MagicMock(), MagicMock()
            dwm.DwmSetWindowAttribute.return_value = 0
            dwm.DwmExtendFrameIntoClientArea.return_value = 0
            user.GetWindowLongPtrW.return_value = 0

            def read_back(hwnd, attribute, output, size):
                output._obj.value = 3
                return 0

            dwm.DwmGetWindowAttribute.side_effect = read_back
            with (
                patch(
                    "native_platform.sys.getwindowsversion",
                    return_value=SimpleNamespace(build=build),
                ),
                patch(
                    "native_platform.c.WinDLL",
                    side_effect=lambda name, **kwargs: dwm if name == "dwmapi" else user,
                ),
                patch("native_platform.transparency_enabled", return_value=True),
            ):
                report = glass(123)
            attrs = [call.args[1] for call in dwm.DwmSetWindowAttribute.call_args_list]
            self.assertEqual(39 in attrs, build >= 26100)
            self.assertFalse(report["compositing_verified"])
            self.assertEqual(report["material"], "desktop-acrylic")
            user.SetForegroundWindow.assert_not_called()
            user.SetFocus.assert_not_called()
