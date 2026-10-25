"""Fake DWM and offscreen-only detail presentation; no native windows or sensors."""
import ctypes
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtGui import QRegion, QWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_settings_acrylic_material import FakeAPI

from top_bar_backdrop_host import DetailAcrylicBackend, TopBarBackdropHost


class CornerAPI:
    def __init__(self, host):
        self.host, self.calls = host, []
        self.version, self.style, self.result, self.hook = 26200, 0, 0, None
        self.process = os.getpid()

    def build(self):
        return self.version

    def is_window(self, handle):
        return handle == self.host._handle

    def owner(self, handle):
        return threading.main_thread().native_id, self.process

    def extended_style(self, handle):
        return self.style

    def round(self, handle):
        if not self.host.mask().isEmpty():
            raise AssertionError("A binary region prevents native rounding")
        self.calls.append((handle, 33, 2))
        if self.hook:
            self.hook()
        return self.result


class DetailCornerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dll_guard = patch.object(ctypes, "WinDLL", side_effect=AssertionError("No native API"))
        self.dll_mock = self.dll_guard.start()
        self.client = QWindow()
        self.client.resize(320, 240)
        self.host = TopBarBackdropHost(self.client, pinned=False, close_panel=lambda: None,
                                      native=False, painter=SimpleNamespace(fill=lambda *args: None))
        self.host.create()  # Hidden offscreen platform surface, never a Windows HWND.
        self.api = CornerAPI(self.host)
        self.host._corner_api = self.api
        self.mask = QRegion(QRect(0, 0, 320, 240))
        self.mask_calls = []

        def set_mask(region):
            self.mask = QRegion(region)
            self.mask_calls.append(QRegion(region))

        self.host.setMask, self.host.mask = set_mask, lambda: self.mask

    def tearDown(self):
        self.host.dispose()
        self.client.deleteLater()
        self.host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.dll_mock.assert_not_called()
        self.dll_guard.stop()

    def configure(self, valid=lambda: True):
        return self.host.configure_native_corners(self.host._handle, valid=valid)

    def test_round_hint_clears_region_and_is_cached_for_surface_not_size(self):
        self.assertTrue(self.configure())
        self.assertEqual(self.api.calls, [(self.host._handle, 33, 2)])
        self.assertTrue(self.mask.isEmpty())
        self.assertTrue(self.client.property("nativeRounded"))
        self.assertFalse(self.host.status()["corners"]["visual_verified"])
        self.host.resize(340, 260)
        self.assertTrue(self.configure())
        self.assertEqual(len(self.api.calls), 1)
        self.assertEqual(len(self.mask_calls), 1)
        self.host._serial += 1
        self.assertTrue(self.configure())
        self.assertEqual(len(self.api.calls), 2)

    def test_unsupported_layered_and_foreign_windows_do_not_receive_native_hint(self):
        for version, style, process in ((21999, 0, os.getpid()),
                                        (26200, 0x80000, os.getpid()),
                                        (26200, 0, os.getpid() + 1)):
            with self.subTest(version=version, style=style, process=process):
                self.host._corner_identity = None
                self.api.version, self.api.style, self.api.process = version, style, process
                self.assertFalse(self.configure())
                self.assertFalse(self.client.property("nativeRounded"))
        self.assertEqual(self.api.calls, [])
        self.assertEqual(self.mask_calls, [])

    def test_hresult_failure_keeps_qml_fallback_and_does_not_claim_rounding(self):
        self.api.result = -1
        self.assertFalse(self.configure())
        self.assertFalse(self.client.property("nativeRounded"))
        self.assertEqual(self.host.status()["corners"]["status"], "fallback")
        self.assertFalse(self.host.status()["corners"]["configured"])
        self.assertTrue(self.mask.isEmpty())  # Manager must restore the fallback region.

    def test_stale_or_reentrant_validator_never_reaches_dwm(self):
        self.assertFalse(self.configure(lambda: False))

        def replace_surface():
            self.host._serial += 1
            return True

        self.assertFalse(self.configure(replace_surface))
        self.assertEqual(self.api.calls, [])

    def test_replacement_during_dwm_call_cannot_publish_success_to_new_surface(self):
        self.api.hook = lambda: setattr(self.host, "_serial", self.host._serial + 1)
        self.assertFalse(self.configure())
        self.assertFalse(self.client.property("nativeRounded"))
        self.assertFalse(self.host.status()["corners"]["configured"])

    def test_worker_and_disposed_host_never_mutate_or_load_native(self):
        results = []
        thread = threading.Thread(target=lambda: results.append(self.configure()))
        thread.start()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results, [False])
        self.host.dispose()
        self.assertFalse(self.configure())
        self.assertEqual(self.api.calls, [])

    def test_default_offscreen_path_does_not_load_dll_or_request_corners(self):
        self.host._corner_api = None
        self.assertFalse(self.configure())
        self.assertEqual(self.api.calls, [])


class DetailAcrylicTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.serial, self.alive, self.paint = 1, True, True
        self.host = SimpleNamespace(
            _handle=123,
            status=lambda: dict(surface_alive=self.alive, surface_serial=self.serial, disposed=False),
            paint_background=lambda: self.paint,
        )
        self.material = DetailAcrylicBackend(self.host, validate=lambda handle: None, api=self.api)

    def test_hidden_setup_uses_dwm_and_cleans_original_identity(self):
        result = self.material.apply(123, enabled=True, policy=dict(state="allowed"))
        self.assertTrue(result["blur_configured"])
        self.assertEqual(result["material"], "desktop-acrylic")
        self.assertEqual(result["backdrop_type"], 3)
        self.assertNotIn("bool_result", result)  # This is DWM, not WCA compatibility blur.
        self.assertFalse(result["compositing_verified"])
        self.assertEqual(self.api.events[:3], [("set", 123, 3), ("extend", 123, (-1, -1, -1, -1)), ("get", 123)])
        self.assertTrue(self.material.close()["cleanup_complete"])
        self.assertEqual(self.api.actual, 1)

    def test_background_paint_failure_clears_instead_of_advertising_glass(self):
        self.paint = False
        result = self.material.apply(123, enabled=True, policy=dict(state="allowed"))
        self.assertFalse(result["blur_configured"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["fallback_reason"], "raster-background-unavailable")
        self.assertEqual(self.api.actual, 1)

    def test_replaced_surface_never_receives_old_material_cleanup(self):
        self.material.apply(123, enabled=True, policy=dict(state="allowed"))
        before = list(self.api.events)
        self.serial = 2
        result = self.material.clear(123)
        self.assertFalse(result["cleanup_complete"])
        self.assertEqual(before, self.api.events)
        self.assertFalse(self.material.close()["complete"])

    def test_disabled_policy_and_non_glass_request_never_enable_acrylic(self):
        for enabled, policy in ((True, dict(state="disabled")), (False, dict(state="allowed"))):
            result = self.material.apply(123, enabled=enabled, policy=policy)
            self.assertFalse(result["blur_configured"])
        self.assertNotIn(("set", 123, 3), self.api.events)


class DetailHostIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_top_bar_runtime as fixture
        cls.fixture = fixture
        fixture.QmlTopBarTests.setUpClass()

    def setUp(self):
        self.case = self.fixture.QmlTopBarTests()
        self.case.setUp()
        self.manager = self.case.manager
        self.api = FakeAPI()
        self.guards = []
        self.hosts = []
        original_make = self.manager._make_window
        original_prepare = self.manager.adapter.prepare
        self.manager.adapter.backend = SimpleNamespace(validate=lambda token: self.guards.append(token.hwnd))

        def make(kind, state, screen, pinned):
            quick = original_make(kind, state, screen, pinned)
            if kind != "details":
                return quick
            host = TopBarBackdropHost(quick, pinned=pinned, close_panel=self.manager.close_panel,
                                      native=False, painter=SimpleNamespace(fill=lambda *args: None))
            host.setMask = lambda _region: None  # Offscreen QPA has no native mask.
            self.hosts.append((host, quick))
            return host

        def prepare(window, screen):
            binding = original_prepare(window, screen)
            binding.token.hwnd = int(window.winId())
            return binding

        self.manager._make_window = make
        self.manager.adapter.prepare = prepare
        self.manager._native_windows = lambda: True
        self.native_guard = patch.object(ctypes, "WinDLL", side_effect=AssertionError("Native API forbidden"))
        self.policy_guard = patch("native_platform.transparency_policy", return_value=dict(state="allowed"))
        self.api_guard = patch("settings_acrylic_material._CtypesAcrylicAPI", return_value=self.api)
        self.accent_guard = patch("native_widget_material._CtypesBlurAPI",
                                  side_effect=AssertionError("DWM details must never load WCA"))
        self.native_guard.start()
        self.policy_guard.start()
        self.api_guard.start()
        self.accent_guard.start()

    def tearDown(self):
        try:
            self.case.tearDown()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        finally:
            self.api_guard.stop()
            self.accent_guard.stop()
            self.policy_guard.stop()
            self.native_guard.stop()

    def test_actual_qml_child_has_prepared_raster_backdrop_on_first_show_and_reopen(self):
        for _ in range(2):
            self.manager._show_panel(self.case.host, "b_0", False)
            self.assertIsNotNone(self.manager._panel, self.manager._errors)
            panel = self.manager._panel
            host, quick = self.hosts[-1]
            self.assertIs(panel["window"], host)
            self.assertIs(quick.parent(), host)
            self.assertEqual(host.format().alphaBufferSize(), 0)
            self.assertEqual(quick.property("nativeHosted"), True)
            report = self.case.host.state.materialReports["details"]
            self.assertEqual(report["material"], "desktop-acrylic")
            self.assertEqual(panel["material_bridge"].bridge.status()["backend"], "desktop-acrylic")
            self.assertEqual(report["preparation"], "before-show")
            self.assertTrue(self.case.host.state.detailCoatingTranslucent)
            self.assertTrue(host.flags() & Qt.WindowDoesNotAcceptFocus)
            self.assertTrue(host.flags() & Qt.WindowStaysOnTopHint)
            self.assertTrue(host.isVisible())
            QTest.qWait(35)
            self.assertTrue(quick.isVisible())
            self.manager.close_panel()
            self.assertTrue(host.status()["disposed"])
            self.assertFalse(quick.isVisible())
            self.assertEqual(self.api.actual, 1)
            self.assertEqual(self.manager.retired, [])

    def test_first_frame_and_settlement_adopt_hidden_dwm_without_native_switch(self):
        self.manager._show_panel(self.case.host, "b_0", False)
        panel = self.manager._panel
        self.assertIsNotNone(panel, self.manager._errors)
        state = self.case.host.state
        self.assertTrue(state.detailCoatingTranslucent)
        self.assertEqual(self.api.events, [("set", panel["binding"].hwnd, 3),
                                          ("extend", panel["binding"].hwnd, (-1, -1, -1, -1)),
                                          ("get", panel["binding"].hwnd)])
        before = list(self.api.events)
        QTest.qWait(600)  # Real offscreen first-frame and finite settle callbacks.
        self.assertEqual(self.api.events, before)
        self.assertTrue(state.detailCoatingTranslucent)
        self.assertEqual(state.materialReports["details"]["material"], "desktop-acrylic")

    def _assert_first_click_recovers_retained_panel(self, state):
        point = self.case.point()
        QTest.mouseClick(self.case.host.window, Qt.LeftButton, Qt.NoModifier, point)
        self.assertIsNotNone(self.manager._panel, self.manager._errors)
        old_host, old_quick = self.hosts[-1]
        QTest.qWait(20)
        self.assertTrue(old_host.isVisible() and old_quick.isVisible())
        if state == "host-hidden":
            old_host.hide()
            self.assertFalse(old_host.isVisible())
        elif state == "client-hidden":
            old_quick.hide()
            # The production host mirrors its child's hidden state synchronously.
            self.assertFalse(old_host.isVisible())
            self.assertFalse(old_quick.isVisible())
        else:
            old_host.setWindowState(Qt.WindowMinimized)
            self.assertEqual(old_host.windowState(), Qt.WindowMinimized)
        QTest.mouseClick(self.case.host.window, Qt.LeftButton, Qt.NoModifier, point)
        self.assertIsNotNone(self.manager._panel, self.manager._errors)
        panel = self.manager._panel
        host = panel["window"]
        quick = host.quick_client
        QTest.qWait(35)
        self.assertTrue(panel["pinned"])
        self.assertTrue(host.isVisible())
        self.assertTrue(quick.isVisible())
        self.assertNotEqual(host.windowState(), Qt.WindowMinimized)
        self.assertEqual(host.size(), quick.size())
        self.assertEqual(self.case.host.state._detail["mode"], "pinned")
        self.assertEqual(self.manager.retired, [])
        QTest.qWait(300)
        self.assertIs(self.manager._panel, panel)
        self.assertTrue(host.isVisible() and quick.isVisible())
        QTest.mouseClick(self.case.host.window, Qt.LeftButton, Qt.NoModifier, point)
        self.assertIsNone(self.manager._panel)

    def test_first_real_click_recovers_a_hidden_pinned_raster_host(self):
        self._assert_first_click_recovers_retained_panel("host-hidden")

    def test_first_real_click_recovers_a_hidden_quick_child_and_its_raster_host(self):
        self._assert_first_click_recovers_retained_panel("client-hidden")

    def test_first_real_click_recovers_a_minimized_pinned_raster_host(self):
        self._assert_first_click_recovers_retained_panel("minimized")

    def test_dynamic_content_size_and_close_do_not_leave_an_empty_host(self):
        # Leave genuine height headroom for this first assertion. The complete
        # trend/summary layout can already reach the 480-DIP work-area cap, in
        # which case expanding metadata must scroll rather than grow the HWND.
        self.case.controller.rows[0].update(history=[], related=[])
        self.manager.update_rows()
        self.manager._show_panel(self.case.host, "b_0", True)
        self.assertIsNotNone(self.manager._panel, self.manager._errors)
        host, quick = self.hosts[-1]
        self.assertFalse(host.flags() & Qt.WindowDoesNotAcceptFocus)
        self.assertTrue(host.flags() & Qt.WindowStaysOnTopHint)
        QTest.qWait(35)
        previous_height = host.height()
        maximum = self.case.host.state.panelMaximumHeight
        self.assertLess(previous_height, maximum)
        quick.setProperty("showMetadata", True)
        # Layout polish and the queued host resize are separate event turns.
        # Await their result under full-suite load, rather than one 25ms tick.
        for _ in range(25):
            if host.height() > previous_height and host.size() == quick.size():
                break
            QTest.qWait(10)
        self.assertGreater(host.height(), previous_height)
        self.assertEqual(host.size(), quick.size())
        self.assertLessEqual(host.height(), maximum)

        # Once content exceeds the cap, retain the same bounded native host and
        # make the additional real delegates and diagnostics reachable inside it.
        self.case.controller.rows[0]["related"] = [
            dict(label=f"Synthetic channel {index}", value=f"{index} W", available=True)
            for index in range(8)
        ]
        self.manager.update_rows()
        scroll = self.case.visual(quick, "topBarDetailScroll")
        self.assertIsNotNone(scroll)
        for _ in range(25):
            if (host.size() == quick.size() and host.height() == maximum
                    and scroll.property("contentHeight") > scroll.height()):
                break
            QTest.qWait(10)
        self.assertEqual(host.size(), quick.size())
        self.assertEqual(host.height(), maximum)
        self.assertGreater(scroll.property("contentHeight"), scroll.height())
        scroll.setProperty("contentY", scroll.property("contentHeight") - scroll.height())
        QTest.qWait(20)
        last = self.case.visual(quick, "topBarRelated_7")
        source = self.case.visual(quick, "topBarDetailSource")
        for item in (last, source):
            self.assertIsNotNone(item)
            self.assertTrue(item.isVisible())
            self.assertGreaterEqual(item.mapToScene(item.boundingRect().topLeft()).y(),
                                    scroll.mapToScene(scroll.boundingRect().topLeft()).y() - 1)
            self.assertLessEqual(item.mapToScene(item.boundingRect().bottomRight()).y(),
                                 scroll.mapToScene(scroll.boundingRect().bottomRight()).y() + 1)
        self.assertEqual(source.property("text"), "Artificial fixture")
        host.close()
        self.assertIsNone(self.manager._panel)
        self.assertTrue(host.status()["disposed"])
        self.assertFalse(quick.isVisible())
        self.assertEqual(self.manager.retired, [])

    def corner_panel(self, result):
        # This verifies real QML geometry and the Manager branch, not material
        # correctness. Its material backend remains outside this test's scope.
        with patch.object(self.manager, "_material_bridge", return_value=None):
            self.manager._show_panel(self.case.host, "b_0", False)
        host, quick = self.hosts[-1]
        masks = []
        mask = QRegion(QRect(0, 0, host.width(), host.height()))

        def set_mask(region):
            nonlocal mask
            mask = QRegion(region)
            masks.append(QRegion(region))

        host.setMask, host.mask = set_mask, lambda: mask
        api = host._corner_api = CornerAPI(host)
        api.result = result
        return host, quick, api, masks

    def test_native_rounding_uses_full_qml_plane_and_never_installs_binary_mask(self):
        host, quick, api, masks = self.corner_panel(0)
        self.manager._position_panel()
        self.assertEqual(len(api.calls), 1)
        self.assertTrue(quick.property("nativeRounded"))
        surface = quick.findChild(QObject, "topBarDetailsMaterialSurface")
        self.assertIsNotNone(surface)
        self.assertEqual(surface.property("cornerRadius"), 0)
        self.assertEqual(len(masks), 1)
        self.assertTrue(masks[0].isEmpty())
        self.manager._position_panel()
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(len(masks), 1)
        self.assertIsNone(self.manager._panel["mask_size"])
        self.assertFalse(host.status()["corners"]["visual_verified"])

    def test_failed_native_rounding_restores_same_size_mask_and_qml_sixteen_radius(self):
        host, quick, api, masks = self.corner_panel(-1)
        self.manager._panel["mask_size"] = (host.width(), host.height())
        self.manager._position_panel()
        self.assertEqual(len(api.calls), 1)
        self.assertFalse(quick.property("nativeRounded"))
        surface = quick.findChild(QObject, "topBarDetailsMaterialSurface")
        self.assertEqual(surface.property("cornerRadius"), 16)
        self.assertEqual(len(masks), 2)
        self.assertTrue(masks[0].isEmpty())
        self.assertFalse(masks[1].isEmpty())
        self.assertFalse(masks[1].contains(QPoint(0, 0)))
        self.assertTrue(masks[1].contains(QPoint(host.width() // 2, host.height() // 2)))
        self.manager._position_panel()
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(len(masks), 2)


if __name__ == "__main__":
    unittest.main()
