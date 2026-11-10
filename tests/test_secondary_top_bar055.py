"""Pure V2 floating-host boundaries; no Qt, native API or desktop mutation."""
import ast
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from appbar_platform import AppBarError
from top_bar_layout import PixelRect
import secondary_top_bar055 as secondary

ROOT = Path(__file__).resolve().parents[1]


class Backend:
    def __init__(self):
        self.calls = []
        self.token = SimpleNamespace(hwnd=55)
        self.valid = True

    def validate(self, token):
        if token is not self.token or not self.valid:
            raise AppBarError('Wrong own generation')
        self.calls.append(('validate', token.hwnd))

    def __getattr__(self, name):
        if name in ('send', 'place', 'claim', 'release', 'set_fullscreen', 'shell_registration_lost'):
            raise AssertionError('No AppBar operation: '+name)
        raise AttributeError(name)


class BaseAdapter:
    def __init__(self):
        self.backend = Backend()
        self.events = []
        self.position_ok = True

    def _api(self):
        def position(hwnd, after, left, top, width, height, flags):
            self.events.append(('position', hwnd, after.value, left, top, width, height, flags))
            return self.position_ok
        return dict(position=position)

    def hide(self, binding):
        self.backend.validate(binding.token)
        self.events.append(('hide', binding.hwnd))

    def show(self, binding, *, activate=False):
        self.backend.validate(binding.token)
        self.events.append(('show', binding.hwnd, activate))

    def screen_identity(self, screen):
        return SimpleNamespace(native_id=screen.native_id)

    def snapshot(self, owner):
        self.backend.validate(owner.token)
        if getattr(self, 'snapshot_error', False):
            raise AppBarError('Selected monitor disappeared')
        return owner.monitor, owner.work, owner.dpi

    def prepare(self, window, screen):
        # This is intentionally before a retained HWND is created. A pinned
        # host/child still accepting focus must fail this actual consumer test.
        for owner in (window, getattr(window, 'quick_client', None)):
            if owner is not None and owner.flags.get('no-focus') is not True:
                raise AssertionError('NoActivate policy missing before prepare')
        if getattr(window, 'guard_required', False) and not getattr(window, 'guard_registered', False):
            raise AssertionError('Secondary guard missing before prepare')
        self.events.append(('prepare', window.kind, window.pinned))
        result = binding(self)
        result.window = window
        return result


def binding(adapter):
    return SimpleNamespace(token=adapter.backend.token, hwnd=55, screen_name=secondary.DEFAULT_TARGET,
                           monitor=PixelRect(2560, -541, 4000, 899),
                           work=PixelRect(2560, -509, 4000, 899), dpi=96)


class BaseManager:
    def __init__(self, runtime, *, adapter=None, adapter_factory=None, **kwargs):
        self.runtime, self.app = runtime, runtime.app
        self.adapter = adapter if adapter is not None else adapter_factory()
        self._injected = adapter is not None
        self._errors, self.hosts, self.base_guard_calls = [], {}, 0
        self._foreground_hidden_screens = frozenset()
        self.created_windows, self.deferred_deletions, self.retired = [], [], []

    def _read_foreground_visibility(self):
        self.base_guard_calls += 1
        self._foreground_hidden_screens = frozenset(('game-monitor',))

    def _make_window(self, *args):
        kind, state, screen, pinned = args
        # Match the existing base policy: hover cannot focus, pinned can.
        class Window:
            def __init__(self, label):
                self.kind, self.pinned, self.flags = label, pinned, {'no-focus': not pinned}
                self.events, self.destroyed_callbacks = [], []
                self.delete_calls, self.dispose_calls, self.dispose_error = 0, 0, False
            def setFlag(self, key, value):
                self.flags[key] = value
            def setTitle(owner, value):
                self.last_title = value
            def hide(self):
                self.events.append('hide')
            def dispose(self):
                self.dispose_calls += 1
                if self.dispose_error:
                    raise RuntimeError('Own disposer unavailable')
                self.events.append('dispose')
                # The real Raster disposer destroys/detaches its native child,
                # but QObject deletion remains the manager's responsibility.
                if hasattr(self, 'quick_client'):
                    self.quick_client = None
            def deleteLater(owner):
                owner.delete_calls += 1
                self.deferred_deletions.append(owner)
        window = Window(kind)
        if kind == 'details':
            window.quick_client = Window('quick-child')
        self.created_windows.append(window)
        return window


def fake_top_bar_module():
    module = ModuleType('top_bar_runtime')
    module.TopBarManager, module.WindowsTopBarAdapter = BaseManager, BaseAdapter
    module.Qt = SimpleNamespace(WindowType=SimpleNamespace(WindowDoesNotAcceptFocus='no-focus'))
    return module


class SecondaryTopBar055Tests(unittest.TestCase):
    def test_cold_import_does_not_load_Qt_profile_or_native_API(self):
        name = '_cold_secondary055'
        module = ModuleType(name)
        code = compile(Path(secondary.__file__).read_text('utf-8'), secondary.__file__, 'exec')
        before = set(sys.modules)
        with patch.dict(sys.modules, {name: module}), \
                patch('ctypes.WinDLL', create=True, side_effect=AssertionError('No native call')), \
                patch.object(Path, 'open', side_effect=AssertionError('No profile/file read')):
            exec(code, module.__dict__)
        self.assertTrue(callable(module.create_secondary_top_bar))
        self.assertFalse(any(value.startswith(('PySide6', 'stats_config', 'profile_paths', 'top_bar_runtime'))
                             for value in set(sys.modules)-before))

    def test_work_area_gap_negative_origin_and_DPI_without_reservation(self):
        adapter = BaseAdapter()
        owner = binding(adapter)
        work = owner.work
        self.assertEqual(secondary.floating_band(owner, 32), PixelRect(2560, -503, 4000, -471))
        owner.dpi = 144
        self.assertEqual(secondary.floating_band(owner, 32), PixelRect(2560, -500, 4000, -452))
        self.assertIs(owner.work, work)
        for gap in (-1, float('nan'), True):
            with self.subTest(gap=gap), self.assertRaises(AppBarError):
                secondary.floating_band(owner, 32, gap)
        owner.work = PixelRect(2560, 880, 4000, 899)
        with self.assertRaises(AppBarError):
            secondary.floating_band(owner, 32)

    def test_session_uses_only_own_nonactivating_position_and_hide_zero_AppBar(self):
        adapter = secondary._adapter_type(BaseAdapter, secondary.DEFAULT_TARGET, 6, lambda: True)()
        owner = binding(adapter)
        original_work = owner.work
        session = adapter.session(owner)
        result = session.register(owner.monitor, dpi=96, height_dip=32)
        self.assertTrue(result.ready)
        self.assertFalse(result.registered)
        self.assertEqual(result.physical_rect, PixelRect(2560, -503, 4000, -471))
        position, = adapter.events
        self.assertEqual(position[0:2], ('position', 55))
        self.assertEqual(position[-1], 0x0010)
        self.assertFalse(any(row[0] == 'show' for row in adapter.events))
        adapter.show(owner, activate=True)
        self.assertEqual(adapter.events[-1], ('show', 55, False))
        self.assertTrue(session.notify_activation(True).ok)
        self.assertTrue(session.notify_window_position().ok)
        self.assertTrue(session.fullscreen(True).ok)
        self.assertTrue(session.shell_recreated(3, invalidate_fullscreen=True).ready)
        self.assertTrue(session.close().cleanup_complete)
        calls = tuple(adapter.events)
        self.assertTrue(session.close().cleanup_complete)
        self.assertEqual(tuple(adapter.events), calls)
        self.assertIs(owner.work, original_work)
        self.assertTrue(all(row[1] == 55 for row in adapter.events))

    def test_desktop_unknown_foreign_target_or_generation_never_places_or_shows(self):
        for state in (None, False, 1):
            adapter = secondary._adapter_type(BaseAdapter, secondary.DEFAULT_TARGET, 6, lambda: state)()
            owner = binding(adapter)
            self.assertFalse(adapter.session(owner).register(owner.monitor).ready)
            self.assertFalse(any(row[0] in ('position', 'show') for row in adapter.events))
            with self.assertRaises(AppBarError):
                adapter.show(owner)
            self.assertFalse(any(row[0] == 'show' for row in adapter.events))
        adapter = secondary._adapter_type(BaseAdapter, secondary.DEFAULT_TARGET, 6, lambda: True)()
        owner = binding(adapter)
        owner.screen_name = r'\\.\DISPLAY36'
        with self.assertRaises(AppBarError):
            adapter.session(owner)
        owner.screen_name = secondary.DEFAULT_TARGET
        session = adapter.session(owner)
        adapter.backend.valid = False
        self.assertFalse(session.register(owner.monitor).ok)
        self.assertEqual(adapter.events, [])
        adapter.backend.valid = True
        adapter.snapshot_error = True
        self.assertFalse(session.register(owner.monitor).ok)
        with self.assertRaises(AppBarError):
            adapter.show(owner)
        self.assertFalse(any(row[0] in ('position', 'show') for row in adapter.events))

    def test_strict_native_monitor_missing_duplicate_and_no_primary_fallback(self):
        target = SimpleNamespace(native_id=secondary.DEFAULT_TARGET)
        other = SimpleNamespace(native_id=r'\\.\DISPLAY36')
        inventory = [other, target]
        app = SimpleNamespace(screens=lambda: inventory,
                              primaryScreen=lambda: self.fail('No primary fallback'))
        runtime = SimpleNamespace(app=app)
        with patch.dict(sys.modules, {'top_bar_runtime': fake_top_bar_module()}):
            manager = secondary.create_secondary_top_bar(runtime, manager_class=BaseManager, desktop_ready=lambda: True)
        self.assertFalse(manager._injected)
        self.assertEqual(manager._targets({'monitor_mode': 'primary'}), ([(secondary.DEFAULT_TARGET, target)], []))
        inventory[:] = [other]
        self.assertEqual(manager._targets({}), ([], [secondary.DEFAULT_TARGET]))
        inventory[:] = [target, SimpleNamespace(native_id=secondary.DEFAULT_TARGET.lower())]
        self.assertEqual(manager._targets({}), ([], [secondary.DEFAULT_TARGET]))

    def test_inherits_production_guard_and_unknown_desktop_adds_own_hide_unique_title(self):
        state = [True]
        runtime = SimpleNamespace(app=SimpleNamespace(screens=lambda: []))
        with patch.dict(sys.modules, {'top_bar_runtime': fake_top_bar_module()}):
            manager = secondary.create_secondary_top_bar(runtime, manager_class=BaseManager, desktop_ready=lambda: state[0])
        manager.hosts = {secondary.DEFAULT_TARGET: object()}
        manager._read_foreground_visibility()
        self.assertEqual(manager._foreground_hidden_screens, frozenset(('game-monitor',)))
        state[0] = None
        manager._read_foreground_visibility()
        self.assertEqual(manager.base_guard_calls, 2)
        self.assertEqual(manager._foreground_hidden_screens, frozenset(('game-monitor', secondary.DEFAULT_TARGET)))
        manager._make_window('bar', None, None, False)
        self.assertEqual(manager.last_title, 'DesktopStats V2 · 状态栏')

    def test_actual_manager_default_and_factory_keep_real_vs_injected_boundary(self):
        # Run only the actual constructor's two adapter assignments; Qt's
        # QObject/timers are deliberately outside this pure contract check.
        tree = ast.parse((ROOT/'top_bar_runtime.py').read_text('utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'TopBarManager')
        function = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
        function.body = [node for node in function.body if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
            and target.value.id == 'self' and target.attr in ('adapter', '_injected') for target in node.targets)]
        self.assertEqual(len(function.body), 2)
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        default = object()
        scope = dict(WindowsTopBarAdapter=lambda: default)
        exec(compile(module, '<actual adapter constructor seam>', 'exec'), scope)
        node = SimpleNamespace()
        scope['__init__'](node, None)
        self.assertIs(node.adapter, default)
        self.assertFalse(node._injected)
        supplied = object()
        scope['__init__'](node, None, adapter_factory=lambda: supplied)
        self.assertIs(node.adapter, supplied)
        self.assertFalse(node._injected)
        scope['__init__'](node, None, adapter=supplied, adapter_factory=lambda: self.fail('Explicit adapter must win'))
        self.assertIs(node.adapter, supplied)
        self.assertTrue(node._injected)

    def test_actual_pinned_and_hover_panel_pipeline_seals_host_and_child_before_prepare(self):
        # Execute both real consumers and their real cleanup. A fake hidden
        # surface emits Created only once; installing its observer later does
        # not invent the event that pre-show material preparation needs.
        tree = ast.parse((ROOT/'top_bar_runtime.py').read_text('utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TopBarManager')
        names = ('_show_panel', '_new_host', 'close_panel', '_dispose_panel', '_dispose', '_close_material')
        nodes = [next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name) for name in names]
        for node in nodes:
            node.decorator_list = []
        class Host:
            def __init__(self, screen, state, window, **kwargs):
                self.screen, self.state, self.window = screen, state, window
                self.binding = self.session = self.material_bridge = None
        class State:
            def __init__(self, manager, identifier):
                self._host_id, self.deleted = identifier, 0
            def deleteLater(self):
                self.deleted += 1
        scope = dict(Host=Host, BarViewState=State, OVERFLOW='overflow', AppBarError=AppBarError,
            WindowPreparationError=type('PreparationError', (Exception,), {}),
            QTimer=SimpleNamespace(singleShot=lambda delay, callback: None))
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<actual host and panel consumers>', 'exec'), scope)

        class Bridge:
            def __init__(self, window):
                self.window, self.alive, self.closed, self.deleted = window, False, 0, 0
                window.events.append('bridge_started')
                window.material_observer = self
                window.surface_observers.append(self.created)
            def created(self):
                self.alive = True
                self.window.events.append('surface_observed')
            def prepare_before_show(self):
                if not self.alive:
                    raise AppBarError('Hidden material missed SurfaceCreated')
                self.window.events.append('material_prepared')
            def close(self):
                self.closed += 1
                self.window.events.append('material_closed')
            def deleteLater(self):
                self.deleted += 1

        class ConsumerAdapter(BaseAdapter):
            def release(self, binding):
                self.backend.validate(binding.token)
                self.events.append(('release', binding.hwnd))

        def fixture(kind, outcome='true', premature=False):
            retained, clients, registered, bridges = {}, [], [], []
            class OwnedBase(BaseManager):
                def _make_window(self, *args):
                    window = super()._make_window(*args)
                    window.surface_observers, window.material_observer = [], None
                    window.native_created = premature
                    if kind == 'bar':
                        window.dispose = None  # A real plain QWindow.
                    else:
                        clients.append(window.quick_client)
                    if outcome == 'policy':
                        owner = getattr(window, 'quick_client', window)
                        def refuse(*args):
                            raise RuntimeError('Policy unavailable')
                        owner.setFlag = refuse
                    return window
            def register(window):
                self.assertTrue(window.flags['no-focus'])
                client = getattr(window, 'quick_client', None)
                if client is not None:
                    self.assertTrue(client.flags['no-focus'])
                self.assertIsNotNone(window.material_observer, 'Observer must start before native creation')
                self.assertEqual(registered, [])  # One callback, one prepare.
                self.assertFalse(any(row[0] in ('prepare', 'show') for row in manager.adapter.events))
                window.events.append('register')
                registered.append(window)
                retained[id(window)] = window
                window.destroyed_callbacks.append(lambda owner=window: retained.pop(id(owner)))
                window.guard_required = window.guard_registered = True
                window.dispose_error = outcome == 'dispose'
                if not window.native_created:
                    window.native_created = True
                    for callback in window.surface_observers:
                        callback()
                if outcome == 'raises':
                    raise RuntimeError('Guard unavailable')
                return None if outcome == 'none' else outcome == 'true'
            runtime = SimpleNamespace(app=SimpleNamespace(screens=lambda: []), register_secondary_window=register)
            fake_module = fake_top_bar_module()
            fake_module.WindowsTopBarAdapter = ConsumerAdapter
            with patch.dict(sys.modules, {'top_bar_runtime': fake_module}):
                manager = secondary.create_secondary_top_bar(runtime, manager_class=OwnedBase,
                    desktop_ready=lambda: True)
            manager.closed = manager.paused = False
            manager._panel = None
            manager._rows = [{'id': 'battery'}]
            manager._detail_serial = 0
            manager._hover_timer = manager._close_timer = SimpleNamespace(stop=lambda: None)
            manager._panel_geometry_timer = SimpleNamespace(stop=lambda: None)
            manager._pending_hover = None
            signal = SimpleNamespace(emit=lambda: None)
            host = SimpleNamespace(screen=object(), state=SimpleNamespace(_host_id=secondary.DEFAULT_TARGET,
                materialChanged=signal, detailChanged=signal))
            manager._details_allowed = lambda owner: owner is host
            manager._trace_detail = lambda *args: None
            manager._await_detail_component = lambda *args: False
            manager._retry_retired = lambda: None
            manager._detail_data = lambda *args, **kwargs: True
            manager._native_windows = lambda: False
            manager._position_panel = lambda: None
            manager._clear_detail_publication = lambda *args: None
            manager._status = lambda *args: None
            manager._bind_material = lambda *args: None
            manager._style, manager._coating, manager._shell_epoch, manager._shell_pending = {}, False, 0, False
            def material(window, state, *args):
                value = Bridge(window)
                bridges.append(value)
                return value
            manager._material_bridge = material
            for name in ('close_panel', '_dispose_panel', '_dispose'):
                setattr(manager, name, scope[name].__get__(manager, type(manager)))
            manager._close_material = scope['_close_material']
            def attempt(*args):
                manager._detail_serial += 1
                manager._detail_attempt = {}
                return manager._detail_serial
            manager._new_detail_attempt = attempt
            return manager, host, registered, retained, clients, bridges

        # Both actual callers retain/start the material before prepare can
        # create the HWND; hover and pinning share the same nonactivating path.
        for kind, pinned in (('bar', False), ('details', False), ('details', True)):
            with self.subTest(kind=kind, pinned=pinned):
                manager, host, registered, retained, clients, bridges = fixture(kind)
                if kind == 'bar':
                    record = scope['_new_host'](manager, host.screen, secondary.DEFAULT_TARGET)
                    self.assertIs(record.material_bridge, bridges[0])
                else:
                    scope['_show_panel'](manager, host, 'battery', pinned)
                    self.assertIsNotNone(manager._panel)
                    self.assertIs(manager._panel['material_bridge'], bridges[0])
                window, = manager.created_windows
                self.assertEqual(registered, [window])
                self.assertEqual(window.events[:3], ['bridge_started', 'register', 'surface_observed'])
                self.assertEqual(manager.adapter.events[0], ('prepare', kind, pinned))
                self.assertEqual(manager._errors, [])
                if kind == 'details':
                    self.assertEqual(manager.adapter.events[-1], ('show', 55, False))
                    self.assertIn('material_prepared', window.events)
                self.assertTrue(window.flags['no-focus'])
                self.assertTrue(all(child.flags['no-focus'] for child in clients))
        # Demonstrate the original bug: observing an already-created hidden
        # owner cannot satisfy the real pre-show material contract.
        manager, host, _, _, _, bridges = fixture('details', premature=True)
        scope['_show_panel'](manager, host, 'battery', True)
        self.assertIsNone(manager._panel)
        self.assertFalse(any(row[0] == 'show' for row in manager.adapter.events))
        self.assertTrue(any('missed SurfaceCreated' in text for text in manager._errors))
        self.assertEqual(bridges[0].closed, 1)

        for kind in ('bar', 'details'):
            for outcome in ('false', 'none', 'raises', 'policy', 'dispose'):
                if kind == 'bar' and outcome == 'dispose':
                    continue
                with self.subTest(kind=kind, outcome=outcome):
                    manager, host, registered, retained, clients, bridges = fixture(kind, outcome)
                    if kind == 'bar':
                        error = RuntimeError if outcome in ('raises', 'policy') else AppBarError
                        message = 'Guard unavailable' if outcome == 'raises' else 'Policy unavailable' if outcome == 'policy' else '显示范围保护'
                        with self.assertRaisesRegex(error, message):
                            scope['_new_host'](manager, host.screen, secondary.DEFAULT_TARGET)
                    else:
                        scope['_show_panel'](manager, host, 'battery', True)
                        self.assertIsNone(manager._panel)
                        message = 'Guard unavailable' if outcome == 'raises' else 'Policy unavailable' if outcome == 'policy' else '显示范围保护'
                        self.assertTrue(any(message in text for text in manager._errors))
                    self.assertEqual(manager.adapter.events, [])
                    window, = manager.created_windows
                    self.assertEqual(registered, [] if outcome == 'policy' else [window])
                    self.assertEqual(len(bridges), 0 if outcome == 'policy' else 1)
                    if bridges:
                        self.assertEqual((bridges[0].closed, bridges[0].deleted), (1, 1))
                    if outcome == 'dispose':
                        self.assertEqual(len(manager.retired), 1)
                        self.assertEqual(manager.deferred_deletions, [])
                        pending = manager.retired.pop()
                        self.assertIs(pending['window'], window)
                        self.assertIsNone(pending['binding'])
                        self.assertIsNone(pending['material_bridge'])
                        window.dispose_error = False
                        manager._dispose_panel(pending)
                    self.assertEqual(manager.retired, [])
                    self.assertEqual(window.dispose_calls, 0 if kind == 'bar' else 2 if outcome == 'dispose' else 1)
                    self.assertEqual(window.delete_calls, 1)
                    self.assertEqual([row.delete_calls for row in clients], [1] if kind == 'details' else [])
                    self.assertEqual(manager.deferred_deletions, clients + [window])
                    while manager.deferred_deletions:
                        owner = manager.deferred_deletions.pop(0)
                        for callback in owner.destroyed_callbacks:
                            callback()
                        if owner in manager.created_windows:
                            manager.created_windows.remove(owner)
                    self.assertEqual(retained, {})
                    self.assertEqual(manager.created_windows, [])


if __name__ == '__main__':
    unittest.main()
