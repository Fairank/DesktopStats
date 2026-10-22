"""Finite settings-backdrop scheduling; no Qt, OS, window, or capture operations.

The GUI adapter supplies context/events, arms one single-shot timer using
next_delay_ms(), calls take_due(), performs the existing material request on the
GUI thread, then calls complete(). Configuration is never visual verification.
"""

import math
import time
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialRequest:
    token: int
    generation: int
    handle: int
    attempt: int
    reasons: tuple[str, ...]
    policy: str
    issued_at: float


class SettingsMaterialLifecycle:
    """One owned settings window, one GUI-thread caller, bounded event recovery.

    policy is 'allowed', 'disabled' (known policy), or 'unknown' (query failed).
    Disabled policy schedules cleanup, never an enabling request. The default
    desktop-acrylic backend keeps its existing no-retry policy behavior;
    system-blur retries a failed cleanup within the finite retry budget.

    notify() ignores movement, ordinary resize, sampling, and unknown events.
    Supply actual normal/maximized/minimized state in update_context() instead.
    A new native handle invalidates old results even if their timer has fired.
    """

    EVENTS = frozenset({
        "activated", "deactivated", "shown", "graphics_ready", "surface_created",
        "theme_changed", "composition_changed", "power_changed", "display_changed",
        "system_preferences", "preference_changed", "exposed", "first_frame",
    })
    POLICIES = frozenset({"allowed", "disabled", "unknown"})
    BACKENDS = frozenset({"desktop-acrylic", "system-blur"})
    WINDOW_STATES = frozenset({"normal", "maximized", "minimized"})
    REPORT_KEYS = frozenset({
        "material", "status", "fallback_reason", "backend_error", "build", "renderer",
        "frame_result", "backdrop_result", "backdrop_read_result", "backdrop_type",
        "redirection_alpha_result", "layered", "compositing_verified", "policy_state",
        "policy_reason", "policy_error", "attribute_20_result", "attribute_33_result",
        "attribute_34_result", "cleanup_backdrop_result", "cleanup_frame_result",
        "cleanup_backdrop_error", "cleanup_frame_error",
        "backend", "mechanism", "ok", "bool_result", "last_error", "accent_state",
        "coating_allowed", "coating_translucent", "blur_configured", "blur_may_remain",
        "cleanup_complete", "noop", "rejected",
        "frame_refresh_result", "frame_refresh_error", "frame_refresh_winerror", "frame_redraw_result",
    })

    def __init__(self, *, clock=None, debounce_ms=150, retry_delays=(.25, 1.0), backend="desktop-acrylic", settle_delay=None):
        if type(backend) is not str or backend not in self.BACKENDS:
            raise ValueError("Unknown material backend")
        if type(debounce_ms) not in (int, float) or not math.isfinite(debounce_ms) or debounce_ms < 0:
            raise ValueError("Nonnegative finite debounce_ms required")
        delays = tuple(retry_delays)
        if len(delays) > 8 or any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in delays):
            raise ValueError("At most eight positive finite retry delays required")
        if settle_delay is not None and (type(settle_delay) not in (int, float)
                or not math.isfinite(settle_delay) or settle_delay <= 0 or not delays):
            raise ValueError("Settlement needs a positive finite delay and a retry budget")
        self._clock = clock or time.monotonic
        self._backend = backend
        self._debounce = debounce_ms / 1000
        self._retry_delays = delays
        self._settle_delay = settle_delay
        self._handle = 0
        self._visible = False
        self._render_ready = True
        self._window_state = "normal"
        self._policy = "unknown"
        self._generation = 0
        self._token = 0
        self._attempt = 0
        self._applies_total = 0
        self._pending = set()
        self._due = None
        self._inflight = None
        self._state = "paused"
        self._closed = False
        self._last_report = {}
        self._last_request = None
        self._last_result_request = None
        self._completed_at = None

    def _eligible(self):
        return (not self._closed and self._handle > 0 and self._visible
                and self._window_state != "minimized"
                and (self._render_ready or self._policy == "disabled"))

    def _new_episode(self, reasons):
        self._pending = set(reasons)
        self._attempt = 0
        if self._eligible():
            self._due = self._clock() + self._debounce
            self._state = "pending"
        else:
            self._due = None
            self._state = ("closed" if self._closed else "waiting_for_render"
                           if self._handle > 0 and self._visible and self._window_state != "minimized"
                           and not self._render_ready else "paused")

    def update_context(self, *, handle, visible, window_state="normal", policy="unknown", render_ready=True):
        """Return whether context changed; never creates or reads a native handle.

        Call with handle=0 on native surface destruction. Hidden/minimized
        context invalidates an in-flight result and removes its scheduled retry.
        Showing/restoring schedules a fresh finite episode rather than replaying
        a callback for an old handle. Identical updates are exact no-ops.
        render_ready=False holds enabling requests without spending attempts;
        explicit policy-disabled cleanup may run before a first frame exists.
        """
        if type(handle) is not int or handle < 0 or type(visible) is not bool or type(render_ready) is not bool:
            raise ValueError("Nonnegative integer handle and boolean visible required")
        if window_state not in self.WINDOW_STATES or policy not in self.POLICIES:
            raise ValueError("Invalid window state or policy")
        if self._closed:
            return False
        current = (handle, visible, window_state, policy, render_ready)
        previous = (self._handle, self._visible, self._window_state, self._policy, self._render_ready)
        if current == previous:
            return False
        fields = ("handle_changed", "visibility_changed", "window_state_changed", "policy_changed", "render_ready_changed")
        reasons = tuple(field for field, one, two in zip(fields, previous, current) if one != two)
        self._handle, self._visible, self._window_state, self._policy, self._render_ready = current
        self._generation += 1
        self._inflight = None
        self._new_episode(reasons)
        return True

    def notify(self, reason):
        """Coalesce meaningful native events; ignore reentrant apply feedback.

        While waiting for a failure retry, events add reasons without resetting
        the retry budget or bringing its backoff deadline forward. A completed
        or exhausted episode may be retried on a later real lifecycle event.
        """
        if reason not in self.EVENTS or not self._eligible() or self._inflight is not None:
            return False
        if self._policy == "disabled":
            return False
        if self._due is not None:
            self._pending.add(reason)
            if self._state not in ("retry_wait", "settle_wait"):
                self._due = self._clock() + self._debounce
            return True
        self._new_episode((reason,))
        return True

    def next_delay_ms(self):
        """Single-shot GUI timer delay, or None when no timer should be armed."""
        if not self._eligible() or self._due is None or self._inflight is not None:
            return None
        return max(0, math.ceil((self._due - self._clock()) * 1000 - 1e-9))

    def request_now(self, reason="explicit"):
        """Queue an explicit GUI-thread request immediately without a window action.

        Used for existing Show/Apply entry points. This is a new finite episode,
        including one cleanup request for disabled policy. Reentrant requests
        and paused/closed windows are no-ops; arbitrary reasons are bounded.
        """
        if not self._eligible() or self._inflight is not None:
            return False
        if type(reason) is not str or not reason:
            raise ValueError("Nonempty explicit request reason required")
        self._new_episode(("explicit:" + reason[:64],))
        self._due = self._clock()
        return True

    def take_due(self):
        """Return one immutable request only when due, never a native call."""
        now = self._clock()
        if not self._eligible() or self._inflight is not None or self._due is None or now + 1e-12 < self._due:
            return None
        self._token += 1
        self._attempt += 1
        self._applies_total += 1
        request = MaterialRequest(self._token, self._generation, self._handle, self._attempt,
                                  tuple(sorted(self._pending)), self._policy, now)
        self._pending.clear()
        self._due = None
        self._inflight = self._last_request = request
        self._state = "applying"
        return request

    def complete(self, request, report):
        """Accept only the current request; return False for stale/closed tokens.

        A true result means accepted bookkeeping, never verified composition.
        The caller must not publish a rejected report to its current window.
        This method takes no callback and cannot activate, resize, or loop.
        """
        if self._closed or request is not self._inflight or request is None:
            return False
        if not isinstance(report, Mapping):
            raise ValueError("Material report must be a mapping")
        self._inflight = None
        self._completed_at = self._clock()
        self._last_report = self._bounded_report(report)
        self._last_result_request = request
        if self._backend == "system-blur":
            result = report.get("bool_result")
            success = (report.get("material") == "system-blur"
                       and report.get("blur_configured") is True
                       and type(result) in (int, bool) and result != 0
                       and report.get("status") != "fallback" and self._policy != "disabled")
            cleared = (report.get("ok") is True
                       and report.get("blur_may_remain") is not True
                       and report.get("status") != "cleanup-failed"
                       and (result is None or type(result) in (int, bool) and result != 0))
        else:
            success = (report.get("material") == "desktop-acrylic"
                       and report.get("backdrop_result") == 0
                       and report.get("backdrop_type") == 3
                       and report.get("status") != "fallback")
            cleared = True  # Preserve the established default backend contract.
        if self._policy == "disabled" and cleared:
            self._state = "policy_disabled"
        elif success and self._attempt == 1 and self._settle_delay is not None:
            # A successful request can precede the compositor's settled frame.
            # One later request shares the existing attempt budget; never poll
            # on every frame or ordinary resize and never claim visual proof.
            self._pending.add("render_settle")
            self._due = self._completed_at + self._settle_delay
            self._state = "settle_wait"
        elif success:
            self._state = "configured_unverified"
        elif report.get("fallback_reason") == "unsupported-windows" or (
            report.get("fallback_reason") == "material-disabled" and cleared
        ):
            self._state = "unavailable"
        elif self._attempt <= len(self._retry_delays):
            self._pending.add("retry")
            self._due = self._completed_at + self._retry_delays[self._attempt - 1]
            self._state = "retry_wait"
        else:
            self._state = "exhausted"
        return True

    @classmethod
    def _bounded_report(cls, report):
        value = {}
        for key in cls.REPORT_KEYS:
            item = report.get(key)
            if item is None or type(item) in (bool, int):
                if key in report:
                    value[key] = item
            elif type(item) is str:
                value[key] = item[:512]
            elif type(item) is float and math.isfinite(item):
                value[key] = item
        # Scheduler/native setup has no rendered-pixel evidence.
        value["compositing_verified"] = False
        return value

    def metadata(self):
        """Bounded, detached own-window bookkeeping; contains no image data."""
        request = self._last_request
        result_request = self._last_result_request
        return dict(state=self._state, backend=self._backend, closed=self._closed, generation=self._generation,
                    handle=self._handle, visible=self._visible, window_state=self._window_state,
                    render_ready=self._render_ready,
                    policy=self._policy, attempt=self._attempt, max_attempts=1 + len(self._retry_delays),
                    applies_total=self._applies_total, in_flight=self._inflight is not None,
                    pending_reasons=sorted(self._pending), due_at=self._due,
                    last_request=(dict(token=request.token, generation=request.generation, handle=request.handle,
                                       attempt=request.attempt, reasons=list(request.reasons), issued_at=request.issued_at)
                                  if request else None),
                    last_completed_at=self._completed_at, last_report=dict(self._last_report),
                    last_report_token=result_request.token if result_request else None,
                    last_report_generation=result_request.generation if result_request else None,
                    last_report_handle=result_request.handle if result_request else None,
                    compositing_verified=False)

    def close(self):
        """Idempotently cancel every pending request without an external action."""
        if self._closed:
            return
        self._closed = True
        self._generation += 1
        self._inflight = None
        self._due = None
        self._pending.clear()
        self._state = "closed"
