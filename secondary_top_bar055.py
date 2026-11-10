"""An explicitly selected V2 floating bar over the real TopBar pipeline.

Cold import performs no profile/native/Qt/window work. Only the V2 factory
imports the production manager after bootstrap has selected its own profile.
No AppBar reservation, foreign-window operation, timer or collector is added.
"""
from dataclasses import dataclass
import ctypes as c
import math
import re
import threading

from appbar_platform import AppBarError
from top_bar_layout import PixelRect

DEFAULT_TARGET = r'\\.\DISPLAY37'
_TARGET = re.compile(r'\\\\\.\\DISPLAY[0-9]+\Z', re.IGNORECASE)


@dataclass(frozen=True)
class FloatingResult:
    ok: bool
    state: str
    registered: bool
    physical_rect: PixelRect | None
    cleanup_complete: bool
    errors: tuple = ()
    fullscreen: bool = False

    @property
    def ready(self):
        # Positioned and owned, deliberately without an AppBar registration.
        return self.ok and self.state == 'READY' and self.physical_rect is not None

    def __bool__(self):
        return self.ok


def _desktop_allowed(reader):
    try:
        return callable(reader) and reader() is True
    except Exception:
        return False


def floating_band(binding, height_dip, gap_dip=6):
    """Use native physical work-area coordinates, including negative origins."""
    monitor, work, dpi = binding.monitor, binding.work, binding.dpi
    if (not isinstance(monitor, PixelRect) or not isinstance(work, PixelRect)
            or monitor.width <= 0 or monitor.height <= 0 or work.width <= 0 or work.height <= 0
            or not (monitor.left <= work.left < work.right <= monitor.right
                    and monitor.top <= work.top < work.bottom <= monitor.bottom)
            or type(dpi) is not int or not 48 <= dpi <= 768
            or type(height_dip) not in (int, float) or not math.isfinite(height_dip) or not 16 <= height_dip <= 128
            or type(gap_dip) not in (int, float) or not math.isfinite(gap_dip) or not 0 <= gap_dip <= 64):
        raise AppBarError('V2 浮动栏的显示区域暂不可用。')
    top = work.top + math.ceil(gap_dip * dpi / 96)
    bottom = top + math.ceil(height_dip * dpi / 96)
    if bottom > work.bottom:
        raise AppBarError('所选显示器没有足够空间显示 V2 浮动栏。')
    return PixelRect(work.left, top, work.right, bottom)


class FloatingSession:
    """Only its already-retained HWND may move/hide; no Shell registration API."""
    def __init__(self, adapter, binding):
        self.adapter, self.binding = adapter, binding
        self._thread = threading.get_ident()
        self._state, self._rect, self._errors = 'IDLE', None, ()
        self._closed, self._fullscreen = False, False
        self._height_dip = 32
        self.needs_relayout = False

    def _result(self, ok):
        return FloatingResult(ok, self._state, False, self._rect, self._closed,
                              self._errors, self._fullscreen)

    def _guard(self):
        if threading.get_ident() != self._thread or self._closed:
            raise AppBarError('V2 浮动栏已关闭或不在自己的窗口线程。')
        self.adapter.backend.validate(self.binding.token)

    def register(self, monitor_bounds, *, dpi=96, height_dip=32):
        return self.relayout(monitor_bounds, dpi=dpi, height_dip=height_dip)

    def relayout(self, monitor_bounds=None, *, dpi=None, height_dip=None):
        try:
            self._guard()
            if monitor_bounds is not None and monitor_bounds != self.binding.monitor:
                raise AppBarError('V2 显示器与当前窗口不匹配。')
            if dpi is not None and dpi != self.binding.dpi:
                raise AppBarError('V2 显示比例与当前窗口不匹配。')
            if height_dip is not None:
                self._height_dip = height_dip
            rect = self.adapter.proposed_band(self.binding, self._height_dip)
            self.adapter.place_floating(self.binding, rect)
            self._rect, self._state, self._errors = rect, 'READY', ()
            self.needs_relayout = False
            return self._result(True)
        except Exception as error:
            self._state, self._errors = 'FAILED', (str(error),)
            return self._result(False)

    def shell_recreated(self, epoch, *, invalidate_fullscreen=False):
        if invalidate_fullscreen:
            self._fullscreen = False
        return self.relayout()

    def fullscreen(self, opened):
        try:
            self._guard()
            if type(opened) is not bool:
                raise AppBarError('V2 全屏状态无效。')
            self._fullscreen = opened
            if opened:
                self.adapter.hide(self.binding)
            return self._result(True)
        except Exception as error:
            self._errors = (str(error),)
            return self._result(False)

    def notify_activation(self, active):
        try:
            self._guard()
            return self._result(True)
        except Exception as error:
            self._errors = (str(error),)
            return self._result(False)

    def notify_window_position(self):
        return self.notify_activation(False)

    def close(self):
        if self._closed:
            return self._result(True)
        try:
            self._guard()
            self.adapter.hide(self.binding)
            self._closed, self._state, self._errors = True, 'CLOSED', ()
            return self._result(True)
        except Exception as error:
            self._errors = (str(error),)
            return self._result(False)


def _adapter_type(base, target, gap_dip, desktop_ready, before_prepare=None):
    class FloatingAdapter(base):
        def prepare(self, window, screen):
            # The real consumer has retained and started its material bridge
            # by this point. Register/create only now, so both observers see
            # SurfaceCreated before hidden material preparation.
            if before_prepare is not None and before_prepare(window) is not True:
                raise AppBarError('V2 窗口的显示范围保护未就绪。')
            return super().prepare(window, screen)

        def _check_target(self, binding):
            if str(binding.screen_name).casefold() != target.casefold():
                raise AppBarError('V2 窗口不在指定显示器。')
            self.backend.validate(binding.token)

        def session(self, binding):
            self._check_target(binding)
            return FloatingSession(self, binding)

        def proposed_band(self, binding, height):
            self._check_target(binding)
            self.snapshot(binding)  # Revalidate the own HWND/selected HMONITOR, no fallback.
            self._check_target(binding)
            return floating_band(binding, height, gap_dip)

        def place_floating(self, binding, rect):
            self._check_target(binding)
            if not _desktop_allowed(desktop_ready):
                raise AppBarError('当前桌面暂不可显示 V2 浮动栏。')
            work = binding.work
            if (not isinstance(rect, PixelRect) or rect.width <= 0 or rect.height <= 0
                    or not (work.left <= rect.left < rect.right <= work.right
                            and work.top <= rect.top < rect.bottom <= work.bottom)):
                raise AppBarError('V2 浮动栏不在指定显示器的可用区域。')
            # Move only this retained generation. NOACTIVATE, without SHOWWINDOW;
            # the inherited event/fullscreen guard authorizes the later show.
            if not self._api()['position'](binding.hwnd, c.c_void_p(-1),
                    rect.left, rect.top, rect.width, rect.height, 0x0010):
                raise AppBarError('V2 浮动栏定位失败。')

        def show(self, binding, *, activate=False):
            self._check_target(binding)
            if not _desktop_allowed(desktop_ready):
                self.hide(binding)
                raise AppBarError('当前桌面暂不可显示 V2 浮动栏。')
            try:
                self.snapshot(binding)
                self._check_target(binding)
            except Exception:
                self.hide(binding)
                raise
            return super().show(binding, activate=False)
    return FloatingAdapter


def create_secondary_top_bar(runtime, *, manager_class=None, target_native_id=DEFAULT_TARGET,
                             gap_dip=6, desktop_ready=None,
                             window_factory=None, fullscreen_guard_factory=None):
    """Keep Runtime's existing game/model guard via its supplied manager class."""
    if type(target_native_id) is not str or not _TARGET.fullmatch(target_native_id):
        raise AppBarError('V2 必须指定有效的 Windows 显示器标识。')
    from top_bar_runtime import Qt, TopBarManager, WindowsTopBarAdapter
    manager_class = manager_class or TopBarManager
    if desktop_ready is None:
        desktop_ready = getattr(runtime, 'secondary_desktop_ready', None)
    def before_prepare(window):
        register = getattr(runtime, 'register_secondary_window', None)
        return register(window) if callable(register) else True

    adapter_class = _adapter_type(WindowsTopBarAdapter, target_native_id, gap_dip, desktop_ready,
                                 before_prepare=before_prepare)

    class SecondaryTopBarManager(manager_class):
        def _targets(self, bar):
            matches = []
            for screen in self.app.screens():
                try:
                    identity = self.adapter.screen_identity(screen)
                    if identity.native_id.casefold() == target_native_id.casefold():
                        matches.append((identity.native_id, screen))
                except Exception:
                    continue
            if len(matches) != 1:
                self._errors.append('V2 指定显示器缺失或标识不唯一。')
                return [], [target_native_id]
            return matches, []

        def _read_foreground_visibility(self):
            try:
                super()._read_foreground_visibility()
            except Exception as error:
                self._fullscreen_guard_error = type(error).__name__
                self._foreground_hidden_screens = frozenset(self.hosts)
            if not _desktop_allowed(desktop_ready):
                self._foreground_hidden_screens = frozenset(self._foreground_hidden_screens) | frozenset(self.hosts)

        def _make_window(self, kind, state, screen, pinned):
            window = super()._make_window(kind, state, screen, pinned)
            try:
                # A legacy pinned panel accepts focus. In V2 pinning retains
                # it only; both surfaces must be sealed before prepare/show.
                for owner in (window, getattr(window, 'quick_client', None)):
                    if owner is not None:
                        setter = getattr(owner, 'setFlag', None)
                        if not callable(setter):
                            raise AppBarError('V2 窗口无法设置非激活策略。')
                        setter(Qt.WindowType.WindowDoesNotAcceptFocus, True)
                title = getattr(window, 'setTitle', None)
                if callable(title):
                    title('DesktopStats V2 · ' + ('状态栏' if kind == 'bar' else '硬件详情'))
            except Exception:
                # The consumer cannot retain a window that never returned.
                # There is no material/binding yet. Use its existing disposer
                # for child/owner deletion and retained cleanup retries.
                try:
                    window.hide()
                except Exception as error:
                    self._errors.append('V2 pending hide: ' + str(error))
                self._dispose_panel(dict(window=window, binding=None, material_bridge=None))
                raise
            return window

    return SecondaryTopBarManager(runtime, adapter_factory=adapter_class,
        window_factory=window_factory, fullscreen_guard_factory=fullscreen_guard_factory)
