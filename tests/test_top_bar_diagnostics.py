"""Read retained detail state without Qt initialization or any native API calls."""
import ast
import json
import math
import unittest
from pathlib import Path
from types import SimpleNamespace


def production_diagnostics():
    """Execute the actual pure method; importing the UI runtime is unnecessary."""
    path = Path(__file__).resolve().parents[1] / "top_bar_runtime.py"
    source = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    manager = next(node for node in source.body if isinstance(node, ast.ClassDef)
                   and node.name == "TopBarManager")
    method = next(node for node in manager.body if isinstance(node, ast.FunctionDef)
                  and node.name == "detail_diagnostics")
    namespace = dict(math=math, Qt=SimpleNamespace(WindowMinimized=1), OVERFLOW="__overflow__")
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["detail_diagnostics"]


DETAIL_DIAGNOSTICS = production_diagnostics()


class RetainedWindow:
    def __init__(self, *, visible=True, exposed=True, minimized=False, client=None,
                 width=336, height=480):
        self.visible, self.exposed, self.minimized = visible, exposed, minimized
        self.quick_client, self.size = client, (width, height)
        self.forbidden_calls = []

    def isVisible(self):
        return self.visible

    def isExposed(self):
        return self.exposed

    def windowState(self):
        return int(self.minimized)

    def width(self):
        return self.size[0]

    def height(self):
        return self.size[1]

    def __getattr__(self, name):
        if name in {"winId", "create", "show", "hide", "destroy", "nativeInterface",
                    "setPosition", "setMask", "requestActivate"}:
            self.forbidden_calls.append(name)
            raise AssertionError("Diagnostics tried to mutate/query a native window")
        raise AttributeError(name)


class DeletedWindow:
    def __getattr__(self, _name):
        raise RuntimeError("Internal C++ object deleted; private C:/private/device.log")


class Timer:
    def __init__(self, active=False):
        self.active = active
        self.forbidden_calls = []

    def isActive(self):
        return self.active

    def __getattr__(self, name):
        self.forbidden_calls.append(name)
        raise AssertionError("Diagnostics must not call timer " + name)


def manager():
    state = SimpleNamespace(_host_id="private-display-id", _detail={"metric": "cpu_usage"})
    host = SimpleNamespace(state=state, closing=False, session=SimpleNamespace(_fullscreen=False))
    value = SimpleNamespace(
        hosts={state._host_id: host}, _notifications={}, _dispatching_fullscreen=False,
        _pending_hover=None, _rows=[dict(id="private-item-id")], _panel=None,
        _hover_timer=Timer(), _close_timer=Timer(), _panel_geometry_timer=Timer(),
        _detail_attempt={}, retired=[], closed=False, paused=False,
    )
    return value, host


class TopBarDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.manager, self.host = manager()

    def read(self):
        result = DETAIL_DIAGNOSTICS(self.manager)
        json.dumps(result, allow_nan=False)  # Reports must remain IPC/JSON-safe.
        return result

    def panel(self, window):
        self.manager._panel = dict(host=self.host, window=window, binding=object(), pinned=True)

    def test_no_panel_reports_absence_without_claiming_window_visibility(self):
        result = self.read()
        self.assertTrue(result["available"])
        self.assertIs(result["panel"]["record_present"], False)
        self.assertIsNone(result["panel"]["host_qt_visible"])
        self.assertIsNone(result["panel"]["client_qt_visible"])
        self.assertIs(result["fullscreen"]["effective"], False)
        self.assertEqual(result["errors"], [])

    def test_parent_and_quick_client_visibility_and_minimization_are_independent(self):
        child = RetainedWindow(visible=False, exposed=False, minimized=True)
        self.panel(RetainedWindow(client=child))
        panel = self.read()["panel"]
        self.assertTrue(panel["record_present"] and panel["current_host"])
        self.assertTrue(panel["binding_present"] and panel["pinned"])
        self.assertTrue(panel["host_qt_visible"] and panel["host_qt_exposed"])
        self.assertIs(panel["host_qt_minimized"], False)
        self.assertTrue(panel["client_present"])
        self.assertIs(panel["client_qt_visible"], False)
        self.assertIs(panel["client_qt_exposed"], False)
        self.assertTrue(panel["client_qt_minimized"])
        self.assertTrue(panel["positive_size"])
        self.assertTrue(panel["detail_data_present"])

        self.manager._panel["window"].visible = False
        self.manager._panel["window"].minimized = True
        child.visible, child.minimized = True, False
        panel = self.read()["panel"]
        self.assertIs(panel["host_qt_visible"], False)
        self.assertTrue(panel["host_qt_minimized"])
        self.assertTrue(panel["client_qt_visible"])
        self.assertIs(panel["client_qt_minimized"], False)

    def test_destroyed_qt_wrapper_is_unknown_and_never_leaks_exception_text(self):
        self.panel(DeletedWindow())
        result = self.read()
        panel = result["panel"]
        for key in ("host_qt_visible", "host_qt_exposed", "host_qt_minimized",
                    "positive_size", "client_qt_visible"):
            self.assertIsNone(panel[key], key)
        self.assertIsNone(panel["client_present"])
        self.assertIn(dict(scope="panel_host", code="qt_object_unavailable"), result["errors"])
        self.assertIn(dict(scope="panel_client", code="state_unavailable"), result["errors"])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("device.log", json.dumps(result))

    def test_absent_or_invalid_getters_do_not_masquerade_as_hidden_healthy_window(self):
        self.panel(SimpleNamespace(isVisible=lambda: 1, isExposed=None,
                                   windowState=lambda: None, width=lambda: 336, height=lambda: 480))
        result = self.read()
        self.assertIsNone(result["panel"]["host_qt_visible"])
        self.assertIsNone(result["panel"]["host_qt_exposed"])
        self.assertIsNone(result["panel"]["host_qt_minimized"])
        self.assertEqual({error["code"] for error in result["errors"]},
                         {"invalid_flag", "getter_unavailable", "getter_failed"})

    def test_replaced_host_and_missing_binding_are_reported_without_following_new_host(self):
        self.panel(RetainedWindow())
        self.manager.hosts[self.host.state._host_id] = SimpleNamespace(
            session=SimpleNamespace(_fullscreen=False))
        self.host.closing = True
        self.manager._panel["binding"] = None
        self.host.state._detail = {}
        panel = self.read()["panel"]
        self.assertIs(panel["current_host"], False)
        self.assertTrue(panel["host_closing"])
        self.assertIs(panel["binding_present"], False)
        self.assertIs(panel["detail_data_present"], False)
        self.assertTrue(panel["host_qt_visible"])

    def test_fullscreen_session_pending_and_dispatch_sources_are_visible_separately(self):
        self.host.session._fullscreen = True
        self.manager._notifications = {"a": {"fullscreen": False}, "b": {"fullscreen": True}}
        self.manager._dispatching_fullscreen = True
        state = self.read()["fullscreen"]
        self.assertTrue(state["effective"])
        self.assertTrue(state["dispatching"])
        self.assertEqual(state["session_active_count"], 1)
        self.assertEqual(state["pending_enter_count"], 1)
        self.assertEqual(state["pending_exit_count"], 1)
        self.host.session._fullscreen = False
        self.manager._notifications = {"a": {"fullscreen": False}}
        self.manager._dispatching_fullscreen = False
        self.assertIs(self.read()["fullscreen"]["effective"], False)

    def test_unknown_or_uninspected_fullscreen_state_does_not_claim_safe_admission(self):
        self.host.session._fullscreen = "not a boolean"
        self.assertIsNone(self.read()["fullscreen"]["effective"])
        self.host.session._fullscreen = False
        self.manager._notifications = {"a": {"fullscreen": 1}}
        self.assertIsNone(self.read()["fullscreen"]["effective"])
        self.manager._notifications = {str(index): {"fullscreen": False} for index in range(17)}
        state = self.read()["fullscreen"]
        self.assertTrue(state["truncated"])
        self.assertIsNone(state["effective"])
        self.host.session._fullscreen = True
        self.assertTrue(self.read()["fullscreen"]["effective"])

    def test_pending_hover_checks_current_target_and_timers_without_exposing_ids(self):
        self.manager._pending_hover = (self.host.state._host_id, "private-item-id")
        self.manager._hover_timer.active = True
        self.manager._close_timer.active = True
        result = self.read()
        self.assertEqual(result["hover"], dict(pending=True, host_current=True,
                                                item_current=True, timer_active=True))
        self.assertTrue(result["close_timer_active"])
        self.assertIs(result["geometry_timer_active"], False)
        self.manager._pending_hover = ("removed-display", "removed-item")
        hover = self.read()["hover"]
        self.assertIs(hover["host_current"], False)
        self.assertIs(hover["item_current"], False)
        self.manager._pending_hover = (self.host.state._host_id, "__overflow__")
        self.assertTrue(self.read()["hover"]["item_current"])
        self.assertNotIn("private-", json.dumps(result))

    def test_last_attempt_is_a_small_allowlisted_record_not_raw_exception_or_paths(self):
        self.manager._detail_attempt = dict(seq=41, kind="click", phase="prepare_native",
                                           outcome="failed", reason="operation_failed",
                                           error="private exception", path="C:/private/settings.json")
        expected = dict(seq=41, kind="click", phase="prepare_native", outcome="failed", reason="operation_failed")
        self.assertEqual(self.read()["last_attempt"], expected)
        self.manager._detail_attempt.update(seq=2**63, kind="C:/private", phase="traceback",
                                            outcome="raw error", reason="adapter secret")
        result = self.read()
        self.assertEqual(result["last_attempt"], dict(seq=2147483647, kind="unknown", phase="unknown",
                                                     outcome="unknown", reason="unknown"))
        self.assertNotIn("private", json.dumps(result))
        for invalid in (-1, True, "41"):
            self.manager._detail_attempt["seq"] = invalid
            self.assertIsNone(self.read()["last_attempt"]["seq"])

    def test_report_is_repeatable_read_only_and_does_not_create_or_query_hwnds(self):
        window = RetainedWindow(client=RetainedWindow())
        self.panel(window)
        calls = []

        def forbidden(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("Status must not create, position or show a window")

        self.manager._make_window = forbidden
        self.manager._material_bridge = forbidden
        self.manager.adapter = SimpleNamespace(prepare=forbidden, show=forbidden, snapshot=forbidden)
        retained_panel, retained_attempt = self.manager._panel, self.manager._detail_attempt
        before = (self.manager.closed, self.manager.paused, self.manager._pending_hover,
                  tuple(self.manager.hosts), tuple(self.manager._notifications))
        first, second = self.read(), self.read()
        self.assertEqual(first, second)
        self.assertIs(self.manager._panel, retained_panel)
        self.assertIs(self.manager._detail_attempt, retained_attempt)
        self.assertEqual(before, (self.manager.closed, self.manager.paused, self.manager._pending_hover,
                                  tuple(self.manager.hosts), tuple(self.manager._notifications)))
        self.assertEqual(calls, [])
        self.assertEqual(window.forbidden_calls, [])
        self.assertEqual(window.quick_client.forbidden_calls, [])
        for timer in (self.manager._hover_timer, self.manager._close_timer, self.manager._panel_geometry_timer):
            self.assertEqual(timer.forbidden_calls, [])

    def test_unavailable_timers_and_invalid_panel_keep_report_bounded_json_safe(self):
        self.manager._panel = "invalid retained record"
        self.manager._hover_timer = DeletedWindow()
        self.manager._close_timer = DeletedWindow()
        self.manager._panel_geometry_timer = DeletedWindow()
        self.manager.closed, self.manager.paused = "bad", 1
        self.manager._dispatching_fullscreen = "bad"
        self.manager.hosts = {str(index): SimpleNamespace(session=SimpleNamespace(_fullscreen="bad"))
                              for index in range(16)}
        result = self.read()
        self.assertTrue(result["panel"]["record_present"])
        self.assertIsNone(result["panel"]["host_qt_visible"])
        self.assertIsNone(result["closed"])
        self.assertIsNone(result["paused"])
        self.assertIsNone(result["close_timer_active"])
        self.assertEqual(len(result["errors"]), 8)
        self.assertTrue(all(set(item) == {"scope", "code"} for item in result["errors"]))

    def test_zero_nonfinite_or_boolean_window_dimensions_never_claim_positive_size(self):
        for size in ((0, 480), (336, float("nan")), (True, 480)):
            with self.subTest(size=size):
                self.panel(RetainedWindow(width=size[0], height=size[1]))
                self.assertIs(self.read()["panel"]["positive_size"], False)


if __name__ == "__main__":
    unittest.main()
