"""Owned bar shutdown reentry/retirement; only fake windows and native boundaries."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtWidgets import QApplication

from appbar_platform import AppBarError
from tests.test_top_bar_runtime import Adapter, Application, Controller, Screen, Window, config
from top_bar_layout import PixelRect
from top_bar_runtime import TopBarManager, WindowPreparationError


class Material:
    def __init__(self):
        self.fail = False
        self.closed = self.deleted = 0
        self.on_close = None
        self.binding = None
        self.on_bind = None

    def bind(self, binding):
        self.binding = binding
        if self.on_bind:
            self.on_bind()

    def close(self):
        self.closed += 1
        callback, self.on_close = self.on_close, None
        if callback:
            callback()
        if self.fail:
            raise AppBarError("synthetic material clear pending")

    def deleteLater(self):
        self.deleted += 1

    def status(self):
        return {}


class ShutdownAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.fail_hide = False
        self.hide_attempts = 0

    def hide(self, binding):
        self.hide_attempts += 1
        if self.fail_hide:
            raise AppBarError("synthetic bar hide pending")
        super().hide(binding)


class TopBarShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise AssertionError("Shutdown tests must never use native windows")

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.menu = self.enterContext(patch("top_bar_runtime.QMenu", side_effect=AssertionError("No visible menus")))
        self.controller, self.adapter = Controller(), ShutdownAdapter()
        screens = [Screen("DISPLAY1", PixelRect(-1920, -200, 0, 880)),
                   Screen("DISPLAY2", PixelRect(0, 0, 2560, 1440), dpi=144)]
        self.settings, self.windows = [], []
        runtime = SimpleNamespace(app=Application(screens), controller=self.controller,
                                  headless=True, show_settings=self.settings.append)

        def make(*args):
            window = Window(*args)
            self.windows.append(window)
            return window

        self.manager = TopBarManager(runtime, adapter=self.adapter, window_factory=make)
        self.manager.apply(config())
        self.host = self.manager.hosts["DISPLAY1"]
        self.binding, self.session = self.host.binding, self.host.session
        self.material = Material()
        self.host.material_bridge = self.material

    def tearDown(self):
        self.material.fail, self.material.on_close = False, None
        self.adapter.fail_hide = self.adapter.fail_close = False
        # Explicitly clean only our fake records even when the old close()
        # implementation fails and its closed flag prevents another attempt.
        self.manager._close_hosts()
        self.manager._retry_retired()
        self.manager.close()
        self.assertEqual(self.native.call_count, 0)
        self.assertEqual(self.process.call_count, 0)
        self.assertEqual(self.menu.call_count, 0)

    def retained(self):
        self.assertEqual(self.manager.retired, [self.host])
        self.assertIs(self.host.binding, self.binding)
        self.assertIs(self.host.session, self.session)
        self.assertTrue(self.session.active)
        self.assertFalse(self.host.window.deleted)
        self.assertNotIn(("release", "bar", "DISPLAY1"), self.adapter.events)

    def test_close_blocks_material_callback_from_reopening_bar_or_settings(self):
        self.manager.apply(config(mode="all"))
        created, shows = len(self.windows), list(self.adapter.shows)

        def reopen():
            self.manager.apply(config(mode="all"))
            self.manager.hover("DISPLAY2", "b_0")
            self.manager.click("DISPLAY2", "b_0")
            self.manager.focus_details()
            self.manager.open_settings()
            self.manager.menu("DISPLAY2")

        self.material.on_close = reopen
        self.manager.close()
        self.assertTrue(self.manager.closed)
        self.assertEqual(self.manager.hosts, {})
        self.assertEqual(self.manager.retired, [])
        self.assertEqual(len(self.windows), created)
        self.assertEqual(self.adapter.shows, shows)
        self.assertEqual(self.settings, [])
        self.assertFalse(self.manager._hover_timer.isActive())
        self.assertTrue(all(window.deleted and not window.visible for window in self.windows))

    def test_close_blocks_same_screen_replacement_and_is_reentrant_idempotent(self):
        created = len(self.windows)

        def reopen():
            self.manager.apply(config())
            self.manager.close()

        self.material.on_close = reopen
        self.manager.close()
        self.assertEqual(len(self.windows), created)
        self.assertEqual(self.manager.hosts, {})
        self.assertEqual(self.manager.retired, [])
        events = list(self.adapter.events)
        self.manager.close()
        self.assertEqual(self.adapter.events, events)
        self.assertEqual(self.material.deleted, 1)

    def test_material_failure_hides_bar_and_retains_exact_resources_until_retry(self):
        self.material.fail = True
        self.manager.pause()
        self.assertFalse(self.host.window.visible)
        self.assertGreater(self.adapter.hide_attempts, 0)
        self.assertGreater(self.material.closed, 0)
        self.assertEqual(self.material.deleted, 0)
        self.assertIs(self.host.material_bridge, self.material)
        self.retained()
        self.assertNotIn(("remove", "DISPLAY1"), self.adapter.events)
        self.material.fail = False
        self.manager._retry_retired()
        self.assertEqual(self.manager.retired, [])
        self.assertTrue(self.host.window.deleted)
        self.assertFalse(self.session.active)
        self.assertEqual(self.material.deleted, 1)
        self.assertEqual(self.adapter.events.count(("release", "bar", "DISPLAY1")), 1)

    def test_hide_failure_still_attempts_material_but_keeps_reservation_and_token(self):
        self.adapter.fail_hide = True
        self.manager.pause()
        self.assertEqual(self.material.closed, 1)
        self.assertEqual(self.material.deleted, 1)
        self.retained()
        self.assertNotIn(("remove", "DISPLAY1"), self.adapter.events)
        self.adapter.fail_hide = False
        self.manager._retry_retired()
        self.assertFalse(self.host.window.visible)
        self.assertTrue(self.host.window.deleted)
        self.assertEqual(self.material.closed, 1, "A confirmed material clear must not repeat")
        self.assertEqual(self.manager.retired, [])

    def test_hide_and_material_failures_are_both_attempted_before_retirement(self):
        self.adapter.fail_hide = self.material.fail = True
        self.manager.pause()
        self.assertGreater(self.adapter.hide_attempts, 0)
        self.assertEqual(self.material.closed, 1)
        self.assertEqual(self.material.deleted, 0)
        self.retained()
        self.adapter.fail_hide = self.material.fail = False
        self.manager._retry_retired()
        self.assertEqual(self.manager.retired, [])
        self.assertFalse(self.host.window.visible)
        self.assertTrue(self.host.window.deleted)

    def test_closed_manager_can_retry_material_cleanup_without_reopening(self):
        self.material.fail = True
        self.manager.close()
        self.assertTrue(self.manager.closed)
        self.assertFalse(self.host.window.visible)
        self.retained()
        self.assertEqual(self.controller.status["state"], "failed")
        created, shows = len(self.windows), list(self.adapter.shows)
        self.material.fail = False
        self.material.on_close = lambda: self.manager.apply(config(mode="all"))
        self.manager.close()
        self.assertEqual(self.manager.retired, [])
        self.assertEqual(self.manager.hosts, {})
        self.assertEqual(self.controller.status["state"], "disabled")
        self.assertEqual(len(self.windows), created)
        self.assertEqual(self.adapter.shows, shows)
        self.assertEqual(self.material.deleted, 1)

    def test_closed_manager_can_retry_unregister_without_repeating_material_clear(self):
        self.adapter.fail_close = True
        self.manager.close()
        self.assertFalse(self.host.window.visible)
        self.retained()
        self.assertEqual(self.material.closed, 1)
        self.adapter.fail_close = False
        self.manager.close()
        self.assertEqual(self.manager.retired, [])
        self.assertFalse(self.session.active)
        self.assertTrue(self.host.window.deleted)
        self.assertEqual(self.material.closed, 1)
        self.assertEqual(self.adapter.events.count(("release", "bar", "DISPLAY1")), 1)

    def test_close_during_prepare_cleans_inflight_host_without_registering_or_showing(self):
        self.manager.pause()
        prepare = self.adapter.prepare
        shows = list(self.adapter.shows)

        def close_after_prepare(window, screen):
            binding = prepare(window, screen)
            self.manager.close()
            return binding

        self.adapter.prepare = close_after_prepare
        self.manager.resume()
        self.assertTrue(self.manager.closed)
        self.assertEqual(self.manager.hosts, {})
        self.assertEqual(self.manager.retired, [])
        self.assertEqual(self.adapter.shows, shows)
        self.assertTrue(all(window.deleted and not window.visible for window in self.windows))

    def test_close_during_snapshot_cannot_relayout_or_show_a_released_host(self):
        snapshot = self.adapter.snapshot
        shows = list(self.adapter.shows)

        def close_after_snapshot(binding):
            result = snapshot(binding)
            self.manager.close()
            return result

        self.adapter.snapshot = close_after_snapshot
        self.adapter.offset = 1
        self.manager.apply(config())
        self.assertTrue(self.manager.closed)
        self.assertEqual(self.manager.hosts, {})
        self.assertEqual(self.manager.retired, [])
        self.assertFalse(self.session.active)
        self.assertEqual(self.adapter.shows, shows)
        self.assertTrue(all(window.deleted and not window.visible for window in self.windows))

    def assert_closed_details_clean(self, shows):
        self.assertTrue(self.manager.closed)
        self.assertEqual(self.manager.hosts, {})
        self.assertEqual(self.manager.retired, [])
        self.assertIsNone(self.manager._panel)
        self.assertEqual(self.adapter.shows, shows)
        self.assertTrue(all(window.deleted and not window.visible for window in self.windows))
        self.manager.close()
        self.assertIsNone(self.manager._panel)

    def test_close_during_detail_prepare_cleans_the_late_owned_binding(self):
        prepare = self.adapter.prepare
        shows = list(self.adapter.shows)
        bindings = []

        def close_after_prepare(window, screen):
            binding = prepare(window, screen)
            if window.kind == "details":
                bindings.append(binding)
                self.manager.close()
            return binding

        self.adapter.prepare = close_after_prepare
        self.manager.click("DISPLAY1", "b_0")
        self.assert_closed_details_clean(shows)
        self.assertEqual(len(bindings), 1)
        self.assertEqual(self.adapter.events.count(("release", "details", "DISPLAY1")), 1)

    def test_close_during_detail_window_creation_never_prepares_or_shows_it(self):
        make = self.manager._window_factory
        shows = list(self.adapter.shows)

        def close_after_creation(*args):
            window = make(*args)
            if window.kind == "details":
                self.manager.close()
            return window

        self.manager._window_factory = close_after_creation
        self.manager.click("DISPLAY1", "b_0")
        self.assert_closed_details_clean(shows)
        self.assertNotIn(("prepare", "details", "DISPLAY1"), self.adapter.events)

    def test_close_during_detail_material_creation_still_owns_and_clears_that_material(self):
        shows = list(self.adapter.shows)
        material = Material()

        def close_after_material(*_args):
            self.manager.close()
            return material

        with patch.object(self.manager, "_material_bridge", side_effect=close_after_material):
            self.manager.click("DISPLAY1", "b_0")
        self.assert_closed_details_clean(shows)
        self.assertEqual((material.closed, material.deleted), (1, 1))
        self.assertNotIn(("prepare", "details", "DISPLAY1"), self.adapter.events)

    def test_close_during_detail_bind_keeps_the_returned_binding_for_cleanup(self):
        shows = list(self.adapter.shows)
        material = Material()
        material.on_bind = self.manager.close
        with patch.object(self.manager, "_material_bridge", return_value=material):
            self.manager.click("DISPLAY1", "b_0")
        self.assert_closed_details_clean(shows)
        self.assertIsNotNone(material.binding)
        self.assertEqual((material.closed, material.deleted), (1, 1))
        self.assertEqual(self.adapter.events.count(("release", "details", "DISPLAY1")), 1)

    def test_partial_detail_prepare_after_close_retains_failed_material_until_retry(self):
        shows = list(self.adapter.shows)
        prepare = self.adapter.prepare
        material = Material()
        material.fail = True
        bindings = []

        def partial_after_close(window, screen):
            binding = prepare(window, screen)
            if window.kind == "details":
                bindings.append(binding)
                self.manager.close()
                raise WindowPreparationError("synthetic retained detail generation", binding)
            return binding

        self.adapter.prepare = partial_after_close
        with patch.object(self.manager, "_material_bridge", return_value=material):
            self.manager.click("DISPLAY1", "b_0")
        self.assertTrue(self.manager.closed)
        self.assertIsNone(self.manager._panel)
        self.assertEqual(len(self.manager.retired), 1)
        pending = self.manager.retired[0]
        self.assertIs(pending["binding"], bindings[0])
        self.assertIs(pending["material_bridge"], material)
        self.assertIs(material.binding, bindings[0])
        self.assertFalse(pending["window"].deleted)
        self.assertFalse(pending["window"].visible)
        self.assertEqual(material.deleted, 0)
        self.assertNotIn(("release", "details", "DISPLAY1"), self.adapter.events)
        self.assertEqual(self.controller.status["state"], "failed")
        material.fail = False
        self.manager.close()
        self.assert_closed_details_clean(shows)
        self.assertEqual(material.deleted, 1)
        self.assertEqual(self.adapter.events.count(("release", "details", "DISPLAY1")), 1)

    def test_detail_bind_error_preserves_actual_binding_and_material_until_dispose_succeeds(self):
        material = Material()
        material.fail = True
        material.on_bind = lambda: (_ for _ in ()).throw(AppBarError("synthetic bind failure"))
        with patch.object(self.manager, "_material_bridge", return_value=material):
            self.manager.click("DISPLAY1", "b_0")
        self.assertIsNone(self.manager._panel)
        self.assertEqual(len(self.manager.retired), 1)
        pending = self.manager.retired[0]
        self.assertIs(pending["binding"], material.binding)
        self.assertIsNotNone(pending["binding"])
        self.assertIs(pending["material_bridge"], material)
        self.assertFalse(pending["window"].deleted)
        self.assertNotIn(("release", "details", "DISPLAY1"), self.adapter.events)
        material.fail, material.on_bind = False, None
        self.manager._retry_retired()
        self.assertEqual(self.manager.retired, [])
        self.assertTrue(pending["window"].deleted)
        self.assertIsNone(pending["binding"])
        self.assertEqual(material.deleted, 1)

    def detail_that_closes_manager_on_clear(self):
        self.manager.click("DISPLAY1", "b_0")
        self.assertIsNotNone(self.manager._panel)
        material = Material()
        material.on_close = self.manager.close
        self.manager._panel["material_bridge"] = material

    def test_open_settings_rechecks_admission_after_detail_cleanup_callback(self):
        self.detail_that_closes_manager_on_clear()
        self.manager.open_settings()
        self.assertTrue(self.manager.closed)
        self.assertEqual(self.settings, [])
        self.assertIsNone(self.manager._panel)

    def test_menu_rechecks_admission_after_detail_cleanup_callback(self):
        self.detail_that_closes_manager_on_clear()
        self.manager.menu("DISPLAY1")
        self.assertTrue(self.manager.closed)
        self.menu.assert_not_called()
        self.assertIsNone(self.manager._menu)

    def test_menu_rechecks_admission_after_old_menu_close_callback(self):
        disposed = []
        self.manager._menu = SimpleNamespace(close=self.manager.close, deleteLater=lambda: disposed.append(True))
        self.manager.menu("DISPLAY1")
        self.assertTrue(self.manager.closed)
        self.assertEqual(disposed, [True])
        self.menu.assert_not_called()
        self.assertIsNone(self.manager._menu)


if __name__ == "__main__":
    unittest.main()
