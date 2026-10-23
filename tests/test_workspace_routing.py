"""Offscreen/fake history routes and worker ownership; no native initialization."""

import copy
import os
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QMargins, QRect, Qt
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication

import native_controller as controls
import workspace_tools as tools
from native_runtime import Runtime
from stats_config import DEFAULT
from tests import test_top_bar_runtime as fixtures
from top_bar_layout import PixelRect
from top_bar_runtime import TopBarManager


class WorkspaceRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("History routes must never open native windows")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="synthetic-workspace-route-")
        self.patches = ExitStack()
        self.native = self.patches.enter_context(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.spawn = self.patches.enter_context(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.patches.enter_context(patch.object(tools, "BASE", Path(self.directory.name)))
        self.patches.enter_context(patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)))
        self.patches.enter_context(patch.object(controls, "save", side_effect=AssertionError("No preference write")))
        self.patches.enter_context(patch.object(tools, "save", side_effect=AssertionError("No preference write")))
        self.backend = Mock()
        self.patches.enter_context(patch.object(tools, "HistoryStore", return_value=self.backend))
        self.ui = controls.Controller()
        self.ui._history_backend = self.backend
        self.ui.rescanExternal = Mock()

    def tearDown(self):
        if self.ui.thread is not None and not isinstance(self.ui.thread, threading.Thread):
            self.ui.thread = None  # A synthetic unjoined thread owns no actual resources.
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()
        self.native.assert_not_called()
        self.spawn.assert_not_called()
        self.patches.close()
        self.directory.cleanup()

    def collect(self, count=25, *, fail_history=False):
        self.ui._saved["refresh"] = .01
        sequence, events = 0, []
        case = self

        class Stop:
            stopped = False
            iterations = 0

            def is_set(inner):
                return inner.stopped

            def set(inner):
                inner.stopped = True

            def wait(inner, interval):
                inner.iterations += 1
                if inner.iterations >= count:
                    inner.stopped = True
                return inner.stopped

        def sample():
            nonlocal sequence
            value = dict(time=time.time(), cpu_usage=sequence, sequence=sequence)
            sequence += 1
            return value

        def record(value):
            events.append(("history", value["sequence"]))
            if fail_history:
                raise PermissionError("Synthetic history write denied")

        sampler = SimpleNamespace(sample=Mock(side_effect=sample), write=Mock(), close=Mock())
        self.backend.record.side_effect = record
        self.ui.sampleReady.connect(lambda value: events.append(("emit", value["sequence"])),
                                    Qt.ConnectionType.DirectConnection)
        self.ui.stop = Stop()
        stop_threads, close_threads = [], []
        timer_stop = self.ui._diagnostic_timer.stop
        self.backend.close.side_effect = lambda: close_threads.append(threading.get_ident())
        with (
            patch.object(controls.sensors, "Sampler", return_value=sampler),
            patch.object(case.ui._diagnostic_timer, "stop",
                         side_effect=lambda: stop_threads.append(threading.get_ident()) or timer_stop()),
            patch.object(tools.logging, "exception") as errors,
        ):
            self.ui.start()
            self.ui.thread.join(3)
            self.assertFalse(self.ui.thread.is_alive(), "Synthetic sampling must terminate")
            self.app.processEvents()
        return SimpleNamespace(events=events, sampler=sampler, errors=errors,
                               stop_threads=stop_threads, close_threads=close_threads)

    def test_history_write_failure_does_not_drop_live_emit_or_optional_diagnostic_export(self):
        result = self.collect(fail_history=True)
        self.assertEqual(result.events, [(kind, index) for index in range(25) for kind in ("emit", "history")])
        self.assertEqual(result.sampler.write.call_count, 25)
        self.assertEqual(self.ui.readings["sequence"], 24)
        self.assertEqual(result.errors.call_count, 1)

    def test_worker_finally_closes_history_backend_without_stopping_any_qt_timer(self):
        result = self.collect(count=3)
        result.sampler.close.assert_called_once_with()
        self.assertEqual(len(result.close_threads), 1)
        self.assertNotEqual(result.close_threads[0], threading.get_ident())
        self.assertEqual(result.stop_threads, [])

    def test_close_retains_backend_while_worker_alive_but_stops_ui_diagnostic_timer(self):
        self.ui._diagnostic_timer.start()
        self.assertTrue(self.ui._diagnostic_timer.isActive())
        self.ui.thread = Mock()
        self.ui.thread.is_alive.return_value = True
        self.ui.close()
        self.ui.thread.join.assert_called_once_with(timeout=4)
        self.backend.close.assert_not_called()
        self.assertFalse(self.ui._diagnostic_timer.isActive(), "Closing UI-owned timers cannot wait for worker exit")
        self.ui.thread.is_alive.return_value = False
        self.ui.close()
        self.backend.close.assert_called_once_with()


class TopBarHistoryRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("History routes require the offscreen platform")

    def setUp(self):
        self.patches = ExitStack()
        self.native = self.patches.enter_context(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.spawn = self.patches.enter_context(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.menu = self.patches.enter_context(patch("top_bar_runtime.QMenu", side_effect=AssertionError("No menu")))
        self.controller = fixtures.Controller()
        self.controller.openHistoryMetric = Mock()
        self.adapter = fixtures.Adapter()
        self.settings = []
        screens = [fixtures.Screen("DISPLAY1", PixelRect(0, 0, 1920, 1080))]
        runtime = SimpleNamespace(app=fixtures.Application(screens), controller=self.controller,
                                  headless=True, show_settings=self.settings.append)
        self.manager = TopBarManager(runtime, adapter=self.adapter, window_factory=fixtures.Window)
        config = fixtures.config()
        config["top_bar"]["items"] = [
            dict(id="b_0", metric="gpu_usage", prefs=dict(gpu_target="1", precision="2")),
            dict(id="b_1", metric="net_download", prefs=dict(network_target="synthetic-nic", network_unit="Mbps")),
        ]
        self.controller.rows = fixtures.rows(2)
        self.manager.apply(config)
        self.host = self.manager.hosts["DISPLAY1"]

    def tearDown(self):
        self.manager.close()
        self.native.assert_not_called()
        self.spawn.assert_not_called()
        self.menu.assert_not_called()
        self.patches.close()

    def test_detail_view_state_routes_exact_metric_and_current_device_preferences(self):
        self.host.state._detail = dict(id="b_0")
        self.host.state.openHistory()
        self.controller.openHistoryMetric.assert_called_once_with("gpu_usage", dict(gpu_target="1", precision="2"))
        self.host.state._detail = dict(id="b_1")
        self.host.state.openHistory()
        self.controller.openHistoryMetric.assert_called_with(
            "net_download", dict(network_target="synthetic-nic", network_unit="Mbps"))

    def test_panel_cleanup_callback_that_closes_manager_cannot_reopen_history_settings(self):
        self.host.state._detail = dict(id="b_0")
        original, fired = self.manager.close_panel, False

        def close_and_shutdown():
            nonlocal fired
            original()
            if not fired:
                fired = True
                self.manager.close()

        with patch.object(self.manager, "close_panel", side_effect=close_and_shutdown):
            self.host.state.openHistory()
        self.assertTrue(self.manager.closed)
        self.controller.openHistoryMetric.assert_not_called()
        self.assertEqual(self.settings, [])

    def test_replaced_screen_generation_cannot_dispatch_the_old_detail_route(self):
        self.host.state._detail = dict(id="b_0")
        original = self.manager.close_panel

        def replace_host():
            original()
            self.manager.hosts["DISPLAY1"] = SimpleNamespace(closing=False)

        try:
            with patch.object(self.manager, "close_panel", side_effect=replace_host):
                self.manager.open_history("DISPLAY1")
            self.controller.openHistoryMetric.assert_not_called()
            self.assertEqual(self.settings, [])
        finally:
            self.manager.hosts["DISPLAY1"] = self.host

    def test_closed_manager_rejects_queued_history_button_and_unknown_item_has_generic_route(self):
        self.host.state._detail = dict(id="removed-item")
        self.host.state.openHistory()
        self.assertEqual(self.settings, ["__history__"])
        self.controller.openHistoryMetric.assert_not_called()
        self.manager.close()
        self.host.state.openHistory()
        self.assertEqual(self.settings, ["__history__"])


class NativeHistorySettingsRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Settings routes require the offscreen platform")

    def setUp(self):
        self.runtime, self.settings = self.make_runtime()

    @staticmethod
    def make_runtime():
        settings = Mock()
        settings.isVisible.return_value = True
        settings.x.return_value = settings.y.return_value = 50
        settings.width.return_value = 900
        settings.height.return_value = 600
        screen = fixtures.Screen("DISPLAY1", PixelRect(0, 0, 1920, 1080))
        runtime = SimpleNamespace(settings=settings, settings_host=None,
            app=fixtures.Application([screen]), controller=Mock(), compose=Mock(), shutting_down=False)
        return runtime, settings

    def test_history_id_and_generic_history_routes_do_not_select_a_desktop_widget(self):
        Runtime.show_settings(self.runtime, "__history__:h_synthetic")
        self.settings.selectHistory.assert_called_once_with("h_synthetic")
        self.settings.selectWidget.assert_not_called()
        self.settings.showNormal.assert_called_once_with()
        Runtime.show_settings(self.runtime, "__history__")
        self.settings.setProperty.assert_called_with("page", 4)

    def test_queued_history_route_cannot_reopen_settings_after_runtime_shutdown(self):
        self.runtime.shutting_down = True
        Runtime.show_settings(self.runtime, "__history__:h_synthetic")
        self.settings.selectHistory.assert_not_called()
        self.settings.showNormal.assert_not_called()
        self.runtime.controller.inspect.assert_not_called()

    def test_history_selection_callback_that_shuts_down_cannot_then_show_the_released_settings(self):
        self.settings.selectHistory.side_effect = lambda _identifier: setattr(self.runtime, "shutting_down", True)
        Runtime.show_settings(self.runtime, "__history__:h_synthetic")
        self.assertTrue(self.runtime.shutting_down)
        self.settings.showNormal.assert_not_called()
        self.runtime.controller.inspect.assert_not_called()

    def test_inspect_callback_shutdown_prevents_all_window_presentation(self):
        self.runtime.controller.inspect.side_effect = lambda: setattr(self.runtime, "shutting_down", True)
        Runtime.show_settings(self.runtime, "__history__:h_synthetic")
        self.settings.showNormal.assert_not_called()
        self.runtime.compose.assert_not_called()
        self.settings.raise_.assert_not_called()
        self.settings.requestActivate.assert_not_called()

    def test_show_callback_shutdown_prevents_compose_raise_and_activation(self):
        self.settings.showNormal.side_effect = lambda: setattr(self.runtime, "shutting_down", True)
        Runtime.show_settings(self.runtime, "__history__:h_synthetic")
        self.runtime.compose.assert_not_called()
        self.settings.raise_.assert_not_called()
        self.settings.requestActivate.assert_not_called()

    def test_compose_callback_shutdown_prevents_raise_and_activation(self):
        self.runtime.compose.side_effect = lambda *_: setattr(self.runtime, "shutting_down", True)
        Runtime.show_settings(self.runtime, "__history__:h_synthetic")
        self.settings.raise_.assert_not_called()
        self.settings.requestActivate.assert_not_called()

    def test_inspect_show_compose_callbacks_cannot_present_a_replaced_host_generation(self):
        for stage in ("inspect", "show", "compose"):
            with self.subTest(stage=stage):
                runtime, settings = self.make_runtime()
                callback = {"inspect": runtime.controller.inspect,
                            "show": settings.showNormal, "compose": runtime.compose}[stage]
                callback.side_effect = lambda *_: setattr(runtime, "settings_host", Mock())
                Runtime.show_settings(runtime, "__history__:h_synthetic")
                settings.raise_.assert_not_called()
                settings.requestActivate.assert_not_called()
                if stage == "inspect":
                    settings.showNormal.assert_not_called()
                if stage in ("inspect", "show"):
                    runtime.compose.assert_not_called()

    def test_inspect_show_compose_callbacks_cannot_present_replaced_settings_content(self):
        for stage in ("inspect", "show", "compose"):
            with self.subTest(stage=stage):
                runtime, settings = self.make_runtime()
                replacement = Mock()
                callback = {"inspect": runtime.controller.inspect,
                            "show": settings.showNormal, "compose": runtime.compose}[stage]
                callback.side_effect = lambda *_: setattr(runtime, "settings", replacement)
                Runtime.show_settings(runtime, "__history__:h_synthetic")
                settings.raise_.assert_not_called()
                settings.requestActivate.assert_not_called()
                replacement.showNormal.assert_not_called()
                replacement.raise_.assert_not_called()
                replacement.requestActivate.assert_not_called()

    def test_compose_callback_that_disposes_same_host_does_not_raise_or_activate_it(self):
        host = Mock()
        disposed = {"value": False}
        host.status.side_effect = lambda: dict(disposed=disposed["value"])
        host.frameMargins.return_value = QMargins(0, 0, 0, 0)
        host.frameGeometry.return_value = QRect(50, 50, 900, 600)
        host.isVisible.return_value = True
        self.runtime.settings_host = host
        self.runtime.compose.side_effect = lambda *_: disposed.update(value=True)
        Runtime.show_settings(self.runtime, "__history__:h_synthetic")
        host.showNormal.assert_called_once_with()
        host.raise_.assert_not_called()
        host.requestActivate.assert_not_called()

    def test_host_creation_shutdown_callback_cannot_reposition_the_released_host(self):
        host = Mock()
        host.status.return_value = dict(disposed=False)
        host.frameMargins.return_value = QMargins(0, 0, 0, 0)
        host.frameGeometry.return_value = QRect(50, 50, 900, 600)
        host.isVisible.return_value = True
        host.create.side_effect = lambda: setattr(self.runtime, "shutting_down", True)
        self.runtime.settings_host = host
        Runtime.show_settings(self.runtime, "__history__:h_synthetic")
        host.create.assert_called_once_with()
        self.assertTrue(self.runtime.shutting_down)
        host.frameMargins.assert_not_called()
        host.setFramePosition.assert_not_called()
        host.showNormal.assert_not_called()

    def test_hidden_offscreen_qt_geometry_signals_reenter_before_resize_or_position_returns(self):
        # These windows are never created or shown. Actual Qt width/x signals,
        # rather than a mock-only assumption, establish synchronous reentry.
        for signal, operation in (("widthChanged", "resize"), ("xChanged", "setPosition")):
            with self.subTest(operation=operation):
                window, events = QWindow(), []
                try:
                    getattr(window, signal).connect(lambda *_: events.append("callback"))
                    if operation == "resize":
                        window.resize(320, 180)
                    else:
                        window.setPosition(25, 30)
                    events.append("returned")
                    self.assertEqual(events, ["callback", "returned"])
                    self.assertFalse(window.isVisible())
                finally:
                    window.destroy()
                    window.deleteLater()
        self.app.processEvents()

    def test_host_resize_callback_shutdown_or_disposal_prevents_later_position_and_presentation(self):
        for mode in ("shutdown", "disposed"):
            with self.subTest(mode=mode):
                runtime, settings = self.make_runtime()
                host, disposed = Mock(), {"value": False}
                host.status.side_effect = lambda: dict(disposed=disposed["value"])
                host.frameMargins.return_value = QMargins(0, 0, 0, 0)
                host.isVisible.return_value = False
                runtime.settings_host = host
                host.resize.side_effect = lambda *_: (setattr(runtime, "shutting_down", True)
                    if mode == "shutdown" else disposed.update(value=True))
                Runtime.show_settings(runtime, "__history__:h_synthetic")
                host.resize.assert_called_once()
                host.frameGeometry.assert_not_called()
                host.setFramePosition.assert_not_called()
                host.showNormal.assert_not_called()
                host.raise_.assert_not_called()
                host.requestActivate.assert_not_called()

    def test_host_position_callback_shutdown_or_disposal_prevents_later_presentation(self):
        for visible in (True, False):
            for mode in ("shutdown", "disposed"):
                with self.subTest(mode=mode, visible=visible):
                    runtime, settings = self.make_runtime()
                    host, disposed = Mock(), {"value": False}
                    host.status.side_effect = lambda: dict(disposed=disposed["value"])
                    host.frameMargins.return_value = QMargins(0, 0, 0, 0)
                    host.frameGeometry.return_value = QRect(50, 50, 900, 600)
                    host.isVisible.return_value = visible
                    runtime.settings_host = host
                    host.setFramePosition.side_effect = lambda *_: (setattr(runtime, "shutting_down", True)
                        if mode == "shutdown" else disposed.update(value=True))
                    Runtime.show_settings(runtime, "__history__:h_synthetic")
                    host.setFramePosition.assert_called_once()
                    host.showNormal.assert_not_called()
                    host.raise_.assert_not_called()
                    host.requestActivate.assert_not_called()
                    runtime.compose.assert_not_called()

    def test_quick_resize_and_position_shutdown_callbacks_cannot_show_or_activate_window(self):
        for stage in ("resize", "position"):
            with self.subTest(stage=stage):
                runtime, settings = self.make_runtime()
                settings.isVisible.return_value = False
                action = settings.resize if stage == "resize" else settings.setPosition
                action.side_effect = lambda *_: setattr(runtime, "shutting_down", True)
                Runtime.show_settings(runtime, "__history__:h_synthetic")
                action.assert_called_once()
                settings.showNormal.assert_not_called()
                settings.raise_.assert_not_called()
                settings.requestActivate.assert_not_called()
                runtime.compose.assert_not_called()
                if stage == "resize":
                    settings.setPosition.assert_not_called()

    def test_raise_callback_that_shuts_down_or_replaces_host_does_not_activate_window(self):
        for field, value in (("shutting_down", True), ("settings_host", Mock())):
            with self.subTest(field=field):
                runtime, settings = self.make_runtime()
                settings.raise_.side_effect = lambda *_: setattr(runtime, field, value)
                Runtime.show_settings(runtime, "__history__:h_synthetic")
                settings.raise_.assert_called_once_with()
                settings.requestActivate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
