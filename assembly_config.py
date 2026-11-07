"""Small assembly-view preferences; no probing or graphics imports."""
import re
from top_bar_config import HARDWARE_ICON_STYLES

DEFAULT_ASSEMBLY = dict(case_model="", exploded=False, fan_animation=False, appearance_style="follow",
                        detail_level="balanced",selection_effects=True,window_mode="inspect",desktop_frame=True,
                        board_model="",cooler_model="",cooler_mount="top",case_fans=[],
                        psu_model="",storage=[],expansion_cards=[],cables_enabled=False,
                        cable_color="black",fan_motion="measured",gpu_waterblock=False,part_styles={},
                        cpu_model="",gpu_model="",memory_models=[])
PART_FIELDS = ("board_model","cooler_model","cooler_mount","case_fans","psu_model","storage",
               "expansion_cards","cables_enabled","cable_color","fan_motion","gpu_waterblock","part_styles",
               "cpu_model","gpu_model","memory_models")
FAN_MOUNTS = ("front","top","rear","bottom","side")
CABLE_COLORS = {"black":"#252d35","white":"#dddfe3","red":"#a63f4b","blue":"#3c6d9b"}
DETAIL_LEVELS = ("eco","balanced","close")
WINDOW_MODES = ("inspect","desktop")
DETAIL_LABELS = {"eco":"简洁","balanced":"精细","close":"近看细节"}
STYLE_LABELS = {
    "miniature":"1 · 原版", "cartoon":"2 · 可爱笑脸", "notebook_color":"3 · 彩色手绘",
    "notebook_line":"4 · 纯线条", "sticker":"5 · 奶油贴纸", "papercut":"6 · 拼色剪纸",
    "inkwash":"7 · 蓝墨手账", "classic":"经典通用", "outline":"结构线稿", "solid":"精简实物",
    "soft":"柔和双色", "sketch":"手绘线稿", "notebook_smile":"笑脸手绘",
}


def style_choices(translate=lambda text:text):
    """Share the bar's complete style directory without changing its settings."""
    return [dict(id="follow",label=translate("跟随顶部栏")), *[
        dict(id=identity,label=translate(STYLE_LABELS[identity])) for identity in HARDWARE_ICON_STYLES]]


def visual_style(config):
    """Resolve an assembly-only override or the existing bar choice, with no I/O."""
    assembly=config.get("assembly")
    selected=assembly.get("appearance_style","follow") if isinstance(assembly,dict) else "follow"
    if selected=="follow":
        bar=config.get("top_bar")
        selected=bar.get("hardware_icon_style") if isinstance(bar,dict) else None
    return selected if type(selected) is str and selected in HARDWARE_ICON_STYLES else "miniature"


def detail_choices(translate=lambda text:text):
    return [dict(id=level,label=translate(DETAIL_LABELS[level])) for level in DETAIL_LEVELS]


def target_screen(screens,bar,primary,native_identity):
    """Honor stored Windows monitor IDs; QScreen names can be friendly labels."""
    if bar.get('monitor_mode')!='selected':return primary
    names=bar.get('screens') or ()
    identified={}
    for screen in screens:
        try:key=native_identity(screen).casefold()
        except Exception:continue
        identified[key]=None if key in identified else screen
    return next((identified[name.casefold()] for name in names
                 if isinstance(name,str) and identified.get(name.casefold()) is not None),None)
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_PART_TARGET = re.compile(r"^(case|gpu|cpu|memory|board|cooler|fans|psu|storage|expansion|cables)(?::[a-z0-9][a-z0-9-]{0,63}){0,3}$")


def validate_assembly(value=None):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("整机视图设置格式不正确")
    import copy
    result = copy.deepcopy(DEFAULT_ASSEMBLY)
    selected = value.get("case_model", "")
    if not isinstance(selected, str) or (selected and not _ID.fullmatch(selected)):
        raise ValueError("机箱型号设置不正确")
    result["case_model"] = selected
    style=value.get("appearance_style","follow")
    if type(style) is not str or style not in ("follow", *HARDWARE_ICON_STYLES):
        raise ValueError("整机外观设置不正确")
    result["appearance_style"]=style
    detail=value.get('detail_level','balanced')
    if type(detail) is not str or detail not in DETAIL_LEVELS:
        raise ValueError("模型细节设置不正确")
    result['detail_level']=detail
    mode=value.get('window_mode','inspect')
    if type(mode) is not str or mode not in WINDOW_MODES:
        raise ValueError("整机显示方式设置不正确")
    result['window_mode']=mode
    for field in ("exploded", "fan_animation", "selection_effects", "cables_enabled", "gpu_waterblock", "desktop_frame"):
        if field in value:
            if type(value[field]) is not bool:
                raise ValueError("整机视图开关设置不正确")
            result[field] = value[field]
    for field in ("board_model","cooler_model","psu_model","cpu_model","gpu_model"):
        selected=value.get(field,"")
        if type(selected) is not str or selected and not _ID.fullmatch(selected):
            raise ValueError("配件型号设置不正确")
        result[field]=selected
    for field,allowed in (("cooler_mount",FAN_MOUNTS),("fan_motion",("measured","demo")),
                          ("cable_color",CABLE_COLORS)):
        selected=value.get(field,DEFAULT_ASSEMBLY[field])
        if type(selected) is not str or selected not in allowed:raise ValueError("配件安装设置不正确")
        result[field]=selected
    for field,maximum in (("case_fans",5),("storage",8),("expansion_cards",3)):
        rows=value.get(field,[])
        if type(rows) is not list or len(rows)>maximum:raise ValueError("配件列表设置不正确")
        clean=[];seen=set()
        for row in rows:
            if type(row) is not dict:raise ValueError("配件列表设置不正确")
            key="model" if field=="case_fans" else "model_id"
            model=row.get(key)
            if type(model) is not str or not _ID.fullmatch(model):raise ValueError("配件型号设置不正确")
            entry={key:model}
            if field in ("case_fans","storage"):
                count=row.get("count",1)
                if type(count) is not int or not 1<=count<=4:raise ValueError("配件数量设置不正确")
                entry['count']=count
            if field=="case_fans":
                mount=row.get('mount');direction=row.get('direction','intake')
                if type(mount) is not str or mount not in FAN_MOUNTS or mount in seen:
                    raise ValueError("配件安装设置不正确")
                if direction not in ('intake','exhaust'):raise ValueError("配件安装设置不正确")
                seen.add(mount);entry.update(mount=mount,direction=direction)
            else:
                if model in seen:raise ValueError("配件列表设置不正确")
                seen.add(model)
            clean.append(entry)
        result[field]=clean
    styles=value.get('part_styles',{})
    if type(styles) is not dict or len(styles)>128:raise ValueError('部件外观设置不正确')
    for target,style in styles.items():
        if type(target) is not str or not _PART_TARGET.fullmatch(target) or type(style) is not str or style not in HARDWARE_ICON_STYLES:
            raise ValueError('部件外观设置不正确')
    result['part_styles']=dict(styles)
    models=value.get('memory_models',[])
    if type(models) is not list or len(models)>8 or any(type(model) is not str or not _ID.fullmatch(model) for model in models):
        raise ValueError('配件列表设置不正确')
    result['memory_models']=list(models)
    return result
