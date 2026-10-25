"""Shell replacement recovery over the real manager methods; no Qt or DLL load."""

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


def manager_type():
    path = Path(__file__).resolve().parents[1] / "top_bar_runtime.py"
    module = ast.parse(path.read_text(encoding="utf-8-sig"))
    owner = next(node for node in module.body if isinstance(node, ast.ClassDef)
                 and node.name == "TopBarManager")
    names = {"_read_shell_identity", "_sync_host", "_refresh", "native_message", "_fullscreen_active"}
    methods = [node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(methods) == len(names)
    namespace = dict(AppBarError=RuntimeError, ABN_POSCHANGED=1, ABN_FULLSCREENAPP=2,
                     WM_ACTIVATE=6, WM_WINDOWPOSCHANGED=71, WM_DPICHANGED=736,
                     WM_DISPLAYCHANGE=126, WM_NCDESTROY=130)
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), "exec"), namespace)
    return type("ManagerMethods", (), {name: namespace[name] for name in names})


class Session:
    def __init__(self, host):
        self.host = host
        self._fullscreen = False
        self.on_recreate = None
        self.resets = []

    def register(self, monitor, **options):
        return NS(ready=True, physical_rect=monitor, errors=())

    relayout = register

    def shell_recreated(self, epoch, *, invalidate_fullscreen=False):
        self.resets.append((epoch, invalidate_fullscreen))
        if invalidate_fullscreen:
            self._fullscreen = False
        if self.on_recreate:
            self.on_recreate()
        return NS(ready=True, physical_rect=self.host.binding.monitor, errors=())

    def fullscreen(self, value):
        self._fullscreen = value
        return NS(ok=True)

    def notify_activation(self, active):
        return NS(ok=True)

    def notify_window_position(self):
        return NS(ok=True)


class Adapter:
    taskbar_message, callback_message = 0xC001, 0xC002

    def __init__(self):
        self.identity = (10, 100)
        self.reads, self.shown_fullscreen = 0, []

    def shell_identity(self):
        self.reads += 1
        if isinstance(self.identity, Exception):
            raise self.identity
        return self.identity

    def snapshot(self, binding):
        pass

    def proposed_band(self, binding, height):
        return binding.monitor

    def show(self, binding, *, activate=False):
        self.shown_fullscreen.append((binding.hwnd, binding.host.session._fullscreen))


class ShellRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.manager = manager_type()()
        manager = self.manager
        manager.adapter = Adapter()
        manager.closed = manager.paused = manager._shell_pending = False
        manager._shell_epoch = manager._shell_notice_serial = 0
        manager._shell_identity, manager._shell_identity_observed = None, False
        manager._dispatching_fullscreen = False
        manager._notifications, manager._errors = {}, []
        manager._config = {"top_bar": {"height": 32}}
        manager.hosts = {}
        manager.panel_closes = 0
        manager.close_panel = self.close_panel
        manager._layout = lambda host: None
        manager.refresh = lambda: None
        manager._status = lambda *args: None
        manager._drop = lambda name: manager.hosts.pop(name)
        self.add_host("a", 101)

    def close_panel(self):
        self.manager.panel_closes += 1

    def add_host(self, name, hwnd):
        host = NS(closing=False, state=NS(_host_id=name), rect=None, shell_epoch=0,
                  applied_monitor=None, applied_dpi=None, applied_height=None)
        host.binding = NS(hwnd=hwnd, monitor=(0, 0, 1920, 32), dpi=96, host=host)
        host.session = Session(host)
        self.manager.hosts[name] = host
        self.manager._sync_host(host)
        return host

    def event(self, message, *, value=0, host="a"):
        record = self.manager.hosts[host]
        self.manager.native_message(record.binding.hwnd, message,
                                    2 if message == self.manager.adapter.callback_message else 0,
                                    value)

    def fullscreen(self, value=True, host="a"):
        self.event(self.manager.adapter.callback_message, value=int(value), host=host)

    def shell(self, identity):
        self.manager.adapter.identity = identity
        self.event(self.manager.adapter.taskbar_message)

    def test_known_replacement_releases_old_fullscreen_guard_on_all_hosts(self):
        other = self.add_host("b", 102)
        self.fullscreen()
        self.fullscreen(host="b")
        self.manager._refresh()
        self.assertTrue(self.manager._fullscreen_active())
        self.shell((20, 200))
        self.manager._refresh()
        self.assertFalse(self.manager._fullscreen_active())
        self.assertFalse(other.session._fullscreen)
        self.assertEqual(self.manager.hosts["a"].session.resets, [(1, True)])
        self.assertEqual(other.session.resets, [(1, True)])
        self.assertEqual(self.manager._errors, [])

    def test_same_shell_dpi_broadcast_preserves_fullscreen_guard(self):
        self.fullscreen()
        self.manager._refresh()
        self.shell((10, 100))
        self.manager._refresh()
        self.assertTrue(self.manager._fullscreen_active())
        self.assertEqual(self.manager.hosts["a"].session.resets, [])
        self.assertTrue(self.manager.hosts["a"].session._fullscreen)

    def test_unknown_or_failed_shell_identity_never_clears_guard(self):
        self.fullscreen()
        self.manager._refresh()
        for identity in (None, OSError("synthetic metadata failure")):
            with self.subTest(identity=identity):
                self.shell(identity)
                self.manager._refresh()
                self.assertTrue(self.manager._fullscreen_active())
                self.assertEqual(self.manager._errors, [])

    def test_missing_initial_identity_does_not_guess_replacement(self):
        self.manager._shell_identity = None
        self.fullscreen()
        self.manager._refresh()
        self.shell((20, 200))
        self.manager._refresh()
        self.assertTrue(self.manager._fullscreen_active())

    def test_queued_old_enter_is_ignored_only_after_verified_replacement(self):
        self.fullscreen()
        self.shell((20, 200))
        self.manager._refresh()
        self.assertFalse(self.manager._fullscreen_active())
        self.assertEqual(self.manager.adapter.shown_fullscreen[-1], (101, False))

    def test_enter_after_shell_notice_is_retained_before_first_show(self):
        self.fullscreen()
        self.manager._refresh()
        self.shell((20, 200))
        self.fullscreen()
        self.manager._refresh()
        self.assertTrue(self.manager._fullscreen_active())
        self.assertEqual(self.manager.adapter.shown_fullscreen[-1], (101, True))

    def test_synchronous_enter_during_registration_is_applied_before_show(self):
        self.fullscreen()
        self.manager._refresh()
        self.shell((20, 200))
        self.manager.hosts["a"].session.on_recreate = self.fullscreen
        self.manager._refresh()
        self.assertTrue(self.manager._fullscreen_active())
        self.assertEqual(self.manager.adapter.shown_fullscreen[-1], (101, True))
        self.assertGreater(self.manager.panel_closes, 0)

    def test_newer_exit_during_registration_wins_over_queued_new_enter(self):
        self.shell((20, 200))
        self.fullscreen()
        self.manager.hosts["a"].session.on_recreate = lambda: self.fullscreen(False)
        self.manager._refresh()
        self.assertFalse(self.manager._fullscreen_active())
        self.assertEqual(self.manager.adapter.shown_fullscreen[-1], (101, False))

    def test_position_and_reading_refreshes_do_not_poll_shell_or_clear_fullscreen(self):
        self.fullscreen()
        self.manager._refresh()
        reads = self.manager.adapter.reads
        for _ in range(3):
            self.manager.native_message(101, 736)
            self.manager._refresh()
            self.manager._sync_host(self.manager.hosts["a"])
        self.assertEqual(self.manager.adapter.reads, reads)
        self.assertTrue(self.manager._fullscreen_active())

    def test_duplicate_display_broadcasts_coalesce_into_one_shell_epoch(self):
        self.add_host("b", 102)
        reads = self.manager.adapter.reads
        self.shell((20, 200))
        self.event(self.manager.adapter.taskbar_message, host="b")
        self.manager._refresh()
        self.assertEqual(self.manager._shell_epoch, 1)
        self.assertEqual(self.manager.adapter.reads, reads + 1)
        self.assertEqual([h.session.resets for h in self.manager.hosts.values()],
                         [[(1, True)], [(1, True)]])

    def test_reentrant_shell_replacement_during_registration_is_not_marked_already_processed(self):
        self.add_host("b", 102)
        self.fullscreen()
        self.fullscreen(host="b")
        self.manager._refresh()
        self.shell((20, 200))
        first = self.manager.hosts["a"]
        observed = []

        def replace_again():
            if not observed:
                observed.append(True)
                self.fullscreen()  # Current Shell 20 enters fullscreen.
                self.shell((30, 300))  # It is replaced while registration is busy.

        first.session.on_recreate = replace_again
        self.manager._refresh()
        self.assertEqual(self.manager._shell_identity, (20, 200))
        self.assertEqual(self.manager._shell_epoch, 1)
        self.assertTrue(self.manager._shell_pending)
        self.assertTrue(self.manager._fullscreen_active())
        self.assertTrue(first.session._fullscreen)
        self.assertEqual(self.manager.adapter.shown_fullscreen[-2:], [(101, True), (102, False)])
        for host in self.manager.hosts.values():
            self.assertEqual(host.shell_epoch, 1, "Pending second Shell has not been registered yet")
            self.assertEqual(host.session.resets, [(1, True)])

        self.manager._refresh()
        self.assertEqual(self.manager._shell_identity, (30, 300))
        self.assertEqual(self.manager._shell_epoch, 2)
        self.assertFalse(self.manager._shell_pending)
        self.assertFalse(self.manager._fullscreen_active())
        self.assertEqual(self.manager.adapter.shown_fullscreen[-2:], [(101, False), (102, False)])
        for host in self.manager.hosts.values():
            self.assertEqual(host.shell_epoch, 2)
            self.assertEqual(host.session.resets, [(1, True), (2, True)])
            self.assertFalse(host.session._fullscreen)
        self.assertEqual(self.manager._errors, [])

    def test_reentrant_shell_replacement_during_identity_read_keeps_both_generations(self):
        self.add_host("b", 102)
        self.fullscreen()
        self.fullscreen(host="b")
        self.manager._refresh()
        self.shell((20, 200))
        original_read = self.manager.adapter.shell_identity
        reads_before = self.manager.adapter.reads
        observed = []

        def read_then_receive_another_shell_notice():
            identity = original_read()
            if not observed:
                observed.append(identity)
                self.fullscreen()
                self.shell((30, 300))
            return identity

        self.manager.adapter.shell_identity = read_then_receive_another_shell_notice
        self.manager._refresh()
        self.assertEqual(observed, [(20, 200)])
        self.assertEqual(self.manager._shell_identity, (20, 200))
        self.assertTrue(self.manager._shell_pending)
        self.assertTrue(self.manager._fullscreen_active())
        self.assertEqual(self.manager.adapter.shown_fullscreen[-2:], [(101, True), (102, False)])
        for host in self.manager.hosts.values():
            self.assertEqual(host.shell_epoch, 1)
            self.assertEqual(host.session.resets, [(1, True)])

        self.manager._refresh()
        self.assertEqual(self.manager._shell_identity, (30, 300))
        self.assertEqual(self.manager.adapter.reads, reads_before + 2)
        self.assertFalse(self.manager._shell_pending)
        self.assertFalse(self.manager._fullscreen_active())
        self.assertEqual(self.manager.adapter.shown_fullscreen[-2:], [(101, False), (102, False)])
        for host in self.manager.hosts.values():
            self.assertEqual(host.shell_epoch, 2)
            self.assertEqual(host.session.resets, [(1, True), (2, True)])
            self.assertFalse(host.session._fullscreen)
        self.assertEqual(self.manager._errors, [])

    def test_initial_identity_read_invalidating_host_never_registers_or_shows(self):
        for change in ("closed", "paused", "host_closing", "binding_replaced", "host_replaced"):
            with self.subTest(change=change):
                case = ShellRecoveryTests()
                case.setUp()
                manager = case.manager
                host = manager.hosts["a"]
                host.rect = None  # This operation would otherwise register a new host.
                manager._shell_identity_observed = False
                shown_before = list(manager.adapter.shown_fullscreen)
                registrations = []
                original_register = host.session.register

                def register(*args, **kwargs):
                    registrations.append(change)
                    return original_register(*args, **kwargs)

                def read_then_invalidate():
                    if change in ("closed", "paused"):
                        setattr(manager, change, True)
                    elif change == "host_closing":
                        host.closing = True
                    elif change == "binding_replaced":
                        host.binding = NS(**vars(host.binding))
                    else:
                        manager.hosts["a"] = NS()
                    return (20, 200)

                host.session.register = register
                manager.adapter.shell_identity = read_then_invalidate
                manager._sync_host(host)
                self.assertEqual(registrations, [])
                self.assertEqual(manager.adapter.shown_fullscreen, shown_before)

    def test_fresh_fullscreen_cleanup_closing_manager_never_shows_after_callback(self):
        for stage in ("fullscreen_cleanup", "reserve_before_relayout"):
            with self.subTest(stage=stage):
                case = ShellRecoveryTests()
                case.setUp()
                manager = case.manager
                case.shell((20, 200))
                host = manager.hosts["a"]
                shown_before = list(manager.adapter.shown_fullscreen)
                cleanups, relayouts = [], []
                original_relayout = host.session.relayout

                def close_manager():
                    cleanups.append(True)
                    manager.closed = True
                    host.closing = True

                def relayout(*args, **kwargs):
                    relayouts.append(True)
                    return original_relayout(*args, **kwargs)

                host.session.relayout = relayout
                manager.close_panel = close_manager
                if stage == "fullscreen_cleanup":
                    host.session.on_recreate = case.fullscreen  # Fresh enter during ABM_NEW.
                else:
                    # A real height/DPI change would otherwise reserve again
                    # immediately after the reentrant first reservation.
                    manager._config["top_bar"]["height"] = 40
                    host.session.on_recreate = close_manager
                manager._refresh()
                self.assertEqual(host.session.resets, [(1, True)])
                self.assertEqual(cleanups, [True])
                self.assertTrue(manager.closed)
                if stage == "fullscreen_cleanup":
                    self.assertTrue(host.session._fullscreen)
                self.assertEqual(relayouts, [], "Closing during reservation must stop before relayout")
                self.assertEqual(manager.adapter.shown_fullscreen, shown_before)
                self.assertEqual(manager._errors, [])


if __name__ == "__main__":
    unittest.main()
