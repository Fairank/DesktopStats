"""Qt-facing history, scene and diagnostic actions, isolated from native windows."""
import copy
import hashlib
import json
import logging
import tempfile
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from diagnostic_actions import cards, safe_report
from history_store import DEFAULT_METRICS, HistoryStore
from metrics import METRICS, SCOPE_FIELDS, metric_value, numeric
from native_layout import windows
from product_version import VERSION
from stats_config import BASE, DEFAULT, save, validate
from top_bar_layout import metric_icon
from workspace_scenarios import BUILTINS, SceneStore, builtin, preview, project, workspace

_HISTORY_DETAILS = {
    "History has not been written yet": "等待第一批历史记录。",
    "Local history storage is unavailable": "本地历史存储不可用，请检查文件访问和磁盘空间。",
    "Local history is up to date": "最近的历史记录已保存到本机。",
    "Local history has been cleared": "本机历史记录已清空。",
}


def _history_choice_id(metric, scope, identifier):
    payload = json.dumps([metric, scope, identifier], ensure_ascii=False)
    return "h_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


class WorkspaceTools(QObject):
    historyChanged = Signal()
    historyOptionsChanged = Signal()
    historyRecordingChanged = Signal()
    scenesChanged = Signal()
    diagnosticCheckChanged = Signal()

    def __init__(self):
        super().__init__()
        self._history_backend = None
        self._history_backend_lock = threading.RLock()
        self._history_announced = float("-inf")
        self._history_choices = {}
        self._history_log_at = float("-inf")
        self._scene_store = SceneStore(BASE / "scenes.json")
        self._scene_rows = [dict(row, preview=preview(workspace(builtin(row["id"], DEFAULT))))
                            for row in BUILTINS]
        self._scene_error = ""
        self._scene_applied = ""
        self._diagnostic_check = dict(state="idle", detail="")
        self._diagnostic_started = 0.0
        self._diagnostic_timer = QTimer(self)
        self._diagnostic_timer.setSingleShot(True)
        self._diagnostic_timer.setInterval(12000)
        self._diagnostic_timer.timeout.connect(self._diagnostic_timeout)

    def _store(self):
        with self._history_backend_lock:
            if self._history_backend is None:
                self._history_backend = HistoryStore(BASE / "sensor-history.sqlite3")
            return self._history_backend

    historyRecording = Property(bool, lambda self: self._saved.get("history_enabled", True),
                                notify=historyRecordingChanged)
    @Property("QVariantMap", notify=historyChanged)
    def historyStatus(self):
        status = dict(self._store().status, recording=self.historyRecording)
        status["detail"] = self.tr(_HISTORY_DETAILS.get(status.get("detail"), status.get("detail", "")))
        return status

    scenes = Property("QVariantList", lambda self: self._scene_rows, notify=scenesChanged)
    sceneError = Property(str, lambda self: self._scene_error, notify=scenesChanged)
    appliedSceneId = Property(str, lambda self: self._scene_applied, notify=scenesChanged)
    diagnosticCards = Property("QVariantList", lambda self: [
        dict(row, badge=self.tr(row["badge"]), hint=self.tr(row["hint"]), detail=self.tr(row["detail"]))
        for row in cards(self._data)], notify=diagnosticCheckChanged)
    diagnosticCheck = Property("QVariantMap", lambda self: self._diagnostic_check,
                               notify=diagnosticCheckChanged)

    def _record_history(self, sample):
        if not self._saved.get("history_enabled", True):
            return
        try:
            self._store().record(sample)
        except Exception:
            # Optional history can never discard a healthy live sample.
            now = time.monotonic()
            if now - self._history_log_at >= 5:
                logging.exception("Optional sensor history failed")
                self._history_log_at = now

    def _workspace_sample_received(self, sample):
        now = time.monotonic()
        if now - self._history_announced >= 2:
            self._history_announced = now
            self.historyChanged.emit()
            self.historyOptionsChanged.emit()
            self.diagnosticCheckChanged.emit()
        if (self._diagnostic_check["state"] == "checking"
                and numeric(sample.get("time")) and sample["time"] >= self._diagnostic_started):
            self._diagnostic_timer.stop()
            self._diagnostic_check = dict(state="updated", detail=self.tr("读数已刷新；未完成来源仍保留具体原因。"))
            self.diagnosticCheckChanged.emit()

    @Property("QVariantList", notify=historyOptionsChanged)
    def historyMetricChoices(self):
        rows = []
        choices = {}

        def append(metric, scope="", identifier="", label=""):
            key = _history_choice_id(metric, scope, identifier)
            prefs = {SCOPE_FIELDS[scope]: identifier} if scope else {}
            meta = METRICS[metric]
            rows.append(dict(id=key, label=self.tr(meta["label"]), unit=meta["unit"], scope=scope,
                             device_id=identifier, device_label=label, icon=metric_icon(metric),
                             available=numeric(metric_value(self._data, metric, prefs))))
            choices[key] = (metric, scope, identifier)

        for metric in DEFAULT_METRICS:
            append(metric)
        for scope in ("gpus", "networks"):
            devices = dict(self._devices.get(scope, {}))
            if scope == "gpus" and not devices:
                devices = {"0": dict(label="GPU 0")}
            for identifier, device in list(devices.items())[:32]:
                for metric, meta in METRICS.items():
                    if meta.get("scope") == scope:
                        append(metric, scope, identifier, device.get("label", identifier))
        # Retain selected IDs across a disconnect so a chart never silently
        # switches devices. Old choices are bounded and contain no sample data.
        for key, entry in self._history_choices.items():
            if key not in choices and len(choices) < 1024:
                metric, scope, identifier = entry
                append(metric, scope, identifier, identifier)
        self._history_choices = choices
        return rows

    @Slot(str, str, result="QVariantMap")
    def historyQuery(self, identifier, period):
        if identifier not in self._history_choices:
            self.historyMetricChoices
        choice = self._history_choices.get(identifier)
        if choice is None or period not in ("10m", "1h", "24h"):
            return dict(state="error", detail=self.tr("请选择有效的指标与时间范围。"), points=[])
        metric, scope, device = choice
        try:
            response = self._store().query(metric, period, scope=scope, device_id=device)
        except (OSError, ValueError, RuntimeError) as error:
            logging.warning("History query unavailable: %s", type(error).__name__)
            return dict(state="error", detail=self.tr("无法读取历史记录"), points=[])
        summary = response["summary"]
        status = response["status"]
        bins = response["points"]
        # A failed clear or write remains visible in historyStatus, but must not
        # hide data from a complete successful read of the original database.
        readable = response.get("read_ok", status["state"] != "unavailable")
        return dict(state="error" if not readable else "ready" if summary["count"] else "empty",
                    detail=self.tr(_HISTORY_DETAILS.get(status["detail"], status["detail"])),
                    metric=metric, label=self.tr(METRICS[metric]["label"]),
                    unit=response["unit"], start=response["start"], end=response["end"],
                    points=[None if row["gap"] else dict(timestamp=row["time"], value=row["mean"],
                                minimum=row["minimum"], peak=row["peak"]) for row in bins],
                    latest=summary["latest"], latest_time=summary.get("latest_time"),
                    mean=summary["mean"], peak=summary["peak"],
                    minimum=summary["minimum"], count=summary["count"], missing_count=summary["missing_count"],
                    coverage=sum(not row["gap"] for row in bins) / max(1, len(bins)),
                    step_seconds=response["resolution"])

    @Slot(str, result=str)
    @Slot(str, "QVariantMap", result=str)
    def openHistoryMetric(self, metric, prefs=None):
        """Open one recorded series without ever changing an explicit device."""
        prefs = prefs if isinstance(prefs, dict) else {}
        scope = METRICS.get(metric, {}).get("scope") or ""
        target = ""
        eligible = metric in DEFAULT_METRICS
        if scope in ("gpus", "networks"):
            target = prefs.get(SCOPE_FIELDS[scope]) or ("0" if scope == "gpus" else "auto")
            if scope == "networks" and target == "auto":
                target = self._data.get("network_active")
            eligible = type(target) in (str, int) and bool(str(target))
            target = str(target) if eligible else ""
        route = "__history__"
        if eligible:
            self.historyMetricChoices
            key = _history_choice_id(metric, scope, target)
            if key in self._history_choices or len(self._history_choices) < 1024:
                self._history_choices[key] = (metric, scope, target)
                route += ":" + key
                self.historyOptionsChanged.emit()
        self.settingsRequested.emit(route)
        return route

    @Slot(bool, result=bool)
    def setHistoryRecording(self, enabled):
        if type(enabled) is not bool:
            return False
        value = copy.deepcopy(self._saved)
        value["history_enabled"] = enabled
        try:
            value = validate(value)
            save(value)
        except (OSError, ValueError):
            self.set_status("未能保存，请重试", error=True)
            return False
        self._saved = value
        self._draft["history_enabled"] = enabled
        for stack in (self._undo_drafts, self._redo_drafts):
            for snapshot in stack:
                snapshot["history_enabled"] = enabled
        self._last_edit_key = None
        self._last_edit_time = 0
        self.savedChanged.emit()
        self.draftChanged.emit()
        self.historyRecordingChanged.emit()
        self.historyChanged.emit()
        return True

    @Slot(result=bool)
    def clearHistory(self):
        success = self._store().clear()
        self.historyChanged.emit()
        if not success:
            self.set_status("未能清空历史记录，请重试", error=True)
        return success

    @Slot()
    def refreshScenes(self):
        try:
            self._scene_rows = self._scene_store.rows(self._saved)
            self._scene_error = ""
            saved = workspace(self._saved)
            self._scene_applied = next((row["id"] for row in self._scene_rows
                if workspace(self._scene_store.prepare(row["id"], self._saved)) == saved), "")
        except (OSError, ValueError):
            self._scene_error = self.tr("无法读取本地场景，原文件已保留。")
        self.scenesChanged.emit()

    @Slot(str, result="QVariantMap")
    def scenePreview(self, identifier):
        """Prepare real card geometry, without committing drafts or hardware IO."""
        try:
            candidate = self._scene_store.prepare(identifier, self._draft)
            result = dict(config=candidate, windows=windows(candidate))
        except (OSError, ValueError):
            self._scene_error = self.tr("无法预览此场景，当前设置未改动。")
            self.scenesChanged.emit()
            return {}
        if self._scene_error:
            self._scene_error = ""
            self.scenesChanged.emit()
        return result

    @Slot(str, result=bool)
    def saveScene(self, name):
        try:
            self._scene_store.save(name, self._draft)
        except (OSError, ValueError) as error:
            self._scene_error = self.tr(str(error)) if isinstance(error, ValueError) else self.tr("未能保存场景，请重试。")
            self.scenesChanged.emit()
            return False
        self.refreshScenes()
        return True

    @Slot(str, result=bool)
    def applyScene(self, identifier):
        if self._replacement_backup is not None:
            self._scene_error = self.tr("请先应用或取消全部设置预览。")
            self.scenesChanged.emit()
            return False
        try:
            candidate = self._scene_store.prepare(identifier, self._draft)
            value = project(self._saved, workspace(candidate))
            changed = value != self._saved
            if changed:
                capacity = self.layout_error(value, True)
                if capacity:
                    raise ValueError(capacity)
                # An already applied scene must not overwrite the useful prior
                # workspace or rearrange windows just to discard editor drafts.
                with self._scene_store.previous_transaction(self._saved):
                    save(value)
        except (OSError, ValueError) as error:
            self._scene_error = self.tr(str(error)) if isinstance(error, ValueError) else self.tr("未能应用场景，请重试。")
            self.scenesChanged.emit()
            return False
        self._saved = value
        self._draft = project(self._draft, workspace(value))
        self._rebase_scope_history("desktop")
        self._rebase_scope_history("topbar")
        if changed:
            self.savedChanged.emit()
        self.draftChanged.emit()
        if changed:
            self.applyRequested.emit(True)
        self.refreshScenes()
        # The recovery entry was replaced with the workspace we just left.
        # refreshScenes() has already found the restored workspace's real ID.
        if identifier != "previous":
            self._scene_applied = identifier
        self.scenesChanged.emit()
        self._applied_status("场景已应用")
        return True

    @Slot(str, result=bool)
    def removeScene(self, identifier):
        try:
            self._scene_store.remove(identifier, self._saved)
        except (OSError, ValueError):
            self._scene_error = self.tr("未能移除场景，请重试。")
            self.scenesChanged.emit()
            return False
        self.refreshScenes()
        return True

    @Slot()
    def checkSources(self):
        if self._diagnostic_check["state"] == "checking":
            return
        self._diagnostic_started = time.time()
        self._diagnostic_check = dict(state="checking", detail=self.tr("正在等待新的读数，来源保留原有重试间隔。"))
        self.rescanExternal()
        self._diagnostic_timer.start()
        self.diagnosticCheckChanged.emit()

    def _diagnostic_timeout(self):
        if self._diagnostic_check["state"] != "checking":
            return
        self._diagnostic_check = dict(state="waiting", detail=self.tr("暂未收到新的采样；原有状态与错误信息已保留。"))
        self.diagnosticCheckChanged.emit()

    @Slot()
    def exportDiagnostics(self):
        path, _ = QFileDialog.getSaveFileName(None, self.tr("导出诊断"), "DesktopStats-diagnostics.json", "JSON (*.json)")
        if path:
            self.exportDiagnosticsPath(path)

    def exportDiagnosticsPath(self, path):
        temporary = None
        try:
            destination = Path(path)
            raw = json.dumps(safe_report(self._data, VERSION), ensure_ascii=False, indent=2)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                             prefix=".diagnostics-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
            temporary.replace(destination)
        except OSError:
            self.set_status("未能导出诊断，请重试", error=True)
            return False
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
        self.set_status("诊断已导出，不含原始读数、设备标识或本地路径。")
        return True

    def close_history_backend(self):
        """Worker-safe backend closure; never call Qt timers from a worker."""
        with self._history_backend_lock:
            if self._history_backend is not None:
                self._history_backend.close()

    def close_workspace_tools(self):
        self._diagnostic_timer.stop()
        self.close_history_backend()
