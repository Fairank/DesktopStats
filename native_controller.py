"""Native Qt state, validated edits and sensor delivery. No browser or HTTP server."""

import copy
import hashlib
import json
import logging
import math
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QTimer, Signal, Slot
from PySide6.QtQml import QJSValue
from PySide6.QtWidgets import QFileDialog

import sensors
from compact_labels import label_options
from configuration_scopes import SCOPE_FIELDS as CONFIGURATION_SCOPES
from configuration_scopes import merge_scope, rebase_saved_changes, scope_dirty
from desktop_placement import desktop_plan
from external_sensor import EXTERNAL_SLOTS, PROVIDER, inventory_display, sensor_binding
from history_store import DEFAULT_METRICS
from installer import set_autostart
from layout_assist import (
    align_layout,
    append_layout,
    assist_rect,
    distribute_layout,
    swap_layout,
)
from localization import LANGUAGES, MESSAGES, translate
from material_policy import render_policy
from metrics import METRICS, SCOPE_FIELDS, display_value, metric_info, numeric
from native_card import formatted
from native_layout import LayoutCapacityError, effective_size, grid_plan, minimum_size, windows
from presets import CATALOG_INFO, catalogue
from product_version import VERSION
from responsive_layout import (
    ResponsiveLayoutError,
    dimensions,
    is_responsive,
    metric_rects,
    minimum_dimensions,
    responsive_plan,
)
from sensor_diagnostics import reading_source, source_rows, unavailable_reason
from skin_styles import GLASS_SKINS, effective_skin
from stats_config import DEFAULT, MAX_WIDGETS, MODULES, SKINS, load, save, validate
from top_bar_layout import present_metric
from top_bar_profiles import (
    align_pair_trends,
    can_gauge,
    detail_profile,
    effect_strength,
    group_channels,
    paired_channels,
    validate_group_metrics,
)
from widget_catalog import CATEGORIES, TEMPLATES, from_template
from workspace_tools import WorkspaceTools


def choices(value):
    return [dict(id=key, label=label) for key, label in value.items()]


class Controller(WorkspaceTools):
    draftChanged = Signal()
    savedChanged = Signal()
    dataChanged = Signal()
    sensorsChanged = Signal()
    devicesChanged = Signal()
    statusChanged = Signal()
    materialChanged = Signal()
    motionChanged = Signal()
    topBarStatusChanged = Signal()
    previewChanged = Signal()
    catalogChanged = Signal()
    languageChanged = Signal()
    themeChanged = Signal()
    draftHistoryChanged = Signal()
    sampleReady = Signal(dict)
    applyRequested = Signal(bool)
    topBarApplyRequested = Signal()
    settingsRequested = Signal(str)
    positionChanged = Signal(str, int, int)
    moveStarted = Signal(str)
    moveFinished = Signal(str)
    menuRequested = Signal(str)
    windowCloseRequested = Signal(str)
    detailsRequested = Signal(str, int, float, float)
    quitRequested = Signal()

    def __init__(self):
        super().__init__()
        self._saved = load()
        self._draft = copy.deepcopy(self._saved)
        self._data = {}
        self._devices = {}
        self._history = deque(maxlen=40)
        self._external_rows = {}
        self._discovered_ids = {}
        self._sensor_revision = 0
        self._sensor_notify_at = 0.0
        self._reading_notify_at = float("-inf")
        self._reading_notify_timer = QTimer(self)
        self._reading_notify_timer.setSingleShot(True)
        self._reading_notify_timer.timeout.connect(self._emit_reading)
        self._external_revision = None
        self._status = ""
        self._commit_error = ""
        self._material = {"material": "solid"}
        self._motion_enabled = True
        self._top_bar_status = {"state": "disabled", "detail": "顶部栏未启用"}
        self._window_materials = {}
        self._preview_area = None
        self._preview_screens = []
        self._preview_positions = {}
        self._undo_drafts = []
        self._redo_drafts = []
        self._replacement_backup = None
        self._last_edit_key = None
        self._last_edit_time = 0
        self._catalog_value = None
        self._catalog_state = self._catalog_fingerprint()
        self._notified_language = self._draft["language"]
        self._notified_theme = self._draft["theme"]
        self.stop = threading.Event()
        self.thread = None
        self.sampleReady.connect(self.receive)
        self.draftChanged.connect(self._update_catalog)
        self.draftChanged.connect(self.previewChanged.emit)
        self.draftChanged.connect(self._update_language)
        self.draftChanged.connect(self._update_theme)
        self.savedChanged.connect(self.historyRecordingChanged.emit)
        self.devicesChanged.connect(self.historyOptionsChanged.emit)

    draft = Property("QVariantMap", lambda self: self._draft, notify=draftChanged)
    saved = Property("QVariantMap", lambda self: self._saved, notify=savedChanged)
    scopeDirty = Property(
        "QVariantMap",
        lambda self: {scope: scope_dirty(self._saved, self._draft, scope) for scope in CONFIGURATION_SCOPES},
        notify=draftChanged,
    )
    replacementPending = Property(bool, lambda self: self._replacement_backup is not None, notify=draftChanged)
    readings = Property("QVariantMap", lambda self: self._data, notify=dataChanged)
    history = Property("QVariantList", lambda self: list(self._history), notify=dataChanged)
    sensorRevision = Property(int, lambda self: self._sensor_revision, notify=sensorsChanged)
    externalStatus = Property(
        "QVariantMap",
        lambda self: self._data.get(
            "external_status",
            {
                "state": "idle",
                "detail": "扩展采集器按需运行",
                "sensor_count": 0,
                "available_count": 0,
                "hardware_count": 0,
                "version": "0.9.6",
                "updated_at": None,
            },
        ),
        notify=sensorsChanged,
    )
    devices = Property("QVariantMap", lambda self: self._devices, notify=devicesChanged)
    language = Property(str, lambda self: self._draft["language"], notify=languageChanged)
    theme = Property(str, lambda self: self._draft["theme"], notify=themeChanged)
    texts = Property(
        "QVariantMap", lambda self: MESSAGES[self._draft["language"]], notify=languageChanged
    )
    dirty = Property(bool, lambda self: self._draft != self._saved, notify=draftChanged)
    canUndoDraft = Property(bool, lambda self: bool(self._undo_drafts), notify=draftHistoryChanged)
    canRedoDraft = Property(bool, lambda self: bool(self._redo_drafts), notify=draftHistoryChanged)
    status = Property(
        str, lambda self: translate(self._status, self._draft["language"]), notify=statusChanged
    )
    version = Property(str, lambda self: VERSION, constant=True)
    material = Property("QVariantMap", lambda self: self._material, notify=materialChanged)
    motionEnabled = Property(bool, lambda self: self._motion_enabled, notify=motionChanged)

    def set_motion_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled != self._motion_enabled:
            self._motion_enabled = enabled
            self.motionChanged.emit()

    topBarStatus = Property(
        "QVariantMap", lambda self: self._top_bar_status, notify=topBarStatusChanged
    )

    def set_top_bar_status(self, value):
        if self._top_bar_status != value:
            self._top_bar_status = copy.deepcopy(value)
            self.topBarStatusChanged.emit()

    @Slot(str, "QVariant")
    def changeTopBar(self, field, selected):
        if field not in ("enabled", "monitor_mode", "height", "screens", "spacing"):
            return
        # QVariant parameters retain a JavaScript array as QJSValue. Convert
        # this explicit list boundary before validation/deepcopy, not into the
        # persistent draft or an undo snapshot.
        if field == "screens" and isinstance(selected, QJSValue):
            selected = selected.toVariant()
        value = copy.deepcopy(self._draft)
        if field == "height" and isinstance(selected, float) and selected.is_integer():
            selected = int(selected)
        value["top_bar"][field] = selected
        self.edit(value, merge_key=("top_bar", field))

    @Slot(str, bool, result=bool)
    def setTopBarScreenSelected(self, identifier, selected):
        """One checkbox edit; only native inventory IDs or stored offline IDs."""
        if identifier not in {row["id"] for row in self._top_bar_screens()}:
            return False
        current = self._draft["top_bar"]["screens"]
        identifiers = [screen for screen in current if screen != identifier]
        if selected:
            identifiers = list(current) if identifier in current else [*current, identifier]
        if identifiers == current:
            return True
        value = copy.deepcopy(self._draft)
        value["top_bar"]["screens"] = identifiers
        return self.edit(value)

    @Slot(str, "QVariant")
    def changeTopBarAppearance(self, field, selected):
        if field not in ("follow_global", "skin", "glass_transparency", "design"):
            return
        value = copy.deepcopy(self._draft)
        appearance = value["top_bar"]["appearance"]
        if field != "design" and (field != "follow_global" or selected is False):
            if appearance["follow_global"]:
                # The first local edit starts from what the user currently sees.
                appearance.update(
                    skin=value["skin"] if value["skin"] != "minimal" else "glass",
                    glass_transparency=value["glass_transparency"],
                )
            if field != "follow_global":
                appearance["follow_global"] = False
        appearance[field] = selected
        self.edit(value, merge_key=("top_bar_appearance", field))

    @Slot(str, str, float)
    def changeTopBarEffect(self, identifier, field, selected):
        if field not in ("effect_intensity", "effect_speed"):
            return
        value = copy.deepcopy(self._draft)
        item = next((row for row in value["top_bar"]["items"]
                     if row["id"] == identifier), None)
        if item is None:
            return
        item["prefs"][field] = selected
        self.edit(value, merge_key=("top_bar_effect", identifier, field))

    @Slot(str, result=bool)
    def applyTopBarPreset(self, name):
        if name not in ("compact", "balanced", "graphs"):
            return False
        value = copy.deepcopy(self._draft)
        for item in value["top_bar"]["items"]:
            metric = item["metric"]
            style = (
                "icon_value" if name == "compact" else
                "graph" if name == "graphs" else
                "duplex" if paired_channels(metric) else
                "ring_value" if metric == "battery_percent" else "stacked"
            )
            item["prefs"]["style"] = style
        value["top_bar"]["spacing"] = 4 if name == "compact" else 8
        return self.edit(value)

    def _commit_top_bar(self, enabled=None):
        """Save just the bar; never submit another editor's pending work."""
        if enabled is None and self._replacement_backup is not None:
            self.set_status("请应用或取消全部设置预览")
            return False
        try:
            value = copy.deepcopy(self._saved)
            if enabled is not None:
                value["top_bar"]["enabled"] = bool(enabled)
            else:
                value["top_bar"] = copy.deepcopy(self._draft["top_bar"])
            value = validate(value)
            save(value)
        except Exception:
            logging.exception("Top bar settings commit failed")
            self.set_status("未能保存，请重试", error=True)
            self.savedChanged.emit()  # Reset a clicked switch to the saved state.
            return False
        self._saved = value
        if enabled is not None:
            self._draft["top_bar"]["enabled"] = bool(enabled)
        else:
            self._draft["top_bar"] = copy.deepcopy(value["top_bar"])
        self._rebase_bar_history(enabled_only=enabled is not None)
        self.savedChanged.emit()
        self.draftChanged.emit()
        self.topBarApplyRequested.emit()
        self._applied_status("顶部栏设置已应用")
        return True

    @Slot(bool, result=bool)
    def setTopBarEnabled(self, enabled):
        return self._commit_top_bar(bool(enabled))

    @Slot(result=bool)
    def applyTopBar(self):
        return self._commit_top_bar()

    @Slot(result=bool)
    def revertTopBarDraft(self):
        """Discard the bar branch only, keeping other editors and their history."""
        if self._replacement_backup is not None:
            self.set_status("请应用或取消全部设置预览")
            return False
        if self._draft["top_bar"] == self._saved["top_bar"]:
            return False
        self._draft["top_bar"] = copy.deepcopy(self._saved["top_bar"])
        self._rebase_bar_history()
        self.draftChanged.emit()
        self.set_status("顶部栏修改已撤销")
        return True

    def _applied_status(self, message):
        status = self._top_bar_status
        if self._saved["top_bar"]["enabled"] and status.get("state") in (
            "error", "failed", "unavailable", "partial", "missing_screen", "unsupported"
        ):
            self.set_status(status.get("reason") or status.get("detail") or "顶部栏暂时无法显示")
        else:
            self.set_status(message)

    @Slot(str, result=bool)
    def addTopBarMetric(self, metric):
        value = copy.deepcopy(self._draft)
        if len(value["top_bar"]["items"]) >= 64:
            self.set_status("顶部栏最多添加 64 项指标")
            return False
        prefs = {"sensor_bindings": {}}
        if metric in self._discovered_ids:
            row = self._external_rows.get(self._discovered_ids[metric])
            if row is None:
                return False
            metric = EXTERNAL_SLOTS[0]
            prefs["sensor_bindings"][metric] = self._binding_for(row)
        elif metric not in METRICS or metric in EXTERNAL_SLOTS:
            return False
        value["top_bar"]["items"].append(
            dict(id="b_" + uuid.uuid4().hex, metric=metric, prefs=prefs)
        )
        return self.edit(value)

    @Slot(str)
    def removeTopBarMetric(self, identifier):
        value = copy.deepcopy(self._draft)
        value["top_bar"]["items"] = [
            item for item in value["top_bar"]["items"] if item["id"] != identifier
        ]
        self.edit(value)

    @Slot(str, int)
    def moveTopBarMetric(self, identifier, delta):
        value = copy.deepcopy(self._draft)
        items = value["top_bar"]["items"]
        index = next((i for i, item in enumerate(items) if item["id"] == identifier), -1)
        if index < 0 or delta not in (-1, 1) or not 0 <= index + delta < len(items):
            return
        items[index], items[index + delta] = items[index + delta], items[index]
        self.edit(value)

    @Slot(str, str, str, result=bool)
    def placeTopBarMetric(self, identifier, before_identifier, placement):
        """One constrained drop transaction; row IDs remain stable."""
        if placement not in ("left", "right") or identifier == before_identifier:
            return False
        value = copy.deepcopy(self._draft)
        items = value["top_bar"]["items"]
        item = next((row for row in items if row["id"] == identifier), None)
        before = next((row for row in items if row["id"] == before_identifier), None)
        if item is None or (before_identifier and (before is None or before["prefs"].get("placement", "right") != placement)):
            return False
        items.remove(item)
        item["prefs"]["placement"] = placement
        if before is not None:
            items.insert(items.index(before), item)
        else:
            index = max((i for i, row in enumerate(items) if row["prefs"].get("placement", "right") == placement), default=len(items)-1)
            items.insert(index+1, item)
        return self.edit(value)

    @Slot(str, str, str, result=bool)
    def placeLiveTopBarMetric(self, identifier, before_identifier, placement):
        """Direct bar dragging commits only its order, preserving other editors."""
        if self._draft["top_bar"] != self._saved["top_bar"]:
            self.set_status("请先应用顶部栏的修改，再拖动实时顶部栏。")
            return False
        if placement not in ("left", "right") or identifier == before_identifier:
            return False
        value = copy.deepcopy(self._saved)
        items = value["top_bar"]["items"]
        item = next((row for row in items if row["id"] == identifier), None)
        before = next((row for row in items if row["id"] == before_identifier), None)
        if item is None or (before_identifier and (before is None or before["prefs"]["placement"] != placement)):
            return False
        items.remove(item)
        item["prefs"]["placement"] = placement
        if before is not None:
            items.insert(items.index(before), item)
        else:
            index = max((i for i, row in enumerate(items) if row["prefs"]["placement"] == placement), default=len(items)-1)
            items.insert(index+1, item)
        try:
            value = validate(value)
            save(value)
        except Exception:
            logging.exception("Live top bar ordering commit failed")
            self.set_status("未能保存，请重试", error=True)
            return False
        self._saved = value
        self._draft["top_bar"] = copy.deepcopy(value["top_bar"])
        self._rebase_bar_history()
        self.savedChanged.emit()
        self.draftChanged.emit()
        self.topBarApplyRequested.emit()
        return True

    @Slot(str, str, str)
    def changeTopBarItem(self, identifier, field, selected):
        if field not in (
            "precision",
            "temperature_unit",
            "network_unit",
            "gpu_target",
            "network_target",
            "disk_target",
            "volume_target",
            "storage_target",
            "placement",
            "style",
            "icon_effect",
        ):
            return
        value = copy.deepcopy(self._draft)
        item = next((item for item in value["top_bar"]["items"] if item["id"] == identifier), None)
        if item is not None:
            item["prefs"][field] = selected
            self.edit(value)

    @Slot(str, 'QVariantList', result=bool)
    def setTopBarGroupMetrics(self, identifier, metrics):
        value = copy.deepcopy(self._draft)
        item = next((row for row in value['top_bar']['items'] if row['id'] == identifier), None)
        if item is None:
            return False
        try:
            selected = validate_group_metrics(item['metric'], metrics)
        except ValueError as error:
            self.set_status(str(error))
            return False
        prefs = item['prefs']
        if len(selected) == 1:
            prefs.pop('metrics', None)
        else:
            prefs['metrics'] = selected
            if (prefs.get('style') in ('duplex', 'duplex_inline')
                    or prefs.get('style') in ('bar_value', 'ring_value') and any(
                        not can_gauge(METRICS[metric]) for metric in selected)):
                prefs['style'] = 'icon_value'
        if value == self._draft:
            return True
        return self.edit(value)

    def _cpu_detail_context(self, data, prefs, language, stale):
        """Current logical CPU readings, never inferred physical-core telemetry."""
        source, api = "Windows / psutil", sensors.CPU_LOGICAL_API
        status = data.get("cpu_per_core_status", {})
        status = status if isinstance(status, dict) else {}
        timestamp = data.get("cpu_per_core_timestamp", data.get("time"))
        frame_stale = stale
        stale = stale or not numeric(timestamp) or not 0 <= time.time() - timestamp < 35
        values = sensors.logical_processor_values(data.get("cpu_per_core"))
        observed = len(values)
        raw_state = status.get("state", "available" if values else "invalid_data")
        reasons = {
            "query_failed": "逻辑处理器查询失败，将自动重试。",
            "warming_up": "逻辑处理器采样正在建立基线。",
            "not_requested": "当前未请求处理器采样。",
            "invalid_data": "Windows 未返回逻辑处理器使用率。",
        }
        reason = translate("读数已过期", language) if stale and values else translate(
            reasons.get(raw_state, "Windows 未返回逻辑处理器使用率。") if not values else "", language)
        errors = status.get("error", {})
        errors = errors if isinstance(errors, dict) else {}
        if raw_state == "query_failed":
            reason += " API " + api
            for field, label in (("winerror", "Win32"), ("errno", "errno")):
                if type(errors.get(field)) is int:
                    reason += " · " + label + " " + str(errors[field])
        readable = not stale and raw_state not in reasons
        rows = []
        precision = prefs.get("precision", "auto")
        digits = int(precision) if precision in ("0", "1", "2") else 1
        for index, sample in enumerate(values[:1024]):
            value = sample if readable else None
            row_reason = reason or (translate("本次逻辑处理器读数无效。", language) if value is None else "")
            text = f"{value:.{digits}f}" if value is not None else "—"
            if precision == "auto" and value is not None:
                text = text.rstrip("0").rstrip(".") if "." in text else text
            rows.append(dict(index=index, label="CPU " + str(index), available=value is not None,
                             numeric_value=value, fraction=value / 100 if value is not None else None,
                             value=text + " %" if value is not None else "—", reason=row_reason,
                             source=source, timestamp=timestamp if numeric(timestamp) else None))
        available_count = sum(value is not None for value in values) if readable else 0
        if readable and values:
            state = "available" if available_count == observed else "partial" if available_count else "unavailable"
            if available_count != observed:
                reason = translate("部分逻辑处理器本次没有有效读数。", language)
        else:
            state = "stale" if stale and values else raw_state if raw_state in ("warming_up", "not_requested") else "unavailable"

        def count(value):
            return value if type(value) is int and 0 < value <= sensors.MAX_LOGICAL_PROCESSORS else None

        related = []
        for metric in ("cpu_frequency", "cpu_temp", "cpu_power", "cpu_fan_rpm"):
            value, unit = formatted({} if frame_stale else data, metric, prefs)
            related.append(dict(metric=metric, label=translate(METRICS[metric]["label"], language),
                                value=value + (" " + unit if value != "—" and unit else ""),
                                available=value != "—", source=reading_source(data, metric, prefs),
                                reason=translate("读数已过期", language) if frame_stale else translate(
                                    unavailable_reason(data, metric, prefs), language) if value == "—" else ""))
        return dict(hardware_name=str(data.get("cpu_name") or ""),
                    physical_cores=count(data.get("cpu_cores")),
                    logical_processors=observed or count(data.get("cpu_threads")),
                    source=source, api=api, state=state, reason=reason,
                    available=available_count > 0, available_count=available_count,
                    timestamp=timestamp if numeric(timestamp) else None,
                    logical_rows=rows, displayed_count=len(rows), truncated=observed > len(rows),
                    related_rows=related)

    def _top_bar_rows(self, config, *, detail_id=None, include_related=True,
                      include_groups=True, force_history=False):
        data = self._data
        stale = bool(data) and not 0 <= time.time() - data.get("time", 0) < 35
        result = []
        language = config["language"]
        samples = list(self._history)[-40:]
        sample_times = [sample.get('time') for sample in samples]

        def label_for(metric, prefs):
            label = metric_info(metric, prefs)["label"]
            return label if metric in EXTERNAL_SLOTS else translate(label, language)

        for item in config["top_bar"]["items"]:
            if detail_id is not None and item["id"] != detail_id:
                continue
            metric, prefs = item["metric"], item["prefs"]
            meta = metric_info(metric, prefs)
            value, unit = formatted({} if stale else data, metric, prefs)
            number, _display_unit, digits = display_value({} if stale else data, metric, prefs)
            binding = sensor_binding(metric, prefs)
            scope = meta.get("scope")
            target = prefs.get(
                SCOPE_FIELDS.get(scope),
                {
                    "gpus": "0",
                    "storages": "0",
                    "networks": data.get("network_active", ""),
                    "disks": "all",
                    "volumes": "system",
                }.get(scope),
            )
            if scope == "networks" and target == "auto":
                target = data.get("network_active", "auto")
            if scope == "volumes" and target == "system":
                target = data.get("volume_system", "system")
            device = data.get(scope, {}).get(target, {})
            hardware_name = (
                binding["hardware_name"]
                if binding
                else device.get("label", str(target or ""))
                if scope
                else ""
            )
            if not binding and meta['source'] == 'cpu' and data.get('cpu_name'):
                hardware_name = str(data['cpu_name'])
            if not binding and scope == 'gpus' and target in ('0', 0, None) and not device.get('label'):
                hardware_name = str(data.get('gpu_name') or hardware_name)
            if scope == "disks" and target == "all":
                hardware_name = translate("所有物理磁盘", language)
            source = reading_source(data, metric, prefs)
            reason = (
                translate("读数已过期", language)
                if stale
                else unavailable_reason(data, metric, prefs)
                if value == "—"
                else ""
            )
            related = []
            family, group_label, related_metrics = detail_profile(metric)
            for other in related_metrics if detail_id is not None and include_related else ():
                val, other_unit = formatted({} if stale else data, other, prefs)
                related.append(
                    dict(
                        metric=other,
                        label=label_for(other, prefs),
                        value=val + (" " + other_unit if val != "—" and other_unit else ""),
                        available=val != "—",
                        source=reading_source(data, other, prefs),
                        reason=translate("读数已过期", language)
                        if stale
                        else unavailable_reason(data, other, prefs)
                        if val == "—"
                        else "",
                    )
                )
            channels = paired_channels(metric)
            icon_effect = prefs.get('icon_effect', 'off')
            effect_intensity = prefs.get('effect_intensity', 0.5)
            effect_speed = prefs.get('effect_speed', 1.0)
            def effect_for(key):
                if icon_effect == 'off' or stale:
                    return None
                canonical = dict(prefs, temperature_unit='C', network_unit='MBps')
                activity, _, _ = display_value(data, key, canonical)
                return effect_strength(activity, metric_info(key, prefs).get('maximum'))
            paired = []
            for other, direction in channels:
                val, other_unit = formatted({} if stale else data, other, prefs)
                channel = dict(metric=other, direction=direction,
                    label=label_for(other, prefs), number_text=val,
                    unit_text=other_unit if val != '—' else '',
                    unit=other_unit,
                    value=val + (' ' + other_unit if val != '—' and other_unit else ''),
                    available=val != '—', numeric_value=display_value({} if stale else data, other, prefs)[0],
                    source=reading_source(data, other, prefs),
                    reason=translate('读数已过期', language) if stale else unavailable_reason(data, other, prefs) if val == '—' else '',
                    history=[display_value(sample, other, prefs)[0] for sample in samples]
                        if detail_id is not None and include_related else [],
                    history_times=sample_times if detail_id is not None and include_related else [])
                channel.update(icon_effect=icon_effect, effect_level=effect_for(other),
                               effect_intensity=effect_intensity, effect_speed=effect_speed)
                paired.append(present_metric(channel))
            paired = align_pair_trends(paired)
            capacity_summary = {}
            capacity_fields = {
                'memory': ('ram_used_gb', 'ram_total_gb'),
                'gpu': ('vram_gb', 'vram_total_gb'),
                'volume': ('disk_used_gb', 'disk_total_gb'),
            }.get(family)
            if capacity_fields and detail_id is not None and include_related:
                used_key, total_key = capacity_fields
                used, _, _ = display_value({} if stale else data, used_key, prefs)
                total, _, _ = display_value({} if stale else data, total_key, prefs)
                if numeric(used) and numeric(total) and 0 <= used <= total and total > 0:
                    used_text, used_unit = formatted(data, used_key, prefs)
                    total_text, total_unit = formatted(data, total_key, prefs)
                    capacity_summary = dict(label=label_for(used_key, prefs),
                        used_text=used_text+' '+used_unit, total_text=total_text+' '+total_unit,
                        fraction=used/total)
            include_history = force_history or detail_id is not None or prefs.get('style') in ('trend_value', 'graph')
            result.append(
                dict(
                    id=item["id"],
                    metric=metric,
                    label=label_for(metric, prefs),
                    bar_label=label_options(metric, label_for(metric, prefs), language)[-1],
                    value=value + (" " + unit if value != "—" and unit else ""),
                    number_text=value,
                    unit_text=unit if value != "—" else "",
                    number_reserve=("100" + ("." + "0" * digits if digits else "")
                                    if unit == "%" else "999.9"),
                    unit=unit,
                    available=value != "—",
                    numeric_value=number,
                    icon_effect=icon_effect,
                    effect_level=effect_for(metric),
                    effect_intensity=effect_intensity,
                    effect_speed=effect_speed,
                    source=source,
                    reason=reason,
                    hardware_name=hardware_name,
                    family=family,
                    group_label=translate(group_label, language),
                    gauge_supported=can_gauge(meta),
                    pair_supported=bool(channels),
                    history_recordable=metric in DEFAULT_METRICS or meta.get("scope") in ("gpus", "networks"),
                    paired_rows=paired,
                    history_samples=min(40, len(self._history)),
                    history_times=sample_times if include_history else [],
                    capacity_summary=capacity_summary,
                    related=related,
                    history=[
                        display_value(sample, metric, prefs)[0]
                        for sample in (samples if include_history else ())
                    ],
                )
            )
            if family == 'cpu' and detail_id is not None and include_related:
                result[-1]['cpu_context'] = self._cpu_detail_context(data, prefs, language, stale)
        preferences = {item["id"]: item["prefs"] for item in config["top_bar"]["items"]}
        rows = [present_metric(row, preferences[row['id']]) for row in result]
        if not include_groups:
            return rows
        group_options = {}
        for row in rows:
            prefs = preferences[row['id']]
            selected = prefs.get('metrics', [row['metric']])
            candidates = group_channels(row['metric'])
            if candidates not in group_options:
                group_options[candidates] = [dict(metric=metric, label=label_for(metric, prefs))
                                             for metric in candidates]
            row.update(
                grouped=len(selected) > 1,
                group_supported=bool(candidates),
                group_metrics=list(selected),
                group_options=group_options[candidates],
                group_rows=[],
            )
            if len(selected) > 1:
                child_prefs = {key: value for key, value in prefs.items() if key != 'metrics'}
                child_items = [dict(id=row['id'] + '_group_' + str(index), metric=metric,
                                    prefs=child_prefs)
                               for index, metric in enumerate(selected)]
                child_config = dict(config, top_bar=dict(config['top_bar'], items=child_items))
                children = self._top_bar_rows(
                    child_config, include_related=False, include_groups=False,
                    force_history=detail_id is not None,
                )
                row['group_rows'] = children
                row['group_value'] = ' · '.join(child['value'] for child in children)
                row['group_available'] = any(child['available'] for child in children)
        return rows

    @Slot(result="QVariantList")
    def topBarRows(self):
        return self._top_bar_rows(self._saved)

    @Slot(result="QVariantList")
    def topBarDraftRows(self):
        return self._top_bar_rows(self._draft)

    @Slot(str, result="QVariantMap")
    def topBarStylePreviewRow(self, identifier):
        """Only the selected draft item's real history, without related rows.

        Style candidates may show trends before the user chooses that style;
        the normal bar row list retains its cheap, on-demand history contract.
        """
        if type(identifier) is not str or not identifier:
            return {}
        rows = self._top_bar_rows(self._draft, detail_id=identifier, include_related=False)
        return rows[0] if rows else {}

    @Slot(str, result="QVariantMap")
    def topBarDetailRow(self, identifier):
        rows = self._top_bar_rows(self._saved, detail_id=identifier)
        return rows[0] if rows else {}

    @Slot()
    def _emit_reading(self):
        self._reading_notify_timer.stop()
        self._reading_notify_at = time.monotonic()
        self.dataChanged.emit()

    def _notify_reading(self):
        """Keep every sample/history entry; paint the latest at most ~30 Hz.

        Sampling at 10 ms is useful for recording, but rebuilding QVariant maps
        and QML bindings at 100 Hz competes with pointer/animation events.
        Ordinary slower sampling and the first/recovery sample remain immediate.
        """
        elapsed = time.monotonic() - self._reading_notify_at
        if elapsed < 0 or elapsed >= .033 or QCoreApplication.instance() is None:
            self._emit_reading()
        elif not self._reading_notify_timer.isActive():
            self._reading_notify_timer.start(max(1, math.ceil((.033 - elapsed) * 1000)))

    screenChoices = Property(
        "QVariantList",
        lambda self: (
            [dict(id="", label=self.tr("主显示器"))]
            + [dict(id=s["id"], label=s.get("label", s["id"])) for s in self._preview_screens]
        ),
        notify=previewChanged,
    )
    topBarScreenChoices = Property(
        "QVariantList", lambda self: self._top_bar_screens(), notify=previewChanged
    )

    def _top_bar_screens(self):
        rows = [
            dict(id=s["native_id"], label=s.get("label", s["native_id"]))
            for s in self._preview_screens
            if s.get("native_id")
        ]
        labels = [row["label"] for row in rows]
        for row in rows:
            if labels.count(row["label"]) > 1:
                row["label"] += " · " + row["id"]
        present = {row["id"] for row in rows}
        rows.extend(
            dict(id=identifier, label=identifier + " · " + self.tr("未连接"))
            for identifier in self._draft["top_bar"]["screens"]
            if identifier not in present
        )
        return rows

    def preview_windows(self):
        specs = windows(self._draft)
        if self._preview_screens:
            try:
                specs, _ = desktop_plan(self._draft, self._preview_screens, self._preview_positions)
            except (LayoutCapacityError, ResponsiveLayoutError):
                pass
        elif self._preview_area:
            try:
                specs, _ = grid_plan(
                    specs,
                    *self._preview_area,
                    self._draft["layout"],
                    gap=self._draft["magnet_gap"] if self._draft["magnet_enabled"] else 10,
                )
            except LayoutCapacityError:
                pass  # Keep a readable editable preview; applying is blocked below.
        return specs

    def layout_error(self, config, rearrange=False):
        if (not self._preview_area and not self._preview_screens) or not config["visible"]:
            return ""
        try:
            if self._preview_screens:
                desktop_plan(config, self._preview_screens, self._preview_positions, rearrange)
            else:
                grid_plan(
                    windows(config),
                    *self._preview_area,
                    config["layout"],
                    gap=config["magnet_gap"] if config["magnet_enabled"] else 10,
                )
        except (LayoutCapacityError, ResponsiveLayoutError):
            return "桌面空间不足，请减少显示的组件或调整布局。"
        return ""

    previewWindows = Property("QVariantList", preview_windows, notify=previewChanged)

    def set_preview_area(self, width, height):
        area = (width, height)
        if area != self._preview_area:
            self._preview_area = area
            self.previewChanged.emit()

    def set_screen_inventory(self, screens, positions=None):
        if screens != self._preview_screens or positions != self._preview_positions:
            self._preview_screens = copy.deepcopy(screens)
            self._preview_positions = copy.deepcopy(positions or {})
            self.previewChanged.emit()

    def update_preview_position(self, key, x, y):
        # Planning must see a just-dragged window immediately. Notification and
        # disk persistence can remain debounced without delaying this snapshot.
        self._preview_positions[key] = [x, y]

    def set_window_materials(self, value):
        if self._window_materials != value:
            self._window_materials = copy.deepcopy(value)
            self.previewChanged.emit()

    @Slot(str, result="QVariantMap")
    def previewState(self, key):
        for spec in self.preview_windows():
            cell = next((cell for cell in spec["cells"] if cell["key"] == key), None)
            if cell is None:
                continue
            policy = render_policy(self._draft, spec)
            report = self._window_materials.get(spec["id"], {})
            skin = effective_skin(self._draft, key)
            frosted = policy["backdrop"] and (
                report.get("material") == "desktop-acrylic"
                or (report.get("material") == "system-blur" and report.get("blur_configured") is True)
            )
            coating = skin in GLASS_SKINS and self._coating_allowed(report)
            return {
                "width": cell["width"],
                "height": cell["height"],
                "cell_x": cell["x"],
                "cell_y": cell["y"],
                "panel_width": spec["width"],
                "panel_height": spec["height"],
                "panel_skin": policy["panel_skin"],
                "panel_options": policy["panel_options"],
                "card_surfaces": policy["card_surfaces"],
                "skin": skin,
                "frosted": frosted,
                "coating_translucent": coating,
                "blur_configured": bool(report.get("blur_configured", frosted)),
                "status": "无底色"
                if skin == "minimal"
                else (
                    "系统模糊尚未确认。"
                    if coating and frosted
                    else "透明背景，未启用系统模糊。"
                    if coating
                    else "实色底色"
                    if skin in GLASS_SKINS
                    else ""
                ),
                "note": "",
                "compositing_verified": bool(report.get("compositing_verified", False)),
                "layout_warning": self.layout_error(self._draft),
            }
        # Disabled widgets still have an editable preview, without an active HWND.
        prefs = self._draft["widgets"].get(key)
        if not prefs:
            return {}
        config = copy.deepcopy(self._draft)
        config["widgets"][key]["enabled"] = True
        config["widget_order"] = [key]
        config["mode"] = "separate"
        cell = windows(config)[0]["cells"][0]
        skin = effective_skin(config, key)
        return dict(
            width=cell["width"],
            height=cell["height"],
            cell_x=0,
            cell_y=0,
            panel_width=cell["width"],
            panel_height=cell["height"],
            panel_skin=None,
            card_surfaces=True,
            skin=skin,
            frosted=False,
            coating_translucent=skin in GLASS_SKINS and self._coating_allowed(),
            blur_configured=False,
            status="无底色"
            if skin == "minimal"
            else "透明背景，未启用系统模糊。"
            if skin in GLASS_SKINS and self._coating_allowed()
            else "实色底色"
            if skin in GLASS_SKINS
            else "",
            note="",
            compositing_verified=False,
        )

    def _coating_allowed(self, report=None):
        """Alpha coating capability is independent of an Acrylic API result.

        An un-applied/disabled widget still has an editable style specimen.
        Explicit accessibility reports override that default for all specimens.
        """
        if report and "coating_allowed" in report:
            return report["coating_allowed"] is True
        return all(
            material.get("coating_allowed", True) is True
            for material in self._window_materials.values()
        )

    coatingAllowed = Property(bool, lambda self: self._coating_allowed(), notify=previewChanged)

    def _catalog_fingerprint(self):
        return (
            self._draft["language"],
            tuple(
                (
                    key,
                    prefs["kind"],
                    prefs["template"],
                    prefs["title"],
                    prefs["enabled"],
                    tuple(prefs.get("content") or ()),
                    tuple(
                        (slot, tuple(sorted(binding.items())))
                        for slot, binding in sorted(prefs.get("sensor_bindings", {}).items())
                    ),
                )
                for key in self._draft["widget_order"]
                for prefs in [self._draft["widgets"][key]]
            ),
        )

    @Slot()
    def _update_catalog(self):
        state = self._catalog_fingerprint()
        if state != self._catalog_state:
            self._catalog_state = state
            self._catalog_value = None
            self.catalogChanged.emit()

    @Slot()
    def _update_language(self):
        language = self._draft["language"]
        if language != self._notified_language:
            self._notified_language = language
            self.languageChanged.emit()
            self.sensorsChanged.emit()

    @Slot()
    def _update_theme(self):
        theme = self._draft["theme"]
        if theme != self._notified_theme:
            self._notified_theme = theme
            self.themeChanged.emit()

    def get_catalog(self):
        if self._catalog_value is None:
            self._catalog_value = self._build_catalog()
        return self._catalog_value

    def _build_catalog(self):
        def tr(value):
            return translate(value, self.language)

        return {
            "categories": choices({k: tr(v) for k, v in CATEGORIES.items()}),
            "templates": [
                dict(
                    id=key,
                    kind=meta["kind"],
                    label=tr(meta["label"]),
                    description=tr(meta["description"]),
                    category=meta.get("category", MODULES[meta["kind"]]["category"]),
                    color=MODULES[meta["kind"]]["color"],
                    content=meta["content"],
                    search=" ".join(
                        (
                            key,
                            meta["label"],
                            tr(meta["label"]),
                            meta["description"],
                            tr(meta["description"]),
                            " ".join(
                                item
                                + " "
                                + METRICS[item]["label"]
                                + " "
                                + tr(METRICS[item]["label"])
                                + " "
                                + METRICS[item]["unit"]
                                for item in meta["content"]
                            ),
                        )
                    ),
                )
                for key, meta in TEMPLATES.items()
            ],
            "instances": [
                dict(
                    id=key,
                    kind=prefs["kind"],
                    enabled=prefs["enabled"],
                    label=prefs["title"] or tr(TEMPLATES[prefs["template"]]["label"]),
                    subtitle=" · ".join(
                        self.metric_label(item, prefs) for item in (prefs["content"] or [])
                    ),
                    color=MODULES[prefs["kind"]]["color"],
                )
                for key in self._draft["widget_order"]
                for prefs in [self._draft["widgets"][key]]
            ],
            "modules": [
                dict(
                    id=key,
                    label=tr(meta["label"]),
                    subtitle=tr(meta["subtitle"]),
                    color=meta["color"],
                    primary=choices({k: tr(v) for k, v in meta["primary"].items()}),
                    secondary=choices({k: tr(v) for k, v in meta["secondary"].items()}),
                )
                for key, meta in MODULES.items()
            ],
            "metrics": [
                dict(
                    id=key,
                    label=tr(meta["label"]),
                    category=meta["category"],
                    unit=meta["unit"],
                    scope=meta["scope"],
                )
                for key, meta in METRICS.items()
                if key not in EXTERNAL_SLOTS
            ],
            "skins": choices({key: tr(value) for key, value in SKINS.items()}),
            "languages": choices(LANGUAGES),
            "presets": [
                dict(id=key, label=tr(meta["label"]), description=tr(meta["description"]))
                for key, meta in CATALOG_INFO.items()
            ],
        }

    catalog = Property("QVariantMap", get_catalog, notify=catalogChanged)

    commitError = Property(str, lambda self: translate(self._commit_error, self.language), notify=statusChanged)

    def set_status(self, value, *, error=False):
        self._status = value
        self._commit_error = value if error else ""
        self.statusChanged.emit()

    def set_material(self, value):
        self._material = value
        self.materialChanged.emit()

    @Slot(str, result=str)
    def tr(self, value):
        return translate(value, self.language)

    def _clear_draft_history(self):
        self._undo_drafts.clear()
        self._redo_drafts.clear()
        self._last_edit_key = None
        self.draftHistoryChanged.emit()

    def _rebase_bar_history(self, *, enabled_only=False):
        """A bar-only save must not erase other editors' undo/redo work."""
        def project(value):
            value = copy.deepcopy(value)
            if enabled_only:
                value["top_bar"]["enabled"] = self._saved["top_bar"]["enabled"]
            else:
                value["top_bar"] = copy.deepcopy(self._saved["top_bar"])
            return value

        def rebase(stack):
            # Both stacks pop from the end. Collapse no-op states introduced by
            # the saved branch, preserving the order of all unrelated edits.
            result, previous = [], self._draft
            for snapshot in reversed(stack):
                candidate = project(snapshot)
                if candidate != previous:
                    result.append(candidate)
                    previous = candidate
            return list(reversed(result))

        self._undo_drafts = rebase(self._undo_drafts)
        self._redo_drafts = rebase(self._redo_drafts)
        self._last_edit_key = None
        self._last_edit_time = 0
        self.draftHistoryChanged.emit()

    def _rebase_scope_history(self, scope):
        def rebase(stack):
            result, previous = [], self._draft
            for snapshot in reversed(stack):
                candidate = merge_scope(snapshot, self._saved, scope)
                if candidate != previous:
                    result.append(candidate)
                    previous = candidate
            return list(reversed(result))
        self._undo_drafts = rebase(self._undo_drafts)
        self._redo_drafts = rebase(self._redo_drafts)
        self._last_edit_key = None
        self._last_edit_time = 0
        self.draftHistoryChanged.emit()

    def _revert_scope(self, scope):
        if self._replacement_backup is not None:
            self.set_status("请应用或取消全部设置预览")
            return False
        if not scope_dirty(self._saved, self._draft, scope):
            return False
        if not self.edit(merge_scope(self._draft, self._saved, scope), record_history=False):
            return False
        self._rebase_scope_history(scope)
        return True

    @Slot(result=bool)
    def revertDesktopDraft(self):
        return self._revert_scope("desktop")

    @Slot(result=bool)
    def revertPreferencesDraft(self):
        return self._revert_scope("preferences")

    def _stage_replacement(self, value):
        previous_backup = self._replacement_backup
        if previous_backup is None:
            self._replacement_backup = dict(
                saved=copy.deepcopy(self._saved), draft=copy.deepcopy(self._draft),
                undo=copy.deepcopy(self._undo_drafts), redo=copy.deepcopy(self._redo_drafts),
                edit_key=self._last_edit_key, edit_time=self._last_edit_time,
            )
        if self.edit(value):
            return True
        self._replacement_backup = previous_backup
        self.draftChanged.emit()
        return False

    @Slot(result=bool)
    def cancelReplacement(self):
        backup = self._replacement_backup
        if backup is None:
            return False
        def rebase(value):
            return rebase_saved_changes(value, backup["saved"], self._saved)
        restored = rebase(backup["draft"])
        self._replacement_backup = None
        if not self.edit(restored, record_history=False):
            self._replacement_backup = backup
            self.draftChanged.emit()
            return False
        self._undo_drafts = [rebase(value) for value in backup["undo"]]
        self._redo_drafts = [rebase(value) for value in backup["redo"]]
        self._last_edit_key = backup["edit_key"]
        self._last_edit_time = backup["edit_time"]
        self.draftHistoryChanged.emit()
        return True

    @Slot(result=bool)
    def undoDraft(self):
        if not self._undo_drafts:
            return False
        target = self._undo_drafts[-1]
        current = copy.deepcopy(self._draft)
        if not self.edit(target, record_history=False):
            return False
        self._undo_drafts.pop()
        self._redo_drafts.append(current)
        self._last_edit_key = None
        self.draftHistoryChanged.emit()
        return True

    @Slot(result=bool)
    def redoDraft(self):
        if not self._redo_drafts:
            return False
        target = self._redo_drafts[-1]
        current = copy.deepcopy(self._draft)
        if not self.edit(target, record_history=False):
            return False
        self._redo_drafts.pop()
        self._undo_drafts.append(current)
        self._last_edit_key = None
        self.draftHistoryChanged.emit()
        return True

    def edit(self, value, *, merge_key=None, record_history=True):
        try:
            # Content mutations in manual mode re-seed the complete layout in
            # one transaction; never leave a new metric overlapping saved cells.
            candidates = value.get("widgets", {}) if isinstance(value, dict) else {}
            for key, prefs in candidates.items() if isinstance(candidates, dict) else ():
                if isinstance(prefs, dict) and prefs.get("layout_mode") == "manual":
                    content = self._content_for(prefs)
                    if set(prefs.get("metric_positions", {})) != set(content):
                        self._seed_manual(value, key)
            value = validate(value)
            windows(value)  # Validate effective readable dimensions before QML.
        except (ValueError, KeyError, TypeError) as error:
            self.set_status(str(error))
            return False
        if record_history and value != self._draft:
            now = time.monotonic()
            merged = (
                merge_key is not None
                and merge_key == self._last_edit_key
                and now - self._last_edit_time < 0.8
                and self._undo_drafts
            )
            if not merged:
                self._undo_drafts.append(copy.deepcopy(self._draft))
                del self._undo_drafts[:-50]
            elif value == self._undo_drafts[-1]:
                self._undo_drafts.pop()
            self._redo_drafts.clear()
            self._last_edit_key, self._last_edit_time = merge_key, now
            self.draftHistoryChanged.emit()
        self._draft = value
        self._refresh_external_values()
        self.draftChanged.emit()
        self.dataChanged.emit()
        self.set_status("设置尚未应用" if self._draft != self._saved else "设置已同步")
        return True

    @Slot(str, "QVariant")
    def change(self, field, value):
        draft = copy.deepcopy(self._draft)
        if field not in draft or field in ("widgets", "version", "widget_order"):
            return
        if (
            field in ("size", "opacity", "group_columns", "refresh", "magnet_gap")
            and isinstance(value, float)
            and value.is_integer()
        ):
            value = int(value)
        draft[field] = value
        self.edit(draft, merge_key=("global", field))

    @Slot(str, str, "QVariant")
    def changeWidget(self, key, field, value):
        if (
            key not in self._draft["widgets"]
            or field not in self._draft["widgets"][key]
            or field in ("kind", "template")
        ):
            return
        if field == "size" and isinstance(value, float) and value.is_integer():
            value = int(value)
        draft = copy.deepcopy(self._draft)
        draft["widgets"][key][field] = value
        if field == "layout_mode" and value == "manual":
            self._seed_manual(draft, key)
        if field == "content":
            draft["widgets"][key]["sensor_bindings"] = {
                slot: binding
                for slot, binding in draft["widgets"][key]["sensor_bindings"].items()
                if slot in (value or [])
            }
        if (
            field == "content"
            and isinstance(value, list)
            and value
            and isinstance(value[0], str)
            and value[0] in METRICS
            and metric_info(value[0], draft["widgets"][key])["unit"] != "%"
            and draft["widgets"][key]["presentation"] in ("ring", "bar")
        ):
            draft["widgets"][key]["presentation"] = "auto"
        if field == "enabled" and value and key not in draft["widget_order"]:
            draft["widget_order"].append(key)
        self.edit(
            draft,
            merge_key=(key, field)
            if field in ("title", "size", "glass_transparency", "glass_curvature", "glass_opacity")
            else None,
        )

    @staticmethod
    def _content_for(prefs):
        from native_card import primary_metric

        if prefs.get("content"):
            return list(prefs["content"])
        if prefs["kind"] == "power" and prefs["primary"] == "watts":
            return ["battery_charge_watts", "battery_discharge_watts"]
        return [primary_metric(prefs["kind"], prefs)]

    def _seed_manual(self, config, key):
        prefs = config["widgets"][key]
        prefs["content"] = self._content_for(prefs)
        prefs["metric_positions"] = {
            metric: rect
            for metric, rect in prefs.get("metric_positions", {}).items()
            if metric in prefs["content"]
        }
        if set(prefs.get("metric_positions", {})) == set(prefs["content"]):
            return
        previous = self._draft["widgets"].get(key, {})
        existing = prefs["metric_positions"]
        added = [metric for metric in prefs["content"] if metric not in existing]
        if previous.get("layout_mode") == "manual" and existing and added:
            width, height, body, _ = self._layout_context(key)
            result = append_layout(existing, body, added)
            if not result["valid"]:
                raise ValueError(self._assist_message(result["reason"]))
            body_height = math.ceil(result["body"]["height"])
            scale_y = result["body"]["height"] / body_height
            positions = {
                metric: dict(rect, y=rect["y"] * scale_y, height=rect["height"] * scale_y)
                for metric, rect in result["positions"].items()
            }
            prefs.update(
                metric_positions=positions,
                width=width,
                height=round(height + body_height - body["height"]),
            )
            return
        candidate = copy.deepcopy(config)
        source_mode = previous.get("layout_mode", "auto")
        snapshot = (
            is_responsive(previous)
            and source_mode != "manual"
            and self._content_for(previous) == prefs["content"]
        )
        candidate["widgets"][key].update(
            layout_mode=source_mode if snapshot else "grid", metric_positions={}
        )
        width, height = dimensions(candidate, key)
        layout = responsive_plan(width, height, prefs["content"], candidate["widgets"][key])
        body = layout.body
        prefs["metric_positions"] = {
            row["id"]: dict(
                x=(row["x"] - body.x) / body.width,
                y=(row["y"] - body.y) / body.height,
                width=row["width"] / body.width,
                height=row["height"] / body.height,
            )
            for row in metric_rects(layout, prefs["content"])
        }
        prefs.update(width=width, height=height)

    @Slot(str, float, float, result=bool)
    def setWidgetDimensions(self, key, width, height):
        if key not in self._draft["widgets"] or not numeric(width) or not numeric(height):
            return False
        if not 80 <= width <= 4096 or not 32 <= height <= 2160:
            return False
        value = copy.deepcopy(self._draft)
        prefs = value["widgets"][key]
        prefs.update(width=round(width), height=round(height))
        if prefs["form"] in ("square", "wide"):
            prefs["form"] = "free"
        try:
            actual_width, actual_height = dimensions(value, key)
            prefs.update(width=actual_width, height=actual_height)
            return self.edit(value)
        except ValueError as error:
            self.set_status(str(error))
            return False

    @Slot(str, str, result=bool)
    def setWidgetShape(self, key, form):
        if key not in self._draft["widgets"] or form not in ("square", "wide", "free", "bar"):
            return False
        value = copy.deepcopy(self._draft)
        prefs = value["widgets"][key]
        width, height = dimensions(value, key)
        prefs["form"] = form
        if form == "bar":
            prefs.update(
                width=900,
                height=40,
                layout_mode="auto",
                show_title=False,
                chart=False,
                metric_positions={},
                dock="top",
            )
        elif form == "free":
            prefs.update(width=width, height=height)
        else:
            prefs.update(
                width=None, height=None, layout_mode="auto", metric_positions={}, dock="free"
            )
        return self.edit(value)

    @Slot(result=str)
    def createStatusBar(self):
        return self.addWidget("status_bar")

    @Slot(str, result="QVariantMap")
    def widgetDimensions(self, key):
        if key not in self._draft["widgets"]:
            return {}
        width, height = dimensions(self._draft, key)
        minw, minh = minimum_dimensions(self._draft["widgets"][key], width)
        return dict(
            width=width,
            height=height,
            min_width=minw,
            min_height=minh,
            max_width=4096,
            max_height=2160,
        )

    @Slot(str, int, int, result=bool)
    def reorderMetric(self, key, source, destination):
        if key not in self._draft["widgets"]:
            return False
        content = list(self._draft["widgets"][key].get("content") or [])
        if not 0 <= source < len(content) or not 0 <= destination < len(content):
            return False
        previous = list(content)
        content.insert(destination, content.pop(source))
        value = copy.deepcopy(self._draft)
        prefs = value["widgets"][key]
        prefs["content"] = content
        if prefs.get("layout_mode") == "manual":
            original = copy.deepcopy(prefs["metric_positions"])
            prefs["metric_positions"] = {
                metric: original[previous[index]] for index, metric in enumerate(content)
            }
        return self.edit(value)

    @Slot(str, float, float, result="QVariantMap")
    def widgetContentLayout(self, key, width, height):
        if key not in self._draft["widgets"] or not numeric(width) or not numeric(height):
            return {}
        config = copy.deepcopy(self._draft)
        prefs = config["widgets"][key]
        current_width, current_height = dimensions(config, key)
        if is_responsive(prefs) or (round(width), round(height)) != (current_width, current_height):
            prefs.update(width=round(width), height=round(height))
            if prefs["form"] in ("square", "wide"):
                prefs["form"] = "free"
        try:
            width, height = dimensions(config, key)
            metrics = self._content_for(prefs)
            layout = responsive_plan(width, height, metrics, prefs)
            return dict(
                width=width,
                height=height,
                body=asdict(layout.body),
                readings=metric_rects(layout, metrics),
            )
        except ValueError:
            return {}

    @Slot(str, result="QVariantList")
    def widgetContentIds(self, key):
        prefs = self._draft["widgets"].get(key)
        return self._content_for(prefs) if prefs else []

    def _layout_context(self, key):
        prefs = self._draft["widgets"][key]
        width, height = dimensions(self._draft, key)
        content = self._content_for(prefs)
        plan = responsive_plan(width, height, content, prefs)
        body = asdict(plan.body)
        positions = {
            r["id"]: dict(
                x=(r["x"] - body["x"]) / body["width"],
                y=(r["y"] - body["y"]) / body["height"],
                width=r["width"] / body["width"],
                height=r["height"] / body["height"],
            )
            for r in metric_rects(plan, content)
        }
        return width, height, body, positions

    def _assist_message(self, reason):
        return (
            self.tr(
                {
                    "outside_content": "指标不能超出组件边界。",
                    "minimum_size": "指标区域太小，请扩大后再调整。",
                    "overlap": "指标重叠，可拖到另一项中央交换位置。",
                    "need_selection": "请先选择指标。",
                    "need_three": "请至少选择三项指标。",
                    "insufficient_space": "空间不足，无法保持间距。",
                }.get(reason, reason)
            )
            if reason
            else ""
        )

    @Slot(str, str, "QVariantMap", str, bool, bool, result="QVariantMap")
    def previewMetricPlacement(self, key, metric, proposal, operation, snap_enabled, bypass):
        try:
            _, _, body, positions = self._layout_context(key)
            result = assist_rect(
                positions,
                metric,
                proposal,
                body,
                operation=operation,
                enabled=snap_enabled,
                bypass=bypass,
            )
            result["reason_code"] = result["reason"]
            result["reason"] = self._assist_message(result["reason"])
            return result
        except (ValueError, TypeError, KeyError):
            return dict(
                valid=False,
                rect=proposal,
                guides=[],
                collisions=[],
                reason=self.tr("位置未更改，请重试。"),
            )

    @Slot(str, str, "QVariantList", result="QVariantMap")
    def previewLayoutOperation(self, key, operation, selection):
        try:
            _, _, body, positions = self._layout_context(key)
            if operation.startswith("distribute_"):
                result = distribute_layout(
                    positions, body, selection, operation.removeprefix("distribute_")
                )
            elif operation == "swap" and len(selection) == 2:
                result = swap_layout(positions, body, *selection)
            else:
                result = align_layout(positions, body, selection, operation)
            result["reason_code"] = result["reason"]
            result["reason"] = self._assist_message(result["reason"])
            return result
        except (ValueError, TypeError, KeyError):
            return dict(valid=False, positions={}, reason=self.tr("位置未更改，请重试。"))

    @Slot(str, "QVariantMap", result=bool)
    def commitMetricPositions(self, key, positions):
        try:
            width, height, _, _ = self._layout_context(key)
            candidate = copy.deepcopy(self._draft)
            prefs = candidate["widgets"][key]
            content = self._content_for(prefs)
            if set(positions) != set(content):
                return False
            prefs.update(
                content=content,
                layout_mode="manual",
                metric_positions=copy.deepcopy(positions),
                width=width,
                height=height,
            )
            if prefs["form"] in ("square", "wide"):
                prefs["form"] = "free"
            validated = validate(candidate)
            actual_width, actual_height = dimensions(validated, key)
            if actual_width > width + 1 or actual_height > height + 1:
                self.set_status("指标区域太小，请扩大后再调整。")
                return False
            return self.edit(validated)
        except (ValueError, TypeError, KeyError):
            self.set_status("位置未更改，请重试。")
            return False

    @Slot(str, str, result=bool)
    def applyLayoutPreset(self, key, preset):
        if key not in self._draft["widgets"] or preset not in (
            "card",
            "horizontal",
            "vertical",
            "auto",
        ):
            return False
        candidate = copy.deepcopy(self._draft)
        prefs = candidate["widgets"][key]
        prefs["content"] = self._content_for(prefs)
        prefs.update(layout_mode="auto", metric_positions={})
        if preset == "horizontal":
            prefs.update(
                form="bar", width=900, height=40, dock="top", show_title=False, chart=False
            )
        elif preset == "vertical":
            prefs.update(
                form="free",
                width=200,
                height=max(122, len(prefs["content"]) * 38 + 8),
                dock="free",
                layout_mode="vertical",
            )
        elif preset == "card":
            prefs.update(form="free", width=360, height=180, dock="free", columns=2)
        return self.edit(candidate)

    @Slot(str, str, float, float, float, float, result=bool)
    def setMetricPosition(self, key, metric, x, y, width, height):
        if key not in self._draft["widgets"]:
            return False
        prefs = self._draft["widgets"][key]
        if prefs.get("layout_mode") != "manual" or metric not in (prefs.get("content") or []):
            return False
        positions = copy.deepcopy(prefs["metric_positions"])
        positions[metric] = dict(x=x, y=y, width=width, height=height)
        return self.commitMetricPositions(key, positions)

    @Slot(str, int, float, float)
    def openDetails(self, key, index, x, y):
        if key in self._saved["widgets"]:
            self.detailsRequested.emit(key, index, x, y)

    @Slot(str, int, result="QVariantMap")
    def detailState(self, key, index):
        prefs = self._saved["widgets"].get(key)
        if not prefs:
            return {}
        content = self._content_for(prefs)
        rows = {row["id"]: row for row in self.sensor_rows(prefs, discovered=False)}
        selected = content[max(0, min(len(content) - 1, index))]
        item = rows[selected]
        return dict(
            title=prefs["title"] or self.tr(TEMPLATES[prefs["template"]]["label"]),
            selected=item,
            items=[rows[metric] for metric in content],
            updated_at=self._data.get("time"),
        )

    @Slot(str, str)
    def contentMode(self, key, mode):
        if key not in self._draft["widgets"]:
            return
        content = self._draft["widgets"][key]["content"]
        if mode == "custom" and not content:
            from native_card import primary_metric

            self.changeWidget(
                key,
                "content",
                [primary_metric(self._draft["widgets"][key]["kind"], self._draft["widgets"][key])],
            )
        elif mode == "preset":
            self.changeWidget(key, "content", None)

    @Slot(str, str)
    def addMetric(self, key, metric):
        if key not in self._draft["widgets"]:
            return
        prefs = self._draft["widgets"][key]
        content = list(prefs["content"] or [])
        if len(content) >= 6:
            return
        if metric in self._discovered_ids:
            row = self._external_rows.get(self._discovered_ids[metric])
            if row is None or any(
                b["sensor_id"] == row["id"] for b in prefs["sensor_bindings"].values()
            ):
                return
            slot = next((slot for slot in EXTERNAL_SLOTS if slot not in content), None)
            if slot is None:
                return
            value = copy.deepcopy(self._draft)
            target = value["widgets"][key]
            target["sensor_bindings"][slot] = self._binding_for(row)
            target["content"] = content + [slot]
            if not content and row["unit"] != "%" and target["presentation"] in ("ring", "bar"):
                target["presentation"] = "auto"
            self.edit(value)
        elif metric in METRICS and metric not in EXTERNAL_SLOTS and metric not in content:
            self.changeWidget(key, "content", content + [metric])

    @Slot(str, "QVariantList", result=bool)
    def addMetrics(self, key, metrics):
        """Confirm a picker selection atomically; cancel never edits preferences."""
        if key not in self._draft["widgets"] or not isinstance(metrics, list) or not metrics:
            return False
        candidate = copy.deepcopy(self._draft)
        prefs = candidate["widgets"][key]
        content = self._content_for(prefs)
        for metric in metrics:
            if not isinstance(metric, str) or len(content) >= 6:
                self.set_status("自由内容请选择 1–6 项指标")
                return False
            if metric in self._discovered_ids:
                channel = self._external_rows.get(self._discovered_ids[metric])
                if channel is None:
                    self.set_status("所选传感器未连接")
                    return False
                if any(
                    binding["sensor_id"] == channel["id"]
                    for binding in prefs["sensor_bindings"].values()
                ):
                    return False
                slot = next((slot for slot in EXTERNAL_SLOTS if slot not in content), None)
                if slot is None:
                    return False
                prefs["sensor_bindings"][slot] = self._binding_for(channel)
                content.append(slot)
            elif metric in METRICS and metric not in EXTERNAL_SLOTS and metric not in content:
                content.append(metric)
            else:
                return False
        prefs["content"] = content
        if metric_info(content[0], prefs)["unit"] != "%" and prefs["presentation"] in (
            "ring",
            "bar",
        ):
            prefs["presentation"] = "auto"
        return self.edit(candidate)

    @Slot(str, int, int)
    def moveMetric(self, key, index, delta):
        if key not in self._draft["widgets"]:
            return
        content = list(self._draft["widgets"][key]["content"] or [])
        destination = index + delta
        if 0 <= index < len(content) and 0 <= destination < len(content):
            self.reorderMetric(key, index, destination)

    @Slot(str, int)
    def removeMetric(self, key, index):
        if key not in self._draft["widgets"]:
            return
        content = list(self._draft["widgets"][key]["content"] or [])
        if len(content) > 1 and 0 <= index < len(content):
            removed = content.pop(index)
            value = copy.deepcopy(self._draft)
            value["widgets"][key]["content"] = content
            value["widgets"][key]["sensor_bindings"].pop(removed, None)
            self.edit(value)

    @Slot(str, result=str)
    def addWidget(self, template):
        if template not in TEMPLATES or len(self._draft["widget_order"]) >= MAX_WIDGETS:
            self.set_status("最多添加 24 个小组件")
            return ""
        key = "w_" + uuid.uuid4().hex[:12]
        draft = copy.deepcopy(self._draft)
        draft["widgets"][key] = from_template(template)
        draft["widget_order"].append(key)
        return key if self.edit(draft) else ""

    @Slot(str, result=str)
    def duplicateWidget(self, key):
        if (
            key not in self._draft["widget_order"]
            or len(self._draft["widget_order"]) >= MAX_WIDGETS
        ):
            return ""
        new_key = "w_" + uuid.uuid4().hex[:12]
        draft = copy.deepcopy(self._draft)
        draft["widgets"][new_key] = copy.deepcopy(draft["widgets"][key])
        draft["widget_order"].insert(draft["widget_order"].index(key) + 1, new_key)
        return new_key if self.edit(draft) else ""

    @Slot(str)
    def removeWidget(self, key):
        if key not in self._draft["widgets"]:
            return
        draft = copy.deepcopy(self._draft)
        draft["widgets"].pop(key)
        draft["widget_order"] = [item for item in draft["widget_order"] if item != key]
        self.edit(draft)

    @Slot(str, int)
    def moveWidget(self, key, delta):
        order = list(self._draft["widget_order"])
        if key not in order:
            return
        index = order.index(key)
        target = index + delta
        if 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            draft = copy.deepcopy(self._draft)
            draft["widget_order"] = order
            self.edit(draft)

    @Slot(str, result="QVariantMap")
    def templatePreview(self, template):
        if template not in TEMPLATES:
            return {}
        prefs = from_template(template)
        if prefs["presentation"] != "cores":
            prefs["content"] = prefs["content"][:1]
            prefs["presentation"] = "auto"
        return dict(self._draft, widgets={"gallery": prefs})

    @Slot(str, str, result="QVariantMap")
    def skinPreview(self, key, skin):
        prefs = copy.deepcopy(self._draft["widgets"].get(key))
        if not prefs:
            first = self._draft["widget_order"][:1]
            prefs = (
                copy.deepcopy(self._draft["widgets"][first[0]]) if first else from_template("cpu")
            )
        # A skin changes the surface, never the user's content or geometry.
        prefs["skin"] = skin if skin in SKINS else None
        return dict(self._draft, widgets={"preview": prefs})

    @Slot(str, result="QVariantMap")
    def widgetHealth(self, key):
        """Availability of this widget's selected channels, not the whole sampler."""
        prefs = self._draft["widgets"].get(key)
        if not prefs:
            return dict(
                total=0, available=0, fresh=False, age_seconds=None, state="empty", missing=[]
            )
        content = prefs.get("content")
        if not content:
            from native_card import primary_metric

            content = [primary_metric(prefs["kind"], prefs)]
            if prefs["kind"] == "power" and prefs["primary"] == "watts":
                content = ["battery_charge_watts", "battery_discharge_watts"]
        stamp = self._data.get("time")
        age = time.time() - stamp if numeric(stamp) else None
        fresh = age is not None and 0 <= age < 35
        rows = {row["id"]: row for row in self.sensor_rows(prefs, discovered=False)}
        missing = []
        available = 0
        for metric in content:
            row = rows[metric]
            if fresh and row["available"]:
                available += 1
            else:
                missing.append(
                    dict(
                        id=metric,
                        label=row["label"],
                        reason=self.tr("读数已过期")
                        if age is not None and not fresh
                        else row["reason"] or self.tr("等待读数"),
                    )
                )
        return dict(
            total=len(content),
            available=available,
            fresh=fresh,
            age_seconds=round(age, 2) if age is not None else None,
            state="stale"
            if age is not None and not fresh
            else "waiting"
            if not fresh
            else "ready"
            if available == len(content)
            else "partial"
            if available
            else "unavailable",
            missing=missing,
        )

    @Slot(str)
    def closeWindow(self, key):
        self.windowCloseRequested.emit(key)

    def hideWindow(self, key):
        """One atomic close of an individual widget or the whole combined panel."""
        spec = next((spec for spec in windows(self._saved) if spec["id"] == key), None)
        if spec is None:
            return False
        value, pending = copy.deepcopy(self._saved), copy.deepcopy(self._draft)
        for cell in spec["cells"]:
            item = cell["key"]
            value["widgets"][item]["enabled"] = False
            if item in pending["widgets"]:
                pending["widgets"][item]["enabled"] = False
        try:
            value, pending = validate(value), validate(pending)
            save(value)
        except (OSError, ValueError):
            self.set_status("操作未完成，请重试")
            return False
        self._saved, self._draft = value, pending
        self._clear_draft_history()
        self.savedChanged.emit()
        self.draftChanged.emit()
        self.applyRequested.emit(False)
        self.set_status("设置尚未应用" if value != pending else "已应用到桌面")
        return True

    @Slot()
    def useGlobalSkin(self):
        value = copy.deepcopy(self._draft)
        for prefs in value["widgets"].values():
            prefs["skin"] = None
        self.edit(value)

    @Slot(str, result="QVariantList")
    def metricRowsFor(self, key):
        prefs = self._draft["widgets"].get(key, {})
        return [
            dict(row, selected=row["id"] in self._content_for(prefs))
            for row in self.sensor_rows(prefs)
        ]

    @Slot(str, str, result="QVariantMap")
    def metricInfoFor(self, key, metric):
        prefs = self._draft["widgets"].get(key, {})
        if metric not in METRICS:
            return {}
        meta = dict(metric_info(metric, prefs))
        meta["label"] = self.metric_label(metric, prefs)
        binding = sensor_binding(metric, prefs)
        meta["hardware_name"] = binding["hardware_name"] if binding else ""
        return meta

    def metric_label(self, key, prefs=None):
        meta = metric_info(key, prefs)
        return meta["label"] if key in EXTERNAL_SLOTS else self.tr(meta["label"])

    @Slot(str, str, result=str)
    def unitFor(self, key, metric):
        return display_value(self._data, metric, self._draft["widgets"].get(key, {}))[1]

    @Slot(str, str, result=str)
    def readingFor(self, key, metric):
        value, unit = formatted(self._data, metric, self._draft["widgets"].get(key, {}))
        return value + (" " + unit if value != "—" and unit else "")

    @Slot(str, str, result="QVariantList")
    def deviceChoices(self, key, scope):
        field, special, label = {
            "networks": ("network_target", "auto", "自动选择活跃网卡"),
            "disks": ("disk_target", "all", "所有物理磁盘"),
            "volumes": ("volume_target", "system", "系统分区"),
            "gpus": ("gpu_target", "0", "GPU 0"),
            "storages": ("storage_target", "0", "PhysicalDrive0"),
        }[scope]
        result = [dict(id=special, label=self.tr(label))]
        result.extend(
            dict(id=device, label=values.get("label", device))
            for device, values in self._devices.get(scope, {}).items()
            if device != special
        )
        selected = self._draft["widgets"].get(key, {}).get(field, special)
        if selected not in [item["id"] for item in result]:
            result.append(dict(id=selected, label=selected + " · " + self.tr("未连接")))
        return result

    @Slot(str, float)
    @Slot(str, float, float)
    def resizeWidget(self, key, width, base_width=0):
        """Commit a completed desktop drag without discarding unrelated editor drafts."""
        if self._saved["locked"] or not numeric(width):
            return
        before = self._saved
        spec = next((item for item in windows(before) if item["id"] == key), None)
        if not spec:
            return
        ratio = width / (base_width if numeric(base_width) and base_width > 0 else spec["width"])
        value = copy.deepcopy(before)
        pending = copy.deepcopy(self._draft)
        for cell in spec["cells"]:
            widget = cell["key"]
            size = max(
                minimum_size(before, widget),
                min(180, round(effective_size(before, widget) * ratio)),
            )
            value["widgets"][widget]["size"] = size
            # A desktop resize wins only for size; all other pending edits remain.
            if widget in pending["widgets"]:
                pending["widgets"][widget]["size"] = size
        try:
            capacity = self.layout_error(value, value["reflow_on_resize"])
            if capacity:
                self.set_status(capacity, error=True)
                self.applyRequested.emit(False)
                return
            save(value)
            self._saved, self._draft = value, pending
            self._clear_draft_history()
            self.savedChanged.emit()
            self.draftChanged.emit()
            self.applyRequested.emit(value["reflow_on_resize"])
            self.set_status("尺寸已保存并重新排列" if value["reflow_on_resize"] else "尺寸已保存")
        except OSError:
            self.set_status("未能保存，请重试", error=True)
            self.applyRequested.emit(False)

    @Slot(str, result="QVariantMap")
    @Slot(str, float, result="QVariantMap")
    def resizeLimits(self, key, candidate_width=0):
        spec = next((item for item in windows(self._saved) if item["id"] == key), None)
        if not spec:
            return {}
        sizes = [effective_size(self._saved, cell["key"]) for cell in spec["cells"]]
        floors = [minimum_size(self._saved, cell["key"]) for cell in spec["cells"]]
        minimum_ratio = max(floor / size for floor, size in zip(floors, sizes))
        if len(spec["cells"]) == 1:
            prefs = copy.deepcopy(self._saved["widgets"][spec["cells"][0]["key"]])
            prefs.update(width=spec["width"], height=spec["height"])
            if prefs["form"] in ("square", "wide"):
                prefs["form"] = "free"
            min_width, _ = minimum_dimensions(prefs, 4096)
            _, min_height = minimum_dimensions(
                prefs, max(min_width, candidate_width or spec["width"])
            )
        else:
            min_width = max(80, spec["width"] * minimum_ratio)
            min_height = max(32, spec["height"] * minimum_ratio)
        return dict(
            minimum=spec["width"] * minimum_ratio,
            maximum=spec["width"] * min(180 / size for size in sizes),
            minimum_ratio=minimum_ratio,
            maximum_ratio=min(180 / size for size in sizes),
            min_width=min_width,
            min_height=min_height,
            max_width=max(4096, min_width),
            max_height=max(2160, min_height),
        )

    @Slot(str, float, float, result=bool)
    def resizeWindow(self, key, width, height):
        if self._saved["locked"] or not numeric(width) or not numeric(height):
            return False
        spec = next((item for item in windows(self._saved) if item["id"] == key), None)
        if spec is None:
            return False
        value, pending = copy.deepcopy(self._saved), copy.deepcopy(self._draft)
        columns = min(value["group_columns"], len(spec["cells"]))
        rows = math.ceil(len(spec["cells"]) / columns)
        sx = (
            (width - 24 - (columns - 1) * 8) / max(1, spec["width"] - 24 - (columns - 1) * 8)
            if key == "group"
            else width / spec["width"]
        )
        sy = (
            (height - 24 - (rows - 1) * 8) / max(1, spec["height"] - 24 - (rows - 1) * 8)
            if key == "group"
            else height / spec["height"]
        )
        try:
            for cell in spec["cells"]:
                prefs = value["widgets"][cell["key"]]
                prefs.update(
                    width=max(80, min(4096, round(cell["width"] * sx))),
                    height=max(32, min(2160, round(cell["height"] * sy))),
                )
                if prefs["form"] in ("square", "wide"):
                    prefs["form"] = "free"
                prefs["width"], prefs["height"] = dimensions(value, cell["key"])
                if cell["key"] in pending["widgets"]:
                    pending["widgets"][cell["key"]].update(
                        {field: prefs[field] for field in ("width", "height", "form")}
                    )
            value, pending = validate(value), validate(pending)
            capacity = self.layout_error(value, value["reflow_on_resize"])
            if capacity:
                self.set_status(capacity, error=True)
                self.applyRequested.emit(False)
                return False
            save(value)
        except (OSError, ValueError):
            self.set_status("未能保存，请重试", error=True)
            self.applyRequested.emit(False)
            return False
        self._saved, self._draft = value, pending
        self._clear_draft_history()
        self.savedChanged.emit()
        self.draftChanged.emit()
        self.applyRequested.emit(value["reflow_on_resize"])
        self.set_status("尺寸已保存并重新排列" if value["reflow_on_resize"] else "尺寸已保存")
        return True

    @Slot(str)
    def preset(self, key):
        presets = catalogue()
        if key not in presets:
            return
        value = presets[key]["config"]
        value["language"] = self.language
        value["autostart"] = self._draft["autostart"]
        for widget in value["widgets"].values():
            if widget["title"] == "系统状态":
                widget["title"] = translate("系统状态", self.language)
        self.edit(merge_scope(self._draft, value, "desktop"))

    @Slot()
    def reset(self):
        value = copy.deepcopy(DEFAULT)
        value.update(language=self.language, skin="glass", autostart=self._draft["autostart"])
        self._stage_replacement(value)

    @Slot()
    def revert(self):
        if self._replacement_backup is not None:
            self.cancelReplacement()
        else:
            self.edit(copy.deepcopy(self._saved))

    def _commit(self, force_rearrange=False, *, scope=None):
        if scope is not None and self._replacement_backup is not None:
            self.set_status("请应用或取消全部设置预览")
            return False
        before = self._saved
        try:
            value = validate(merge_scope(self._saved, self._draft, scope) if scope else self._draft)
            rearrange = any(
                before[k] != value[k] for k in ("mode", "layout", "size", "group_columns")
            )
            rearrange = (
                rearrange
                or before["widget_order"] != value["widget_order"]
                or any(
                    before["widgets"].get(key, {}).get(field) != prefs[field]
                    for key, prefs in value["widgets"].items()
                    for field in ("size", "form", "enabled", "grouped")
                )
            )
            rearrange = rearrange or force_rearrange
            capacity = self.layout_error(value, rearrange)
            if capacity:
                self.set_status(capacity, error=True)
                return False
            if value["autostart"] != before["autostart"]:
                set_autostart(value["autostart"])
            try:
                save(value)
            except Exception:
                if value["autostart"] != before["autostart"]:
                    set_autostart(before["autostart"])
                raise
            self._saved = value
            if scope:
                self._draft = merge_scope(self._draft, value, scope)
                self._rebase_scope_history(scope)
            else:
                self._replacement_backup = None
                self._clear_draft_history()
                self._draft = copy.deepcopy(value)
            self.savedChanged.emit()
            self.draftChanged.emit()
            self.applyRequested.emit(rearrange)
            self._applied_status("已应用到桌面")
            return True
        except Exception:
            logging.exception("Native settings commit failed")
            self.set_status("未能保存，请重试", error=True)
            return False

    @Slot()
    def apply(self):
        self._commit()

    @Slot(result=bool)
    def applyDesktop(self):
        return self._commit(scope="desktop")

    @Slot(result=bool)
    def applyPreferences(self):
        return self._commit(scope="preferences")

    @Slot(result=bool)
    def applyReplacement(self):
        return self._commit() if self._replacement_backup is not None else False

    @Slot(result=bool)
    def rearrangeDesktop(self):
        return self._commit(force_rearrange=True, scope="desktop")

    @Slot()
    def rearrange(self):
        self._commit(force_rearrange=True)

    @Slot(str)
    def quick(self, field):
        if field not in ("visible", "locked"):
            return
        value = copy.deepcopy(self._saved)
        value[field] = not value[field]
        if field == "visible" and value[field]:
            capacity = self.layout_error(value)
            if capacity:
                self.set_status(capacity, error=True)
                return
        try:
            save(value)
            self._saved = value
            self._clear_draft_history()
            self._draft[field] = value[field]
            self.savedChanged.emit()
            self.draftChanged.emit()
            self.applyRequested.emit(False)
        except OSError:
            logging.exception("Native quick action failed")
            self.set_status("操作未完成，请重试")

    @Slot(str, str, "QVariant", result=bool)
    def quickWidget(self, key, field, selected):
        """Apply one desktop action while retaining every unrelated editor draft."""
        if key not in self._saved["widgets"] or field not in (
            "skin",
            "show_title",
            "size",
            "form",
            "presentation",
            "chart",
            "enabled",
            "grouped",
            "dock",
            "layer",
        ):
            return False
        value, pending = copy.deepcopy(self._saved), copy.deepcopy(self._draft)
        if field == "size" and isinstance(selected, float) and selected.is_integer():
            selected = int(selected)
        prefs = value["widgets"][key]
        prefs[field] = selected
        changed_fields = [field]
        if field == "form":
            changed_fields += ["width", "height", "layout_mode", "metric_positions", "dock"]
            if selected == "bar":
                prefs.update(
                    width=900,
                    height=40,
                    layout_mode="auto",
                    metric_positions={},
                    dock="top",
                    show_title=False,
                    chart=False,
                )
                changed_fields += ["show_title", "chart"]
            elif selected == "free":
                prefs["width"], prefs["height"] = dimensions(self._saved, key)
            else:
                prefs.update(
                    width=None, height=None, layout_mode="auto", metric_positions={}, dock="free"
                )
        rearrange = field in ("form", "grouped") or (field == "size" and value["reflow_on_resize"])
        if field == "enabled" and selected and key not in value["widget_order"]:
            value["widget_order"].append(key)
        try:
            value = validate(value)
            capacity = self.layout_error(value, rearrange)
            if capacity:
                self.set_status(capacity, error=True)
                return False
            if key in pending["widgets"]:
                pending["widgets"][key].update(
                    {name: copy.deepcopy(value["widgets"][key][name]) for name in changed_fields}
                )
                if field == "enabled" and selected and key not in pending["widget_order"]:
                    pending["widget_order"].append(key)
            pending = validate(pending)
            save(value)
        except (OSError, ValueError):
            self.set_status("操作未完成，请重试")
            return False
        self._saved, self._draft = value, pending
        self._clear_draft_history()
        self.savedChanged.emit()
        self.draftChanged.emit()
        self.applyRequested.emit(rearrange)
        self.set_status("设置尚未应用" if pending != value else "已应用到桌面")
        return True

    def import_path(self, path):
        path = Path(path)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("设置文件过大")
        self._stage_replacement(validate(json.loads(path.read_text(encoding="utf-8-sig"))))

    @Slot()
    def importSettings(self):
        path, _ = QFileDialog.getOpenFileName(None, self.tr("导入设置"), "", "JSON (*.json)")
        if path:
            try:
                self.import_path(path)
            except (OSError, ValueError) as error:
                self.set_status(str(error) if isinstance(error, ValueError) else "无法读取设置文件")

    @Slot()
    def exportSettings(self):
        path, _ = QFileDialog.getSaveFileName(
            None, self.tr("导出设置"), "DesktopStats.json", "JSON (*.json)"
        )
        if path:
            try:
                Path(path).write_text(
                    json.dumps(validate(self._draft), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self.set_status("设置已导出")
            except OSError:
                self.set_status("未能保存，请重试", error=True)

    @Slot(str)
    def openSettings(self, key=""):
        self.settingsRequested.emit(key)

    @Slot(str, int, int)
    def moved(self, key, x, y):
        self.positionChanged.emit(key, x, y)

    @Slot(str)
    def beginMove(self, key):
        self.moveStarted.emit(key)

    @Slot(str)
    def endMove(self, key):
        self.moveFinished.emit(key)

    @Slot(str)
    def widgetMenu(self, key):
        self.menuRequested.emit(key)

    @Slot()
    def quit(self):
        self.quitRequested.emit()

    @Slot()
    def inspect(self):
        sensors.INSPECT_UNTIL = time.monotonic() + 8

    @Slot()
    def rescanExternal(self):
        self.inspect()
        sensors.EXTERNAL_RESCAN += 1

    @staticmethod
    def _binding_for(row):
        return dict(
            provider=PROVIDER,
            sensor_id=row["id"],
            sensor_type=row["type"],
            name=row["name"],
            hardware_name=row["hardware_name"],
        )

    def _refresh_external_values(self):
        selected = {
            b["sensor_id"]
            for config in (self._saved, self._draft)
            for prefs in config["widgets"].values()
            for b in prefs.get("sensor_bindings", {}).values()
        }
        selected.update(
            b["sensor_id"]
            for config in (self._saved, self._draft)
            for item in config["top_bar"]["items"]
            for b in item["prefs"].get("sensor_bindings", {}).values()
        )
        self._data["external_sensors"] = {
            key: self._external_rows[key] for key in selected if key in self._external_rows
        }

    def expire_readings(self, now=None):
        """Invalidate one expired sample without discarding known sensor identities.

        Discovery and its bound subset share a freshness boundary. Keeping valid
        values in the discovery cache would allow an unrelated draft edit to
        repopulate the expired bound readings via _refresh_external_values().
        """
        data = self._data
        if not data or data.get("sample_status", {}).get("state") == "stale":
            return False
        now = time.time() if now is None else now
        if not numeric(now):
            return False
        timestamp = data.get("time")
        if numeric(timestamp) and 0 <= now - timestamp < 35:
            return False
        # Copy instead of mutating rows owned by the collector/transport cache.
        self._external_rows = {
            identifier: dict(channel, value=None, min=None, max=None, available=False)
            for identifier, channel in self._external_rows.items()
        }
        external_status = copy.deepcopy(data.get("external_status", {}))
        previous_state, previous_detail = (
            external_status.get("state"),
            external_status.get("detail"),
        )
        if previous_state not in ("ready", "empty") and (previous_state or previous_detail):
            external_status["last_state"] = str(previous_state or "unknown")[:64]
            external_status["last_detail"] = str(previous_detail or "")[:700]
        external_status.update(state="stale", detail="读数已过期", available_count=0)
        external_status.setdefault("sensor_count", len(self._external_rows))
        external_status.setdefault(
            "hardware_count", len({row.get("hardware_id") for row in self._external_rows.values()})
        )
        expired = dict(
            time=timestamp if numeric(timestamp) else 0,
            sample_status=dict(
                state="stale",
                detail="读数已过期",
                last_sample_time=timestamp if numeric(timestamp) else None,
                invalidated_at=now,
            ),
            external_status=external_status,
        )
        # Preserve observed errors and source labels for diagnosis, not readings.
        for field in (
            "provider_status",
            "cpu_power_state",
            "cpu_power_error",
            "cpu_temp_source",
            "cpu_power_source",
            "battery_status",
            "storage_status",
        ):
            if field in data:
                expired[field] = copy.deepcopy(data[field])
        for scope in ("gpus", "storages"):
            if scope in data:
                expired[scope] = {
                    identifier: {
                        key: copy.deepcopy(value)
                        for key, value in device.items()
                        if key
                        in (
                            "label",
                            "gpu_source",
                            "channel_status",
                            "channel_reasons",
                            "winerror",
                            "state",
                            "reason",
                            "api",
                            "status_code",
                            "status_text",
                        )
                    }
                    for identifier, device in data[scope].items()
                }
        self._data = expired
        self._refresh_external_values()
        self._history.clear()
        self._reading_notify_timer.stop()
        self._reading_notify_at = float("-inf")
        self._sensor_revision += 1
        # The first recovery sample must notify even at the same provider revision.
        self._sensor_notify_at = time.monotonic() - 1
        self.dataChanged.emit()
        self.sensorsChanged.emit()
        return True

    @Slot(dict)
    def receive(self, data):
        inventory = copy.deepcopy(self._devices)
        for scope in ("gpus", "networks", "disks", "volumes", "storages"):
            if scope in data:
                inventory[scope] = {
                    key: dict(label=value.get("label", key)) for key, value in data[scope].items()
                }
        if inventory != self._devices:
            self._devices = inventory
            self.devicesChanged.emit()
        # Keep the full discovery tree out of every 100 Hz QML paint/history
        # conversion. Only bound readings go to desktop cards; the virtualized
        # browser obtains the complete inventory at the independent sensor pace.
        catalog = data.get("external_catalog", data.get("external_sensors", {}))
        if catalog is not self._external_rows:
            self._external_rows = catalog
            self._discovered_ids = {
                "lhm:" + hashlib.sha256(key.encode("utf-8")).hexdigest(): key for key in catalog
            }
        self._data = {key: value for key, value in data.items() if key != "external_catalog"}
        self._refresh_external_values()
        self._history.append(self._data)
        self._workspace_sample_received(data)
        self._notify_reading()
        now = time.monotonic()
        revision = data.get("external_revision")
        if revision != self._external_revision or now - self._sensor_notify_at >= 0.5:
            self._external_revision = revision
            self._sensor_notify_at = now
            self._sensor_revision += 1
            self.sensorsChanged.emit()

    def sensor_rows(self, prefs=None, *, discovered=True):
        data = self._data
        rows = []
        for key in METRICS:
            if key in EXTERNAL_SLOTS and sensor_binding(key, prefs) is None:
                continue
            meta = metric_info(key, prefs)
            value, unit = formatted(data, key, prefs)
            source = reading_source(data, key, prefs)
            reason = ""
            if value == "—":
                reason = self.tr(unavailable_reason(data, key, prefs))
            rows.append(
                dict(
                    id=key,
                    label=self.metric_label(key, prefs),
                    value=value + (" " + unit if value != "—" else ""),
                    source=source,
                    available=value != "—",
                    category=meta["category"],
                    scope=meta["scope"],
                    unit=unit,
                    note=self.tr(meta["note"]),
                    reason=reason,
                    hardware_name=(sensor_binding(key, prefs) or {}).get("hardware_name", "")
                    or (
                        data.get("storages", {})
                        .get((prefs or {}).get("storage_target", "0"), {})
                        .get("label", "")
                        if meta.get("scope") == "storages"
                        else ""
                    ),
                    search=" ".join((key, meta["label"], self.tr(meta["label"]), unit)),
                )
            )
        bound = {b["sensor_id"] for b in (prefs or {}).get("sensor_bindings", {}).values()}
        for row_id, identifier in self._discovered_ids.items() if discovered else ():
            if identifier in bound:
                continue
            channel = self._external_rows[identifier]
            value, unit = inventory_display(identifier, channel, prefs)
            rows.append(
                dict(
                    id=row_id,
                    label=channel["name"],
                    hardware_name=channel["hardware_name"],
                    sensor_type=channel["type"],
                    provider=PROVIDER,
                    unit=unit,
                    value=value + (" " + unit if value != "—" and unit else ""),
                    source=PROVIDER,
                    available=value != "—",
                    category="advanced",
                    scope=None,
                    note=channel["hardware_name"],
                    reason=""
                    if value != "—"
                    else self.tr("读数已过期")
                    if data.get("sample_status", {}).get("state") == "stale"
                    else "已识别传感器，但采集库本轮返回空值；尚不能确定硬件原因。",
                    search=" ".join(
                        (
                            channel["name"],
                            channel["hardware_name"],
                            channel["hardware_type"],
                            channel["type"],
                            unit,
                            PROVIDER,
                        )
                    ),
                )
            )
        return rows

    sensorRows = Property("QVariantList", lambda self: self.sensor_rows(), notify=sensorsChanged)
    sourceDiagnostics = Property(
        "QVariantList",
        lambda self: [dict(row, detail=self.tr(row["detail"])) for row in source_rows(self._data)],
        notify=sensorsChanged,
    )

    def start(self):
        def collect():
            sampler = None
            export_retry_at = float("-inf")
            export_failed = False
            try:
                sampler = sensors.Sampler()
                sampler.config_provider = lambda: self._saved
                while not self.stop.is_set():
                    try:
                        data = sampler.sample()
                        self.sampleReady.emit(data)
                        self._record_history(data)
                    except Exception:
                        logging.exception("Sensor sampling failed")
                    else:
                        # Diagnostic files are optional. A locked/full profile
                        # must not discard healthy readings or their history.
                        if time.monotonic() >= export_retry_at:
                            try:
                                sampler.write(data)
                            except Exception:
                                if not export_failed:
                                    logging.exception("Sensor diagnostic export failed; will retry")
                                export_failed = True
                                export_retry_at = time.monotonic() + 1.0
                            else:
                                if export_failed:
                                    logging.info("Sensor diagnostic export recovered")
                                export_failed = False
                    self.stop.wait(self._saved["refresh"])
            finally:
                if sampler:
                    sampler.close()
                self.close_history_backend()

        self.thread = threading.Thread(target=collect, name="hardware-readings", daemon=True)
        self.thread.start()

    def close(self):
        self._reading_notify_timer.stop()
        self._diagnostic_timer.stop()
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=4)
        if not self.thread or not self.thread.is_alive():
            self.close_workspace_tools()
