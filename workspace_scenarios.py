"""Local, reversible workspace scenes. Never change language, startup or sampling."""
import copy
import json
import re
import tempfile
import threading
import unicodedata
import uuid
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from configuration_scopes import DESKTOP_FIELDS
from metrics import METRICS
from stats_config import validate
from top_bar_layout import metric_icon
from widget_catalog import MODULES, TEMPLATES, from_template

FIELDS = DESKTOP_FIELDS | {"top_bar"}
MAX_CUSTOM = 8
BUILTINS = (
    dict(id="office", label="日常办公", description="轻巧的状态栏，让注意力留给工作。",
         icon="grid", accent="#3678c9", summary="1 个桌面条 · CPU · 内存 · 网络 · 电池", kind="bar",
         metrics=["cpu_usage", "ram_percent", "net_download", "battery_percent"]),
    dict(id="performance", label="性能观察", description="温度、负载与功率，放在一起看。",
         icon="cpu", accent="#ae7750", summary="2 个小组件 · CPU · GPU · 温度 · 功率", kind="cards",
         metrics=["cpu_temp", "gpu_temp", "cpu_power", "gpu_power"]),
    dict(id="endurance", label="电池续航", description="保留必要读数，不主动唤醒独显。",
         icon="battery", accent="#3e8770", summary="1 个桌面条 · 电池 · 内存", kind="compact",
         metrics=["battery_percent", "battery_discharge_watts", "ram_percent"]),
)


def workspace(config):
    clean = validate(config)
    return {field: copy.deepcopy(clean[field]) for field in sorted(FIELDS)}


def project(base, snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != FIELDS:
        raise ValueError("场景内容不完整")
    return validate(dict(copy.deepcopy(base), **copy.deepcopy(snapshot)))


def builtin(identifier, base):
    spec = next((row for row in BUILTINS if row["id"] == identifier), None)
    if spec is None:
        raise ValueError("场景不存在")
    value = copy.deepcopy(base)
    # Display selection and material choices belong to the user. Scenes replace
    # content/layout only, not their preferred monitor or glass appearance.
    value.update(mode="separate", visible=True, widget_order=[], widgets={})
    if identifier == "performance":
        for key, template in (("w_scene_cpu", "cpu"), ("w_scene_gpu", "gpu")):
            prefs = from_template(template)
            prefs.update(form="free", width=250, height=146, show_title=True,
                         content=["cpu_temp", "cpu_usage", "cpu_power"] if template == "cpu"
                         else ["gpu_temp", "gpu_usage", "gpu_power"])
            value["widgets"][key] = prefs
            value["widget_order"].append(key)
    else:
        prefs = from_template("status_bar")
        prefs.update(content=list(spec["metrics"]), width=680 if identifier == "office" else 460,
                     height=40, show_title=False)
        value["widgets"]["w_scene_status"] = prefs
        value["widget_order"] = ["w_scene_status"]
    # Keep the user's enable/monitor/appearance choices. A disabled menu bar
    # stays disabled; when enabled it adopts the same selected scene's content.
    value["top_bar"]["items"] = [
        dict(id="b_scene_" + metric, metric=metric,
             prefs=dict(style="duplex_inline" if metric == "net_download" else "icon_value",
                        placement="right", sensor_bindings={}))
        for metric in spec["metrics"]
    ]
    return validate(value)


def preview(snapshot):
    metrics, tiles = [], []
    for key in snapshot["widget_order"]:
        prefs = snapshot["widgets"][key]
        if not prefs.get("enabled", True):
            continue
        content = prefs.get("content") or TEMPLATES.get(prefs.get("template"), {}).get("content", [])
        entries = [dict(label=METRICS[metric]["label"], icon=metric_icon(metric))
                   for metric in content if metric in METRICS]
        label = prefs.get("title") or TEMPLATES.get(prefs.get("template"), {}).get("label")
        label = label or MODULES.get(prefs.get("kind"), {}).get("label", "小组件")
        category = TEMPLATES.get(prefs.get("template"), {}).get("category", prefs.get("kind"))
        icon = {"cooling": "fan", "hwinfo": "power", "custom": "grid"}.get(category, category)
        tiles.append(dict(label=label, icon=icon or "grid", metrics=entries[:6],
                          form=prefs.get("form", "square")))
        for metric in content:
            if metric not in metrics and metric in METRICS:
                metrics.append(metric)
    return dict(kind="bar" if len(tiles) == 1 and tiles[0]["form"] == "bar" else "cards",
                metrics=[dict(label=METRICS[key]["label"], icon=metric_icon(key)) for key in metrics[:6]],
                tiles=tiles, widget_count=len(tiles))


def _locked(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


class SceneRecoveryError(ValueError):
    """A failed preference commit could not restore the scene recovery point."""


class SceneStore:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _read(self, base):
        try:
            if self.path.stat().st_size > 1024 * 1024:
                raise ValueError("场景文件过大")
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        if (not isinstance(data, dict) or data.get("version") != 1
                or not isinstance(data.get("scenes"), list) or len(data["scenes"]) > MAX_CUSTOM + 1):
            raise ValueError("场景文件格式不正确")
        seen = set()
        for row in data["scenes"]:
            if (not isinstance(row, dict) or set(row) != {"id", "label", "workspace"}
                    or not isinstance(row["id"], str)
                    or not re.fullmatch(r"previous|s_[0-9a-f]{12}", row["id"])
                    or row["id"] in seen):
                raise ValueError("场景标识不正确")
            self._name(row["label"])
            project(base, row["workspace"])
            seen.add(row["id"])
        if sum(row["id"] != "previous" for row in data["scenes"]) > MAX_CUSTOM:
            raise ValueError("最多保存 8 个自定义场景")
        return data["scenes"]

    @staticmethod
    def _name(name):
        if (not isinstance(name, str) or not name.strip() or len(name.strip()) > 20
                or any(unicodedata.category(ch).startswith("C") for ch in name)):
            raise ValueError("场景名称需为 1–20 个字")
        return name.strip()

    def _write(self, rows):
        raw = json.dumps(dict(version=1, scenes=rows), ensure_ascii=False, indent=2)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".scene-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @_locked
    def rows(self, base):
        rows = [dict(row, preview=preview(workspace(builtin(row["id"], base))))
                for row in BUILTINS]
        for row in self._read(base):
            rows.append(dict(id=row["id"], label=row["label"], icon="undo" if row["id"] == "previous" else "grid",
                             accent="#78718e", description="恢复最近一次场景切换前的已保存布局。"
                             if row["id"] == "previous" else "你保存的桌面组件与顶部栏组合。",
                             summary="桌面组件 · 顶部栏", preview=preview(row["workspace"]), custom=True))
        return rows

    @_locked
    def prepare(self, identifier, base):
        if any(row["id"] == identifier for row in BUILTINS):
            return builtin(identifier, base)
        row = next((row for row in self._read(base) if row["id"] == identifier), None)
        if row is None:
            raise ValueError("场景不存在")
        return project(base, row["workspace"])

    @_locked
    def remember_previous(self, config):
        rows = [row for row in self._read(config) if row["id"] != "previous"]
        rows.insert(0, dict(id="previous", label="上次布局", workspace=workspace(config)))
        self._write(rows)

    @contextmanager
    def previous_transaction(self, config):
        """Retain an exact recovery copy until the preference save succeeds.

        Scene and preference files cannot form one filesystem transaction. The
        scene replacement itself is atomic; if preference persistence fails,
        restore the exact old scene bytes. If that restoration also fails, leave
        a local recovery copy and report the incomplete rollback explicitly.
        """
        with self._lock:
            self._read(config)  # Validate before staging or replacing anything.
            try:
                original = self.path.read_bytes()
            except FileNotFoundError:
                original = None
            self.path.parent.mkdir(parents=True, exist_ok=True)
            recovery = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=".scene-recovery-",
                                                 suffix=".json", delete=False) as stream:
                    recovery = Path(stream.name)
                    stream.write(original if original is not None else b'{"version":1,"scenes":[]}')
            except OSError:
                if recovery is not None:
                    recovery.unlink(missing_ok=True)
                raise
            retain_recovery = False
            try:
                self.remember_previous(config)
                yield
            except BaseException as error:
                try:
                    if original is None:
                        self.path.unlink(missing_ok=True)
                    else:
                        try:
                            current = self.path.read_bytes()
                        except FileNotFoundError:
                            current = None
                        if current != original:
                            recovery.replace(self.path)
                except OSError:
                    retain_recovery = True
                    raise SceneRecoveryError("未能应用场景，旧场景恢复未完成；本地恢复副本已保留。") from error
                raise
            finally:
                if not retain_recovery:
                    try:
                        recovery.unlink(missing_ok=True)
                    except OSError:
                        pass  # A leftover private recovery copy is harmless.

    @_locked
    def save(self, name, config):
        label = self._name(name)
        rows = self._read(config)
        if sum(row["id"] != "previous" for row in rows) >= MAX_CUSTOM:
            raise ValueError("最多保存 8 个自定义场景")
        identifier = "s_" + uuid.uuid4().hex[:12]
        rows.append(dict(id=identifier, label=label, workspace=workspace(config)))
        self._write(rows)
        return identifier

    @_locked
    def remove(self, identifier, base):
        if not re.fullmatch(r"s_[0-9a-f]{12}", identifier or ""):
            raise ValueError("只能移除自定义场景")
        rows = self._read(base)
        remaining = [row for row in rows if row["id"] != identifier]
        if len(rows) == len(remaining):
            raise ValueError("场景不存在")
        self._write(remaining)
