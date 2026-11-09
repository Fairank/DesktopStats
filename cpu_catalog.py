"""Source authoring catalog of named desktop/workstation CPU references.

This pure module is used to author optional data packs. Importing it never reads
hardware, files, the network or graphics. The application can keep its original
three CPU seeds and load user-selected JSON packs without importing this table.
Each SKU has its own official identity/socket source. Several SKUs deliberately
share one package family: a different name does not imply a different exterior.
Unknown dimensions, contact maps, thicknesses and cooling remain unverified.
Original code/art: PolyForm Noncommercial 1.0.0; third-party names retain owners.
"""
from copy import deepcopy

REVIEWED = "2026-11-07"
SEED_IDS = frozenset(("intel-13700kf", "amd-9950x", "amd-7800x3d"))
PACKAGE_IDS = frozenset(("intel_lga115x_1200", "intel_lga1700_1851",
    "intel_lga2011_2066", "amd_am4", "amd_am5", "amd_tr4_family", "amd_str5"))
INTEL_PACKAGE_GUIDE = "https://www.intel.com/content/www/us/en/support/articles/000005670/processors.html"
AMD_AM5_MECHANICAL = "https://www.amd.com/en/newsroom/press-releases/2023-11-14-amd-expands-ryzen-embedded-processor-family-for-h.html"
AMD_AM5_TOPOLOGY = "https://www.amd.com/content/dam/amd/en/documents/partner-hub/ryzen/amd-socket-am5-quick-reference-guide.pdf"
AMD_AM4_TOPOLOGY = "https://community.amd.com/t5/pc-building-how-to-articles/how-to-install-a-cpu/ta-p/590457"
AMD_TR_INSTALLATION = "https://www.amd.com/en/resources/support-articles/warranty/PIB.html"
# The last link is the manufacturer's installation-video index. No screenshot,
# animation, logo, pin map, cooler or internal die layout is redistributed.

_INTEL = (
    ("Pentium G4560","LGA1151",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/97143/intel-pentium-processor-g4560-3m-cache-3-50-ghz/specifications.html"),
    ("Celeron G5905","LGA1200",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/201899/intel-celeron-processor-g5905-4m-cache-3-50-ghz/specifications.html"),
    ("i7-870","LGA1156",None,"https://www.intel.com/content/dam/support/us/en/documents/processors/corei7/sb/intelcorei7comparisonchartrev8.pdf"),
    ("i7-2600K","LGA1155",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/52214/intel-core-i72600k-processor-8m-cache-up-to-3-80-ghz/specifications.html"),
    ("i7-3770K","LGA1155",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/65523/intel-core-i73770k-processor-8m-cache-up-to-3-90-ghz/specifications.html"),
    ("i7-4790K","LGA1150",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/80807/intel-core-i74790k-processor-8m-cache-up-to-4-40-ghz/specifications.html"),
    ("i7-6700K","LGA1151",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/88195/intel-core-i76700k-processor-8m-cache-up-to-4-20-ghz/specifications.html"),
    ("i7-7700K","LGA1151",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/97129/intel-core-i77700k-processor-8m-cache-up-to-4-50-ghz/specifications.html"),
    ("i7-8700K","LGA1151",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/126684/intel-core-i78700k-processor-12m-cache-up-to-4-70-ghz/specifications.html"),
    ("i9-9900K","LGA1151",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/186605/intel-core-i99900k-processor-16m-cache-up-to-5-00-ghz/specifications.html"),
    ("i9-10900K","LGA1200",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/199332/intel-core-i910900k-processor-20m-cache-up-to-5-30-ghz/specifications.html"),
    ("i7-10700K","LGA1200",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/199335/intel-core-i710700k-processor-16m-cache-up-to-5-10-ghz/specifications.html"),
    ("i5-10600K","LGA1200",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/199311/intel-core-i510600k-processor-12m-cache-up-to-4-80-ghz/specifications.html"),
    ("i9-11900K","LGA1200",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/212325/intel-core-i911900k-processor-16m-cache-up-to-5-30-ghz/specifications.html"),
    ("i7-11700K","LGA1200",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/212047/intel-core-i711700k-processor-16m-cache-up-to-5-00-ghz/specifications.html"),
    ("i5-11600K","LGA1200",(37.5,37.5),"https://www.intel.com/content/www/us/en/products/sku/212275/intel-core-i511600k-processor-12m-cache-up-to-4-90-ghz/specifications.html"),
    ("i9-12900K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/134599/intel-core-i912900k-processor-30m-cache-up-to-5-20-ghz/specifications.html"),
    ("i7-12700K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/134594/intel-core-i712700k-processor-25m-cache-up-to-5-00-ghz/specifications.html"),
    ("i5-12600K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/134589/intel-core-i512600k-processor-20m-cache-up-to-4-90-ghz/specifications.html"),
    ("i5-12400F","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/134587/intel-core-i512400f-processor-18m-cache-up-to-4-40-ghz/specifications.html"),
    ("i3-12100F","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/132223/intel-core-i312100f-processor-12m-cache-up-to-4-30-ghz/specifications.html"),
    ("i9-13900K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/230496/intel-core-i913900k-processor-36m-cache-up-to-5-80-ghz/specifications.html"),
    ("i7-13700K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/230500/intel-core-i713700k-processor-30m-cache-up-to-5-40-ghz/specifications.html"),
    ("i7-13700KF","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/230489/intel-core-i713700kf-processor-30m-cache-up-to-5-40-ghz/specifications.html"),
    ("i5-13600K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/230493/intel-core-i513600k-processor-24m-cache-up-to-5-10-ghz/specifications.html"),
    ("i9-14900K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/236773/intel-core-i9-processor-14900k-36m-cache-up-to-6-00-ghz/specifications.html"),
    ("i7-14700K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/236783/intel-core-i7-processor-14700k-33m-cache-up-to-5-60-ghz/specifications.html"),
    ("i5-14600K","LGA1700",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/236799/intel-core-i5-processor-14600k-24m-cache-up-to-5-30-ghz/specifications.html"),
    ("Ultra 9 285K","LGA1851",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/241060/intel-core-ultra-9-processor-285k-36m-cache-up-to-5-70-ghz/specifications.html"),
    ("Ultra 7 265K","LGA1851",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/241063/intel-core-ultra-7-processor-265k-30m-cache-up-to-5-50-ghz/specifications.html"),
    ("Ultra 5 245K","LGA1851",(37.5,45),"https://www.intel.com/content/www/us/en/products/sku/241067/intel-core-ultra-5-processor-245k-24m-cache-up-to-5-20-ghz/specifications.html"),
    ("i7-3930K","LGA2011",(45,52.5),"https://www.intel.com/content/www/us/en/products/sku/63697/intel-core-i73930k-processor-12m-cache-up-to-3-80-ghz/specifications.html"),
    ("i7-5960X","LGA2011",(45,52.5),"https://www.intel.com/content/www/us/en/products/sku/82930/intel-core-i75960x-processor-extreme-edition-20m-cache-up-to-3-50-ghz/specifications.html"),
    ("i9-10980XE","LGA2066",None,"https://www.intel.com/content/www/us/en/products/sku/198017/intel-core-i910980xe-extreme-edition-processor-24-75m-cache-3-00-ghz/specifications.html"),
)

_AMD = (
    ("AMD Ryzen 3 1200","AM4","Ryzen 1000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-1000-series/amd-ryzen-3-1200.html"),
    ("AMD Ryzen 3 3200G","AM4","Ryzen 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-3000-series/amd-ryzen-3-3200g.html"),
    ("AMD Athlon 3000G","AM4","Athlon 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/athlon/athlon-3000-series/amd-athlon-3000g.html"),
    ("AMD Ryzen 5 5600","AM4","Ryzen 5000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-5-5600.html"),
    ("AMD Ryzen 7 5800X","AM4","Ryzen 5000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-7-5800x.html"),
    ("AMD Ryzen 5 1600","AM4","Ryzen 1000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-1000-series/amd-ryzen-5-1600.html"),
    ("AMD Ryzen 7 1700","AM4","Ryzen 1000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-1000-series/amd-ryzen-7-1700.html"),
    ("AMD Ryzen 7 2700X","AM4","Ryzen 2000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-2000-series/amd-ryzen-7-2700x.html"),
    ("AMD Ryzen 5 3600","AM4","Ryzen 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-3000-series/amd-ryzen-5-3600.html"),
    ("AMD Ryzen 7 3700X","AM4","Ryzen 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-3000-series/amd-ryzen-7-3700x.html"),
    ("AMD Ryzen 9 3900X","AM4","Ryzen 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-3000-series/amd-ryzen-9-3900x.html"),
    ("AMD Ryzen 9 3950X","AM4","Ryzen 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-3000-series/amd-ryzen-9-3950x.html"),
    ("AMD Ryzen 5 5600X","AM4","Ryzen 5000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-5-5600x.html"),
    ("AMD Ryzen 7 5700X","AM4","Ryzen 5000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-7-5700x.html"),
    ("AMD Ryzen 7 5800X3D","AM4","Ryzen 5000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-7-5800x3d.html"),
    ("AMD Ryzen 9 5900X","AM4","Ryzen 5000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-9-5900x.html"),
    ("AMD Ryzen 9 5950X","AM4","Ryzen 5000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-5000-series/amd-ryzen-9-5950x.html"),
    ("AMD Ryzen 5 7600X","AM5","Ryzen 7000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-7000-series/amd-ryzen-5-7600x.html"),
    ("AMD Ryzen 7 7700X","AM5","Ryzen 7000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-7000-series/amd-ryzen-7-7700x.html"),
    ("AMD Ryzen 9 7900X","AM5","Ryzen 7000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-7000-series/amd-ryzen-9-7900x.html"),
    ("AMD Ryzen 9 7950X","AM5","Ryzen 7000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-7000-series/amd-ryzen-9-7950x.html"),
    ("AMD Ryzen 7 7800X3D","AM5","Ryzen 7000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-7000-series/amd-ryzen-7-7800x3d.html"),
    ("AMD Ryzen 9 7950X3D","AM5","Ryzen 7000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-7000-series/amd-ryzen-9-7950x3d.html"),
    ("AMD Ryzen 5 9600X","AM5","Ryzen 9000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-9000-series/amd-ryzen-5-9600x.html"),
    ("AMD Ryzen 7 9700X","AM5","Ryzen 9000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-9000-series/amd-ryzen-7-9700x.html"),
    ("AMD Ryzen 9 9950X","AM5","Ryzen 9000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-9000-series/amd-ryzen-9-9950x.html"),
    ("AMD Ryzen 7 9800X3D","AM5","Ryzen 9000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen/ryzen-9000-series/amd-ryzen-7-9800x3d.html"),
    ("AMD Ryzen Threadripper 1950X","sTR4","Ryzen Threadripper 1000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-1000-series/amd-ryzen-threadripper-1950x.html"),
    ("AMD Ryzen Threadripper 2950X","sTR4","Ryzen Threadripper 2000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-2000-series/amd-ryzen-threadripper-2950x.html"),
    ("AMD Ryzen Threadripper 2990WX","sTR4","Ryzen Threadripper 2000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-2000-series/amd-ryzen-threadripper-2990wx.html"),
    ("AMD Ryzen Threadripper 3960X","sTRX4","Ryzen Threadripper 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-3000-series/amd-ryzen-threadripper-3960x.html"),
    ("AMD Ryzen Threadripper 3970X","sTRX4","Ryzen Threadripper 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-3000-series/amd-ryzen-threadripper-3970x.html"),
    ("AMD Ryzen Threadripper 3990X","sTRX4","Ryzen Threadripper 3000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-3000-series/amd-ryzen-threadripper-3990x.html"),
    ("AMD Ryzen Threadripper PRO 3995WX","sWRX8","Ryzen Threadripper PRO 3000 WX-Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper-pro/ryzen-threadripper-pro-3000wx-series/amd-ryzen-threadripper-pro-3995wx.html"),
    ("AMD Ryzen Threadripper PRO 5975WX","sWRX8","Ryzen Threadripper PRO 5000 WX-Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper-pro/ryzen-threadripper-pro-5000wx-series/amd-ryzen-threadripper-pro-5975wx.html"),
    ("AMD Ryzen Threadripper PRO 5995WX","sWRX8","Ryzen Threadripper PRO 5000 WX-Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper-pro/ryzen-threadripper-pro-5000wx-series/amd-ryzen-threadripper-pro-5995wx.html"),
    ("AMD Ryzen Threadripper 7960X","sTR5","Ryzen Threadripper 7000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-7000-series/amd-ryzen-threadripper-7960x.html"),
    ("AMD Ryzen Threadripper 7980X","sTR5","Ryzen Threadripper 7000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-7000-series/amd-ryzen-threadripper-7980x.html"),
    ("AMD Ryzen Threadripper PRO 7995WX","sTR5","Ryzen Threadripper PRO 7000 WX-Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper-pro/amd-ryzen-threadripper-pro-7000-wx-series/amd-ryzen-threadripper-pro-7995wx.html"),
    ("AMD Ryzen Threadripper 9980X","sTR5","Ryzen Threadripper 9000 Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper/ryzen-threadripper-9000-series/amd-ryzen-threadripper-9980x.html"),
    ("AMD Ryzen Threadripper PRO 9995WX","sTR5","Ryzen Threadripper PRO 9000 WX-Series","https://www.amd.com/en/support/downloads/drivers.html/processors/ryzen-threadripper-pro/ryzen-threadripper-pro-9000-wx-series/amd-ryzen-threadripper-pro-9995wx.html"),
)


def _unique(values):
    return tuple(dict.fromkeys(values))


def _intel_family(socket):
    if socket in ("LGA1700", "LGA1851"):
        return "intel_lga1700_1851", "intel_rectangle", "lga_rect"
    if socket in ("LGA2011", "LGA2066"):
        return "intel_lga2011_2066", "intel_hedt", "lga_rect"
    return "intel_lga115x_1200", "intel_square", "chip"


def _amd_family(socket):
    if socket == "AM4":
        return "amd_am4", "amd_am4", "chip"
    if socket == "AM5":
        return "amd_am5", "amd_am5_notched", "am5"
    return ("amd_str5" if socket == "sTR5" else "amd_tr4_family"), "amd_threadripper", "lga_rect"


def _record(identity, label, brand, series, socket, family, ihs, style, dimensions,
            source, aliases, *, dimensions_source="", topology_source="", contact_count=None):
    width, length = dimensions if dimensions else (None, None)
    dimension_status = "primary_verified" if dimensions else "unverified_reference"
    contacts = "pga" if socket == "AM4" else "lga"
    # The interface type can be source-known without an exact electrical map.
    # Threadripper geometry is a family reference, not reviewed mechanical CAD.
    topology_status = "unverified_reference" if family.startswith("amd_tr") or family == "amd_str5" else "interface_verified"
    sources = _unique((source, *((dimensions_source,) if dimensions_source else ()),
                       *((topology_source,) if topology_source else ())))
    ascii_label = label.upper().replace("RYZEN THREADRIPPER", "THREADRIPPER")
    package = dict(id=family, model_id=identity, vendor=brand, socket=socket,
        width_mm=width, length_mm=length, substrate_mm=None, ihs_kind=ihs,
        contacts=contacts, pin_count=contact_count,
        notch_profile="threadripper_carrier" if ihs == "amd_threadripper" else ihs,
        label_ascii=ascii_label, status="reviewed" if dimensions else "unverified_reference",
        dimensions_status=dimension_status, topology_status=topology_status,
        source_urls=sources, topology_map_verified=False, internal_layout_verified=False,
        cooler_inferred=False)
    return dict(id=identity, kind="cpu", label=label, brand=brand, series=series,
        socket=socket, package_family=family, style=style, aliases=_unique(aliases),
        source_url=source, sources=sources, reviewed=REVIEWED,
        identity_status="primary_verified", socket_status="primary_verified",
        dimensions_mm=dict(width=width, length=length, height=None),
        dimensions_status=dimension_status,
        dimensions_source=dimensions_source or (source if dimensions else ""),
        mechanical_source_scope="socket_family" if dimensions_source and dimensions_source != source else "sku",
        topology=dict(kind=contacts, contact_count=contact_count,
            count_status="primary_verified" if contact_count is not None else "unverified_reference",
            map_verified=False, status=topology_status, source=topology_source or source),
        cpu_package=package, cooler_inferred=False, cooling_verified=False,
        internal_layout_verified=False, exact_ihs_dimensions_verified=False,
        surface_method="original_shared_family_reference", market_coverage="named_sku_only",
        license="PolyForm-Noncommercial-1.0.0")


def _models():
    rows=[]
    for code, socket, dimensions, url in _INTEL:
        family, ihs, style = _intel_family(socket)
        entry = code.startswith(("Pentium ","Celeron "))
        label = ("Intel " if entry else "Intel Core ") + code
        number = code.rsplit(" ", 1)[-1] if code.startswith("Ultra ") or entry else code.split("-", 1)[1]
        identity = "intel-" + ("ultra-" if code.startswith("Ultra ") else "") + number.lower()
        aliases=[label]
        if entry:
            aliases += ["Intel " + code.split()[0] + " CPU " + number,
                        "Intel " + code.split()[0] + " Processor " + number]
        if code == "i7-870":
            aliases.append("Intel Core i7 CPU 870")
        if code.startswith("Ultra "):
            aliases.append("Intel Core " + code.rsplit(" ",1)[0] + " Processor " + number)
        count = 1700 if socket == "LGA1700" else None
        rows.append(_record(identity,label,"intel",
            code.split()[0] if entry else "Core X-series" if family == "intel_lga2011_2066" else "Core Ultra 200S" if code.startswith("Ultra ") else "Core " + code.split("-",1)[0],
            socket,family,ihs,style,dimensions,url,aliases,
            topology_source=INTEL_PACKAGE_GUIDE,contact_count=count))
    for label, socket, series, url in _AMD:
        family, ihs, style = _amd_family(socket)
        number = label.rsplit(" ",1)[-1]
        identity = "amd-" + ("threadripper-pro-" if "Threadripper PRO" in label else "threadripper-" if "Threadripper" in label else "") + number.lower()
        dimensions = (40.,40.) if socket == "AM5" else None
        count = 1718 if socket == "AM5" else 1331 if socket == "AM4" else None
        topology_source = AMD_AM5_TOPOLOGY if socket == "AM5" else AMD_AM4_TOPOLOGY if socket == "AM4" else AMD_TR_INSTALLATION
        rows.append(_record(identity,label,"amd",series,socket,family,ihs,style,
            dimensions,url,(label,),dimensions_source=AMD_AM5_MECHANICAL if dimensions else "",
            topology_source=topology_source,contact_count=count))
    return tuple(rows)


MODELS = _models()
_BY_ID = {row["id"]: row for row in MODELS}


def get_model(identity):
    """Return detached SKU facts; unknown/non-string IDs never choose a family."""
    row = _BY_ID.get(identity) if isinstance(identity,str) else None
    return deepcopy(row) if row else None


def by_appearance(appearance):
    """Detached drawing descriptor, bound to an exact reviewed CPU identity."""
    if not isinstance(appearance,dict) or appearance.get("kind") not in (None,"cpu"):
        return {}
    row=_BY_ID.get(appearance.get("id")) if isinstance(appearance.get("id"),str) else None
    if not row:
        return {}
    if appearance.get("vendor",row["brand"]) != row["brand"]:
        return {}
    if appearance.get("style",row["style"]) != row["style"]:
        return {}
    if appearance.get("confidence","model") != "model":
        return {}
    return deepcopy(row["cpu_package"])


def extension_rows():
    """Ten-field rows compatible with hardware_appearance, excluding base seeds."""
    return tuple((row["id"],"cpu",row["brand"],"unknown",row["label"],row["style"],
                  None,"neutral",row["source_url"],row["aliases"])
                 for row in MODELS if row["id"] not in SEED_IDS)

