"""Small assembly-view preferences; no probing or graphics imports."""
import re
from top_bar_config import HARDWARE_ICON_STYLES

DEFAULT_ASSEMBLY = dict(case_model="", exploded=False, fan_animation=False, appearance_style="follow",
                        detail_level="balanced",selection_effects=True)
DETAIL_LEVELS = ("eco","balanced","close")
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


def validate_assembly(value=None):
    if value is None:
        return dict(DEFAULT_ASSEMBLY)
    if not isinstance(value, dict):
        raise ValueError("整机视图设置格式不正确")
    result = dict(DEFAULT_ASSEMBLY)
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
    for field in ("exploded", "fan_animation", "selection_effects"):
        if field in value:
            if type(value[field]) is not bool:
                raise ValueError("整机视图开关设置不正确")
            result[field] = value[field]
    return result
