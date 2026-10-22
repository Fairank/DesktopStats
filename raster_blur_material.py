"""Owned Raster-host blur: DWM none/frame -1, WCA state3, then black paint.

The existing Acrylic adapter supplies the GUI-thread, HWND ownership and surface
generation guards. API loading stays lazy. A host may supply its black-paint
callback here or keep its existing guarded paint immediately after apply().
Configured requests do not establish a visible compositor result.
"""

from native_widget_material import _CtypesBlurAPI
from settings_acrylic_material import SettingsAcrylicMaterial, _Rejected


class RasterBlurMaterial(SettingsAcrylicMaterial):
    """Same apply/clear/close contract as SettingsAcrylicMaterial.

    One instance owns one retained (surface_id, HWND). Failed cleanup keeps that
    identity and can be retried with clear/close; it never clears a replacement.
    No frame, flag, geometry, activation, capture or delayed operation is added.
    """

    def __init__(self, dwm_api=None, accent_api=None, *, paint_background=None):
        super().__init__(api=dwm_api)
        if paint_background is not None and not callable(paint_background):
            raise TypeError("Raster background painter must be callable")
        self._accent_api = accent_api
        self._paint_background = paint_background

    def _report(self, hwnd=None, policy=None, reason=""):
        return dict(super()._report(hwnd, policy, reason),
                    mechanism="raster-frame-accent-blur", bool_result=None,
                    last_error=None, accent_state=0, frame_margins=[-1] * 4,
                    activation_independent=True)

    @staticmethod
    def _accent_result(value):
        if (not isinstance(value, tuple) or len(value) != 2
                or any(type(part) is not int for part in value)
                or not -(1 << 31) <= value[0] < 1 << 31
                or not 0 <= value[1] < 1 << 32):
            raise ValueError("Invalid native WCA result")
        return value

    def _accent_call(self, identity, valid, enabled, *, releasing=False):
        self._guard(identity, valid, releasing=releasing)
        if self._accent_api is None:
            self._accent_api = _CtypesBlurAPI()
        # Loading a library or a fake callback can reenter owner destruction.
        self._guard(identity, valid, releasing=releasing)
        self._pending = True
        self._mutations += 1
        value = self._accent_api.set_blur(identity[1], enabled)
        self._guard(identity, valid, releasing=releasing)
        return self._accent_result(value)

    @staticmethod
    def _error(report, error):
        SettingsAcrylicMaterial._error(report, error)
        if not isinstance(error, _Rejected):
            report["fallback_reason"] = "raster-blur-api-error"

    def _clear_current(self, identity, valid):
        report = self._report(identity[1])
        report.update(status="cleanup-failed", cleanup_complete=False,
                      frame_margins=[0] * 4)
        errors = []
        try:
            # Keep this order even if a request fails. Ownership/generation
            # rejection aborts immediately; an API failure permits best effort.
            try:
                value, last_error = self._accent_call(identity, valid, False, releasing=True)
                report.update(bool_result=value, last_error=last_error)
                if value == 0:
                    errors.append("accent-clear-failed")
            except _Rejected:
                raise
            except Exception as error:
                errors.append(f"{type(error).__name__}: {error}")
            for name, args, field in (
                ("set_backdrop", (1,), "backdrop_result"),
                ("extend_frame", ((0, 0, 0, 0),), "frame_result"),
            ):
                try:
                    report[field] = self._hr(
                        self._call(identity, valid, name, *args, releasing=True))
                    if report[field] != 0:
                        errors.append(field + "-failed")
                except _Rejected:
                    raise
                except Exception as error:
                    errors.append(f"{type(error).__name__}: {error}")
            read_hr, actual = self._call(identity, valid, "get_backdrop", releasing=True)
            report.update(readback_result=self._hr(read_hr), backdrop_type=actual)
            if read_hr != 0 or type(actual) is not int or actual != 1:
                errors.append("cleanup-readback-mismatch")
            self._guard(identity, valid, releasing=True)
            if not errors:
                self.identity = self._alive = None
                self._pending = self.prepared = self.cleanup_failed = False
                return dict(report, ok=True, status="no-blur", complete=True,
                            cleanup_complete=True, blur_may_remain=False,
                            fallback_reason="")
            report.update(fallback_reason="raster-blur-clear-failed",
                          backend_error="; ".join(errors)[:500])
        except Exception as error:
            self._error(report, error)
            report["status"] = "cleanup-failed"
        self.cleanup_failed = True
        report.update(complete=False, blur_may_remain=self._pending)
        return report

    def apply(self, hwnd, policy, *, surface_id, valid):
        report = self._report(hwnd, policy)
        if self.closed:
            return dict(report, fallback_reason="settings-backend-closed")
        if self._busy:
            return dict(report, rejected=True,
                        fallback_reason="settings-native-operation-in-progress")
        identity = (surface_id, hwnd)
        mutations_before = self._mutations
        self._busy = True
        try:
            self._input(hwnd, surface_id, valid)
            if self.identity is not None and self.identity != identity:
                raise _Rejected("settings-surface-not-released")
            allowed = report["policy"]["state"] == "allowed"
            if self.cleanup_failed and allowed:
                raise _Rejected("settings-previous-surface-cleanup-failed")
            self._guard(identity, valid, unclaimed=True)
            self.identity, self._alive = identity, valid
            if not allowed:
                cleanup = self._clear_current(identity, valid)
                return dict(report, cleanup=cleanup, ok=cleanup["ok"],
                            cleanup_complete=cleanup["cleanup_complete"],
                            blur_may_remain=cleanup["blur_may_remain"],
                            fallback_reason=(report["policy"]["reason"]
                                if cleanup["cleanup_complete"] else cleanup["fallback_reason"]))
            report["backdrop_result"] = self._hr(self._call(identity, valid, "set_backdrop", 1))
            if report["backdrop_result"] != 0:
                raise RuntimeError("DWM backdrop removal failed")
            report["frame_result"] = self._hr(
                self._call(identity, valid, "extend_frame", (-1, -1, -1, -1)))
            if report["frame_result"] != 0:
                raise RuntimeError("Raster frame request failed")
            read_hr, actual = self._call(identity, valid, "get_backdrop")
            report.update(readback_result=self._hr(read_hr), backdrop_type=actual)
            if read_hr != 0 or type(actual) is not int or actual != 1:
                raise RuntimeError("DWM backdrop readback mismatch")
            value, last_error = self._accent_call(identity, valid, True)
            report.update(bool_result=value, last_error=last_error, accent_state=3)
            if value == 0:
                raise RuntimeError("Raster blur request failed")
            if self._paint_background is not None:
                self._guard(identity, valid)
                if self._paint_background() is not True:
                    raise RuntimeError("Raster background paint failed")
                self._guard(identity, valid)
                report["background_paint_completed"] = True
            else:
                report["background_paint_external"] = True
            self.prepared = True
            report.update(ok=True, material="system-blur", status="configured-unverified",
                          coating_allowed=True, coating_translucent=True,
                          blur_configured=True, blur_may_remain=False, fallback_reason="")
        except Exception as error:
            self._error(report, error)
            if self.identity == identity and self._mutations > mutations_before:
                report["cleanup"] = self._clear_current(identity, valid)
                report["blur_may_remain"] = self._pending
        finally:
            self._busy = False
        return report
