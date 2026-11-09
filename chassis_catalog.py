"""Bounded, source-backed chassis references for the on-demand assembly view.

These are original schematic models, not manufacturer CAD files or a complete
market catalog. Dimensions describe the exterior, normally including feet.
Fan mounts describe supported mounting options, NEVER detected/installed fans.
GPU lengths are reference limits, not a fit check: radiators, brackets, power
connectors and the actual GPU thickness can change available clearance.

No product photos, logos, downloaded meshes or background network access.
"""

from copy import deepcopy
import re
import unicodedata

CATALOG_VERSION = 2
SOURCES_REVIEWED = "2026-11-07"
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z", re.ASCII)
_FORM_IDS = {"ATX": "atx", "Micro-ATX": "micro_atx", "Mini-ITX": "mini_itx",
             "E-ATX": "e_atx", "SSI-EEB": "ssi_eeb", "SSI-CEB": "ssi_ceb",
             "Mini-DTX": "mini_dtx", "DTX": "dtx"}


def valid_case_id(value):
    return isinstance(value, str) and 0 < len(value) <= 64 and _ID.fullmatch(value) is not None


def _mount(position, count, *sizes):
    return dict(position=position, count=count, size_mm=list(sizes))


def _case(case_id, label, brand, width, height, depth, layout, front, left, top,
          forms, gpu, sources, features=(), mounts=(), fit_note=""):
    return dict(id=case_id, label=label, brand=brand,
                dimensions_mm=dict(width=width, height=height, depth=depth),
                layout=layout, panels=dict(front=front, left=left, top=top),
                form_factors=[_FORM_IDS[form] for form in forms], max_gpu_length_mm=gpu,
                fan_mounts=list(mounts), features=list(features),
                sources=list(sources), sources_reviewed=SOURCES_REVIEWED,
                fit_note=fit_note, geometry_accuracy="schematic")


_ATX = ("ATX", "Micro-ATX", "Mini-ITX")
_EATX = ("E-ATX",) + _ATX
_CASES = (
    _case("lian-li-o11d-evo-rgb", "Lian Li O11D EVO RGB", "Lian Li", 290, 471, 478,
          "dual_chamber", "glass", "glass", "mesh", _EATX, 455.7,
          ("https://lian-li.com/product/o11d-evo-rgb/",),
          ("panoramic_glass", "removable_corner_pillar", "top_bottom_light_strips"),
          (_mount("top", 3, 120, 140), _mount("side", 3, 120, 140),
           _mount("bottom", 3, 120, 140), _mount("rear", 1, 120)),
          "E-ATX 主板宽度不超过 280 mm；可反转结构按标准方向示意。"),
    _case("lian-li-lancool-216", "Lian Li LANCOOL 216", "Lian Li", 235, 491.7, 480.9,
          "tower", "mesh", "glass", "mesh", _EATX, None,
          ("https://lian-li.com/product/lancool-216/",),
          ("large_front_intakes", "bottom_psu_shroud"),
          (_mount("front", 2, 160),),
          "前部 160 mm 安装位为结构参考；本批未录入其他安装组合或显卡长度。"),
    _case("nzxt-h5-flow-2024", "NZXT H5 Flow (2024)", "NZXT", 225, 465, 430,
          "tower", "mesh", "glass", "mesh", _EATX, 410,
          ("https://support.nzxt.com/hc/en-us/articles/40225168535451-H5-Flow-2024-Specs",
           "https://support.nzxt.com/hc/en-us/articles/47061130443291-What-is-the-maximum-GPU-length-for-the-H5-Flow-2024"),
          ("perforated_psu_shroud", "bottom_psu_shroud"),
          (_mount("front", 3, 120), _mount("front", 2, 140), _mount("top", 2, 120, 140),
           _mount("bottom", 2, 120), _mount("rear", 1, 120)),
          "采用厂家更正后的 410 mm，旧手册 425 mm 有误；前置冷排会进一步减少空间；E-ATX 宽度不超过 277 mm。"),
    _case("nzxt-h6-flow-2023", "NZXT H6 Flow (2023)", "NZXT", 287, 435, 415,
          "dual_chamber", "glass", "glass", "mesh", _ATX, 365,
          ("https://support.nzxt.com/hc/en-us/articles/40183529624347-H6-Flow-2023-Specs",
           "https://nzxt.com/en-intl/products/h6-flow?option1=Black"),
          ("angled_front_right_intake", "panoramic_glass"),
          (_mount("angled_front_right", 3, 120), _mount("top", 3, 120),
           _mount("top", 2, 140), _mount("bottom", 2, 140), _mount("rear", 1, 120))),
    _case("corsair-4000d-airflow", "Corsair 4000D AIRFLOW", "Corsair", 230, 466, 453,
          "tower", "mesh", "glass", "mesh", _ATX, 360,
          ("https://assets.corsair.com/image/upload/v1684779868/corsairmedia/sys_master/productcontent/WW_4000D_4000D_Airflow_QSG_AB.pdf",),
          ("triangular_front_mesh", "bottom_psu_shroud")),
    _case("corsair-6500x", "Corsair 6500X", "Corsair", 328, 496, 481,
          "dual_chamber", "glass", "glass", "mesh", _EATX, 400,
          ("https://www.corsair.com/ca/en/p/pc-cases/cc-9011258-ww/6500x-mid-tower-dual-chamber-pc-case-white-cc-9011258-ww",),
          ("panoramic_glass", "back_connect_tray"),
          (_mount("top", 3, 120, 140), _mount("bottom", 3, 120, 140),
           _mount("side", 3, 120), _mount("rear", 1, 120, 140)),
          "E-ATX 最大 305 × 277 mm；示意不包括选配前面板。"),
    _case("fractal-north-mesh", "Fractal Design North Mesh", "Fractal Design", 215, 469, 447,
          "tower", "wood", "mesh", "mesh", _ATX, 355,
          ("https://www.fractal-design.com/products/cases/north-series/north/north-chalk-white/",
           "https://www.fractal-design.com/app/uploads/2022/12/North_Product-Sheet_EN.pdf"),
          ("wooden_front_slats", "bottom_psu_shroud"),
          (_mount("front", 3, 120), _mount("front", 2, 140), _mount("top", 2, 120, 140),
           _mount("side", 2, 120, 140), _mount("rear", 1, 120)),
          "此条目为网孔侧板版，不能替代 TG 玻璃侧板版。"),
    _case("fractal-terra-graphite", "Fractal Design Terra Graphite", "Fractal Design", 153, 218, 343,
          "compact", "solid", "slotted", "slotted", ("Mini-ITX",), 322,
          ("https://www.fractal-design.com/products/cases/terra-series/terra/terra-graphite/",),
          ("sandwich_layout", "slotted_aluminium", "front_wood_strip"),
          (_mount("bottom", 1, 120),),
          "显卡厚度与 CPU 散热器空间随中脊位置变化；322 mm 不是任意厚度显卡的装配保证。"),
    _case("fractal-torrent-tg", "Fractal Design Torrent TG", "Fractal Design", 242, 530, 544,
          "tower", "slotted", "glass", "solid", ("SSI-EEB", "SSI-CEB") + _EATX, None,
          ("https://www.fractal-design.com/products/cases/torrent-series/torrent/torrent-rgb-black-tg-light-tint/",
           "https://www.fractal-design.com/app/uploads/2024/10/Torrent-manual-v.1.1_2024-10-28.pdf"),
          ("open_front_grille", "top_psu_shroud", "bottom_intake"),
          (_mount("front", 3, 120, 140), _mount("front", 2, 180),
           _mount("bottom", 3, 120, 140), _mount("bottom", 2, 180), _mount("rear", 1, 120, 140)),
          "手册带前部 180 mm 风扇时显卡限长 423 mm，产品最大值 461 mm 与装配条件有关，故不填单一限长。"),
    _case("fractal-node-304-black", "Fractal Design Node 304 Black", "Fractal Design", 250, 210, 374,
          "horizontal", "solid", "solid", "solid", ("Mini-ITX", "Mini-DTX"), 310,
          ("https://www.fractal-design.com/products/cases/node-series/node-304/node-304-black/",),
          ("compact_cube", "side_ventilation", "aluminium_front"),
          (_mount("front", 2, 92), _mount("rear", 1, 120, 140)),
          "长显卡需要移除对应硬盘架，电源长度及接口位置仍可能干涉。"),
    _case("hyte-y60", "HYTE Y60", "HYTE", 285, 462, 456,
          "dual_chamber", "glass", "glass", "mesh", _EATX, 375,
          ("https://hyte.com/store/y60/cs-hyte-y60-b",),
          ("angular_glass_corner", "vertical_gpu_mount", "bottom_intake"),
          (_mount("side", 2, 120, 140), _mount("top", 3, 120),
           _mount("bottom", 2, 120, 140), _mount("rear", 1, 120)),
          "显卡仅竖装，官方建议厚度不超过 60 mm 以获得较好散热；最大厚度 75 mm。"),
    _case("hyte-y70", "HYTE Y70", "HYTE", 320, 470, 470,
          "dual_chamber", "glass", "glass", "mesh", _EATX, 422,
          ("https://hyte.com/store/y70/cs-hyte-y70-b",),
          ("angular_glass_corner", "vertical_gpu_mount", "bottom_intake"),
          (_mount("top", 3, 120), _mount("top", 2, 140), _mount("side", 3, 120),
           _mount("side", 2, 140), _mount("bottom", 3, 120), _mount("bottom", 2, 140),
           _mount("rear", 1, 120, 140)),
          "此条目为无触屏 Y70，不代替 Y70 Touch；显卡最大厚度 105 mm。"),
    _case("asus-proart-pa602", "ASUS ProArt PA602", "ASUS", 245, 560, 593,
          "tower", "slotted", "glass", "mesh", ("Mini-DTX", "DTX") + _EATX, 440,
          ("https://www.asus.com/motherboards-components/cases/proart/proart-pa602/techspec/",),
          ("wide_front_grille", "large_front_intakes", "bottom_psu_shroud"),
          (_mount("front", 2, 200), _mount("top", 3, 120, 140), _mount("rear", 1, 120, 140)),
          "采用当前官方规格的 440 mm；旧宣传资料中的 450 mm 未采用；E-ATX 最大 12 × 10.9 英寸。"),
    _case("asus-rog-hyperion-gr701", "ASUS ROG Hyperion GR701", "ASUS", 268, 659, 639,
          "tower", "slotted", "glass", "mesh", _EATX, None,
          ("https://rog.asus.com/cases/rog-hyperion-gr701-model/spec/",
           "https://rog.asus.com/uk/cases/rog-hyperion-gr701-model/wtb/"),
          ("external_exoskeleton", "diagonal_frame_rails", "bottom_psu_shroud"),
          (), "E-ATX 最大 12 × 10.9 英寸；本批未录入显卡限长和风扇安装组合。"),
    _case("asus-tuf-gt502", "ASUS TUF Gaming GT502", "ASUS", 285, 450, 446,
          "dual_chamber", "glass", "glass", "mesh", _ATX, 400,
          ("https://www.asus.com/motherboards-components/cases/tuf-gaming/tuf-gaming-gt502/techspec/",),
          ("panoramic_glass",),
          (_mount("top", 3, 120), _mount("top", 2, 140), _mount("side", 3, 120),
           _mount("bottom", 3, 120),
           _mount("rear", 1, 120))),
    _case("cooler-master-nr200p-v2", "Cooler Master NR200P V2 (TG)", "Cooler Master", 185, 292, 372,
          "compact", "solid", "glass", "mesh", ("Mini-ITX",), None,
          ("https://www.coolermaster.com/en-au/products/masterbox-nr200p-v2.html",),
          ("vertical_gpu_mount", "compact_box"), (),
          "尺寸包含突出部分；侧板按玻璃面板示意，原厂另提供钢网侧板；显卡和底部风扇空间取决于装配条件。"),
    _case("cooler-master-haf-700-evo", "Cooler Master HAF 700 EVO", "Cooler Master", 291, 626, 666,
          "tower", "slotted", "glass", "mesh", ("SSI-EEB", "SSI-CEB") + _EATX, 490,
          ("https://www.coolermaster.com/en-au/products/haf-700-evo.html",),
          ("front_vertical_intake_blades", "front_round_display", "wide_external_frame"),
          (_mount("front", 2, 200), _mount("front", 3, 120, 140),
           _mount("rear", 2, 120), _mount("bottom", 3, 120, 140)),
          "尺寸包含突出部分；本批仅列已核实的部分风扇安装位。"),
    _case("thermaltake-tower-300", "Thermaltake The Tower 300", "Thermaltake", 342, 551, 281,
          "vertical", "angled_glass", "glass", "mesh", ("Micro-ATX", "Mini-ITX"), None,
          ("https://thermaltakeusa.com/products/the-tower-300-racing-green-micro-tower-chassis-ca-1y4-00scwn-00",),
          ("octagonal_front", "vertical_motherboard", "top_io"), (),
          "直立八角外形；显卡长度与电源盖板配置有关，本批不填单一限长。"),
    _case("phanteks-nv7", "Phanteks NV7", "Phanteks", 253, 586, 532,
          "dual_chamber", "glass", "glass", "mesh", _EATX, 450,
          ("https://phanteks.com/product/nv7-black/", "https://phanteks.com/manuals/NV7_Manual_v1.1.pdf"),
          ("recessed_motherboard_frame", "tall_glass_front", "panoramic_glass"),
          (_mount("top", 3, 120), _mount("side", 4, 120),
           _mount("bottom", 3, 120, 140), _mount("rear", 2, 120)),
          "标准 E-ATX 宽度不超过 277 mm；更宽主板需要按官方说明调整盖板。"),
    _case("be-quiet-shadow-base-800-fx", "be quiet! Shadow Base 800 FX", "be quiet!", 247, 522, 550,
          "tower", "mesh", "glass", "mesh", _EATX, 430,
          ("https://www.bequiet.com/en/case/4483",),
          ("wide_mesh_front", "vertical_front_light_strips", "bottom_psu_shroud"),
          (_mount("front", 3, 120, 140), _mount("top", 3, 120, 140),
           _mount("rear", 1, 120, 140), _mount("bottom", 1, 120, 140))),
    _case("jonsbo-d31-mesh", "Jonsbo D31 MESH", "Jonsbo", 205, 363, 452,
          "compact", "mesh", "glass", "mesh", ("Micro-ATX", "Mini-ITX", "DTX"), None,
          ("https://www.jonsbo.com/en/products/D31meshblack.html",),
          ("front_psu_mount", "compact_box"),
          (_mount("top", 3, 120), _mount("top", 2, 140), _mount("bottom", 3, 120),
           _mount("bottom", 2, 140), _mount("rear", 1, 120)),
          "尺寸包含突出部分；显卡限长随前置电源高度变化为 330–400 mm，故不填单一值；此款不含屏幕。"),
    _case("antec-c8-argb", "Antec C8 ARGB", "Antec", 303, 476, 464,
          "dual_chamber", "glass", "glass", "mesh", _EATX, 440,
          ("https://www.antec.com/documents/product/case-Antec_C8_ARGB_Manual_240516_compressed.pdf",
           "https://www.antec.com/documents/product/case-Antec_C8_ARGB_Black_Flyer_240515.pdf"),
          ("pillarless_glass_corner", "wide_bottom_intake"),
          (_mount("top", 3, 120, 140), _mount("top", 2, 160), _mount("side", 3, 120),
           _mount("side", 2, 140), _mount("bottom", 3, 120, 140), _mount("bottom", 2, 160),
           _mount("rear", 1, 120, 140)), "E-ATX 宽度不超过 280 mm。"),
    _case("montech-king-95", "Montech KING 95", "Montech", 300, 442, 475,
          "dual_chamber", "glass", "glass", "mesh", _ATX, 420,
          ("https://www.montechpc.com/king-95",),
          ("curved_front_glass", "wide_front_corner"),
          (_mount("top", 3, 120), _mount("top", 2, 140), _mount("side", 2, 120, 140),
           _mount("bottom", 3, 120), _mount("bottom", 2, 140), _mount("rear", 1, 120)),
          "按默认弧形玻璃前面板示意；附带可替换网孔面板；不是 KING 95 PRO。"),
    _case("msi-mag-pano-100r-pz", "MSI MAG PANO 100R PZ", "MSI", 290, 482, 518.7,
          "dual_chamber", "glass", "glass", "mesh", _ATX, None,
          ("https://uk.msi.com/PC-Case/MAG-PANO-100R-PZ/Specification",
           "https://download.msi.com/archive/mnu_exe/case/MAGPANO100L100RPZWHITE_English.pdf",
           "https://storage-asset.msi.com/datasheet/pcc/hk/MAG-PANO-100R-PZ.pdf"),
          ("angular_glass_corner", "back_connect_tray"),
          (_mount("top", 3, 120, 140), _mount("side", 3, 120), _mount("side", 2, 140),
           _mount("bottom", 3, 120), _mount("bottom", 2, 140, 160), _mount("rear", 1, 120)),
          "官方现行网页 400 mm 与另一官方数据表 380 mm 不一致；未确认配置前不填单一限长。"),
)
from chassis_catalog_group_a import records as _group_a
from chassis_catalog_group_b import records as _group_b
from chassis_catalog_group_c import records as _group_c
from chassis_catalog_group_d import records as _group_d
from chassis_catalog_group_e import records as _group_e

_CASES += _group_a(_case, _mount, _ATX, _EATX)
_CASES += _group_b(_case, _mount, _ATX, _EATX)
_CASES += _group_c(_case, _mount, _ATX, _EATX)
_CASES += _group_d(_case, _mount, _ATX, _EATX)
_CASES += _group_e(_case, _mount, _ATX, _EATX)
from chassis_detail_catalog import details_for as _exterior_details
for _entry in _CASES:
    _details=_exterior_details(_entry['id'])
    if _details:_entry['exterior_details']=_details
_BY_ID = {row["id"]: row for row in _CASES}
# A detached export is offered for catalog tooling. Runtime getters use the
# private records, so an accidental caller mutation cannot corrupt later views.
CASES = tuple(deepcopy(_CASES))

# A product name on a sales page is not proof of a firmware identity. No retail
# enclosure here has a verified SMBIOS Type 3 mapping yet. Add only evidence-
# backed (manufacturer, version-or-SKU, model ID, official source) entries.
_FIRMWARE_IDENTITIES = ()


def get_case(case_id):
    """Return a detached JSON-friendly record, or None for an invalid/unknown ID."""
    return deepcopy(_BY_ID.get(case_id)) if valid_case_id(case_id) else None


def choices():
    """Return inexpensive detached picker labels, in the same order for all styles."""
    return [dict(id=row["id"], label=row["label"], brand=row["brand"]) for row in _CASES]


def coverage():
    return dict(cases=len(_CASES), brands=len({row["brand"] for row in _CASES}),
                complete_market=False, verified_firmware_identities=len(_FIRMWARE_IDENTITIES),
                geometry_accuracy="schematic", sources_reviewed=SOURCES_REVIEWED)


def _normal(value):
    if not isinstance(value, str) or len(value) > 512:
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def match_enclosure(enclosure):
    """Match only verified exact Type 3 identities, never a system/baseboard brand."""
    if not isinstance(enclosure, dict):
        return []
    manufacturer = _normal(enclosure.get("manufacturer"))
    values = {_normal(enclosure.get("version")), _normal(enclosure.get("sku"))} - {""}
    if not manufacturer or not values:
        return []
    found = {}
    for maker, model, case_id, source in _FIRMWARE_IDENTITIES:
        if source.startswith("https://") and manufacturer == _normal(maker) and _normal(model) in values:
            row = get_case(case_id)
            if row is not None:
                found[row["id"]] = row
    return list(found.values())
