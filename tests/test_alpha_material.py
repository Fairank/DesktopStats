"""Layered coating contracts: isolated Controller, real QML and QImage only.

No Runtime instance, IPC listener, sampler, real profile or native window is
created. Platform preferences and every persistence boundary are substituted.
"""

import copy
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

import native_controller as controls
import native_platform as platform
from material_policy import render_policy
from native_card import HardwareCard
from native_glass import widget_flags
from native_layout import windows
from native_runtime import Runtime
from native_surface import MaterialSurface
from skin_styles import GLASS_SKINS, SKINS, glass_options, palette
from stats_config import DEFAULT, validate


class AlphaPlatformTests(unittest.TestCase):
    def test_coating_permission_is_independent_of_blur_and_never_calls_dwm(self):
        for enabled in (False, True):
            for allowed in (False, True):
                with self.subTest(enabled=enabled, allowed=allowed):
                    with (
                        patch.object(platform, "transparency_enabled", return_value=allowed),
                        patch.object(
                            platform.c, "WinDLL", side_effect=AssertionError("No DWM call")
                        ),
                    ):
                        report = platform.widget_material(enabled)
                    self.assertIs(report["coating_allowed"], allowed)
                    self.assertIs(report["coating_translucent"], enabled and allowed)
                    self.assertEqual(
                        report["material"], "translucent" if enabled and allowed else "solid"
                    )
                    self.assertIs(report["blur_configured"], False)
                    self.assertIs(report["compositing_verified"], False)

    def test_legacy_alpha_flags_keep_desktop_tool_nonactivation(self):
        flags = widget_flags(False)
        self.assertEqual(flags & Qt.WindowType_Mask, Qt.Tool)
        self.assertTrue(flags & Qt.FramelessWindowHint)
        self.assertTrue(flags & Qt.WindowStaysOnBottomHint)
        self.assertTrue(flags & Qt.WindowDoesNotAcceptFocus)

    @staticmethod
    def fake_runtime():
        controller = SimpleNamespace(
            _draft={"theme": "dark"},
            _saved={"theme": "light"},
            set_material=Mock(),
            set_window_materials=Mock(),
        )
        runtime = SimpleNamespace(controller=controller, composition={})
        window = Mock()
        window.winId.return_value = 123
        window.rendererInterface.return_value.graphicsApi.return_value = SimpleNamespace(
            name="FakeRenderer"
        )
        return runtime, window

    def test_widget_composition_uses_alpha_report_without_requesting_acrylic(self):
        for enabled in (False, True):
            runtime, window = self.fake_runtime()
            report = dict(
                material="translucent" if enabled else "solid",
                coating_allowed=True,
                coating_translucent=enabled,
                blur_configured=False,
                compositing_verified=False,
            )
            with (
                patch(
                    "native_runtime.widget_material", return_value=copy.deepcopy(report)
                ) as alpha,
                patch(
                    "native_runtime.glass",
                    side_effect=AssertionError("Widget must not request DWM"),
                ),
                patch("native_runtime.desktop_level") as place,
            ):
                Runtime.compose(runtime, window, "cpu", enabled)
            alpha.assert_called_once_with(enabled)
            place.assert_called_once_with(123)
            delivered = runtime.composition["cpu"]
            self.assertEqual(delivered["material"], report["material"])
            self.assertIs(delivered["coating_translucent"], enabled)
            self.assertFalse(delivered["blur_configured"])
            self.assertFalse(delivered["compositing_verified"])
            window.setProperty.assert_called_once_with("composition", delivered)

    def test_settings_keep_their_separate_dwm_request_without_using_widget_alpha(self):
        runtime, window = self.fake_runtime()
        report = dict(
            material="desktop-acrylic", status="configured-unverified", compositing_verified=False
        )
        with (
            patch(
                "native_runtime.widget_material",
                side_effect=AssertionError("Settings are separate"),
            ),
            patch("native_runtime.glass", return_value=copy.deepcopy(report)) as dwm,
            patch("native_runtime.desktop_level") as place,
        ):
            Runtime.compose(runtime, window, "settings")
        dwm.assert_called_once_with(123, True, True)
        place.assert_not_called()
        self.assertFalse(runtime.composition["settings"]["compositing_verified"])


class AlphaPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        self.value = copy.deepcopy(DEFAULT)
        self.value.update(mode="separate", widget_order=["cpu", "gpu"], autostart=False)
        for key in ("cpu", "gpu"):
            self.value["widgets"][key].update(enabled=True, skin=None, grouped=True, chart=False)
        self.value = validate(self.value)
        with patch.object(controls, "load", return_value=copy.deepcopy(self.value)):
            self.ui = controls.Controller()
        self.saved = []
        guards = (
            patch.object(
                controls, "save", side_effect=lambda data: self.saved.append(copy.deepcopy(data))
            ),
            patch.object(
                controls, "set_autostart", side_effect=AssertionError("No registry writes")
            ),
            patch.object(controls.sensors, "Sampler", side_effect=AssertionError("No hardware")),
        )
        for guard in guards:
            guard.start()
            self.addCleanup(guard.stop)
        self.qml_objects = []

    def tearDown(self):
        for root, engine, _component in reversed(self.qml_objects):
            if isValid(root):
                root.deleteLater()
            if isValid(engine):
                engine.deleteLater()
        self.app.processEvents()
        self.assertIsNone(self.ui.thread)

    def report(self, *, allowed=True, material="translucent", **options):
        result = dict(
            material=material,
            coating_allowed=allowed,
            coating_translucent=allowed,
            blur_configured=False,
            compositing_verified=False,
        )
        result.update(options)
        self.ui.set_window_materials(
            {key: copy.deepcopy(result) for key in ("cpu", "gpu", "group")}
        )
        return result

    def preview(self, key="cpu"):
        warnings = []
        state = self.ui.previewState(key)
        engine = QQmlEngine()
        engine.rootContext().setContextProperty("stats", self.ui)
        engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
        component = QQmlComponent(
            engine,
            QUrl.fromLocalFile(
                str(Path(__file__).resolve().parents[1] / "native/WidgetPreview.qml")
            ),
        )
        root = component.createWithInitialProperties(
            dict(
                width=state["width"],
                height=state["height"],
                moduleKey=key,
                config=copy.deepcopy(self.ui.draft),
                previewInfo=state,
                readings=dict(time=time.time(), cpu_temp=65, gpu_temp=45),
                history=[],
            )
        )
        self.assertIsNotNone(root, [error.toString() for error in component.errors()])
        QQmlEngine.setObjectOwnership(root, QQmlEngine.CppOwnership)
        self.qml_objects.append((root, engine, component))
        self.app.processEvents()
        self.assertEqual(warnings, [])
        card = next(item for item in root.findChildren(HardwareCard))
        surface = next(item for item in root.findChildren(MaterialSurface))
        return state, card, surface

    @staticmethod
    def image(item):
        image = QImage(
            round(item.width()), round(item.height()), QImage.Format_ARGB32_Premultiplied
        )
        image.fill(Qt.transparent)
        painter = QPainter(image)
        item.paint(painter)
        painter.end()
        return image

    def test_preview_coating_is_available_without_blur_and_uses_resolved_skin(self):
        self.report()
        for skin in SKINS:
            with self.subTest(skin=skin):
                self.ui.changeWidget("cpu", "skin", skin)
                state = self.ui.previewState("cpu")
                self.assertIs(state["coating_translucent"], skin in GLASS_SKINS)
                self.assertFalse(state["frosted"])
                self.assertFalse(state["blur_configured"])
                self.assertFalse(state["compositing_verified"])

    def test_real_qml_forwards_coating_permission_independently_of_legacy_frosted(self):
        self.report()
        state, card, surface = self.preview()
        self.assertTrue(state["coating_translucent"])
        self.assertFalse(state["frosted"])
        self.assertTrue(card.property("frosted"))
        self.assertTrue(surface.property("frosted"))

    def test_uniform_group_renders_continuous_alpha_from_its_shared_panel(self):
        self.ui.change("mode", "combined")
        self.report()
        for skin in GLASS_SKINS:
            with self.subTest(skin=skin):
                self.ui.change("skin", skin)
                alphas = []
                for level in (0, 37.25, 100):
                    self.ui.change("glass_transparency", level)
                    state, card, surface = self.preview()
                    self.assertEqual(state["panel_skin"], skin)
                    self.assertFalse(state["card_surfaces"])
                    self.assertFalse(card.property("surface"))
                    self.assertTrue(surface.isVisible())
                    image = self.image(surface)
                    actual = image.pixelColor(image.width() // 2, image.height() // 2).alpha()
                    alphas.append(actual)
                    colors = palette(skin, frosted=True, transparency=level)
                    top, bottom = (QColor(colors[stop]).alpha() for stop in ("top", "bottom"))
                    fraction = (image.height() // 2 + .5) / image.height()
                    self.assertLessEqual(abs(actual - (top + (bottom - top) * fraction)), 1)
                self.assertEqual(alphas[0], 255)
                self.assertEqual(alphas[-1], 0)
                self.assertTrue(alphas[0] > alphas[1] > alphas[2])

    def test_alpha_preview_curvature_changes_actual_corner_coverage(self):
        self.ui.change("mode", "combined")
        self.ui.change("glass_transparency", 0)
        self.report()
        coverage = []
        for curvature in (0, 37.25, 100):
            self.ui.change("glass_curvature", curvature)
            state, _card, surface = self.preview()
            self.assertTrue(state["coating_translucent"])
            image = self.image(surface)
            self.assertEqual(image.pixelColor(image.width() // 2, image.height() // 2).alpha(), 255)
            coverage.append(
                sum(image.pixelColor(x, y).alpha() > 200 for x in range(40) for y in range(40))
            )
        self.assertTrue(coverage[0] > coverage[1] > coverage[2], coverage)

    def test_mixed_minimal_and_glass_keep_per_card_alpha_without_whole_window_blur(self):
        self.ui.change("mode", "combined")
        self.ui.changeWidget("gpu", "skin", "minimal")
        self.ui.changeWidget("cpu", "glass_transparency", 100)
        self.report()
        policy = render_policy(self.ui.draft, windows(self.ui.draft)[0])
        self.assertFalse(policy["backdrop"])
        self.assertIsNone(policy["panel_skin"])
        self.assertTrue(policy["card_surfaces"])
        for key, translucent in (("cpu", True), ("gpu", False)):
            with self.subTest(key=key):
                state, card, _ = self.preview(key)
                self.assertIs(state["coating_translucent"], translucent)
                self.assertFalse(state["blur_configured"])
                self.assertFalse(state["compositing_verified"])
                self.assertTrue(card.property("surface"))
                image = self.image(card)
                center_x = image.width() // 2
                self.assertEqual(image.pixelColor(center_x, image.height() - 10).alpha(), 0)
                ink_pixels = sum(
                    image.pixelColor(x, y).alpha() > 240
                    for x in range(image.width())
                    for y in range(image.height())
                )
                self.assertGreater(
                    ink_pixels, 10, "Foreground digits must not fade with the coating"
                )

    def test_standalone_mixed_and_disabled_cards_render_continuous_alpha(self):
        self.report()
        self.ui.changeWidget("gpu", "skin", "minimal")
        for mode in ("separate", "combined"):
            self.ui.change("mode", mode)
            for enabled in (True, False):
                self.ui.changeWidget("cpu", "enabled", enabled)
                with self.subTest(mode=mode, enabled=enabled):
                    alphas = []
                    for level in (0, 37.25, 100):
                        self.ui.changeWidget("cpu", "glass_transparency", level)
                        state, card, _ = self.preview()
                        self.assertTrue(state["coating_translucent"])
                        image = self.image(card)
                        actual = image.pixelColor(image.width() // 2, image.height() - 10).alpha()
                        alphas.append(actual)
                        expected = QColor(
                            palette("glass", frosted=True, transparency=level)["bottom"]
                        ).alpha()
                        self.assertEqual(actual, expected)
                    self.assertEqual(alphas[0], 255)
                    self.assertEqual(alphas[-1], 0)
                    self.assertTrue(alphas[0] > alphas[1] > alphas[2])

    def test_accessibility_policy_keeps_actual_qml_coatings_readable_and_opaque(self):
        self.report(allowed=False, material="solid", coating_translucent=False)
        for level in (0, 37.25, 100):
            self.ui.change("glass_transparency", level)
            state, card, surface = self.preview()
            self.assertFalse(state["coating_translucent"])
            self.assertFalse(card.property("frosted"))
            self.assertFalse(surface.property("frosted"))
            image = self.image(card)
            self.assertGreaterEqual(
                image.pixelColor(image.width() // 2, image.height() - 10).alpha(), 246
            )
            self.assertFalse(state["blur_configured"])
            self.assertFalse(state["compositing_verified"])

    def test_disabled_widget_remains_editable_with_coating_policy(self):
        self.ui.changeWidget("cpu", "enabled", False)
        for allowed in (True, False):
            with self.subTest(allowed=allowed):
                self.report(allowed=allowed, material="translucent" if allowed else "solid")
                state = self.ui.previewState("cpu")
                self.assertEqual(state["skin"], "glass")
                self.assertIs(state["coating_translucent"], allowed)
                self.assertFalse(state["blur_configured"])
                self.assertFalse(state["compositing_verified"])

    def test_old_dwm_configuration_cannot_override_disabled_coating_or_prove_verification(self):
        self.report(allowed=False, material="desktop-acrylic", blur_configured=True)
        state = self.ui.previewState("cpu")
        self.assertFalse(state["coating_translucent"])
        self.assertFalse(state["compositing_verified"])

    def test_fractional_overrides_wait_for_apply_and_preserve_independent_inheritance(self):
        original = copy.deepcopy(self.ui.saved)
        self.ui.change("glass_transparency", 81.25)
        self.ui.change("glass_curvature", 67.75)
        self.ui.changeWidget("cpu", "glass_transparency", 37.25)
        self.ui.changeWidget("cpu", "glass_curvature", 0)
        self.assertEqual(self.ui.saved, original)
        self.assertEqual(self.saved, [])
        self.assertEqual(
            glass_options(self.ui.draft, "cpu"), dict(transparency=37.25, curvature=0.0)
        )
        self.assertEqual(
            glass_options(self.ui.draft, "gpu"), dict(transparency=81.25, curvature=67.75)
        )
        self.ui.apply()
        self.assertEqual(len(self.saved), 1)
        self.assertFalse(self.ui.dirty)
        self.assertEqual(self.ui.saved, self.saved[0])
        restored = validate(copy.deepcopy(self.saved[0]))
        self.assertEqual(restored, self.ui.saved)
        self.assertIsNone(restored["widgets"]["gpu"]["glass_transparency"])
        self.assertIsNone(restored["widgets"]["gpu"]["glass_curvature"])
        self.ui.changeWidget("cpu", "glass_transparency", None)
        self.assertEqual(glass_options(self.ui.draft, "cpu")["transparency"], 81.25)
        self.ui.undoDraft()
        self.assertEqual(glass_options(self.ui.draft, "cpu")["transparency"], 37.25)
        self.ui.revert()
        self.assertEqual(self.ui.draft, self.ui.saved)


if __name__ == "__main__":
    unittest.main()
