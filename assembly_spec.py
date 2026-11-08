"""Assemble a detached illustration from cached identities, never from live probes."""
import copy
import math

from assembly_config import STYLE_LABELS,validate_assembly,visual_style
from assembly_parts import selected_parts
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
    from hardware_packs import library_generation
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
            repr(firmware), repr(config.get("assembly", {})),visual_style(config),library_generation())


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
    rejected=[]
    if options['gpu_model']:
        from hardware_appearance import CATALOG
        row=next((row for row in CATALOG if row[0]==options['gpu_model'] and row[1]=='gpu'),None)
        if row:
            appearance=appearance_for('gpu',row[-1][0]);appearance['selection_source']='reference'
        else:rejected.append(options['gpu_model'])
    devices = data.get("gpus")
    device = devices.get(target, {}) if isinstance(devices, dict) else data if target == "0" else {}
    device = device if isinstance(device, dict) else {}
    dimensions = appearance.get("board_details", {}).get("dimensions_mm") or {}
    gpu = dict(appearance=appearance, present=bool(appearance.get('selection_source')=='reference' or text(device.get("gpu_name") or device.get("label"))),
               target=target,
               label=(appearance.get("label") if appearance.get("confidence")=="model"
                      or appearance.get("selection_source")=="manual"
                      else text(device.get("gpu_name") or device.get("label"))) or "显卡未识别",
               selection_source=appearance.get("selection_source", "automatic"),
               length_mm=number(dimensions.get("length")), width_mm=number(dimensions.get("height")),
               thickness_mm=number(dimensions.get("thickness")), dimensions_verified=bool(dimensions),
               telemetry_bound=appearance.get('selection_source')!='reference',detected_label=text(device.get('gpu_name') or device.get('label')))
    cpu_appearance = appearance_for("cpu", data.get("cpu_name"))
    if options['cpu_model']:
        from hardware_appearance import catalog_rows
        row=next((row for row in catalog_rows() if row[0]==options['cpu_model'] and row[1]=='cpu'),None)
        if row:
            cpu_appearance=appearance_for('cpu',row[-1][0]);cpu_appearance['selection_source']='reference'
        else:rejected.append(options['cpu_model'])
    cpu = dict(appearance=cpu_appearance, style=cpu_appearance.get("style", "chip"),
               label=cpu_appearance['label'] if cpu_appearance.get('selection_source')=='reference' else text(data.get("cpu_name")) or "处理器未识别",
               telemetry_bound=cpu_appearance.get('selection_source')!='reference',detected_label=text(data.get('cpu_name')))
    populated = [r for r in modules if isinstance(r, dict)]
    reference_memory=False
    if options['memory_models']:
        from memory_appearance import CATALOG as MEMORY
        lookup={row['id']:row for row in MEMORY}
        if all(model in lookup for model in options['memory_models']):
            populated=[dict(part_number=lookup[model]['aliases'][0],manufacturer=lookup[model]['brand']) for model in options['memory_models']]
            reference_memory=True
        else:rejected.extend(model for model in options['memory_models'] if model not in lookup)
    memory = dict(count=len(populated), rendered_count=min(8,len(populated)),
                  label="内存型号未识别", style="memory_neutral", modules=[],telemetry_bound=not reference_memory)
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
    from motherboard_catalog import identify as identify_board
    board_identity=identify_board(board_maker,board_name,manual_id=options['board_model'])
    profile=board_identity.get('model')
    board.update(manufacturer=board_maker,detected_label=board_name,
                 selection_source=board_identity['state'])
    if profile:
        for field in ('detail_profile','slot_counts','rear_ports','source','count_source','finish_source'):
            board.pop(field,None)
        board.update(model_id=profile['id'],model_profile=profile,label=profile['label'],
            form_factor={'matx':'micro_atx','itx':'mini_itx','eatx':'e_atx'}.get(profile.get('form_factor'),profile.get('form_factor','unknown')),
            dimensions_mm=profile['dimensions_mm'],
            slot_counts=dict(dimm=len(profile.get('dimm_uv',())),m2=len(profile.get('m2',())),
                pcie_x16=sum(row.get('kind')=='x16' for row in profile.get('pcie',())),
                pcie_x1=sum(row.get('kind')=='x1' for row in profile.get('pcie',())),
                sata=sum(row.get('count',1) for row in profile.get('connectors',()) if row.get('kind')=='sata')),
            source=next(iter(profile.get('sources',())),''))
        for field in ('pcb_color','heatsink_color','slot_counts','rear_ports','detail_profile'):
            if field in profile:board[field]=copy.deepcopy(profile[field])
    parts=selected_parts(options)
    checks = [dict(kind='reference_model',state='unsupported',model_id=model) for model in rejected]
    # Exact catalog facts only; a generic CPU drawing cannot identify a socket.
    cpu_socket=(cpu_appearance.get('cpu_package') or {}).get('socket')
    if profile:
        board_socket=profile.get('socket')
        if cpu_socket and board_socket:
            checks.append(dict(kind='cpu_socket',state='within_limit' if cpu_socket.casefold()==board_socket.casefold() else 'unsupported',
                               component=cpu_socket,reference=board_socket))
        generations={row['appearance'].get('board_details',{}).get('generation') for row in memory['modules']}
        generations.discard(None);generations.discard('unknown')
        board_memory=profile.get('memory_type','').casefold()
        if generations and board_memory:
            checks.append(dict(kind='memory_type',state='within_limit' if all(value.casefold()==board_memory for value in generations) else 'unsupported',
                               component=sorted(generations),reference=board_memory))
        if memory['count']>len(profile.get('dimm_uv',())):
            checks.append(dict(kind='memory_slots',state='unsupported',component=memory['count'],reference=len(profile.get('dimm_uv',()))))
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
    from hardware_packs import library_generation
    return dict(case=case, case_identity=identity, gpu=gpu, cpu=cpu, memory=memory, board=board,model_library_generation=library_generation(),
                **parts,
                options=options, checks=checks, schematic=True,visual_style=visual_style(config),
                detail_level=options['detail_level'],inspection_cutaway=options['inspection_cutaway'],show_psu=options['show_psu'],
                part_styles=copy.deepcopy(options['part_styles']),lighting_preview=options['lighting_preview'],
                limitations=["比例与安装位置为三维示意，不能代替实物安装检查。",
                             "自选配件模型不代表已识别的本机硬件。"])


def fan_state(data, config):
    return gpu_fan_feedback(data, gpu_preferences(config))


def summary(spec):
    case = spec["case"]
    return dict(initialized=True, case_id=case.get("id", ""), case_label=case["label"],
                identity_state=spec["case_identity"].get("state", "unidentified"),
                cpu_label=spec["cpu"]["label"], gpu_label=spec["gpu"]["label"],
                gpu_source=spec["gpu"]["selection_source"], memory_label=spec["memory"]["label"],
                memory_count=spec["memory"]["count"], board_label=spec["board"]["label"],
                board_source=spec['board'].get('selection_source','unidentified'),
                visual_style=spec.get("visual_style","miniature"),
                visual_style_label=STYLE_LABELS.get(spec.get("visual_style","miniature"),STYLE_LABELS["miniature"]),
                checks=spec["checks"], limitations=spec["limitations"],
                case_sources=case.get("sources", []),fan_mounts=copy.deepcopy(case.get('fan_mounts') or []))
