"""Project temporary desktop appearance without applying other draft settings."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

_GLOBAL_FIELDS = ("skin", "theme", "opacity", "glass_transparency", "glass_curvature")
_WIDGET_FIELDS = ("skin", "glass_transparency", "glass_curvature")


def project_appearance(
    saved: Mapping[str, Any], draft: Mapping[str, Any], active: bool
) -> dict[str, Any]:
    """Copy validated settings, overlaying only appearance while preview is active.

    Missing draft fields retain their saved values. Explicit ``None`` values
    stay ``None`` so widget appearance can continue to inherit global settings.
    Saved widget membership and all non-appearance settings remain unchanged.
    """
    result = deepcopy(dict(saved))
    if not active:
        return result
    for field in _GLOBAL_FIELDS:
        if field in draft:
            result[field] = deepcopy(draft[field])
    draft_widgets = draft.get("widgets", {})
    for identifier, prefs in result.get("widgets", {}).items():
        if identifier not in draft_widgets:
            continue
        candidate = draft_widgets[identifier]
        for field in _WIDGET_FIELDS:
            if field in candidate:
                prefs[field] = deepcopy(candidate[field])
    return result
