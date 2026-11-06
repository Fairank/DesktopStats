"""Assemble a detached illustration from cached identities, never from live probes."""
import copy
import math

from assembly_config import STYLE_LABELS,validate_assembly,visual_style
from hardware_appearance import metric_appearance, appearance_for
from memory_appearance import appearance_for_memory
from metrics import metric_info
from top_bar_feedback import gpu_fan_feedback

BOARD_SOURCE = "https://rog.asus.com/motherboards/rog-strix/rog-strix-z790-a-gaming-wifi-d4-model/spec/"
REFERENCE_CASE = dict(id="", label="参考机箱（未识别）", brand="", layout="tower",
    dimensions_mm=dict(width=230, height=470, depth=460), dimensions_verified=False,
    panels=dict(left="glass", front="mesh"), form_factors=(), max_gpu_length_mm=None,
    sources=(), schematic=True)


def text(value, limit=160):
    return " ".join("".join(c for c in value[:limit] if c.isprintable()).split()) if isinstance(value, str) else ""


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value > 0 else None


def gpu_preferences(config):
    for item in config.get("top_bar", {}).get("items", ()):
        if isinstance(item, dict):
            prefs = item.get("prefs", {})
            if (isinstance(prefs, dict) and not prefs.get("sensor_bindings")
                    and metric_info(item.get("metric", ""),prefs).get("scope")=="gpus"):
                return prefs
    return {}


def component_fingerprint(data, config, firmware, modules):
    prefs = gpu_preferences(config)
    selected = str(prefs.get("gpu_target") or "0")
    gpus = data.get("gpus")
    gpu = gpus.get(selected, {}) if isinstance(gpus, dict) else data if selected == "0" else {}
    gpu = gpu if isinstance(gpu, dict) else {}
    return (str(data.get("cpu_name", "")), selected,
            tuple(str(gpu.get(k, "")) for k in ("gpu_name", "board_model", "board_vendor")),
            str(prefs.get("hardware_model", "")),
            tuple((r.get("manufacturer", ""), r.get("part_number", ""), r.get("form_factor", ""))
                  for r in modules if isinstance(r, dict)),
            repr(firmware), repr(config.get("assembly", {})),visual_style(config))


def build_spec(data, config, firmware, modules, *, identify_case=None):
    """All inputs are existing snapshots; neither Windows nor a sensor is queried."""
    if identify_case is None:
        from chassis_identity import identify as identify_case
    options = validate_assembly(config.get("assembly"))
    identity = identify_case(firmware, manual_id=options["case_model"])
    known_case = identity.get("model")
    case = copy.deepcopy(known_case if isinstance(known_case, dict) else REFERENCE_CASE)
    case["dimensions_verified"] = bool(known_case)
    case["selection_source"] = identity.get("state", "unidentified")
    prefs = gpu_preferences(config)
    target = str(prefs.get("gpu_target") or "0")
    appearance = metric_appearance(data, "gpu_usage", prefs, scope="gpus", target=target)
    devices = data.get("gpus")
    device = devices.get(target, {}) if isinstance(devices, dict) else data if target == "0" else {}
    device = device if isinstance(device, dict) else {}
    dimensions = appearance.get("board_details", {}).get("dimensions_mm") or {}
    gpu = dict(appearance=appearance, present=bool(text(device.get("gpu_name") or device.get("label"))),
               target=target,
               label=(appearance.get("label") if appearance.get("confidence")=="model"
                      or appearance.get("selection_source")=="manual"
                      else text(device.get("gpu_name") or device.get("label"))) or "显卡未识别",
               selection_source=appearance.get("selection_source", "automatic"),
               length_mm=number(dimensions.get("length")), width_mm=number(dimensions.get("height")),
               thickness_mm=number(dimensions.get("thickness")), dimensions_verified=bool(dimensions))
    cpu_appearance = appearance_for("cpu", data.get("cpu_name"))
    cpu = dict(appearance=cpu_appearance, style=cpu_appearance.get("style", "chip"),
               label=text(data.get("cpu_name")) or "处理器未识别")
    populated = [r for r in modules if isinstance(r, dict)]
    memory = dict(count=len(populated), rendered_count=min(8,len(populated)),
                  label="内存型号未识别", style="memory_neutral", modules=[])
    for row in populated[:8]:
        matched = appearance_for_memory(model=row.get("part_number", ""), manufacturer=row.get("manufacturer", ""))
        form = row.get("form_factor", "unknown")
        if matched["confidence"] != "model" and form in ("dimm", "sodimm"):
            matched["style"] = form
        memory["modules"].append(dict(appearance=matched, label=text(row.get("part_number")) or matched["label"]))
    if memory["modules"]:
        memory.update(appearance=memory["modules"][0]["appearance"],
                      label=memory["modules"][0]["label"], style=memory["modules"][0]["appearance"]["style"])
    boards = firmware.get("baseboards", ()) if isinstance(firmware, dict) else ()
    board_name = text(boards[0].get("product")) if len(boards) == 1 and isinstance(boards[0], dict) else ""
    board = dict(label=board_name or "主板布局示意", form_factor="unknown", schematic=True)
    board_maker = text(boards[0].get("manufacturer")).casefold() if len(boards) == 1 and isinstance(boards[0], dict) else ""
    if (board_name.casefold() == "rog strix z790-a gaming wifi d4"
            and board_maker in ("asus", "asustek computer inc.", "asustek computer inc")):
        board.update(form_factor="atx", dimensions_mm=dict(height=305, width=244), source=BOARD_SOURCE,
            detail_profile='asus_z790_a_d4',pcb_color='#242a2d',heatsink_color='#c5cbd0',
            slot_counts=dict(dimm=4,pcie_x16=3,pcie_x1=1,m2=4,sata=4),
            rear_ports=dict(usb_a=8,usb_c=2,displayport=1,hdmi=1,audio_3_5=5,spdif=1,lan=1,buttons=2),
            count_source=BOARD_SOURCE,finish_source=BOARD_SOURCE.replace('/spec/','/'))
    checks = []
    if (known_case and 'no_expansion_slots' in case.get('features',())
            and gpu['present'] and appearance.get('style')!='gpu_integrated'):
        checks.append(dict(kind='gpu_mount',state='unsupported',reason='no_slots'))
    elif (known_case and 'low_profile_only' in case.get('features',()) and gpu['present']
            and gpu['width_mm'] and gpu['width_mm']>80):
        checks.append(dict(kind='gpu_mount',state='unsupported',reason='low_profile'))
    max_length = number(case.get("max_gpu_length_mm"))
    if max_length and gpu["length_mm"]:
        checks.append(dict(kind="gpu_length", state="within_limit" if gpu["length_mm"] <= max_length else "exceeds_limit",
                           component_mm=gpu["length_mm"], limit_mm=max_length))
    else:
        checks.append(dict(kind="gpu_length", state="unknown"))
    forms = case.get("form_factors") or ()
    if known_case and board["form_factor"] != "unknown" and forms:
        checks.append(dict(kind="board_form", state="within_limit" if board["form_factor"] in forms else "exceeds_limit"))
    return dict(case=case, case_identity=identity, gpu=gpu, cpu=cpu, memory=memory, board=board,
                options=options, checks=checks, schematic=True,visual_style=visual_style(config),
                detail_level=options['detail_level'],
                limitations=["比例与安装位置为三维示意，不能代替实物安装检查。",
                             "散热器、电源和机箱风扇的实际型号尚未识别。"])


def fan_state(data, config):
    return gpu_fan_feedback(data, gpu_preferences(config))


def summary(spec):
    case = spec["case"]
    return dict(initialized=True, case_id=case.get("id", ""), case_label=case["label"],
                identity_state=spec["case_identity"].get("state", "unidentified"),
                cpu_label=spec["cpu"]["label"], gpu_label=spec["gpu"]["label"],
                gpu_source=spec["gpu"]["selection_source"], memory_label=spec["memory"]["label"],
                memory_count=spec["memory"]["count"], board_label=spec["board"]["label"],
                visual_style=spec.get("visual_style","miniature"),
                visual_style_label=STYLE_LABELS.get(spec.get("visual_style","miniature"),STYLE_LABELS["miniature"]),
                checks=spec["checks"], limitations=spec["limitations"],
                case_sources=case.get("sources", []))
