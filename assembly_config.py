"""Small assembly-view preferences; no probing or graphics imports."""
import re

DEFAULT_ASSEMBLY = dict(case_model="", exploded=False, fan_animation=False)


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
    for field in ("exploded", "fan_animation"):
        if field in value:
            if type(value[field]) is not bool:
                raise ValueError("整机视图开关设置不正确")
            result[field] = value[field]
    return result
