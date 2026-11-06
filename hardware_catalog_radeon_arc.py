"""Reviewed AMD Radeon / Intel Arc era-specific board appearances.

Pure static data: importing this module performs no discovery, downloads or I/O.
Every casing is a simplified study of the cited complete representative SKU,
not a promise about all cards carrying its chip or marketing-family name.
Empty family aliases deliberately keep older coolers out of current-series
matching. Reference coolers require an explicitly qualified complete alias.
Tier is relative to that era; it is not a present-day performance comparison.
"""

_MSI = "https://storage-asset.msi.com/datasheet/vga/global/"


def _series(identifier, board, label, era, tier, source, features, *, legacy=False):
    return dict(id=identifier, board_vendor=board, label=label, motif=identifier,
                aliases=(), source_url=source, features=features,
                era=era, tier=tier, legacy=legacy)


SERIES = (
    _series("msi_hd4870_reference", "msi", "MSI Reference · Radeon HD 4870", "radeon_hd", "reference",
            _MSI + "R4870T2D512OC.pdf", ("弧形端部开口", "一体式框架"), legacy=True),
    _series("msi_hd5450_passive", "msi", "MSI Passive LP · Radeon HD 5450", "radeon_hd", "entry",
            "https://storage-asset.msi.com/datasheet/vga/my/R5450-MD1GD3HLP.pdf",
            ("外露板卡布局", "外露散热鳍片"), legacy=True),
    _series("msi_hd5870_reference", "msi", "MSI Reference · Radeon HD 5870", "radeon_hd", "reference",
            "https://storage-asset.msi.com/datasheet/vga/ua/R5870PM2D1G.pdf",
            ("简洁平直外壳", "利落外壳分区"), legacy=True),
    _series("msi_twin_frozr_hd7970", "msi", "MSI Twin Frozr · Radeon HD 7970", "radeon_hd", "flagship",
            _MSI + "R7970_TF_3GD5OC_BE.pdf", ("拉丝金属饰面", "外露热管轮廓"), legacy=True),
    _series("msi_r9_290x_reference", "msi", "MSI Reference · Radeon R9 290X", "r9", "reference",
            _MSI + "R9-290X-4GD5.pdf", ("流线弧形外壳", "一体式框架"), legacy=True),
    _series("asus_strix_fury", "asus", "ASUS STRIX · Radeon R9 Fury", "r9", "flagship",
            "https://www.asus.com/it/news/ohcitiw9wqe49eh8/",
            ("锐角动感线条", "装甲折线"), legacy=True),
    _series("msi_rx480_reference", "msi", "MSI Reference · Radeon RX 480", "rx400", "reference",
            _MSI + "AMD-Radeon-RX-480-8G.pdf", ("简洁标准外壳", "一体式框架"), legacy=True),
    _series("sapphire_nitro_polaris", "sapphire", "SAPPHIRE NITRO+ · Polaris", "rx500", "mainstream",
            "https://www.sapphiretech.com/en/consumer/nitro-rx-580-8g-g5",
            ("简约外框轮廓", "简洁低调护罩"), legacy=True),
    _series("msi_vega64_reference", "msi", "MSI Reference · Radeon RX Vega 64", "vega", "reference",
            _MSI + "Radeon-RX-Vega-64-8G.pdf", ("简洁平直外壳", "一体式框架"), legacy=True),
    _series("asrock_challenger_rdna1", "asrock", "ASRock Challenger D · RDNA 1", "rdna1", "entry",
            "https://asrock.com/Graphics-Card/AMD/Radeon%20RX%205500%20XT%20Challenger%20D%208G%20OC/",
            ("斜向连接桥", "简洁分区外壳"), legacy=True),
    _series("msi_rx5700xt_reference", "msi", "MSI Reference · Radeon RX 5700 XT", "rdna1", "reference",
            _MSI + "Radeon-RX-5700-XT-8G.pdf", ("流线弧形外壳", "利落外壳分区"), legacy=True),
    _series("sapphire_pulse_rdna2_lp", "sapphire", "SAPPHIRE PULSE LP · RDNA 2", "rdna2", "entry",
            "https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-6400-4g-gddr6",
            ("外露板卡布局", "简洁低调护罩")),
    _series("asus_tuf_rdna2", "asus", "ASUS TUF Gaming · RDNA 2", "rdna2", "flagship",
            "https://www.asus.com/motherboards-components/graphics-cards/tuf-gaming/tuf-rx6800xt-o16g-gaming/",
            ("拉丝金属饰面", "斜切装甲线条")),
    _series("sapphire_pulse_rdna3", "sapphire", "SAPPHIRE PULSE · RDNA 3", "rdna3", "mainstream",
            "https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-7900-xt-20g-gddr6",
            ("简洁平直外壳", "利落外壳分区")),
    _series("asrock_taichi_rdna4", "asrock", "ASRock Taichi · RDNA 4", "rdna4", "flagship",
            "https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%209070%20XT%20Taichi%2016GB%20OC/",
            ("中央环形饰框", "多面切割装饰")),
    _series("asrock_challenger_arc_a380", "asrock", "ASRock Challenger ITX · Arc A380", "arc_a", "entry",
            "https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20A380%20Challenger%20ITX%206GB%20OC/index.asp",
            ("简约外框轮廓", "斜切装甲线条")),
    _series("sparkle_titan_arc_a750", "sparkle", "SPARKLE TITAN · Arc A750", "arc_a", "mainstream",
            "https://www.sparkle.com.tw/files/20240202122437352.pdf",
            ("方正框架轮廓", "利落外壳分区")),
    _series("acer_bifrost_arc_a770", "acer", "Acer Predator BiFrost · Arc A770", "arc_a", "flagship",
            "https://www.acer.com/us-en/predator/desktops-and-all-in-ones/components/predator-bifrost-intel-arc-a770-oc",
            ("简洁分区外壳", "贯通风道")),
    _series("asrock_challenger_arc_b570", "asrock", "ASRock Challenger · Arc B570", "arc_b", "entry",
            "https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20B570%20Challenger%2010GB%20OC/",
            ("工业几何造型", "斜向连接桥")),
    _series("sparkle_titan_arc_b580", "sparkle", "SPARKLE TITAN · Arc B580", "arc_b", "mainstream",
            "https://www.sparkle.com.tw/files/20241203213858182.pdf",
            ("简洁分区外壳", "斜向连接桥")),
)

# id, kind, chip vendor, board vendor, complete model, style, physical fans,
# shroud, official source, strict complete model/SKU aliases. The MSI reference
# photos show radial blowers; no generic Radeon chip name asserts that cooler.
CATALOG = (
    ("msi-hd4870-t2d512-oc-reference", "gpu", "amd", "msi",
     "MSI Radeon HD 4870 R4870-T2D512-OC Reference", "gpu_blower", 1, "soft", SERIES[0]["source_url"],
     ("MSI Radeon HD 4870 R4870-T2D512-OC Reference", "MSI R4870-T2D512-OC Reference")),
    ("msi-hd5450-md1gd3h-lp", "gpu", "amd", "msi",
     "MSI Radeon HD 5450 R5450-MD1GD3H/LP", "gpu_axial", 0, "box", SERIES[1]["source_url"],
     ("MSI Radeon HD 5450 R5450-MD1GD3H/LP", "R5450-MD1GD3H/LP")),
    ("msi-hd5870-pm2d1g-reference", "gpu", "amd", "msi",
     "MSI Radeon HD 5870 R5870-PM2D1G Reference", "gpu_blower", 1, "box", SERIES[2]["source_url"],
     ("MSI Radeon HD 5870 R5870-PM2D1G Reference", "MSI R5870-PM2D1G Reference")),
    ("msi-hd7970-tf-3gd5-oc-be", "gpu", "amd", "msi",
     "MSI Radeon HD 7970 R7970 TF 3GD5/OC BE", "gpu_axial", 2, "box", SERIES[3]["source_url"],
     ("MSI Radeon HD 7970 R7970 TF 3GD5/OC BE", "R7970 TF 3GD5/OC BE")),
    ("msi-r9-290x-4gd5-reference", "gpu", "amd", "msi",
     "MSI Radeon R9 290X 4GD5 Reference", "gpu_blower", 1, "box", SERIES[4]["source_url"],
     ("MSI Radeon R9 290X 4GD5 Reference", "MSI R9 290X 4GD5 Reference")),
    ("asus-strix-r9fury-dc3-4g", "gpu", "amd", "asus",
     "ASUS STRIX Radeon R9 Fury DC3 4G GAMING", "gpu_axial", 3, "angular", SERIES[5]["source_url"],
     ("STRIX-R9FURY-DC3-4G-GAMING", "ASUS STRIX Radeon R9 Fury DC3 4G GAMING")),
    ("msi-rx480-8g-reference", "gpu", "amd", "msi",
     "MSI Radeon RX 480 8G Reference", "gpu_blower", 1, "box", SERIES[6]["source_url"],
     ("MSI Radeon RX 480 8G Reference", "MSI AMD Radeon RX 480 8G Reference")),
    # Standard 11265-01-20G only, not the separate Special/Limited Editions.
    ("sapphire-nitro-rx580-8g-01", "gpu", "amd", "sapphire",
     "SAPPHIRE NITRO+ Radeon RX 580 8G G5 11265-01-20G", "gpu_axial", 2, "soft", SERIES[7]["source_url"],
     ("11265-01-20G", "SAPPHIRE NITRO+ Radeon RX 580 8G G5 11265-01-20G")),
    ("msi-vega64-8g-reference", "gpu", "amd", "msi",
     "MSI Radeon RX Vega 64 8G Reference", "gpu_blower", 1, "box", SERIES[8]["source_url"],
     ("MSI Radeon RX Vega 64 8G Reference",)),
    ("asrock-rx5500xt-challenger-d-8g", "gpu", "amd", "asrock",
     "ASRock Radeon RX 5500 XT Challenger D 8G OC", "gpu_axial", 2, "angular", SERIES[9]["source_url"],
     ("RX5500XT CLD 8GO", "ASRock Radeon RX 5500 XT Challenger D 8G OC")),
    ("msi-rx5700xt-8g-reference", "gpu", "amd", "msi",
     "MSI Radeon RX 5700 XT 8G Reference", "gpu_blower", 1, "soft", SERIES[10]["source_url"],
     ("MSI Radeon RX 5700 XT 8G Reference",)),
    ("sapphire-pulse-rx6400-4g-lp", "gpu", "amd", "sapphire",
     "SAPPHIRE PULSE Radeon RX 6400 4GB 11315-01-20G", "gpu_axial", 1, "box", SERIES[11]["source_url"],
     ("11315-01-20G", "SAPPHIRE PULSE Radeon RX 6400 4GB 11315-01-20G")),
    ("asus-tuf-rx6800xt-o16g", "gpu", "amd", "asus",
     "ASUS TUF Gaming Radeon RX 6800 XT OC 16GB", "gpu_axial", 3, "angular", SERIES[12]["source_url"],
     ("TUF-RX6800XT-O16G-GAMING", "ASUS TUF Gaming Radeon RX 6800 XT OC 16GB")),
    ("sapphire-pulse-rx7900xt-20g", "gpu", "amd", "sapphire",
     "SAPPHIRE PULSE Radeon RX 7900 XT 20GB 11323-02-20G", "gpu_axial", 3, "box", SERIES[13]["source_url"],
     ("11323-02-20G", "SAPPHIRE PULSE Radeon RX 7900 XT 20GB 11323-02-20G")),
    ("asrock-taichi-rx9070xt-16g-oc", "gpu", "amd", "asrock",
     "ASRock AMD Radeon RX 9070 XT Taichi 16GB OC", "gpu_axial", 3, "angular", SERIES[14]["source_url"],
     ("ASRock AMD Radeon RX 9070 XT Taichi 16GB OC",)),
    ("asrock-a380-challenger-itx-6g", "gpu", "intel", "asrock",
     "ASRock Intel Arc A380 Challenger ITX 6GB OC", "gpu_axial", 1, "angular", SERIES[15]["source_url"],
     ("A380 CLI 6GO", "ASRock Intel Arc A380 Challenger ITX 6GB OC")),
    # The official PDF says SA750T-8GOC (8 GB); the product HTML has a 16GOC typo.
    ("sparkle-a750-titan-8g-oc", "gpu", "intel", "sparkle",
     "SPARKLE Intel Arc A750 TITAN OC Edition 8GB", "gpu_axial", 3, "box", SERIES[16]["source_url"],
     ("SA750T-8GOC", "SPARKLE Intel Arc A750 TITAN OC Edition 8GB")),
    # Official hybrid cooler: small blower left, 92 mm axial right. The blower
    # diameter is unpublished; its illustration is not a dimensional assertion.
    ("acer-bifrost-a770-16g-oc", "gpu", "intel", "acer",
     "Acer Predator BiFrost Intel Arc A770 OC 16GB", "gpu_hybrid", 2, "box", SERIES[17]["source_url"],
     ("APBF-IA770-16G-OC", "Acer Predator BiFrost Intel Arc A770 OC 16GB")),
    ("asrock-b570-challenger-10g-oc", "gpu", "intel", "asrock",
     "ASRock Intel Arc B570 Challenger 10GB OC", "gpu_axial", 2, "angular", SERIES[18]["source_url"],
     ("B570 CL 10GO", "ASRock Intel Arc B570 Challenger 10GB OC")),
    ("sparkle-b580-titan-12g-oc", "gpu", "intel", "sparkle",
     "SPARKLE Intel Arc B580 TITAN OC Edition 12GB", "gpu_axial", 3, "angular", SERIES[19]["source_url"],
     ("SB580T-12GOC", "SPARKLE Intel Arc B580 TITAN OC Edition 12GB")),
)

MODEL_SERIES = {model[0]: series["id"] for model, series in zip(CATALOG, SERIES)}

# Precomputed canonical ASIC identity disambiguates board part numbers from
# chip names and permits cross-era name/model conflict rejection without I/O.
MODEL_CHIPS = dict(zip((row[0] for row in CATALOG), (
    "AMD Radeon HD 4870", "AMD Radeon HD 5450", "AMD Radeon HD 5870",
    "AMD Radeon HD 7970", "AMD Radeon R9 290X", "AMD Radeon R9 Fury",
    "AMD Radeon RX 480", "AMD Radeon RX 580", "AMD Radeon RX Vega 64",
    "AMD Radeon RX 5500 XT", "AMD Radeon RX 5700 XT", "AMD Radeon RX 6400",
    "AMD Radeon RX 6800 XT", "AMD Radeon RX 7900 XT", "AMD Radeon RX 9070 XT",
    "Intel Arc A380", "Intel Arc A750", "Intel Arc A770", "Intel Arc B570", "Intel Arc B580",
)))

# All reviewed coolers' physical fans are visible on their front. This includes
# the differently sized and differently typed pair on Acer BiFrost, not two
# equal axial fans. No fan count here comes from telemetry or zero-RPM modes.
VISIBLE_FANS = {row[0]: row[6] for row in CATALOG}
