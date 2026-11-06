"""Offline review filters; product-line position is not a performance ranking.

Entry/mainstream/flagship describe the cooler/product line within a board maker,
not the speed of its GPU chip. Explicit historical records override these hints.
Generation labels group the reviewed representative's model number, not every
product sold under a long-lived series name. No I/O or discovery.
"""

import re

TIERS = {
    "entry": ("asus_dual", "asus_prime", "msi_ventus", "msi_shadow", "gigabyte_windforce",
              "gigabyte_eagle", "zotac_solo", "zotac_twin_edge", "sapphire_pulse",
              "powercolor_fighter", "powercolor_reaper", "asrock_challenger", "xfx_swft",
              "pny_verto", "gainward_ghost", "inno3d_x3", "inno3d_twin_x2", "maxsun_terminator"),
    "flagship": ("asus_rog_strix", "asus_astral", "msi_suprim", "msi_vanguard", "gigabyte_aorus",
                 "zotac_amp_infinity", "zotac_amp_airo", "sapphire_nitro", "powercolor_red_devil",
                 "asrock_taichi", "xfx_merc", "pny_xlr8", "evga_ftw3", "palit_gamerock",
                 "gainward_phantom", "galax_hof", "inno3d_ichill_x3", "inno3d_ichill_x4",
                 "colorful_vulcan", "maxsun_icraft", "yeston_atlantis"),
    "creator": ("asus_proart", "msi_expert", "gigabyte_aero"),
    "reference": ("nvidia_founders", "amd_reference", "intel_limited"),
}
_TIERS = {identifier: tier for tier, identifiers in TIERS.items() for identifier in identifiers}


def generation(label):
    """Only classify explicit model-number families; leave the rest unspecified."""
    if not isinstance(label, str):
        return "unspecified"
    text = label[:256].casefold()
    patterns = ((r"\brtx\s*([2-5])\d{3}(?!\d)", "rtx{}0"),
                (r"\bgtx?\s*10\d{2}(?!\d)", "gtx10"),
                (r"\bgtx\s*16\d{2}(?!\d)", "gtx16"),
                (r"\bgtx\s*([2-9])\d{2}(?!\d)", "gtx{}00"),
                (r"\brx\s*([5-9])\d{3}(?!\d)", "rx{}000"),
                (r"\brx\s*([4-5])\d{2}(?!\d)", "rx{}00"),
                (r"\barc\s*([ab])\d{3}\b", "arc_{}"))
    for pattern, template in patterns:
        found = re.search(pattern, text)
        if found:
            return template.format(found.group(1)) if found.lastindex else template
    for pattern, era in ((r"\b(?:geforce\s*(?:fx\s*)?\d{4})", "pre_gtx"),
                         (r"\bhd\s*\d{4}", "radeon_hd"), (r"\br9\s*\d{3}(?!\d)|\bfury\b", "r9"),
                         (r"\bvega\s*\d{2}\b", "vega")):
        if re.search(pattern, text):
            return era
    return "unspecified"


def fields(series, model_label=""):
    """Detached metadata for a reviewed representative, without new matching."""
    if not series:
        return dict(era="unspecified", tier="unspecified")
    era = series.get("era") or generation(model_label)
    era = {"rdna1": "rx5000", "rdna2": "rx6000", "rdna3": "rx7000", "rdna4": "rx9000"}.get(era, era)
    return dict(era=era,
                tier=series.get("tier") or _TIERS.get(series.get("id"),
                     "unspecified" if series.get("product_line") else "mainstream"))
