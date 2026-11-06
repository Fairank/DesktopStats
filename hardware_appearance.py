"""Small, offline hardware appearance catalog. Never reads sensors or starts a scan.

Chip vendor, board manufacturer and exact cooler model are distinct identities.
Only reviewed complete model aliases select a fan layout. Unknown names retain
a neutral outline, including mobile GPUs, whose chassis fans are not card fans.
The bounded cache stores immutable tuples; callers receive their own small map.
"""

import re
from functools import lru_cache

import hardware_catalog_core_expansion as core_catalog
import hardware_catalog_nvidia_legacy as nvidia_legacy_catalog
import hardware_catalog_radeon_arc as radeon_arc_catalog
import hardware_catalog_group_a as group_a_catalog
import hardware_catalog_group_b as group_b_catalog
import hardware_catalog_group_c as group_c_catalog
from hardware_model_extensions import CATALOG_EXTENSIONS, MODEL_SERIES
from hardware_series import SERIES_CATALOG
from hardware_catalog_metadata import fields as catalog_fields, generation as catalog_generation
from memory_appearance import appearance_for_memory

# These are restrained interface accents, not claims about a product's paint.
BRANDS = {
    "intel": ("Intel", "#4387c7"),
    "amd": ("AMD", "#c96651"),
    "nvidia": ("NVIDIA", "#6e993d"),
    "asus": ("ASUS", "#64938b"),
    "msi": ("MSI", "#bd6673"),
    "gigabyte": ("GIGABYTE", "#c38a4e"),
    "zotac": ("ZOTAC", "#ba9b47"),
    "sapphire": ("SAPPHIRE", "#638ac3"),
    "powercolor": ("PowerColor", "#7c80c2"),
    "asrock": ("ASRock", "#7f9964"),
    "pny": ("PNY", "#7b91a9"),
    "palit": ("Palit", "#ad8669"),
    "gainward": ("Gainward", "#ab6c63"),
    "galax": ("GALAX", "#9b80b8"),
    "inno3d": ("INNO3D", "#b38a5c"),
    "colorful": ("Colorful", "#b67a9b"),
    "xfx": ("XFX", "#ab6966"),
    "evga": ("EVGA", "#7e9c8a"),
    "leadtek": ("Leadtek", "#7c91ae"),
    "maxsun": ("MAXSUN", "#879dc6"),
    "yeston": ("Yeston", "#b08fab"),
    "biostar": ("BIOSTAR", "#a98864"),
    "sparkle": ("SPARKLE", "#7088b4"),
    "acer": ("Acer", "#829c6c"),
    "unknown": ("", "#83909e"),
}

_ALIASES = {
    **{key: (key,) for key in BRANDS if key != "unknown"},
    "asus": ("asus", "asustek"),
    "msi": ("msi", "micro star", "microstar"),
    "gigabyte": ("gigabyte", "aorus"),
    "galax": ("galax", "kfa2", "影驰"),
    "colorful": ("colorful", "colourful", "igame", "七彩虹"),
    "amd": ("amd", "radeon", "advanced micro devices", "ryzen", "threadripper", "epyc"),
    "nvidia": ("nvidia", "geforce", "quadro"),
    "intel": ("intel", "genuineintel"),
}
_ALIASES.update({"asus": (*_ALIASES["asus"], "华硕"), "msi": (*_ALIASES["msi"], "微星"),
                 "gigabyte": (*_ALIASES["gigabyte"], "技嘉"), "zotac": ("zotac", "索泰"),
                 "sapphire": ("sapphire", "蓝宝石"), "powercolor": ("powercolor", "撼讯"),
                 "asrock": ("asrock", "华擎"), "xfx": ("xfx", "讯景"), "pny": ("pny", "必恩威"),
                 "inno3d": ("inno3d", "映众"), "gainward": ("gainward", "耕升"),
                 "leadtek": ("leadtek", "丽台"), "maxsun": ("maxsun", "铭瑄"),
                 "yeston": ("yeston", "盈通"), "biostar": ("biostar", "映泰")})

# Exact reviewed seed models, not family-wide fan-count guesses. Each row is
# id, kind, silicon vendor, board brand, label, style, fans, shroud, URL, aliases.
# New SKUs require an official reference and collision/mobile negative tests.
_SEED_CATALOG = (
    ("intel-13700kf", "cpu", "intel", "unknown", "Intel Core i7-13700KF",
     "lga_rect", None, "neutral",
     "https://www.intel.com/content/www/us/en/products/sku/230489/intel-core-i713700kf-processor-30m-cache-up-to-5-40-ghz/specifications.html",
     ("Intel Core i7 13700KF",)),
    ("amd-9950x", "cpu", "amd", "unknown", "AMD Ryzen 9 9950X", "am5", None,
     "neutral", "https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-9-9950x.html",
     ("AMD Ryzen 9 9950X",)),
    ("amd-7800x3d", "cpu", "amd", "unknown", "AMD Ryzen 7 7800X3D", "am5", None,
     "neutral", "https://www.amd.com/en/products/processors/desktops/ryzen/7000-series/amd-ryzen-7-7800X3d.html",
     ("AMD Ryzen 7 7800X3D",)),
    ("asus-dual-4060-oc", "gpu", "nvidia", "asus", "ASUS Dual RTX 4060 OC",
     "gpu_axial", 2, "soft",
     "https://www.asus.com/motherboards-components/graphics-cards/dual/dual-rtx4060-o8g/",
     ("DUAL RTX4060 O8G", "ASUS Dual GeForce RTX 4060 OC Edition 8GB")),
    ("asus-tuf-4070tis-oc", "gpu", "nvidia", "asus", "ASUS TUF RTX 4070 Ti SUPER OC",
     "gpu_axial", 3, "angular",
     "https://www.asus.com/motherboards-components/graphics-cards/tuf-gaming/tuf-rtx4070tis-o16g-gaming/",
     ("TUF RTX4070TIS O16G GAMING", "ASUS TUF Gaming GeForce RTX 4070 Ti SUPER 16GB GDDR6X OC Edition")),
    ("msi-ventus-4060-2x-oc", "gpu", "nvidia", "msi", "MSI RTX 4060 VENTUS 2X BLACK OC",
     "gpu_axial", 2, "angular",
     "https://us.msi.com/Graphics-Card/GeForce-RTX-4060-VENTUS-2X-BLACK-8G-OC",
     ("MSI GeForce RTX 4060 VENTUS 2X BLACK 8G OC",)),
    ("gigabyte-windforce-4060-oc", "gpu", "nvidia", "gigabyte", "GIGABYTE RTX 4060 WINDFORCE OC",
     "gpu_axial", 2, "box", "https://www.gigabyte.com/press/news/2096",
     ("GV N4060WF2OC 8GD", "GIGABYTE GeForce RTX 4060 WINDFORCE OC 8G")),
    ("zotac-solo-4060", "gpu", "nvidia", "zotac", "ZOTAC RTX 4060 SOLO",
     "gpu_axial", 1, "soft",
     "https://marketplace.nvidia.com/en-us/consumer/graphics-cards/zotac-nvidia-geforce-rtx-4060-solo-single-fan-8gb-gddr6-pcie-4-0-graphics-card/",
     ("ZT D40600G 10L", "ZOTAC GAMING GeForce RTX 4060 8GB SOLO")),
    ("sapphire-pulse-7600", "gpu", "amd", "sapphire", "SAPPHIRE PULSE RX 7600",
     "gpu_axial", 2, "box",
     "https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-7600-8g-gddr6",
     ("SAPPHIRE PULSE AMD Radeon RX 7600 8G GDDR6", "SAPPHIRE PULSE RX 7600")),
)
_EXTRA_CATALOGS = (group_a_catalog, group_b_catalog, group_c_catalog, core_catalog,
                   nvidia_legacy_catalog, radeon_arc_catalog)
CATALOG = (_SEED_CATALOG + CATALOG_EXTENSIONS
           + tuple(row for package in _EXTRA_CATALOGS for row in package.CATALOG))
_VISIBLE_FANS = {key: count for package in _EXTRA_CATALOGS
                 for key, count in getattr(package, "VISIBLE_FANS", {}).items()}

_FIELDS = ("id", "kind", "vendor", "board_vendor", "label", "style", "fan_count",
           "shroud", "source_url", "confidence", "accent", "series_id", "series_label", "features")


def _text(value):
    # Bound untrusted provider strings before regex/cache retention. Never turn
    # arbitrary objects into strings (or accept bool as a numeric identifier).
    if not isinstance(value, str):
        return ""
    text = value[:256].casefold()
    text = re.sub(r"\((?:r|tm)\)|[®™]", " ", text)
    return " ".join(re.sub(r"[^a-z0-9\u3400-\u9fff]+", " ", text).split())


def _has(text, token):
    if any("\u3400" <= char <= "\u9fff" for char in token):
        return bool(token and token in text)
    return bool(token and f" {token} " in f" {text} ")


def _brands(text, *, silicon=False):
    keys = ("intel", "amd", "nvidia") if silicon else tuple(
        key for key in BRANDS if key not in ("intel", "amd", "nvidia", "unknown"))
    return [key for key in keys if any(_has(text, alias) for alias in _ALIASES[key])]


def _gpu_chips(text):
    chips = {(family, number, variant.replace(" ", "")) for family, number, variant in
            re.findall(r"\b(rtx|gtx|rx|arc)\s*([ab]?\d{3,4})"
                       r"\s*(ti\s*super|super|ti|xtx|xt|gre|m)?\b", text)}
    chips.update((family, number, variant) for family, number, variant in
                 re.findall(r"\b(hd|gt)\s*(\d{3,4})\s*(x2|xt|x|m)?\b", text))
    # R5450/R7970 are MSI HD-series product codes, not R5 450 / R7 970.
    # Compact R9/R7/R5 chip names need the Radeon context; spaced names are clear.
    for pattern in (r"\b(r9|r7|r5)\s+(\d{3})\s*(x2|x|m)?\b",
                    r"\bradeon\s+(r9|r7|r5)\s*(\d{3})\s*(x2|x|m)?\b"):
        chips.update(re.findall(pattern, text))
    chips.update(("geforce_fx" if fx else "geforce", number, variant)
                 for fx, number, variant in re.findall(
                     r"\bgeforce\s*(fx\s*)?(\d{4})\s*(gtx|gts|gt|gs|ultra|le)?\b", text))
    chips.update(("vega", number, "") for number in re.findall(r"\bvega\s*(\d{2})\b", text))
    chips.update(("fury", "", variant) for variant in re.findall(r"\bfury\s*(x)?\b", text))
    return chips


_MODELS = tuple((row, tuple(_text(alias) for alias in row[-1])) for row in CATALOG)
_SERIES = tuple((row, tuple(_text(alias) for alias in row["aliases"])) for row in SERIES_CATALOG)
_MODEL_SERIES = {
    "asus-dual-4060-oc": "asus_dual", "asus-tuf-4070tis-oc": "asus_tuf",
    "msi-ventus-4060-2x-oc": "msi_ventus", "gigabyte-windforce-4060-oc": "gigabyte_windforce",
    "zotac-solo-4060": "zotac_solo", "sapphire-pulse-7600": "sapphire_pulse",
    **MODEL_SERIES,
    **{key: series for package in _EXTRA_CATALOGS for key, series in package.MODEL_SERIES.items()},
}
_MODEL_CHIP_NAMES = {key: value for package in _EXTRA_CATALOGS
                     for key, value in getattr(package, "MODEL_CHIPS", {}).items()}
_MODEL_CHIPS = {row[0]: _gpu_chips(_text(_MODEL_CHIP_NAMES.get(row[0], row[4])))
                for row in CATALOG if row[1] == "gpu"}
_SERIES_METADATA = {row["id"]: row for row in SERIES_CATALOG}
_SERIES_FILTERS = {row["id"]: catalog_fields(row) for row in SERIES_CATALOG}
_MODEL_FILTERS = {row[0]: catalog_fields(_SERIES_METADATA.get(_MODEL_SERIES.get(row[0])), row[4])
                  for row in CATALOG if row[1] == "gpu"}
_SERIES_REP_ERAS = {_MODEL_SERIES[row[0]]: _MODEL_FILTERS[row[0]]["era"]
                    for row in CATALOG if row[1] == "gpu" and row[0] in _MODEL_SERIES}
_CPU_FEATURES = {"lga_rect": ("长方形金属顶盖",), "am5": ("八处边缘缺口", "中央金属顶盖")}
_MOBILE = re.compile(r"\b(?:laptop|mobile|notebook|max q)\b|\b\d{4,5}(?:hx|hs|hk|h|u|m)\b")


def _series(board, text, *, exact_id=""):
    matches = [row for row, aliases in _SERIES if row["board_vendor"] == board
               and (row["id"] == exact_id or any(_has(text, alias) for alias in aliases))]
    if len(matches) > 1:
        # Broader cooling/marketing names can accompany a precise family name.
        weak = ("msi_gaming", "gigabyte_windforce", "pny_verto")
        specific = [row for row in matches if row["id"] not in weak]
        if len(specific) == 1:
            return specific[0]
        # A genuine subfamily phrase can contain its parent's whole phrase:
        # Sakura Atlantis/Sakura, iCHILL X3/X3. Unrelated TUF + Dual stays ambiguous.
        candidates = specific or matches
        for row in candidates:
            phrases = [_text(alias) for alias in row["aliases"] if _has(text, _text(alias))]
            if any(all(other["id"] == row["id"] or
                       any(_has(phrase, _text(alias)) for alias in other["aliases"])
                       for other in candidates) for phrase in phrases):
                return row
    return matches[0] if len(matches) == 1 else None


def _series_fields(series, *, style=""):
    return ((series["id"], series["label"], tuple(series["features"][:2])) if series else
            ("", "", _CPU_FEATURES.get(style, ())))


@lru_cache(maxsize=128)
def _resolve(kind, name, model, board):
    name, model, board = _text(name), _text(model), _text(board)
    name_vendors = _brands(name, silicon=True)
    vendor = name_vendors[0] if len(name_vendors) == 1 else "unknown"
    name_boards = _brands(name)
    # In the explicit board field, the chip makers can identify their own
    # reference boards. An opposite supplied maker must not be overwritten by
    # a Founders/Reference/Limited phrase in the model name.
    reference_boards = _brands(board, silicon=True) if board else []
    explicit_boards = _brands(board) + reference_boards if board else []
    boards = explicit_boards if board else name_boards
    board_vendor = boards[0] if len(boards) == 1 else "unknown"
    if kind == "gpu" and board_vendor == "unknown":
        identity = name + " " + model + " " + board
        reference = ((vendor == "nvidia" and _has(identity, "founders edition"))
                     or (vendor == "amd" and (_has(identity, "reference") or _has(identity, "made by amd")))
                     or (vendor == "intel" and _has(identity, "limited edition")))
        if reference:
            board_vendor = vendor
    name_chips = _gpu_chips(name) if kind == "gpu" else set()
    conflict = len(name_vendors) > 1
    if kind == "gpu":
        conflict |= (len(name_boards) > 1 or len(explicit_boards) > 1 or len(name_chips) > 1
                     or bool(reference_boards and vendor not in ("unknown", reference_boards[0]))
                     or bool(name_boards and explicit_boards and name_boards != explicit_boards))
    text = model or name
    mobile = bool(_MOBILE.search(name + " " + model))
    matches = [row for row, aliases in _MODELS if row[1] == kind
               and not mobile and any((text == alias if kind == "gpu" else _has(text, alias))
                                      for alias in aliases)]
    if len(matches) == 1:
        row = matches[0]
        # An explicit conflicting board/chip identity invalidates a model alias.
        chip_conflict = (kind == "gpu" and name_chips
                         and name_chips != _MODEL_CHIPS[row[0]])
        if (not conflict and not chip_conflict and vendor in ("unknown", row[2])
                and board_vendor in ("unknown", row[3])):
            brand = row[3] if row[3] != "unknown" else row[2]
            series = _series(row[3], "", exact_id=_MODEL_SERIES.get(row[0], ""))
            return (*row[:-1], "model", BRANDS[brand][1], *_series_fields(series, style=row[5]))
        conflict = True
    if kind == "gpu":
        if conflict:
            board_vendor = "unknown"
        # Integrated/mobile names never borrow the desktop card's fan assembly.
        integrated = bool(re.search(r"\b(?:uhd|iris|integrated)\b", name))
        style = "gpu_integrated" if integrated or mobile else "gpu_neutral"
        brand = board_vendor if board_vendor != "unknown" else vendor
    else:
        style, brand, board_vendor = "chip", vendor, "unknown"
    confidence = "brand" if brand != "unknown" else "generic"
    series = (_series(board_vendor, name + " " + model)
              if kind == "gpu" and style == "gpu_neutral" and not matches and not conflict else None)
    if series:
        supplied_era = catalog_generation(name + " " + model)
        represented_era = _SERIES_REP_ERAS.get(series["id"], "unspecified")
        if supplied_era != "unspecified" and represented_era != "unspecified" and supplied_era != represented_era:
            # A reused marketing family cannot put a modern enclosure on an
            # unreviewed older card. Its exact era/SKU needs its own drawing.
            series = None
    if series:
        return (f"gpu-{series['id']}", kind, vendor, board_vendor, BRANDS[brand][0], style,
                None, "neutral", series["source_url"], "series", BRANDS[brand][1],
                *_series_fields(series))
    return (f"{kind}-{brand}-{style}", kind, vendor, board_vendor, BRANDS[brand][0],
            style, None, "neutral", "", confidence, BRANDS[brand][1], "", "", ())


def appearance_for(kind, name, *, model="", board_vendor=""):
    """Return a detached style map, independent of dynamic values/animation.

    `board_vendor` must come from the selected GPU, never the motherboard or
    machine maker. Names alone cannot resolve an OEM cooler's physical layout.
    """
    if kind not in ("cpu", "gpu"):
        return {}
    def bounded(value):
        return value[:256] if isinstance(value, str) else ""
    result = dict(zip(_FIELDS, _resolve(kind, bounded(name), bounded(model), bounded(board_vendor))))
    result["features"] = list(result["features"])
    result["visible_fan_count"] = _VISIBLE_FANS.get(result["id"], result["fan_count"])
    result["legacy"] = bool(_SERIES_METADATA.get(result["series_id"], {}).get("legacy", False))
    result.update(_MODEL_FILTERS.get(result["id"]) or _SERIES_FILTERS.get(result["series_id"]) or {})
    return result


def memory_appearance(data):
    """An aggregate RAM reading never borrows one arbitrary stick's appearance."""
    if not isinstance(data, dict):
        return appearance_for_memory()
    devices = data.get("memory_modules")
    if "memory_modules" in data:
        if not isinstance(devices, list) or not devices or len(devices) > 64 or any(not isinstance(row, dict) for row in devices):
            return appearance_for_memory()
        keys = ("manufacturer", "part_number", "form_factor")
        if any(not isinstance(row.get(key, ""), str) for row in devices for key in keys):
            return appearance_for_memory()
        identities = {tuple(row.get(key, "")[:256] for key in keys) for row in devices}
        if len(identities) != 1:
            result = appearance_for_memory()
            result.update(label="混合内存", features=["不同型号内存条"])
            return result
        row = devices[0]
        result = appearance_for_memory(model=row.get("part_number", ""), manufacturer=row.get("manufacturer", ""))
        form = {"cudimm": "dimm", "csodimm": "sodimm"}.get(row.get("form_factor"), row.get("form_factor"))
        if result["confidence"] != "model" and form in ("dimm", "sodimm"):
            result["style"] = form
            result["form_factor"] = form
        # A source-backed full SKU cannot override an opposite known form.
        if result["confidence"] == "model" and form in ("dimm", "sodimm") and result["style"] != form:
            result = appearance_for_memory()
            result["style"] = form
            result["form_factor"] = form
        # Preserve the actual firmware part for details even when its retail
        # enclosure is unconfirmed. Never turn it into an exact catalog claim.
        result["reported_label"] = " ".join("".join(char for char in row.get(key, "")[:128]
                                             if char.isprintable()).strip()
                                           for key in ("manufacturer", "part_number")).strip()
        return result
    return appearance_for_memory(name=data.get("memory_name", ""),
                                 model=data.get("memory_model", ""), manufacturer=data.get("memory_manufacturer", ""))


def metric_appearance(data, metric, prefs, *, scope=None, target=None, external=False):
    """Project only the selected processor's existing identity; no I/O.

    A present GPU table is authoritative, including a missing selected row.
    Legacy flat GPU data can stand in only for the default GPU, never GPU 1+.
    """
    if external:
        return {}
    if metric.startswith("cpu_"):
        return appearance_for("cpu", data.get("cpu_name"))
    if metric.startswith("ram_") and scope != "gpus":
        return memory_appearance(data)
    if scope != "gpus":
        return {}
    selected = str(target if target is not None else prefs.get("gpu_target") or "0")
    devices = data.get("gpus")
    device = devices.get(selected, {}) if isinstance(devices, dict) else (
        data if selected == "0" else {})
    if not isinstance(device, dict):
        device = {}
    return appearance_for("gpu", device.get("gpu_name") or device.get("label"),
                          model=device.get("board_model"), board_vendor=device.get("board_vendor"))
