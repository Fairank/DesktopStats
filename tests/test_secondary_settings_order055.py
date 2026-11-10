"""Exercise the real lazy Settings flow without importing Qt or live profiles."""
import ast
import copy
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def body(name):
    tree = ast.parse((ROOT / 'native_runtime.py').read_text('utf-8'))
    runtime = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Runtime')
    return copy.deepcopy(next(node for node in runtime.body
        if isinstance(node, ast.FunctionDef) and node.name == name))


class Signal:
    def connect(self, callback):
        pass


class Rect:
    def __init__(self, x=2560, y=-509, width=1440, height=2480):
        self.values = x, y, width, height
    def x(self): return self.values[0]
    def y(self): return self.values[1]
    def width(self): return self.values[2]
    def height(self): return self.values[3]


class Window:
    def __init__(self, events, name):
        self.events, self.name = events, name
        self.visibleChanged = Signal()
        self.paintFailed = Signal()
        self.title, self.target = None, None
        self.no_focus = False
        self.created = self.visible = self.disposed = False
        self.deleted = self.shown = self.activations = self.raised = 0
        self.destroyed = False
        self.deferred = []
        self.on_destroyed = lambda: None
        self.release_failure = None
        self.listeners = []
        self.frame = Rect(width=900, height=600)
        self.properties = {}
    def objectName(self): return 'settingsWindow'
    def setIcon(self, icon): pass
    def setPersistentGraphics(self, value): pass
    def setPersistentSceneGraph(self, value): pass
    def setTitle(self, value): self.title = value
    def setScreen(self, target): self.target = target
    def setFlag(self, flag, value): self.no_focus = value
    def setProperty(self, name, value): self.properties[name] = value
    def create(self):
        if self.created:
            return
        self.created = True
        self.events.append('create')
        for callback in tuple(self.listeners):
            callback()
    def frameMargins(self):
        return SimpleNamespace(left=lambda: 0, right=lambda: 0, top=lambda: 0, bottom=lambda: 0)
    def frameGeometry(self): return self.frame
    def resize(self, width, height):
        self.frame = Rect(self.frame.x(), self.frame.y(), width, height)
    def setFramePosition(self, point):
        self.frame = Rect(*point, self.frame.width(), self.frame.height())
    def setPosition(self, x, y): self.setFramePosition((x, y))
    def x(self): return self.frame.x()
    def y(self): return self.frame.y()
    def width(self): return self.frame.width()
    def height(self): return self.frame.height()
    def isVisible(self): return self.visible
    def showNormal(self):
        self.events.append('show')
        self.visible = True
        self.shown += 1
    def hide(self): self.visible = False
    def raise_(self): self.raised += 1
    def requestActivate(self): self.activations += 1
    def paint_background(self): pass
    def status(self): return {'disposed': self.disposed}
    def dispose(self):
        self.events.append('dispose-host')
        if self.release_failure == 'host':
            raise RuntimeError('dispose fixture')
        self.disposed = True
    def deleteLater(self):
        if self.name == 'host':
            assert self.disposed, 'Do not delete a host whose release failed'
        self.deleted += 1
        def destroy():
            self.destroyed = True
            self.on_destroyed()
        self.deferred.append(destroy)


class Material:
    """Model the bridge contract: hidden preexisting surfaces are not adopted."""
    def __init__(self, host, events, **kwargs):
        self.host, self.events, self.kwargs = host, events, kwargs
        self.observed = self.closed = False
        self.deleted = 0
        self.destroyed = False
        self.deferred = []
        self.release_failure = None
    def start(self):
        self.events.append('bridge-start')
        self.host.listeners.append(self.surface_created)
        if self.host.isVisible():
            self.observed = self.host.created
    def surface_created(self):
        self.events.append('bridge-observed-surface')
        self.observed = True
    def prepare_hidden(self):
        self.events.append('prepare-hidden')
        return object() if self.observed and not self.host.visible and not self.closed else None
    def close(self):
        self.events.append('close-bridge')
        if self.release_failure == 'bridge':
            raise RuntimeError('close fixture')
        self.closed = True
    def deleteLater(self):
        assert self.closed, 'Do not delete a bridge whose release failed'
        self.deleted += 1
        self.deferred.append(lambda: setattr(self, 'destroyed', True))
    def status(self): return {'closed': self.closed}


def fixture(*, secondary=True, headless=False, registration=True, old_order=False, release_failure=None):
    events, owners, materials = [], [], []
    deferred, guard_owned = [], {}
    target = SimpleNamespace(availableGeometry=lambda: Rect())
    settings = Window(events, 'client')
    prior = Window(events, 'prior')
    engine = SimpleNamespace(roots=[prior])
    engine.rootObjects = lambda: list(engine.roots)
    engine.load = lambda url: engine.roots.append(settings)
    runtime_class = type('Runtime', (), {})

    def register(runtime, owner):
        events.append('register')
        if runtime.headless:
            return False
        if secondary:
            assert owner.no_focus and settings.no_focus
            assert owner.target is target and settings.target is target
            assert owner.title == settings.title == 'DesktopStats V2'
            guard_owned[id(owner)] = owner
            owner.on_destroyed = lambda: guard_owned.pop(id(owner), None)
        if isinstance(registration, Exception):
            raise registration
        if registration is True:
            owner.create()
        return registration

    runtime_class.register_secondary_window = register
    runtime_class._settings_window = lambda self: self.settings_host or self.settings
    runtime_class._secondary_screen = lambda self: target
    runtime_class._secondary_admitted = lambda self: True
    runtime_class._secondary_window_admitted = lambda self, owner: owner.created
    runtime_class._allowed_screens = lambda self: [target]
    runtime_class._placement_screen = lambda self: target

    def host(client):
        owner = Window(events, 'host')
        owner.deferred, owner.release_failure = deferred, release_failure
        owners.append(owner)
        return owner

    def blur(**kwargs):
        return SimpleNamespace(close=lambda: events.append('close-blur'))

    def bridge(owner, runtime, **kwargs):
        material = Material(owner, events, **kwargs)
        material.deferred, material.release_failure = deferred, release_failure
        materials.append(material)
        return material

    scope = dict(Runtime=runtime_class, secondary_active=lambda: secondary,
        session_display_name=lambda: 'DesktopStats V2', QUrl=SimpleNamespace(fromLocalFile=lambda value: value),
        ASSETS=ROOT, Qt=SimpleNamespace(WindowDoesNotAcceptFocus=1), QPoint=lambda x, y: (x, y),
        SettingsBackdropHost=host, ThinRasterAcrylicMaterial=blur, SettingsBlurMaterial=blur,
        SettingsMaterialBridge=bridge, transparency_policy=lambda: {},
        logging=logging, fit=lambda x, y, width, height, areas: (x, y))
    ensure = body('ensure_settings')
    if old_order:
        # Restore only the failing producer/observer ordering in the real body.
        main = next(node for node in ensure.body if isinstance(node, ast.Try))
        guard = next(node for node in main.body if isinstance(node, ast.If)
            and any(isinstance(call, ast.Attribute) and call.attr == 'register_secondary_window'
                for call in ast.walk(node)))
        main.body.remove(guard)
        early = next(node for node in main.body if isinstance(node, ast.If)
            and ast.unparse(node.test) == 'secondary_active()')
        early.body.extend(guard.body)
    for node in (ensure, body('show_settings')):
        code = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
        exec(compile(code, 'native_runtime.py::<actual lazy Settings>', 'exec'), scope)
        setattr(runtime_class, node.name, scope[node.name])
    runtime = runtime_class()
    runtime.shutting_down = runtime._settings_loading = False
    runtime.settings = runtime.settings_host = runtime.settings_blur = runtime.settings_material = None
    runtime.headless, runtime.engine = headless, engine
    runtime.app = SimpleNamespace(platformName=lambda: 'windows', windowIcon=lambda: None)
    runtime.controller = SimpleNamespace(_draft={'theme': 'dark'}, set_status=lambda *a, **k: None)
    for name in ('refresh_appearance', '_settings_material_request', '_publish_settings_material',
                 '_release_settings_surface', '_settings_paint_failed', 'compose'):
        setattr(runtime, name, lambda *args, **kwargs: None)
    return SimpleNamespace(runtime=runtime, events=events, owners=owners, materials=materials,
                           settings=settings, prior=prior, deferred=deferred, guard_owned=guard_owned)


class SecondarySettingsOrder055Tests(unittest.TestCase):
    def test_real_ensure_and_show_observe_hidden_surface_before_preparation(self):
        case = fixture()
        case.runtime.show_settings('__top_bar__')
        self.assertEqual(case.events, ['bridge-start', 'register', 'create',
            'bridge-observed-surface', 'prepare-hidden', 'show'])
        self.assertTrue(case.materials[0].observed)
        self.assertFalse(case.materials[0].kwargs['activation_requests'])
        self.assertEqual(case.settings.properties['page'], 3)
        self.assertEqual((case.owners[0].activations, case.owners[0].raised), (0, 0))
        case.runtime.show_settings()
        self.assertEqual(case.events.count('create'), 1)
        self.assertEqual(case.events.count('bridge-start'), 1)
        self.assertEqual(case.owners[0].shown, 2)

    def test_reproduced_old_order_cannot_pass_hidden_preparation(self):
        case = fixture(old_order=True)
        case.runtime.show_settings()
        self.assertEqual(case.events, ['register', 'create', 'bridge-start', 'prepare-hidden'])
        self.assertFalse(case.materials[0].observed)
        self.assertEqual(case.owners[0].shown, 0)

    def test_failed_registration_releases_started_bridge_and_candidate(self):
        for result in (False, None, RuntimeError('registration fixture')):
            with self.subTest(result=result):
                case = fixture(registration=result)
                with self.assertRaises(RuntimeError):
                    case.runtime.ensure_settings()
                self.assertEqual(case.events, ['bridge-start', 'register', 'close-bridge',
                    'close-blur', 'dispose-host'])
                self.assertTrue(case.materials[0].closed)
                self.assertTrue(case.owners[0].disposed)
                self.assertEqual((case.materials[0].deleted, case.owners[0].deleted), (1, 1))
                self.assertFalse(case.materials[0].destroyed)
                self.assertFalse(case.owners[0].destroyed)
                self.assertIs(case.guard_owned[id(case.owners[0])], case.owners[0])
                for callback in case.deferred:
                    callback()
                self.assertTrue(case.materials[0].destroyed)
                self.assertTrue(case.owners[0].destroyed)
                self.assertEqual(case.guard_owned, {})
                self.assertEqual((case.settings.deleted, case.prior.deleted), (1, 0))
                self.assertFalse(case.runtime._settings_loading)
                for name in ('settings', 'settings_host', 'settings_blur', 'settings_material'):
                    self.assertIsNone(getattr(case.runtime, name))
        for failure in ('bridge', 'host'):
            with self.subTest(release_failure=failure):
                case = fixture(registration=False, release_failure=failure)
                with self.assertLogs(level='ERROR'):
                    with self.assertRaisesRegex(RuntimeError, 'bounds protection unavailable'):
                        case.runtime.ensure_settings()
                bridge, host = case.materials[0], case.owners[0]
                self.assertEqual(bridge.deleted, 0 if failure == 'bridge' else 1)
                self.assertEqual(host.deleted, 0 if failure == 'host' else 1)
                for callback in case.deferred:
                    callback()
                self.assertEqual(bridge.destroyed, failure != 'bridge')
                self.assertEqual(host.destroyed, failure != 'host')
                self.assertEqual(bool(case.guard_owned), failure == 'host')
                self.assertEqual((case.settings.deleted, case.prior.deleted), (1, 0))

    def test_legacy_keeps_bridge_then_show_without_secondary_registration(self):
        case = fixture(secondary=False)
        case.runtime.show_settings()
        self.assertEqual(case.events, ['bridge-start', 'create', 'bridge-observed-surface',
            'prepare-hidden', 'show'])
        self.assertTrue(case.materials[0].kwargs['activation_requests'])
        self.assertEqual((case.owners[0].activations, case.owners[0].raised), (1, 1))

    def test_headless_ensure_keeps_no_native_or_material_construction(self):
        for secondary in (False, True):
            with self.subTest(secondary=secondary):
                case = fixture(secondary=secondary, headless=True)
                # Execute the real early gate too, so the fake cannot silently
                # invent support for a secondary headless native window.
                scope = dict(secondary_active=lambda: secondary)
                code = ast.fix_missing_locations(ast.Module(
                    body=[body('register_secondary_window')], type_ignores=[]))
                exec(compile(code, 'native_runtime.py::<actual registration gate>', 'exec'), scope)
                self.assertIs(scope['register_secondary_window'](case.runtime, case.settings),
                              not secondary)
                if secondary:
                    with self.assertRaisesRegex(RuntimeError, 'bounds protection unavailable'):
                        case.runtime.ensure_settings()
                    self.assertIsNone(case.runtime.settings)
                    self.assertEqual((case.settings.deleted, case.prior.deleted), (1, 0))
                else:
                    self.assertIs(case.runtime.ensure_settings(), case.settings)
                self.assertEqual(case.materials, [])
                self.assertEqual(case.owners, [])
                self.assertEqual(case.events, ['register'] if secondary else [])
                self.assertFalse(case.settings.created)


if __name__ == '__main__':
    unittest.main()
