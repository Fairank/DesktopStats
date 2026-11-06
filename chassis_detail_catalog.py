"""Verified exterior facts for selected original case variants.

Counts describe the factory front I/O, never detected or installed hardware.
Missing fields are unknown. Port spacing remains an original schematic: the
sources establish counts/placement, not dimensioned manufacturing geometry.
This table performs no I/O and includes no third-party images or CAD assets.
"""

from copy import deepcopy


_REVIEWED = "2026-11-07"
_RECORDS = {
    "hyte-y60": (
        {"position": "front_bottom", "usb_a": 2, "usb_c": 1, "audio": 1, "buttons": 1},
        ("https://hyte.com/ja/press/hyte-launches-y60-midtower-pc-case-a-new-angle-on-design-",
         "https://hyte.com/store/y60/cs-hyte-y60-b",
         "https://content.ibuypower.com/hyte/product-page-pdfs/y60.pdf"),
    ),
    "hyte-y70": (
        {"position": "front_bottom", "usb_a": 2, "usb_c": 1, "audio": 1, "buttons": 1},
        ("https://hyte.com/store/y70/cs-hyte-y70-b",),
    ),
    "lian-li-o11-vision": (
        {"position": "front_bottom", "usb_a": 2, "usb_c": 1, "audio": 1, "buttons": 2},
        ("https://lian-li.com/product/o11-vision/",),
    ),
    "nzxt-h6-flow-2023": (
        {"position": "front_bottom", "usb_a": 2, "usb_c": 1, "audio": 1, "buttons": 1},
        ("https://support.nzxt.com/hc/en-us/articles/40183529624347-H6-Flow-2023-Specs",
         "https://support.nzxt.com/hc/en-us/articles/40177439747483-How-to-replace-the-Front-I-O-Module-on-the-H6-Flow",
         "https://support.nzxt.com/hc/en-us/articles/35757770991003-H6-Flow-2023-Downloads",
         "https://cdn-g.nzxt.com/dl/1698993634-h6-flow_digital-manual_231027_v2-pdf.pdf"),
    ),
    "fractal-north-mesh": (
        {"position": "top", "usb_a": 2, "usb_c": 1, "audio": 2, "buttons": 1},
        ("https://www.fractal-design.com/products/cases/north-series/north/north-charcoal-black/",),
    ),
    "corsair-4000d-airflow": (
        {"position": "top", "usb_a": 1, "usb_c": 1, "audio": 1, "buttons": 2},
        ("https://www.corsair.com/kr/en/explorer/diy-builder/cases/4000d-airflow-vs-4000d-rgb-airflow-vs-4000x-rgb-whats-the-difference/",
         "https://assets.corsair.com/image/upload/c_pad,q_auto,h_1024,w_1024,f_auto/products/Cases/base-4000d-airflow-config/Gallery/4000D_AF_BLACK_07.webp"),
    ),
    "corsair-5000d-airflow": (
        {"position": "top", "usb_a": 2, "usb_c": 1, "audio": 1, "buttons": 2},
        ("https://www.corsair.com/ww/en/p/pc-cases/cc-9011210-ww/5000d-airflow-tempered-glass-mid-tower-atx-pc-case-black-cc-9011210-ww",
         "https://help.corsair.com/hc/en-us/articles/9999949647757-5000D-5000X-IO-Panel-Replacement"),
    ),
    "corsair-7000d-airflow": (
        {"position": "top", "usb_a": 4, "usb_c": 1, "audio": 1, "buttons": 2},
        ("https://www.corsair.com/us/en/p/pc-cases/cc-9011218-ww/7000d-airflow-full-tower-atx-pc-case-black-cc-9011218-ww",),
    ),
    "asus-rog-strix-helios-gx601": (
        {"position": "top", "usb_a": 4, "usb_c": 1, "audio": 2, "buttons": 4},
        ("https://rog.asus.com/us/cases/rog-strix-helios-model/spec/",
         "https://rog.asus.com/us/cases/rog-strix-helios-model/"),
    ),
    "asus-tuf-gt302-argb": (
        {"position": "top", "usb_a": 2, "usb_c": 1, "audio": 1, "buttons": 1},
        ("https://www.asus.com/us/motherboards-components/cases/tuf-gaming/tuf-gaming-gt302-argb/techspec/",
         "https://dlcdnets.asus.com/pub/ASUS/ODD/DC/GT302/GT302_R2R_Manual.pdf?model=TUF+Gaming+GT302"),
    ),
    "deepcool-ch160": (
        {"position": "left_front", "usb_a": 2, "usb_c": 1, "audio": 1, "buttons": 1},
        ("https://www.deepcool.com/products/Cases/CH160-Portable-High-Airflow-M-ITX-Case/2024/18115.shtml",),
    ),
    "antec-flux": (
        {"position": "top", "usb_a": 2, "usb_c": 1, "audio": 1, "buttons": 2},
        ("https://www.antec.com/product/case/flux",),
    ),
}


def details_for(case_id: object) -> dict:
    """Return detached verified facts, or an empty mapping for an unknown ID."""
    record = _RECORDS.get(case_id) if isinstance(case_id, str) else None
    if record is None:
        return {}
    io, sources = record
    return {
        "io": {**deepcopy(io), "layout_schematic": True},
        "sources": list(sources),
        "reviewed": _REVIEWED,
    }
