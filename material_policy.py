"""One material decision shared by the desktop, previews and diagnostics."""

from skin_styles import GLASS_SKINS, effective_skin, glass_options


def render_policy(config, spec):
    skins = {effective_skin(config, cell["key"]) for cell in spec.get("cells", [])}
    grouped = spec.get("id") == "group"
    options = [glass_options(config, cell["key"]) for cell in spec.get("cells", [])]
    uniform = grouped and len(skins) == 1 and (
        not skins & GLASS_SKINS or all(option == options[0] for option in options)
    )
    mixed_minimal = "minimal" in skins and bool(skins & GLASS_SKINS)
    return {
        "panel_skin": next(iter(skins)) if uniform else None,
        "panel_options": options[0] if uniform and options else {},
        "card_surfaces": bool(skins) and not uniform,
        # A single HWND cannot apply system Acrylic to only part of its content.
        # Preserve truly unpainted minimal digits, and expose the glass fallback.
        "backdrop": bool(skins & GLASS_SKINS) and not mixed_minimal,
        # Ordinary alpha coatings can coexist with unpainted minimal digits.
        # This permission does not request or certify a system blur backdrop.
        "translucent": bool(skins & GLASS_SKINS),
        "fallback_reason": "mixed-minimal" if mixed_minimal else "",
    }
