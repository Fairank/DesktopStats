"""Material projection and owned offscreen reading surfaces; no native requests."""

import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import Property, QObject, QPoint, QPointF, QUrl, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlRegisterType
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from skin_styles import palette

ROOT = Path(__file__).resolve().parents[1]


class ThemeState(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.report = {}
        self.mode = "light"
        self.locale = "en"

    material = Property("QVariantMap", lambda self: self.report, notify=changed)
    theme = Property(str, lambda self: self.mode, notify=changed)
    language = Property(str, lambda self: self.locale, notify=changed)
    texts = Property("QVariantMap", lambda self: {}, constant=True)
    motionEnabled = Property(bool, lambda self: False, constant=True)


class ThemeMaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Theme projection tests require offscreen Qt")

    def setUp(self):
        self.native = self.enterContext(
            patch("ctypes.WinDLL", side_effect=AssertionError("No native API"))
        )
        self.process = self.enterContext(
            patch("subprocess.Popen", side_effect=AssertionError("No process"))
        )
        self.stats = ThemeState()
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(
            lambda values: self.warnings.extend(error.toString() for error in values)
        )
        self.engine.rootContext().setContextProperty("stats", self.stats)
        self.component = QQmlComponent(
            self.engine, QUrl.fromLocalFile(str(ROOT / "native/Theme.qml"))
        )
        self.theme = self.component.create()
        self.assertIsNotNone(self.theme, [error.toString() for error in self.component.errors()])

    def tearDown(self):
        self.assertEqual(self.warnings, [])
        self.assertEqual(self.native.call_count, 0)
        self.assertEqual(self.process.call_count, 0)
        self.theme.deleteLater()
        self.engine.deleteLater()
        self.app.processEvents()

    def publish(self, report, mode="light"):
        self.stats.report = copy.deepcopy(report)
        self.stats.mode = mode
        self.stats.changed.emit()
        self.app.processEvents()

    @staticmethod
    def dwm():
        return dict(
            material="desktop-acrylic",
            status="configured-unverified",
            policy={"state": "allowed"},
            backdrop_result=0,
            backdrop_type=3,
            compositing_verified=False,
        )

    @staticmethod
    def blur():
        return dict(
            material="system-blur",
            status="configured-unverified",
            policy={"state": "allowed"},
            coating_allowed=True,
            coating_translucent=True,
            blur_configured=True,
            bool_result=1,
            ok=True,
            compositing_verified=False,
        )

    def assert_opaque(self):
        self.assertFalse(self.theme.property("translucentBackdrop"))
        for name in (
            "windowTop",
            "windowBottom",
            "railTop",
            "railBottom",
            "panelTop",
            "panelBottom",
            "fieldTop",
            "fieldBottom",
            "popupTop",
            "popupBottom",
            "frostedPopupTop",
        ):
            self.assertEqual(self.theme.property(name).alpha(), 255, name)

    def test_supported_backend_identity_is_separate_from_paint_permission(self):
        self.publish(self.dwm())
        self.assertTrue(self.theme.property("acrylic"))
        self.assertTrue(self.theme.property("translucentBackdrop"))
        self.publish(self.blur())
        self.assertFalse(self.theme.property("acrylic"))
        self.assertTrue(self.theme.property("translucentBackdrop"))

    def test_backend_label_or_visual_verified_flag_alone_does_not_enable_alpha(self):
        for report in (
            {},
            {"material": "desktop-acrylic"},
            {"material": "system-blur"},
            {"material": "system-blur", "compositing_verified": True},
        ):
            with self.subTest(report=report):
                self.publish(report)
                self.assert_opaque()

    def test_dwm_result_and_readback_are_strict(self):
        for field, value in (
            ("backdrop_result", None),
            ("backdrop_result", False),
            ("backdrop_result", "0"),
            ("backdrop_result", -1),
            ("backdrop_type", 1),
            ("backdrop_type", "3"),
        ):
            with self.subTest(field=field, value=value):
                report = self.dwm()
                report[field] = value
                self.publish(report)
                self.assert_opaque()

    def test_blur_requires_configured_numeric_nonzero_bool_and_coating(self):
        cases = [
            ("bool_result", value)
            for value in (None, 0, False, True, "1", 0.5, 2**35, float("nan"), float("inf"))
        ]
        cases += [("blur_configured", value) for value in (False, 1, "true", None)]
        cases += [
            (field, value)
            for field in ("coating_allowed", "coating_translucent", "ok")
            for value in (False, None)
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                report = self.blur()
                report[field] = value
                self.publish(report)
                self.assert_opaque()

    def test_policy_unknown_disabled_missing_or_contradictory_is_opaque(self):
        for base in (self.dwm(), self.blur()):
            for value in (None, {}, {"state": "unknown"}, {"state": "disabled"}, {"state": True}):
                with self.subTest(backend=base["material"], policy=value):
                    report = copy.deepcopy(base)
                    report["policy"] = value
                    self.publish(report)
                    self.assert_opaque()

    def test_explicit_failure_never_uses_translucent_tokens(self):
        for base in (self.dwm(), self.blur()):
            cases = [
                ("status", value)
                for value in (None, "fallback", "failed", "unknown", "disabled", "no-blur")
            ]
            cases += [
                ("fallback_reason", "native-request-failed"),
                ("ok", False),
                ("coating_allowed", False),
                ("coating_translucent", False),
            ]
            for field, value in cases:
                with self.subTest(backend=base["material"], field=field, value=value):
                    report = copy.deepcopy(base)
                    report[field] = value
                    self.publish(report)
                    self.assert_opaque()

    def test_live_changes_restore_solid_and_update_dark_palette(self):
        self.publish(self.blur())
        self.assertTrue(self.theme.property("translucentBackdrop"))
        self.publish({"material": "solid", "status": "fallback"}, "dark")
        self.assert_opaque()
        self.assertEqual(self.theme.property("ink").name(), "#f5f6f8")
        self.publish(self.dwm(), "dark")
        self.assertTrue(self.theme.property("translucentBackdrop"))

    def test_accepted_alpha_anchor_matches_widget_glass_palette(self):
        for mode, dark in (("light", False), ("dark", True)):
            for report in (self.dwm(), self.blur()):
                with self.subTest(mode=mode, backend=report["material"]):
                    self.publish(report, mode)
                    self.assertEqual(
                        self.theme.property("windowTop").name(
                            self.theme.property("windowTop").NameFormat.HexArgb
                        ),
                        palette("glass", dark, frosted=True, transparency=50)["top"],
                    )

    def test_normal_text_contrast_on_requested_alpha_planes(self):
        def luminance(rgb):
            channels = [
                value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                for value in rgb
            ]
            return sum(value * weight for value, weight in zip(channels, (0.2126, 0.7152, 0.0722)))

        # Controlled mathematical underlays, not evidence of a native compositor.
        backgrounds = [(value / 255,) * 3 for value in range(256)]
        backgrounds += [(r, g, b) for r in (0, 1) for g in (0, 1) for b in (0, 1)]
        for mode in ("light", "dark"):
            for report in (self.dwm(), self.blur()):
                self.publish(report, mode)
                for surface in ("windowTop", "railTop"):
                    coating = self.theme.property(surface)
                    for underlay in backgrounds:
                        rgb = tuple(
                            channel * coating.alphaF() + back * (1 - coating.alphaF())
                            for channel, back in zip(
                                (coating.redF(), coating.greenF(), coating.blueF()), underlay
                            )
                        )
                        if surface == "railTop":
                            # The actual sidebar groups add this local reading
                            # surface; untouched blank rail retains 32/72%.
                            reading = self.theme.property("railReading")
                            rgb = tuple(
                                channel * reading.alphaF() + back * (1 - reading.alphaF())
                                for channel, back in zip(
                                    (reading.redF(), reading.greenF(), reading.blueF()), rgb
                                )
                            )
                        for state in (
                            ("normal", "hover", "pressed") if surface == "railTop" else ("normal",)
                        ):
                            actual = rgb
                            if state != "normal":
                                overlay = self.theme.property(state)
                                actual = tuple(
                                    channel * overlay.alphaF() + back * (1 - overlay.alphaF())
                                    for channel, back in zip(
                                        (overlay.redF(), overlay.greenF(), overlay.blueF()), rgb
                                    )
                                )
                            for foreground in ("ink", "muted", "subtle"):
                                text = self.theme.property(foreground)
                                low, high = sorted(
                                    (
                                        luminance(actual),
                                        luminance((text.redF(), text.greenF(), text.blueF())),
                                    )
                                )
                                self.assertGreaterEqual(
                                    (high + 0.05) / (low + 0.05),
                                    4.5,
                                    (mode, surface, state, foreground, underlay),
                                )

    def test_blank_chrome_keeps_wuji_alpha_and_local_reading_surface_is_translucent(self):
        for mode, rail, window, reading in (("light", 82, 163, 144), ("dark", 184, 214, 136)):
            self.publish(self.dwm(), mode)
            self.assertEqual(self.theme.property("railTop").alpha(), rail)
            self.assertEqual(self.theme.property("windowTop").alpha(), window)
            self.assertEqual(self.theme.property("railReading").alpha(), reading)
            self.assertLess(reading, 255)
            self.publish({}, mode)
            self.assertEqual(self.theme.property("railReading").alpha(), 0)
            self.assert_opaque()

    def test_actual_sidebar_reading_groups_cover_text_and_preserve_blank_glass(self):
        import native_controller as controls
        from native_card import HardwareCard
        from native_surface import MaterialSurface
        from stats_config import DEFAULT

        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")
        config = copy.deepcopy(DEFAULT)
        config.update(language="zh-CN", theme="light", widget_order=["cpu", "gpu", "memory"])
        config["widgets"]["gpu"]["enabled"] = False
        with patch.object(controls, "load", return_value=config):
            controller = controls.Controller()
        self.enterContext(
            patch.object(controls, "save", side_effect=AssertionError("No persistence"))
        )
        engine = QQmlEngine()
        engine.warnings.connect(
            lambda values: self.warnings.extend(error.toString() for error in values)
        )
        engine.rootContext().setContextProperty("stats", controller)
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "native/Settings.qml")))
        window = component.create()
        self.assertIsNotNone(window, [error.toString() for error in component.errors()])

        def find(name):
            pending = [window.contentItem()]
            while pending:
                item = pending.pop()
                if item.objectName() == name:
                    return item
                pending.extend(item.childItems())
            self.fail("Missing sidebar visual item: " + name)

        def bounds(item):
            point = item.mapToItem(window.contentItem(), QPointF(0, 0))
            return point.x(), point.y(), item.width(), item.height()

        def covered(item, group):
            x, y, width, height = bounds(item)
            left, top, outer_width, outer_height = bounds(group)
            self.assertGreaterEqual(x, left, item.objectName())
            self.assertGreaterEqual(y, top, item.objectName())
            self.assertLessEqual(x + width, left + outer_width + 0.1, item.objectName())
            self.assertLessEqual(y + height, top + outer_height + 0.1, item.objectName())

        def composite(color, under):
            return tuple(
                channel * color.alphaF() + back * (1 - color.alphaF())
                for channel, back in zip((color.redF(), color.greenF(), color.blueF()), under)
            )

        try:
            window.setProperty("nativeHosted", True)
            window.setProperty("page", 1)
            window.resize(960, 640)
            window.show()
            for mode in ("light", "dark"):
                self.publish(self.dwm(), mode)
                controller.change("theme", mode)
                controller.set_material(self.dwm())
                QTest.qWait(60)
                QTest.mouseMove(window, QPoint(900, 550))
                QTest.qWait(30)
                brand = find("sidebarBrandReadingSurface")
                nav = find("sidebarNavigationReadingSurface")
                widgets = find("sidebarWidgetsReadingSurface")
                footer = find("sidebarFooterReadingSurface")
                covered(find("sidebarBrandContent"), brand)
                for name in ("nav_0", "nav_1", "nav_3"):
                    covered(find(name), nav)
                covered(find("sidebarWidgetCountContent"), widgets)
                for key in config["widget_order"]:
                    covered(find("widgetRow_" + key), widgets)
                covered(find("sidebarFooterContent"), footer)
                # Three rows must not produce a full-height blank reading card.
                self.assertLess(widgets.height(), find("widgetListScroll").height())
                self.assertLess(widgets.y() + widgets.height(), footer.y())
                for item in (brand, nav, widgets, footer):
                    self.assertLess(item.property("color").alpha(), 255)
                    self.assertEqual(
                        QQmlExpression(engine.rootContext(), item, "border.width").evaluate()[0], 0
                    )

                raw = window.grabWindow()
                self.assertFalse(raw.isNull())
                underlay = (0.0,) * 3 if mode == "light" else (1.0,) * 3
                canvas = QImage(raw.size(), QImage.Format_ARGB32_Premultiplied)
                canvas.fill(QColor.fromRgbF(*underlay))
                painter = QPainter(canvas)
                painter.drawImage(0, 0, raw)
                painter.end()
                # Sample a real, unhovered navigation background, clear of text.
                x = int(window.property("railWidth")) - 17
                point = canvas.pixelColor(x, 114)
                expected = composite(
                    self.theme.property("railReading"),
                    composite(self.theme.property("railTop"), underlay),
                )
                for actual, wanted in zip((point.redF(), point.greenF(), point.blueF()), expected):
                    self.assertAlmostEqual(actual, wanted, delta=2 / 255)
                # The inter-group gap is still the original thin WUJI coating.
                self.assertAlmostEqual(
                    raw.pixelColor(40, 80).alpha(), 82 if mode == "light" else 184, delta=1
                )
                self.assertAlmostEqual(
                    raw.pixelColor(int(window.property("railWidth")) + 6, 80).alpha(),
                    163 if mode == "light" else 214,
                    delta=1,
                )
                proof = os.environ.get("DESKTOP_STATS_THEME_PROOF_DIR")
                if proof:
                    directory = Path(proof).resolve()
                    self.assertTrue(directory.is_relative_to((ROOT / "qa-private").resolve()))
                    directory.mkdir(parents=True, exist_ok=True)
                    self.assertTrue(canvas.save(str(directory / ("sidebar-" + mode + ".png"))))
        finally:
            window.hide()
            window.deleteLater()
            engine.deleteLater()
            controller.close()
            controller.deleteLater()
            self.app.processEvents()

    def test_form_text_contrast_solid_fallback(self):
        def luminance(color):
            channels = [color.redF(), color.greenF(), color.blueF()]
            values = [
                value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                for value in channels
            ]
            return sum(value * weight for value, weight in zip(values, (0.2126, 0.7152, 0.0722)))

        for mode in ("light", "dark"):
            self.publish({}, mode)
            for foreground in ("ink", "muted", "subtle"):
                for background in ("fallback", "railTop", "fieldTop", "popupTop"):
                    values = sorted(
                        (
                            luminance(self.theme.property(foreground)),
                            luminance(self.theme.property(background)),
                        )
                    )
                    self.assertGreaterEqual(
                        (values[1] + 0.05) / (values[0] + 0.05), 4.5, (mode, foreground, background)
                    )
            fill = luminance(self.theme.property("accentFill"))
            self.assertGreaterEqual((1 + 0.05) / (fill + 0.05), 4.5, (mode, "white button text"))
            focus = sorted(
                (
                    luminance(self.theme.property("accent")),
                    luminance(self.theme.property("fieldTop")),
                )
            )
            self.assertGreaterEqual((focus[1] + 0.05) / (focus[0] + 0.05), 3, (mode, "focus edge"))
            for hover in ("#0066d6", "#0058bf"):
                self.assertGreaterEqual((1 + 0.05) / (luminance(QColor(hover)) + 0.05), 4.5)


if __name__ == "__main__":
    unittest.main()
