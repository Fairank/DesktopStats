"""Own-window Qt events to finite backdrop recovery; never manipulates a window.

All callbacks run on the owning GUI thread. compose_once(handle, policy) returns
a native setup report; publish(report) runs only for a still-current request.
This module contains no native API calls, window creation, focus/position/style
changes, capture, file IO, or production-app IPC.
"""

import copy
import logging
from ctypes import wintypes

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QEvent,
    QObject,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication, QPlatformSurfaceEvent, QSurface
from PySide6.QtQuick import QQuickWindow

from settings_material_lifecycle import SettingsMaterialLifecycle


class _NativeMaterialEvents(QAbstractNativeEventFilter):
    REASONS = {
        0x031A: "theme_changed",                 # WM_THEMECHANGED
        0x031E: "composition_changed",           # WM_DWMCOMPOSITIONCHANGED
        0x001A: "system_preferences",            # WM_SETTINGCHANGE
        0x0218: "power_changed",                 # WM_POWERBROADCAST
        0x007E: "display_changed",               # WM_DISPLAYCHANGE
    }

    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge

    def nativeEventFilter(self, event_type, message):
        bridge = self.bridge
        if bridge._closed or not bridge._handle or event_type != b"windows_generic_MSG":
            return False, 0
        try:
            # Qt supplies this live MSG pointer. Read no HWND outside our window.
            address = int(message)
            if address <= 0:
                return False, 0
            msg = wintypes.MSG.from_address(address)
            if int(msg.hWnd or 0) == bridge._handle:
                reason = self.REASONS.get(msg.message)
                if reason:
                    bridge.request(reason)
        except (ValueError, TypeError, OverflowError):
            logging.warning("Could not decode an own-window material notification")
        return False, 0  # Never consume or modify a native message.


class SettingsMaterialBridge(QObject):
    """Bind one existing QWindow; start()/request()/compose_now()/status()/close().

    policy_reader() returns a dict with state allowed|disabled|unknown. The exact
    returned dict is supplied to compose_once(handle, policy), so policy is not
    read a second time during that attempt. The caller owns the native call.
    wait_for_first_frame=None automatically gates Quick desktop-acrylic only;
    True explicitly gates a Quick client (including system-blur), and False
    preserves immediate requests. Opt-in on a plain window is rejected unless
    a separate actual QQuickWindow is supplied as frame_source. The native
    window remains the sole handle/event/cleanup owner in that arrangement.
    """

    _render_notice = Signal(int, str)

    def __init__(self, window, parent=None, *, compose_once, policy_reader, publish, clock=None,
                 backend="desktop-acrylic", release_surface=None, wait_for_first_frame=None,
                 activation_requests=True, frame_source=None, allow_hidden_prepare=False):
        super().__init__(parent)
        if release_surface is not None and not callable(release_surface):
            raise ValueError("release_surface must be callable or None")
        if wait_for_first_frame is not None and type(wait_for_first_frame) is not bool:
            raise ValueError("wait_for_first_frame must be None or a boolean")
        if type(activation_requests) is not bool:
            raise ValueError("activation_requests must be a boolean")
        if type(allow_hidden_prepare) is not bool:
            raise ValueError("allow_hidden_prepare must be a boolean")
        if frame_source is not None and not isinstance(frame_source, QQuickWindow):
            raise ValueError("frame_source requires an actual QQuickWindow")
        self._separate_frame_source = frame_source is not None and frame_source is not window
        if self._separate_frame_source and wait_for_first_frame is False:
            raise ValueError("A separate frame_source requires first-frame gating")
        if frame_source is not None and frame_source.thread() != window.thread():
            raise ValueError("Native window and frame_source require the same GUI thread")
        if allow_hidden_prepare and (not self._separate_frame_source or backend not in ("desktop-acrylic", "system-blur")
                or window.surfaceType() != QSurface.RasterSurface or window.format().alphaBufferSize() != 0
                or frame_source.parent() is not window):
            raise ValueError("Hidden preparation requires a Raster alpha0 owner and its Quick child")
        self._allow_hidden_prepare = allow_hidden_prepare
        self._backend_name = backend
        self._hidden_revision = 0
        self._hidden_token_counter = 0
        self._hidden_token = None
        self._hidden_snapshot = None
        self._hidden_prepare_count = 0
        self._hidden_adoptions = 0
        self._hidden_report = {}
        self._hidden_release_pending = False
        self._activation_requests = activation_requests
        self._frame_window = window if frame_source is None else frame_source
        quick_frames = (callable(getattr(self._frame_window, "isSceneGraphInitialized", None))
                        and getattr(self._frame_window, "frameSwapped", None) is not None
                        and getattr(self._frame_window, "sceneGraphInvalidated", None) is not None)
        if wait_for_first_frame is True and not quick_frames:
            raise ValueError("First-frame gating requires a Quick window with frame signals")
        self._window = window
        self._compose_once = compose_once
        self._policy_reader = policy_reader
        self._publish = publish
        self._life = SettingsMaterialLifecycle(clock=clock, backend=backend)
        self._release_surface = release_surface
        self._surface_serial = 0
        self._released_surface = None
        self._releasing_surface = False
        self._release_error = ""
        self._release_report = {}
        self._release_count = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._handle = 0
        self._surface_alive = False
        self._started = False
        self._closed = False
        self._native_installed = False
        self._native = _NativeMaterialEvents(self)
        self._policy = {"state": "unknown", "reason": "not-read"}
        self._publish_error = ""
        self._graphics_connected = False
        self._frame_filter_installed = False
        self._frame_surface_alive = False
        self._frame_surface_serial = 0
        self._frame_exposed = False
        # A QQuickWindow's HWND/Show and sceneGraphInitialized both precede its
        # first submitted frame. DWM configuration can succeed during that gap.
        # The normal settings backend waits automatically. A new Quick client
        # may explicitly opt in with system-blur; its existing callers retain
        # the immediate contract unless they request that gate.
        self._wait_for_frame = bool(quick_frames and (
            (self._separate_frame_source or backend == "desktop-acrylic")
            if wait_for_first_frame is None else wait_for_first_frame))
        # Only the normal Quick settings host needs a post-present settlement.
        # Legacy alpha widgets and opt-in blur clients retain their contract.
        if self._wait_for_frame and backend == "desktop-acrylic":
            self._life = SettingsMaterialLifecycle(clock=clock, backend=backend, settle_delay=.25)
        self._render_epoch = 0
        self._latched_frame_epoch = -1
        self._update_requested_epoch = -1
        self._first_frame = False
        self._exposed = False
        self._frame_connected = False
        self._invalidated_connected = False
        self._render_notice.connect(self._render_event, Qt.QueuedConnection)

    def _assert_gui_thread(self):
        # Closed bridges may still receive already queued render notices after
        # the native owner has been deleted. Never dereference that Qt wrapper.
        if self._closed:
            return
        if self._window is not None and QThread.currentThread() != self._window.thread():
            raise RuntimeError("Settings material bridge requires the window GUI thread")
        if self._frame_window is not None and QThread.currentThread() != self._frame_window.thread():
            raise RuntimeError("Settings material bridge requires the frame source GUI thread")

    def start(self):
        self._assert_gui_thread()
        if self._started or self._closed:
            return False
        self._started = True
        self._window.installEventFilter(self)
        self._window.destroyed.connect(self._window_destroyed)
        if self._separate_frame_source:
            self._frame_window.installEventFilter(self)
            self._frame_window.destroyed.connect(self._frame_source_destroyed)
            self._frame_filter_installed = True
            self._adopt_frame_surface()
            self._exposed = self._window.isExposed()
            self._frame_exposed = self._frame_window.isExposed()
        ready = getattr(self._frame_window, "sceneGraphInitialized", None)
        if ready is not None:
            ready.connect(self._queue_graphics_ready, Qt.DirectConnection)
            self._graphics_connected = True
        if self._wait_for_frame:
            self._frame_window.frameSwapped.connect(self._queue_first_frame, Qt.DirectConnection)
            self._frame_connected = True
            self._frame_window.sceneGraphInvalidated.connect(self._queue_graphics_invalidated, Qt.DirectConnection)
            self._invalidated_connected = True
        app = QGuiApplication.instance()
        if app is not None and app.platformName() == "windows":
            app.installNativeEventFilter(self._native)
            self._native_installed = True
        # A visible window necessarily has a native surface. Never call winId()
        # on an unshown window merely to obtain or force-create its handle.
        self._adopt_visible_surface()
        self._sync_context()
        self._request_render()
        self._arm()
        return True

    def _adopt_visible_surface(self):
        """Adopt an already-visible surface even if it predates this bridge.

        Another own-window adapter may have created an HWND while hidden before
        start() could observe SurfaceCreated. Show proves it now exists; a
        hidden window remains untouched. Repeated show never invents a new
        surface generation when the native identity did not change.
        """
        if self._window is None or not self._window.isVisible():
            return
        handle = int(self._window.winId())
        if handle > 0 and (not self._surface_alive or handle != self._handle):
            self._surface_serial += 1
            self._reset_render_wait()
        self._surface_alive = handle > 0
        self._handle = handle

    def _reset_render_wait(self):
        """Invalidate queued render notices without touching the Qt window."""
        self._render_epoch += 1
        self._first_frame = False

    def _adopt_frame_surface(self):
        # Show/visible proves a rendering surface can exist. Never obtain the
        # renderer's winId: only the native owner supplies a material handle.
        if (self._frame_window is not None and self._frame_window.isVisible()
                and not self._frame_surface_alive):
            self._frame_surface_alive = True
            self._frame_surface_serial += 1

    def _pause_frame_context(self):
        # GUI-only invalidation also retires an in-flight disabled-policy clear
        # whose render_ready was already false. No native handle is changed.
        context = self._life.metadata()
        self._life.update_context(handle=self._handle, visible=False,
                                  window_state=context["window_state"],
                                  policy=context["policy"], render_ready=False)

    def _separate_windows_ready(self, *, visible=None):
        return bool(self._window is not None and self._frame_window is not None
                    and self._surface_alive and self._frame_surface_alive
                    and (self._window.isVisible() if visible is None else visible)
                    and self._window.isExposed()
                    and not self._window.windowState() & Qt.WindowMinimized
                    and self._frame_window.isVisible() and self._frame_window.isExposed()
                    and not self._frame_window.windowState() & Qt.WindowMinimized)

    def _render_ready(self):
        if self._separate_frame_source and not self._separate_windows_ready():
            return False
        return (not self._wait_for_frame or (self._first_frame and self._frame_window is not None
                and self._frame_window.isExposed() and self._frame_window.isSceneGraphInitialized()))

    def _request_render(self):
        # A bridge attached after the initial frame still needs one fresh frame.
        # update() schedules normal Qt rendering; it cannot resize, raise, focus,
        # create a hidden native window, or repeatedly request every frame.
        if (self._wait_for_frame and self._frame_window is not None and self._frame_window.isVisible()
                and self._frame_window.isExposed() and self._frame_window.windowState() != Qt.WindowMinimized
                and (not self._separate_frame_source or self._separate_windows_ready())
                and self._update_requested_epoch != self._render_epoch):
            self._update_requested_epoch = self._render_epoch
            self._frame_window.update()

    def _read_policy(self):
        previous = self._policy
        try:
            value = self._policy_reader()
            if not isinstance(value, dict) or value.get("state") not in self._life.POLICIES:
                raise ValueError("Policy reader must return an explicit policy state")
            self._policy = dict(value)
        except Exception as error:
            self._policy = {"state": "unknown", "reason": "policy-query-failed",
                            "error": (type(error).__name__ + ": " + str(error))[:512]}
        if self._allow_hidden_prepare and previous != self._policy:
            self._invalidate_hidden_preparation()

    def _sync_context(self, *, visible=None):
        if self._closed or self._window is None or self._releasing_surface:
            return False
        self._read_policy()
        if self._closed or self._window is None or self._releasing_surface:
            return False
        state = self._window.windowState()
        window_state = ("minimized" if state & Qt.WindowMinimized
                        else "maximized" if state & Qt.WindowMaximized else "normal")
        visible = self._window.isVisible() if visible is None else visible
        if self._separate_frame_source:
            # Also blocks policy-disabled API calls until both owned windows
            # are shown/exposed. Teardown cleanup retains its native owner.
            visible = self._separate_windows_ready(visible=visible)
        return self._life.update_context(handle=self._handle,
                                         visible=visible,
                                         window_state=window_state, policy=self._policy["state"],
                                         render_ready=self._render_ready())

    def _arm(self):
        self._timer.stop()
        delay = self._life.next_delay_ms()
        if delay is not None and not self._closed:
            self._timer.start(delay)

    def request(self, reason):
        """Merge one meaningful event; unknown events do not trigger policy IO."""
        self._assert_gui_thread()
        if self._closed or self._releasing_surface or not self._started or reason not in self._life.EVENTS:
            return False
        if reason in {"theme_changed", "composition_changed", "power_changed", "display_changed",
                      "system_preferences", "preference_changed"}:
            self._invalidate_hidden_preparation()
        changed = self._sync_context()
        queued = self._life.notify(reason)
        self._arm()
        return changed or queued

    def compose_now(self, reason="explicit"):
        """Existing Show/Apply request, or None while paused/not-rendered/closed.

        Returns the accepted/published report. Does not show, activate, resize,
        create a native handle, or change flags. Policy-disabled still clears
        the backdrop once, with no automatic retry. A Quick settings window
        waits for its exposed, current-surface first frame before enabling.
        """
        self._assert_gui_thread()
        if self._closed or self._releasing_surface or not self._started:
            return None
        self._sync_context()
        if not self._life.request_now(reason):
            self._arm()
            return None
        return self._run_due()

    def refresh_policy(self):
        """Low-rate policy check; identical context never restarts an episode."""
        self._assert_gui_thread()
        if self._closed or self._releasing_surface or not self._started:
            return False
        changed = self._sync_context()
        self._arm()
        return changed

    def _invalidate_hidden_preparation(self):
        # Also called by a direct render-thread signal. Change only Python
        # scalars here; window/policy/native work remains on the GUI thread.
        self._hidden_revision += 1
        self._hidden_snapshot = None

    def _hidden_current(self, token):
        """Exact temporary capability, never an alternative visible gate."""
        return bool(token is not None and self._hidden_token is token and self._allow_hidden_prepare
                    and self._started and not self._closed and not self._releasing_surface
                    and self._window is not None and self._frame_window is not None
                    and self._surface_alive and self._handle > 0
                    and token["identity"] == (self._surface_serial, self._handle)
                    and token["revision"] == self._hidden_revision
                    and token["epoch"] == self._render_epoch
                    and token["generation"] == self._life.metadata()["generation"]
                    and token["frame"] is self._frame_window
                    and self._frame_window.parent() is self._window
                    and self._window.surfaceType() == QSurface.RasterSurface
                    and self._window.format().alphaBufferSize() == 0
                    and not self._window.isVisible() and not self._frame_window.isVisible()
                    and not self._window.windowState() & Qt.WindowMinimized)

    def hidden_preparation_current(self, handle, serial, token):
        """Runtime's native validity callback for this one synchronous attempt."""
        self._assert_gui_thread()
        current = self._hidden_token
        return bool(self._hidden_current(current) and type(token) is int
                    and current["token"] == token and current["identity"] == (serial, handle))

    def prepare_hidden(self):
        """Prepare an already-created Raster owner before its explicit Show.

        This opt-in does not create/read either window's native ID and does not
        make the ordinary lifecycle eligible while hidden. Cleanup continues to
        belong to this bridge's observed owner surface, even if Show never runs.
        The current opening adopts its prepared result after the actual Quick
        first-frame gate, including a readable fallback. A first-show failure
        must not turn into glass later in that same opening. A real recovery,
        policy change, hide or surface invalidation retires this snapshot.
        """
        self._assert_gui_thread()
        if (not self._allow_hidden_prepare or self._closed or not self._started
                or self._releasing_surface or self._hidden_token is not None
                or self._window is None or self._frame_window is None):
            return None
        self._sync_context()
        self._invalidate_hidden_preparation()
        self._hidden_token_counter += 1
        token = dict(token=self._hidden_token_counter, identity=(self._surface_serial, self._handle),
                     revision=self._hidden_revision, epoch=self._render_epoch,
                     generation=self._life.metadata()["generation"], frame=self._frame_window)
        self._hidden_token = token
        try:
            if not self._hidden_current(token):
                return None
            policy = copy.deepcopy(self._policy)
            self._hidden_prepare_count += 1
            try:
                report = self._compose_once(self._handle, policy)
                if not isinstance(report, dict):
                    raise ValueError("Material callback must return a dict")
            except Exception as error:
                report = dict(material="solid", status="fallback", ok=False,
                              coating_allowed=False, coating_translucent=False, blur_configured=False,
                              fallback_reason="native-api-unavailable",
                              backend_error=(type(error).__name__ + ": " + str(error))[:512])
            if not self._hidden_current(token):
                return None
            result = dict(report, preparation="before-show", surface_serial=self._surface_serial,
                          compositing_verified=False, policy=self._safe_policy(policy),
                          lifecycle=self._life.metadata())
            try:
                self._publish(result)
                self._publish_error = ""
            except Exception as error:
                self._publish_error = (type(error).__name__ + ": " + str(error))[:512]
                logging.warning("Could not publish hidden settings material: %s", self._publish_error)
                return None
            if not self._hidden_current(token):
                return None
            self._hidden_report = self._life._bounded_report(result)
            acrylic_ready = (self._backend_name == "desktop-acrylic"
                and report.get("material") == "desktop-acrylic"
                and report.get("backdrop_type") == 3 and report.get("backdrop_result") == 0)
            blur_result = report.get("bool_result")
            blur_ready = (self._backend_name == "system-blur" and report.get("material") == "system-blur"
                and report.get("blur_configured") is True and type(blur_result) is int
                and -(1 << 31) <= blur_result < (1 << 31) and blur_result != 0)
            configured = (report.get("ok") is True and report.get("status") == "configured-unverified"
                          and (acrylic_ready or blur_ready) and report.get("coating_allowed") is True
                          and report.get("coating_translucent") is True and policy.get("state") == "allowed")
            self._hidden_snapshot = dict(identity=token["identity"], revision=token["revision"],
                                         frame=token["frame"], policy=policy, configured=configured,
                                         report=copy.deepcopy(result))
            return result
        finally:
            if self._hidden_token is token:
                self._hidden_token = None
            if self._hidden_release_pending:
                # A synchronous native callback may close the bridge while
                # its backend is busy. Release after that callback unwinds,
                # while retaining the original native owner's identity.
                self._hidden_release_pending = False
                self._release_current_surface()

    def _prepared_report(self, handle, policy):
        snapshot = self._hidden_snapshot
        if (snapshot is None or self._closed or not self._surface_alive
                or snapshot["identity"] != (self._surface_serial, handle)
                or snapshot["revision"] != self._hidden_revision
                or snapshot["frame"] is not self._frame_window
                or self._frame_window is None or self._frame_window.parent() is not self._window
                or snapshot["policy"] != policy):
            return None
        report = snapshot["report"]
        if policy.get("state") != "allowed" and (
                report.get("blur_may_remain") is True or report.get("cleanup_complete") is False
                or report.get("status") == "cleanup-failed"):
            # Policy cleanup cannot enable glass. Keep its bounded retry rather
            # than freeze a potentially uncleared backdrop for this opening.
            return None
        self._hidden_adoptions += 1
        return dict(copy.deepcopy(report), preparation=(
            "adopted-before-show" if snapshot["configured"] else "adopted-before-show-fallback"))

    def _run_due(self):
        if self._releasing_surface:
            return None
        request = self._life.take_due()
        if request is None:
            self._arm()
            return None
        render_epoch = self._render_epoch
        policy = dict(self._policy)
        try:
            report = self._prepared_report(request.handle, policy)
            if report is None:
                report = self._compose_once(request.handle, policy)
            if not isinstance(report, dict):
                raise ValueError("Material callback must return a dict")
        except Exception as error:
            report = dict(material="solid", status="fallback", fallback_reason="native-api-unavailable",
                          backend_error=(type(error).__name__ + ": " + str(error))[:512],
                          compositing_verified=False)
        if self._separate_frame_source and render_epoch != self._render_epoch:
            # A render-thread invalidation may be queued behind this native
            # callback. Its scalar epoch changes immediately, before GUI Qt
            # work is allowed, so it cannot publish success for that frame.
            self._pause_frame_context()
            self._sync_context()
            self._request_render()
            self._arm()
            return None
        if not self._life.complete(request, report):
            self._arm()
            return None
        if self._life.metadata()["state"] == "settle_wait":
            # Schedule an actual client frame before the finite second request.
            # This changes no geometry, z-order, activation, or window flags.
            try:
                if self._frame_window is not None:
                    self._frame_window.update()
            except RuntimeError as error:
                report = dict(report, render_update_error=str(error)[:512])
            # update() normally just queues a frame, but can reenter window
            # lifetime handlers. Keep the same stale-publication guard as the
            # native callback; an old report must not relight a hidden window.
            current = self._life.metadata()
            if self._separate_frame_source and render_epoch != self._render_epoch:
                self._pause_frame_context()
                self._sync_context()
                self._request_render()
                self._arm()
                return None
            if (self._closed or self._window is None
                    or current["generation"] != request.generation
                    or current["handle"] != request.handle or not current["visible"]):
                self._arm()
                return None
        result = dict(report)
        result["compositing_verified"] = False
        result["policy"] = self._safe_policy(policy)
        result["lifecycle"] = self._life.metadata()
        try:
            self._publish(result)
            self._publish_error = ""
        except Exception as error:
            self._publish_error = (type(error).__name__ + ": " + str(error))[:512]
            logging.warning("Could not publish settings material recovery: %s", self._publish_error)
        self._arm()
        return result

    @Slot()
    def _on_timeout(self):
        if self._closed or self._releasing_surface:
            return
        self._sync_context()
        self._run_due()

    @Slot()
    def _queue_graphics_ready(self):
        # These direct slots may run on Qt's render thread. Only read immutable
        # Python epoch scalars and emit a queued notice; never call Qt window,
        # policy, native backend, or controller APIs on the render thread.
        if not self._closed:
            self._render_notice.emit(self._render_epoch, "graphics_ready")

    @Slot()
    def _queue_first_frame(self):
        epoch = self._render_epoch
        if not self._closed and self._latched_frame_epoch != epoch:
            self._latched_frame_epoch = epoch
            self._render_notice.emit(epoch, "first_frame")

    @Slot()
    def _queue_graphics_invalidated(self):
        if not self._closed:
            self._invalidate_hidden_preparation()
            if self._separate_frame_source:
                # Only scalar metadata changes on the render thread. Reject
                # an in-flight host success even before queued GUI delivery.
                self._reset_render_wait()
            self._render_notice.emit(self._render_epoch, "graphics_invalidated")

    @Slot(int, str)
    def _render_event(self, epoch, reason):
        if self._closed or self._window is None or epoch != self._render_epoch:
            return
        self._assert_gui_thread()
        if reason == "graphics_invalidated":
            self._reset_render_wait()
            if self._separate_frame_source:
                self._pause_frame_context()
            self._sync_context()
            self._request_render()
            self._arm()
            return
        if reason == "first_frame":
            if (not self._window.isVisible() or not self._window.isExposed()
                    or self._frame_window is None or not self._frame_window.isVisible()
                    or not self._frame_window.isExposed()
                    or not self._frame_window.isSceneGraphInitialized()
                    or self._separate_frame_source and not self._separate_windows_ready()):
                # A delayed frame notice from a stopped renderer cannot stand
                # in for the next initialized scene's first submitted frame.
                self._latched_frame_epoch = -1
                return
            self._first_frame = True
        self.request(reason)

    def eventFilter(self, watched, event):
        if self._closed or self._releasing_surface:
            return False
        if self._separate_frame_source and watched is self._frame_window:
            return self._frame_event(event)
        if watched is not self._window:
            return False
        kind = event.type()
        if kind == QEvent.PlatformSurface:
            if event.surfaceEventType() == QPlatformSurfaceEvent.SurfaceCreated:
                self._invalidate_hidden_preparation()
                self._surface_alive = True
                self._surface_serial += 1
                self._reset_render_wait()
                self._handle = int(self._window.winId())
                self._sync_context()
                self._life.notify("surface_created")
            elif event.surfaceEventType() == QPlatformSurfaceEvent.SurfaceAboutToBeDestroyed:
                self._invalidate_hidden_preparation()
                # Invalidate in-flight reports before a synchronous native clear
                # can dispatch any more window messages. Keep our known handle
                # available for release; never query/create one during teardown.
                context = self._life.metadata()
                self._life.update_context(handle=0, visible=context["visible"],
                                          window_state=context["window_state"], policy=context["policy"])
                self._timer.stop()
                self._release_current_surface()
                self._reset_render_wait()
                self._surface_alive = False
                self._handle = 0
                self._sync_context()
            self._arm()
        elif kind in (QEvent.Show, QEvent.Hide):
            if kind == QEvent.Hide:
                self._invalidate_hidden_preparation()
            self._reset_render_wait()
            if kind == QEvent.Show:
                self._adopt_visible_surface()
            self._sync_context(visible=kind == QEvent.Show)
            if kind == QEvent.Show:
                self._life.notify("shown")
                self._request_render()
            self._arm()
        elif kind == QEvent.Expose and self._wait_for_frame:
            exposed = self._window.isExposed()
            if exposed != self._exposed:
                self._exposed = exposed
                self._reset_render_wait()
                self._sync_context()
                if exposed:
                    self._life.notify("exposed")
                    self._request_render()
                self._arm()
        elif kind == QEvent.WindowStateChange:
            if self._wait_for_frame:
                self._reset_render_wait()
            self._sync_context()
            self._request_render()
            self._arm()
        elif self._activation_requests and kind in (QEvent.WindowActivate, QEvent.WindowDeactivate):
            self.request("activated" if kind == QEvent.WindowActivate else "deactivated")
        return False

    def _frame_event(self, event):
        """Render-only lifecycle: never queries a client native handle."""
        kind = event.type()
        if kind == QEvent.PlatformSurface:
            if event.surfaceEventType() == QPlatformSurfaceEvent.SurfaceCreated:
                self._frame_surface_alive = True
                self._frame_surface_serial += 1
            elif event.surfaceEventType() == QPlatformSurfaceEvent.SurfaceAboutToBeDestroyed:
                self._invalidate_hidden_preparation()
                self._frame_surface_alive = False
            else:
                return False
        elif kind in (QEvent.Show, QEvent.Hide):
            if kind == QEvent.Show:
                self._adopt_frame_surface()
            else:
                self._invalidate_hidden_preparation()
        elif kind == QEvent.Expose:
            exposed = self._frame_window.isExposed()
            if exposed == self._frame_exposed:
                return False
            self._frame_exposed = exposed
        elif kind not in (QEvent.WindowStateChange, QEvent.ScreenChangeInternal,
                           QEvent.DevicePixelRatioChange):
            return False
        self._reset_render_wait()
        self._pause_frame_context()
        self._sync_context()
        self._request_render()
        self._arm()
        return False

    @staticmethod
    def _safe_policy(policy):
        # Policy is diagnostics, never an arbitrary serialized image/payload.
        value = {}
        for key in ("state", "enabled", "reason", "error", "winerror", "api", "high_contrast",
                    "high_contrast_query_ok", "enable_transparency", "registry_error"):
            item = policy.get(key)
            if item is None or type(item) in (bool, int):
                if key in policy:
                    value[key] = item
            elif type(item) is str:
                value[key] = item[:512]
        return value

    def _release_current_surface(self):
        identity = (self._surface_serial, self._handle)
        if (self._release_surface is None or self._window is None or not self._surface_alive
                or self._handle <= 0 or identity == self._released_surface):
            return
        # Mark before invoking user code: nested close/destroy must not release
        # this surface twice, even if its callback raises.
        self._released_surface = identity
        self._release_count += 1
        self._release_error = ""
        self._release_report = {}
        self._releasing_surface = True
        try:
            report = self._release_surface(self._handle)
            if isinstance(report, dict):
                self._release_report = self._life._bounded_report(report)
        except Exception as error:
            self._release_error = (type(error).__name__ + ": " + str(error))[:512]
            logging.warning("Could not release owned window material: %s", self._release_error)
        finally:
            self._releasing_surface = False

    def status(self):
        value = self._life.metadata()
        value.update(started=self._started, native_filter_installed=self._native_installed,
                     allow_hidden_prepare=self._allow_hidden_prepare,
                     preparing_hidden=self._hidden_token is not None,
                     preparation_token=self._hidden_token["token"] if self._hidden_token else None,
                      hidden_prepared=bool(self._hidden_snapshot and self._hidden_snapshot["configured"]),
                      hidden_fallback_prepared=bool(self._hidden_snapshot and not self._hidden_snapshot["configured"]),
                     hidden_prepare_count=self._hidden_prepare_count,
                     hidden_adoptions=self._hidden_adoptions,
                     hidden_prepare_report=dict(self._hidden_report),
                     hidden_release_pending=self._hidden_release_pending,
                     surface_serial=self._surface_serial, surface_handle=self._handle,
                     surface_alive=self._surface_alive, policy_details=self._safe_policy(self._policy),
                     publish_error=self._publish_error, timer_active=self._timer.isActive(),
                     release_error=self._release_error, release_count=self._release_count,
                     release_report=dict(self._release_report),
                     render_gate=self._wait_for_frame, render_epoch=self._render_epoch,
                     frame_epoch=self._render_epoch, separate_frame_source=self._separate_frame_source,
                     frame_source_alive=self._frame_window is not None,
                     frame_surface_alive=(self._frame_surface_alive if self._separate_frame_source else self._surface_alive),
                     frame_surface_serial=(self._frame_surface_serial if self._separate_frame_source else self._surface_serial),
                     frame_visible_now=self._frame_window.isVisible() if self._frame_window is not None else False,
                     frame_exposed=self._frame_window.isExposed() if self._frame_window is not None else False,
                     first_frame_observed=self._first_frame,
                     window_visible_now=self._window.isVisible() if self._window is not None else False,
                     window_minimized_now=(self._window.windowState() == Qt.WindowMinimized) if self._window is not None else False,
                     exposed=self._window.isExposed() if self._window is not None else False,
                     released_surface=(dict(serial=self._released_surface[0], handle=self._released_surface[1])
                                       if self._released_surface else None))
        return value

    @Slot()
    def _window_destroyed(self):
        # SurfaceAboutToBeDestroyed is the last safe opportunity to clear.
        # A QObject destruction notification must never recreate/query an HWND.
        self._invalidate_hidden_preparation()
        self._surface_alive = False
        self._reset_render_wait()
        self._handle = 0
        context = self._life.metadata()
        self._life.update_context(handle=0, visible=False, window_state=context["window_state"],
                                  policy=context["policy"])
        self._window = None
        if not self._separate_frame_source:
            self._frame_window = None
        self.close()

    @Slot()
    def _frame_source_destroyed(self):
        # The native owner remains live for release_surface()/close(). Never
        # inspect the deleted renderer, obtain its winId, or close the bridge
        # before that independent owner's material can be cleaned up.
        self._invalidate_hidden_preparation()
        self._frame_window = None
        self._frame_surface_alive = False
        self._frame_filter_installed = False
        self._graphics_connected = False
        self._frame_connected = False
        self._invalidated_connected = False
        self._reset_render_wait()
        context = self._life.metadata()
        self._life.update_context(handle=self._handle, visible=False,
                                  window_state=context["window_state"],
                                  policy=context["policy"], render_ready=False)
        self._timer.stop()

    def close(self):
        self._assert_gui_thread()
        if self._closed:
            return
        preparing = self._hidden_token is not None
        self._invalidate_hidden_preparation()
        self._hidden_token = None
        self._closed = True
        self._timer.stop()
        self._life.close()
        if preparing:
            self._hidden_release_pending = True
        else:
            self._release_current_surface()
        app = QGuiApplication.instance()
        if self._native_installed and app is not None:
            app.removeNativeEventFilter(self._native)
        self._native_installed = False
        if self._window is not None:
            try:
                self._window.removeEventFilter(self)
                self._window.destroyed.disconnect(self._window_destroyed)
            except (RuntimeError, TypeError):
                pass
        if self._frame_window is not None:
            try:
                if self._frame_filter_installed:
                    self._frame_window.removeEventFilter(self)
                    self._frame_window.destroyed.disconnect(self._frame_source_destroyed)
                if self._graphics_connected:
                    self._frame_window.sceneGraphInitialized.disconnect(self._queue_graphics_ready)
                if self._frame_connected:
                    self._frame_window.frameSwapped.disconnect(self._queue_first_frame)
                if self._invalidated_connected:
                    self._frame_window.sceneGraphInvalidated.disconnect(self._queue_graphics_invalidated)
            except (RuntimeError, TypeError):
                pass
        self._frame_filter_installed = False
        if self._separate_frame_source:
            self._frame_window = None
            self._frame_surface_alive = False
