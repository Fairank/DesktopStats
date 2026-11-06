"""Additional, source-linked product families of the original six board makers.

No I/O at import. Exact aliases never transfer fan counts to adjacent editions.
VISIBLE_FANS describes this illustration's front view, not the physical total.
"""


def _series(identifier, brand, label, aliases, source, features):
    return dict(id=identifier, board_vendor=brand, label=label, motif=identifier,
                aliases=aliases, source_url=source, features=features)


def _model(identifier, brand, label, fans, source, aliases=(), *, vendor="nvidia", shroud="angular"):
    return (identifier, "gpu", vendor, brand, label, "gpu_axial", fans, shroud,
            source, (label, *aliases))


_ASTRAL = "https://rog.asus.com/graphics-cards/graphics-cards/rog-astral/rog-astral-rtx5080-o16g-gaming/"
_PRIME = "https://www.asus.com/motherboards-components/graphics-cards/prime/prime-rtx5080-o16g/"
_PROART = "https://press.asus.com/news/press-releases/asus-proart-geforce-rtx-50-series/"
_EXPERT = "https://www.msi.com/Graphics-Card/GeForce-RTX-4080-SUPER-16G-EXPERT"
_VANGUARD = "https://storage-asset.msi.com/datasheet/vga/cn/GeForce-RTX-5080-16G-VANGUARD-SOC.pdf"
_INSPIRE = "https://www.msi.com/Graphics-Card/GeForce-RTX-5080-16G-INSPIRE-3X-OC/Overview"
_SHADOW = "https://storage-asset.msi.com/datasheet/vga/sg/GeForce-RTX-5080-16G-SHADOW-3X-OC.pdf"
_GAMING = "https://www.gigabyte.com/Graphics-Card/GV-N5070GAMING-OC-12GD"
_EAGLE = "https://www.gigabyte.com/Graphics-Card/GV-N5070EAGLE-OC-12GD"
_TWIN = "https://mktportal.zotac.com/uploadPath/ZT-D40610E-10M-brochure_4.pdf"
_SOLID = "https://www.zotac.com/download/mediadrivers/External/GraphicsCard/5080/Brochure/ZT-B50800D-10P-brochure.pdf"
_INFINITY = "https://www.zotac.com/download/mediadrivers/External/GraphicsCard/5080/Brochure/ZT-B50800B-10P-brochure.pdf"
_AIRO = "https://www.zotac.com/us/news/zotac-gaming-announces-geforce-rtx-40-super-series?l=en"
_PURE = "https://www.sapphiretech.com/en/consumer/pure-radeon-rx-7800-xt-16g-gddr6"
_FIGHTER = "https://www.powercolor.com/product-detail33.htm"
_REAPER = "https://www.powercolor.com/product-detail212.htm"

SERIES = (
    _series("asus_astral", "asus", "ASUS ROG Astral", ("rog astral",), _ASTRAL, ("一体式框架", "背置辅助风扇")),
    _series("asus_prime", "asus", "ASUS Prime", ("prime",), _PRIME, ("简洁平直外壳", "简洁分区外壳")),
    _series("asus_proart", "asus", "ASUS ProArt", ("proart",), _PROART, ("简洁平直外壳", "简洁分区外壳")),
    _series("msi_expert", "msi", "MSI EXPERT", ("expert",), _EXPERT, ("双面推拉布局", "一体式框架")),
    _series("msi_vanguard", "msi", "MSI VANGUARD", ("vanguard",), _VANGUARD, ("装甲外壳轮廓", "多面切割装饰")),
    _series("msi_inspire", "msi", "MSI INSPIRE", ("inspire",), _INSPIRE, ("方正框架轮廓", "方格面板分区")),
    _series("msi_shadow", "msi", "MSI SHADOW", ("shadow",), _SHADOW, ("简洁低调护罩", "利落硬直线条")),
    _series("gigabyte_gaming_oc", "gigabyte", "GIGABYTE GAMING OC", ("gaming oc",), _GAMING, ("装甲外壳轮廓", "环状灯效语言")),
    _series("gigabyte_eagle", "gigabyte", "GIGABYTE EAGLE", ("eagle",), _EAGLE, ("利落硬直线条", "简洁分区外壳")),
    _series("zotac_twin_edge", "zotac", "ZOTAC Twin Edge", ("twin edge",), _TWIN, ("几何切线饰面", "简约外框轮廓")),
    _series("zotac_solid", "zotac", "ZOTAC SOLID", ("solid",), _SOLID, ("方正框架轮廓", "多边形切面")),
    _series("zotac_amp_infinity", "zotac", "ZOTAC AMP Extreme INFINITY", ("amp extreme infinity",), _INFINITY, ("一体式框架", "长条灯带")),
    _series("zotac_amp_airo", "zotac", "ZOTAC AMP Extreme AIRO", ("amp extreme airo",), _AIRO, ("流线弧形外壳", "灯效饰面")),
    _series("zotac_trinity", "zotac", "ZOTAC Trinity", ("trinity",), _AIRO, ("流线弧形外壳", "简洁分区外壳")),
    _series("sapphire_pure", "sapphire", "SAPPHIRE PURE", ("pure",), _PURE, ("一体式框架", "方正框架轮廓")),
    _series("powercolor_fighter", "powercolor", "PowerColor Fighter", ("fighter",), _FIGHTER, ("简洁标准外壳", "利落外壳分区")),
    _series("powercolor_reaper", "powercolor", "PowerColor Reaper", ("reaper",), _REAPER, ("简洁低调护罩", "简洁平直外壳")),
)

CATALOG = (
    _model("asus-astral-5080-oc", "asus", "ASUS ROG Astral GeForce RTX 5080 OC Edition 16GB GDDR7", 4, _ASTRAL, ("ROG-ASTRAL-RTX5080-O16G-GAMING",)),
    _model("asus-prime-5080-oc", "asus", "ASUS Prime GeForce RTX 5080 OC Edition 16GB GDDR7", 3, _PRIME, ("PRIME-RTX5080-O16G",), shroud="soft"),
    _model("asus-proart-5080-oc", "asus", "ASUS ProArt GeForce RTX 5080 OC Edition 16GB GDDR7", 3, _PROART, ("PROART-RTX5080-O16G",), shroud="box"),
    _model("msi-expert-4080super", "msi", "MSI GeForce RTX 4080 SUPER 16G EXPERT", 2, _EXPERT, ("GeForce RTX 4080 SUPER 16G EXPERT",), shroud="soft"),
    _model("msi-vanguard-5080soc", "msi", "MSI GeForce RTX 5080 16G VANGUARD SOC", 3, _VANGUARD, ("GeForce RTX 5080 16G VANGUARD SOC",)),
    _model("msi-inspire-5080oc", "msi", "MSI GeForce RTX 5080 16G INSPIRE 3X OC", 3, _INSPIRE, ("GeForce RTX 5080 16G INSPIRE 3X OC",), shroud="box"),
    _model("msi-shadow-5080oc", "msi", "MSI GeForce RTX 5080 16G SHADOW 3X OC", 3, _SHADOW, ("G5080-16S3C",), shroud="box"),
    _model("gigabyte-gaming-5070oc", "gigabyte", "GIGABYTE GeForce RTX 5070 GAMING OC 12G", 3, _GAMING, ("GV-N5070GAMING OC-12GD",)),
    _model("gigabyte-eagle-5070oc", "gigabyte", "GIGABYTE GeForce RTX 5070 EAGLE OC SFF 12G", 3, _EAGLE, ("GV-N5070EAGLE OC-12GD",)),
    _model("zotac-twin-4060ti", "zotac", "ZOTAC GAMING GeForce RTX 4060 Ti 8GB Twin Edge", 2, _TWIN, ("ZT-D40610E-10M",), shroud="soft"),
    _model("zotac-solid-5080", "zotac", "ZOTAC GAMING GeForce RTX 5080 SOLID", 3, _SOLID, ("ZT-B50800D-10P",), shroud="box"),
    _model("zotac-infinity-5080", "zotac", "ZOTAC GAMING GeForce RTX 5080 AMP Extreme INFINITY", 3, _INFINITY, ("ZT-B50800B-10P",)),
    _model("zotac-airo-4080super", "zotac", "ZOTAC GAMING GeForce RTX 4080 SUPER AMP Extreme AIRO", 3, _AIRO, shroud="soft"),
    _model("zotac-trinity-4080super", "zotac", "ZOTAC GAMING GeForce RTX 4080 SUPER Trinity Black Edition", 3, _AIRO, shroud="soft"),
    _model("sapphire-pure-7800xt", "sapphire", "SAPPHIRE PURE AMD Radeon RX 7800 XT 16G GDDR6", 3, _PURE, vendor="amd", shroud="box"),
    _model("powercolor-fighter-7800xt", "powercolor", "PowerColor Fighter AMD Radeon RX 7800 XT 16GB GDDR6", 3, _FIGHTER, ("RX7800XT 16G-F/OC",), vendor="amd", shroud="box"),
    _model("powercolor-reaper-9070xt", "powercolor", "PowerColor Reaper AMD Radeon RX 9070 XT 16GB GDDR6", 3, _REAPER, vendor="amd", shroud="soft"),
)

MODEL_SERIES = dict(zip((row[0] for row in CATALOG), (row["id"] for row in SERIES)))
VISIBLE_FANS = {"asus-astral-5080-oc": 3, "msi-expert-4080super": 1}
