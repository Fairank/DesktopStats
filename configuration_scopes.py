"""Pure configuration regions; no Qt, persistence, or hardware access."""
import copy

DESKTOP_FIELDS = frozenset({
    "widgets", "widget_order", "skin", "opacity", "glass_transparency", "glass_curvature",
    "mode", "layout", "size", "group_columns", "visible", "locked", "magnet_enabled",
    "magnet_gap", "magnet_bounce", "reflow_on_resize",
})
PREFERENCE_FIELDS = frozenset({"language", "theme", "autostart", "refresh"})
SCOPE_FIELDS = {
    "desktop": DESKTOP_FIELDS,
    "preferences": PREFERENCE_FIELDS,
    "topbar": frozenset({"top_bar"}),
}


def merge_scope(base, source, scope):
    """Project one stable region, leaving all other branches independent."""
    fields = SCOPE_FIELDS[scope]
    result = copy.deepcopy(base)
    for field in fields:
        result[field] = copy.deepcopy(source[field])
    return result


def scope_dirty(saved, draft, scope):
    return any(saved[field] != draft[field] for field in SCOPE_FIELDS[scope])


def rebase_saved_changes(snapshot, before, after):
    """Keep later saved quick actions when cancelling an explicit global preview.

    Lists/scalars are atomic. Dictionary leaves are projected independently, so
    a saved skin change never erases an older pending title on the same widget.
    """
    if before == after:
        return copy.deepcopy(snapshot)
    if isinstance(before, dict) and isinstance(after, dict) and isinstance(snapshot, dict):
        result = copy.deepcopy(snapshot)
        for key in before.keys() | after.keys():
            if key not in after:
                result.pop(key, None)
            elif key not in before or key not in result:
                result[key] = copy.deepcopy(after[key])
            else:
                result[key] = rebase_saved_changes(result[key], before[key], after[key])
        return result
    return copy.deepcopy(after)
