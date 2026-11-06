"""Offline, bounded identity matching for simplified memory-module drawings.

Only complete reviewed part numbers establish a model. Kit and single-module
part numbers are separate: no suffix is removed or decoded. Series matching
requires an independently established memory-module brand. The drawings do not
report DDR generation, capacity, rank, chip count or current lighting state.
No hardware, registry, profile, filesystem, driver, network or thread is read.
"""

import re
from functools import lru_cache

BRANDS = {
    "corsair": ("CORSAIR", "#ae975b"),
    "gskill": ("G.SKILL", "#b06470"),
    "kingston": ("Kingston", "#a36a70"),
    "crucial": ("Crucial", "#608eaf"),
    "teamgroup": ("TEAMGROUP T-FORCE", "#af7279"),
    "adata": ("ADATA XPG", "#b57678"),
    "unknown": ("", "#83909e"),
}


def _series(identity, brand, label, aliases, form, presentation, features, url, excludes=()):
    return dict(id=identity, brand=brand, label=label, aliases=aliases, features=features,
                source_url=url, form_factor=form, presentation=presentation, excludes=excludes)


SERIES_CATALOG = (
    _series("corsair_vengeance_lpx", "corsair", "CORSAIR VENGEANCE LPX", ("vengeance lpx",),
            "dimm", "low", ("矮式散热片", "直立散热鳍片"),
            "https://www.corsair.com/uk/en/p/memory/cmk16gx4m2b3200c16/vengeancea-lpx-16gb-2-x-8gb-ddr4-dram-3200mhz-c16-memory-kit-black-cmk16gx4m2b3200c16"),
    _series("corsair_vengeance_rgb", "corsair", "CORSAIR VENGEANCE RGB DDR5", ("vengeance rgb ddr5",),
            "dimm", "rgb", ("全长扩散罩", "简洁分区外壳"),
            "https://www.corsair.com/us/en/p/memory/cmh32gx5m2b6000c30/vengeance-rgb-32gb-2x16gb-ddr5-dram-6000mt-s-c30-memory-kit-black-cmh32gx5m2b6000c30"),
    _series("corsair_dominator_platinum", "corsair", "CORSAIR DOMINATOR PLATINUM RGB", ("dominator platinum rgb",),
            "dimm", "rgb", ("分段顶盖", "直立散热鳍片"),
            "https://www.corsair.com/ww/en/p/memory/cmt32gx5m2b5600c36/dominatora-platinum-rgb-32gb-2x16gb-ddr5-dram-5600mhz-c36-memory-kit-a-black-cmt32gx5m2b5600c36"),
    _series("gskill_ripjaws_v", "gskill", "G.SKILL Ripjaws V", ("ripjaws v", "ripjawsv"),
            "dimm", "spreader", ("高低错层鳍片", "硬朗工业外壳"),
            "https://www.gskill.com/product/165/184/1536110676/F4-3200C16D-16GVKB"),
    _series("gskill_trident_z_rgb", "gskill", "G.SKILL Trident Z RGB", ("trident z rgb",),
            "dimm", "rgb", ("全长扩散罩", "斜切装甲线条"),
            "https://www.gskill.com/product/165/166/1536654268/F4-3200C16D-16GTZR", ("trident z rgb dc",)),
    _series("gskill_trident_z_royal", "gskill", "G.SKILL Trident Z Royal", ("trident z royal",),
            "dimm", "rgb", ("晶体切面扩散罩", "多边形切面"),
            "https://www.gskill.com/product/165/299/1552461134/F4-3600C18D-16GTRS",
            ("trident z royal elite", "trident z royal collector")),
    _series("gskill_flare_x5", "gskill", "G.SKILL Flare X5", ("flare x5",),
            "dimm", "low", ("矮式散热片", "简洁平直外壳"),
            "https://www.gskill.com/product/165/396/1673491242/F5-6000J3038F16GX2-FX5"),
    _series("kingston_fury_beast", "kingston", "Kingston FURY Beast", ("fury beast",),
            "dimm", "low", ("矮式散热片", "高低错层鳍片"),
            "https://www.kingston.com/datasheets/KF560C36BBEK2-32.pdf", ("fury beast rgb", "fury beast se")),
    _series("kingston_fury_renegade", "kingston", "Kingston FURY Renegade", ("fury renegade",),
            "dimm", "spreader", ("利落外壳分区", "斜切装甲线条"),
            "https://www.kingston.com/datasheets/KF564C32RSK2-32.pdf", ("fury renegade rgb", "fury renegade pro")),
    _series("kingston_valueram_dimm", "kingston", "Kingston ValueRAM DIMM", ("valueram udimm", "value ram udimm"),
            "dimm", "bare", ("裸露PCB与芯片", "标准长条模块"),
            "https://www.kingston.com/datasheets/KVR32N22S8_16.pdf"),
    _series("kingston_valueram_sodimm", "kingston", "Kingston ValueRAM SO-DIMM", ("valueram sodimm", "valueram so dimm", "value ram sodimm"),
            "sodimm", "bare", ("裸露PCB与芯片", "短型笔记本模块"),
            "https://www.kingston.com/datasheets/KVR32S22S8_16.pdf"),
    # The official Basics flyer names this complete UDIMM part number. Its
    # original image endpoint was unavailable during review, so no specific
    # bare-chip layout or heatspreader is attributed to this model.
    _series("crucial_basics_udimm", "crucial", "Crucial Basics UDIMM", ("basics udimm", "basics dimm"),
            "dimm", "neutral", ("标准长条模块",),
            "https://content.crucial.com/content/dam/crucial/dram-products/basics/flyer/crucial-basics-memory-productflyer.pdf"),
    _series("teamgroup_delta_rgb", "teamgroup", "T-FORCE DELTA RGB DDR5", ("delta rgb ddr5",),
            "dimm", "rgb", ("全长扩散罩", "斜切肩部"),
            "https://images.teamgroupinc.com/products/memory/u-dimm/ddr5/delta-rgb/spec-sheet/delta-rgb-en.pdf"),
    _series("teamgroup_vulcan", "teamgroup", "T-FORCE VULCAN DDR5", ("vulcan ddr5",),
            "dimm", "low", ("矮式散热片", "多边形切面"),
            "https://images.teamgroupinc.com/products/memory/u-dimm/ddr5/vulcan/spec-sheet/vulcan-en.pdf"),
    _series("adata_lancer_rgb", "adata", "XPG LANCER RGB", ("lancer rgb",),
            "dimm", "rgb", ("全长扩散罩", "几何切线饰面"),
            "https://www.adata.com/storage/downloadfile/datasheet_xpg_lancer_rgb_ddr5_memory_v6.pdf"),
    _series("adata_spectrix_d60g", "adata", "XPG SPECTRIX D60G", ("spectrix d60g",),
            "dimm", "rgb", ("双面大块扩散罩", "多边形切面"),
            "https://webapi3.adata.com/storage/downloadfile/datasheet_xpg_spectrix_d60g_ddr4_memory_v1.pdf"),
)


def _model(identity, series, label, *aliases):
    row = next(item for item in SERIES_CATALOG if item["id"] == series)
    return dict(id=identity, brand=row["brand"], series_id=series, label=label,
                aliases=aliases, form_factor=row["form_factor"], source_url=row["source_url"])


CATALOG = (
    _model("corsair-cmk16gx4m2b3200c16", "corsair_vengeance_lpx", "CORSAIR VENGEANCE LPX CMK16GX4M2B3200C16", "CMK16GX4M2B3200C16"),
    _model("corsair-cmh32gx5m2b6000c30", "corsair_vengeance_rgb", "CORSAIR VENGEANCE RGB CMH32GX5M2B6000C30", "CMH32GX5M2B6000C30"),
    _model("corsair-cmt32gx5m2b5600c36", "corsair_dominator_platinum", "CORSAIR DOMINATOR PLATINUM RGB CMT32GX5M2B5600C36", "CMT32GX5M2B5600C36"),
    _model("gskill-f4-3200c16d-16gvkb", "gskill_ripjaws_v", "G.SKILL Ripjaws V F4-3200C16D-16GVKB", "F4-3200C16D-16GVKB"),
    _model("gskill-f4-3200c16d-16gtzr", "gskill_trident_z_rgb", "G.SKILL Trident Z RGB F4-3200C16D-16GTZR", "F4-3200C16D-16GTZR"),
    _model("gskill-f4-3600c18d-16gtrs", "gskill_trident_z_royal", "G.SKILL Trident Z Royal F4-3600C18D-16GTRS", "F4-3600C18D-16GTRS"),
    _model("gskill-f5-6000j3038f16gx2-fx5", "gskill_flare_x5", "G.SKILL Flare X5 F5-6000J3038F16GX2-FX5", "F5-6000J3038F16GX2-FX5"),
    _model("kingston-kf560c36bbek2-32", "kingston_fury_beast", "Kingston FURY Beast KF560C36BBEK2-32", "KF560C36BBEK2-32"),
    _model("kingston-kf564c32rsk2-32", "kingston_fury_renegade", "Kingston FURY Renegade KF564C32RSK2-32", "KF564C32RSK2-32"),
    _model("kingston-kvr32n22s8-16", "kingston_valueram_dimm", "Kingston ValueRAM KVR32N22S8/16", "KVR32N22S8/16"),
    _model("kingston-kvr32s22s8-16", "kingston_valueram_sodimm", "Kingston ValueRAM KVR32S22S8/16", "KVR32S22S8/16"),
    _model("crucial-cb16gu4800", "crucial_basics_udimm", "Crucial Basics CB16GU4800", "CB16GU4800"),
    _model("teamgroup-ff3d532g6000hc30dc01", "teamgroup_delta_rgb", "T-FORCE DELTA RGB FF3D532G6000HC30DC01", "FF3D532G6000HC30DC01"),
    _model("teamgroup-flbd532g6000hc38jdc01", "teamgroup_vulcan", "T-FORCE VULCAN FLBD532G6000HC38JDC01", "FLBD532G6000HC38JDC01"),
    _model("adata-ax5u6000c3016g-dclarwh", "adata_lancer_rgb", "XPG LANCER RGB AX5U6000C3016G-DCLARWH", "AX5U6000C3016G-DCLARWH"),
    _model("adata-ax4u32008g16a-st60", "adata_spectrix_d60g", "XPG SPECTRIX D60G AX4U32008G16A-ST60", "AX4U32008G16A-ST60"),
)

_SERIES_BY_ID = {row["id"]: row for row in SERIES_CATALOG}
_BRAND_ALIASES = {
    "corsair": ("corsair", "海盗船", "美商海盗船"),
    "gskill": ("g skill", "gskill", "芝奇"),
    "kingston": ("kingston", "金士顿"),
    "crucial": ("crucial", "英睿达"),
    "teamgroup": ("teamgroup", "team group", "t force", "十铨"),
    "adata": ("adata", "xpg", "威刚"),
}


def _bounded(value):
    return value[:256].replace("\x00", " ").strip().lower()[:256] if isinstance(value, str) else ""


def _words(value):
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", " ", value).strip()


def _phrase(text, phrase):
    return (" " + phrase + " ") in (" " + text + " ")


def _brands(texts):
    return {brand for brand, aliases in _BRAND_ALIASES.items()
            if any(_phrase(text, alias) for text in texts for alias in aliases)}


def _part_match(text, alias):
    # Keep identifier punctuation in both boundaries. Appending a revision,
    # capacity, color or kit suffix never turns an unreviewed SKU into this SKU.
    return re.search(r"(?<![a-z0-9/_.-])" + re.escape(alias.lower())
                     + r"(?![a-z0-9/_.-])", text) is not None


def _explicit_form(texts):
    forms = set()
    for text in texts:
        if re.search(r"\b(?:so dimm|sodimm)\b", text):
            forms.add("sodimm")
            text = re.sub(r"\b(?:so dimm|sodimm)\b", " ", text)
        if re.search(r"\b(?:u dimm|udimm|dimm)\b", text):
            forms.add("dimm")
    return next(iter(forms)) if len(forms) == 1 else "unknown"


def _result(brand="unknown", *, model=None, series=None, form="unknown"):
    if series:
        form = series["form_factor"]
    presentation = series["presentation"] if series else "neutral"
    return (model["id"] if model else "memory-" + (series["id"] if series else brand),
            brand, model["label"] if model else series["label"] if series else BRANDS[brand][0],
            form, presentation, series["id"] if series else "", series["label"] if series else "",
            tuple(series["features"]) if series else (),
            model["source_url"] if model else series["source_url"] if series else "",
            "model" if model else "series" if series else "brand" if brand != "unknown" else "generic")


@lru_cache(maxsize=128)
def _resolve(name, model, manufacturer):
    raw = (name, model, manufacturer)
    words = tuple(_words(text) for text in raw)
    hints = _brands(words)
    matches = [row for row in CATALOG if any(_part_match(text, alias)
               for text in (name, model) for alias in row["aliases"])]
    form = _explicit_form(words)
    if len(hints) > 1 or len(matches) > 1:
        return _result()
    if matches:
        row = matches[0]
        if hints and hints != {row["brand"]}:
            return _result()
        if form != "unknown" and form != row["form_factor"]:
            return _result(row["brand"])
        return _result(row["brand"], model=row, series=_SERIES_BY_ID[row["series_id"]])
    if not hints:
        return _result(form=form)
    brand = next(iter(hints))
    joined = " ".join(words[:2])
    series_matches = [row for row in SERIES_CATALOG if row["brand"] == brand
                      and any(_phrase(joined, alias) for alias in row["aliases"])
                      and not any(_phrase(joined, alias) for alias in row["excludes"])]
    if len(series_matches) == 1:
        series = series_matches[0]
        if form == "unknown" or form == series["form_factor"]:
            return _result(brand, series=series)
    return _result(brand, form=form)


def appearance_for_memory(name="", model="", manufacturer=""):
    """Return a fresh map using existing identity strings only, never a scan.

    ``presentation='rgb'`` describes a verified physical diffuser enclosure;
    it says nothing about whether its LEDs are enabled or their current color.
    An unknown form remains ``memory_neutral``; DDR words alone do not set it.
    """
    identity, brand, label, form, presentation, series, series_label, features, url, confidence = _resolve(
        _bounded(name), _bounded(model), _bounded(manufacturer))
    return dict(id=identity, kind="memory", vendor="unknown", brand=brand, board_vendor=brand,
                label=label, style=form if form in ("dimm", "sodimm") else "memory_neutral",
                form_factor=form, presentation=presentation, shroud=presentation,
                series_id=series, series_label=series_label, features=list(features), source_url=url,
                confidence=confidence, accent=BRANDS[brand][1], fan_count=None,
                visible_fan_count=None, legacy=False)
