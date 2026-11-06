"""Reviewed NVIDIA legacy board designs; pure data, with no discovery or I/O.

Each era-specific illustration is selected by an exact reviewed SKU, never by
the bare GPU chip or a modern series word. Empty series aliases intentionally
prevent a current GAMING/LIGHTNING/WINDFORCE name inheriting an older cooler.
Tier describes the board/cooler line within its era, not current performance.
The pictures are simplified front-view studies, not dimensional drawings.
"""

_MSI = "https://storage-asset.msi.com/datasheet/vga/global/"
_GTX1080 = "https://www.nvidia.com/en-us/geforce/news/geforce-gtx-1080-founders-edition/"
_GTX780 = "https://nvidianews.nvidia.com/news/nvidia-unveils-geforce-gtx-780-ti-the-best-gaming-gpu-on-the-planet-6622622"
_GT1030 = "https://www.gigabyte.com/Graphics-Card/GV-N1030SL-2GL"
_GTX460 = "https://www.gigabyte.com/Graphics-Card/GV-N460OC-1GI"
_FX5200 = "https://www.gigabyte.com/Graphics-Card/GV-N52128D"


def _series(identifier, board, label, era, tier, source, features):
    return dict(id=identifier, board_vendor=board, label=label, motif=identifier,
                aliases=(), source_url=source, features=features,
                era=era, tier=tier, legacy=True)


SERIES = (
    _series("nvidia_founders_pascal", "nvidia", "NVIDIA Founders · Pascal", "gtx10", "reference",
            _GTX1080, ("多边形切面", "一体式框架")),
    _series("msi_aero_itx_pascal", "msi", "MSI AERO ITX · Pascal", "gtx10", "entry",
            _MSI+"GeForce-GTX-1050-AERO-ITX-2G-OC.pdf", ("简洁标准外壳", "几何切线饰面")),
    _series("msi_low_profile_pascal", "msi", "MSI Low Profile · Pascal", "gtx10", "entry",
            _MSI+"GeForce-GTX-1050-Ti-4GT-LP.pdf", ("简洁平直外壳", "利落外壳分区")),
    _series("msi_gaming_pascal", "msi", "MSI GAMING X · Pascal", "gtx10", "mainstream",
            _MSI+"GeForce-GTX-1080-Ti-GAMING-X-11G.pdf", ("装甲折线", "简洁分区外壳")),
    _series("msi_lightning_pascal", "msi", "MSI LIGHTNING Z · Pascal", "gtx10", "flagship",
            _MSI+"GeForce-GTX-1080-Ti-LIGHTNING-Z.pdf", ("硬朗工业外壳", "多边形切面")),
    _series("gigabyte_silent_pascal", "gigabyte", "GIGABYTE Silent LP · Pascal", "gtx10", "entry",
            _GT1030, ("外露散热鳍片",)),
    _series("msi_gaming_maxwell", "msi", "MSI GAMING · Maxwell", "gtx900", "mainstream",
            _MSI+"GTX-980-Ti-GAMING-6G.pdf", ("斜切装甲线条", "简洁分区外壳")),
    _series("nvidia_reference_kepler", "nvidia", "NVIDIA Reference · Kepler", "gtx700", "reference",
            _GTX780, ("一体式框架", "利落外壳分区")),
    _series("msi_lightning_kepler", "msi", "MSI LIGHTNING · Kepler", "gtx600", "flagship",
            _MSI+"N680GTX_Lightning.pdf", ("装甲外壳轮廓", "外露热管轮廓")),
    _series("msi_twinfrozr_kepler", "msi", "MSI Twin Frozr III · Kepler", "gtx600", "mainstream",
            _MSI+"N660_TF_2GD5OC.pdf", ("拉丝金属饰面", "外露热管轮廓")),
    _series("msi_lightning_fermi", "msi", "MSI LIGHTNING · Fermi", "gtx500", "flagship",
            _MSI+"N580GTX_Lightning.pdf", ("简洁平直外壳", "外露热管轮廓")),
    _series("msi_blower_fermi", "msi", "MSI Blower · Fermi", "gtx400", "mainstream",
            _MSI+"N480GTXM2D15.pdf", ("外露散热鳍片", "一体式框架")),
    _series("gigabyte_windforce_fermi", "gigabyte", "GIGABYTE WINDFORCE 2X · Fermi", "gtx400", "mainstream",
            _GTX460, ("简洁分区外壳", "利落外壳分区")),
    _series("msi_lightning_tesla", "msi", "MSI LIGHTNING · Tesla", "gtx200", "flagship",
            _MSI+"N260GTX_Lightning.pdf", ("拉丝金属饰面", "外露热管轮廓")),
    _series("msi_blower_g80", "msi", "MSI Blower · GeForce 8", "pre_gtx", "mainstream",
            _MSI+"NX8800GTST2D320EHDOC.pdf", ("简洁标准外壳", "利落外壳分区")),
    _series("gigabyte_fx5200", "gigabyte", "GIGABYTE · GeForce FX", "pre_gtx", "entry",
            _FX5200, ("外露板卡布局", "外露散热鳍片")),
)

# id, kind, silicon vendor, board vendor, complete model, style, physical fans,
# shroud, official source, strict complete model/SKU aliases. Front views in the
# cited official PDFs/product images were inspected, not inferred from names.
CATALOG = (
    # NVIDIA explicitly identifies the Founders Edition and its radial blower.
    ("nvidia-gtx1080-founders", "gpu", "nvidia", "nvidia",
     "NVIDIA GeForce GTX 1080 Founders Edition", "gpu_blower", 1, "angular", _GTX1080,
     ("NVIDIA GeForce GTX 1080 Founders Edition", "GeForce GTX 1080 Founders Edition")),
    # Original OC edition, 155 mm; OCV1 is a different, longer reviewed SKU.
    ("msi-gtx1050-aero-itx-2g-oc", "gpu", "nvidia", "msi",
     "MSI GeForce GTX 1050 AERO ITX 2G OC", "gpu_axial", 1, "soft",
     SERIES[1]["source_url"], ("G1050AI2C", "MSI GeForce GTX 1050 AERO ITX 2G OC",
                               "GeForce GTX 1050 AERO ITX 2G OC")),
    ("msi-gtx1050ti-4gt-lp", "gpu", "nvidia", "msi",
     "MSI GeForce GTX 1050 Ti 4GT LP", "gpu_axial", 2, "box",
     SERIES[2]["source_url"], ("MSI GeForce GTX 1050 Ti 4GT LP", "GeForce GTX 1050 Ti 4GT LP")),
    # Twin Frozr VI front, not the later GAMING X TRIO cooler.
    ("msi-gtx1080ti-gaming-x-11g", "gpu", "nvidia", "msi",
     "MSI GeForce GTX 1080 Ti GAMING X 11G", "gpu_axial", 2, "angular",
     SERIES[3]["source_url"], ("G1080TGX11", "MSI GeForce GTX 1080 Ti GAMING X 11G",
                               "GeForce GTX 1080 Ti GAMING X 11G")),
    # Official TRI-FROZR description and front view: three TORX 2.0 fans.
    ("msi-gtx1080ti-lightning-z", "gpu", "nvidia", "msi",
     "MSI GeForce GTX 1080 Ti LIGHTNING Z", "gpu_axial", 3, "angular",
     SERIES[4]["source_url"], ("MSI GeForce GTX 1080 Ti LIGHTNING Z", "GeForce GTX 1080 Ti LIGHTNING Z")),
    # Explicit passive cooler in the official page, not merely a silent mode.
    ("gigabyte-gt1030-silent-lp-2g", "gpu", "nvidia", "gigabyte",
     "GIGABYTE GeForce GT 1030 Silent Low Profile 2G", "gpu_axial", 0, "box", _GT1030,
     ("GV-N1030SL-2GL", "GIGABYTE GeForce GT 1030 Silent Low Profile 2G")),
    ("msi-gtx980ti-gaming-6g", "gpu", "nvidia", "msi",
     "MSI GeForce GTX 980 Ti GAMING 6G", "gpu_axial", 2, "angular",
     SERIES[6]["source_url"], ("MSI GeForce GTX 980 Ti GAMING 6G", "GeForce GTX 980 Ti GAMING 6G")),
    # The launch press image is NVIDIA's stock aluminum/window cooler. Bare
    # 'GTX 780 Ti' never asserts this cooler; an explicit Reference name is needed.
    ("nvidia-gtx780ti-reference", "gpu", "nvidia", "nvidia",
     "NVIDIA GeForce GTX 780 Ti Reference", "gpu_blower", 1, "reference", _GTX780,
     ("NVIDIA GeForce GTX 780 Ti Reference", "GeForce GTX 780 Ti Reference")),
    ("msi-n680gtx-lightning", "gpu", "nvidia", "msi",
     "MSI N680GTX Lightning", "gpu_axial", 2, "angular",
     SERIES[8]["source_url"], ("MSI N680GTX Lightning", "N680GTX Lightning")),
    # Official text confirms dual PWM fans; not the reference N660 SKU.
    ("msi-n660-tf-2gd5-oc", "gpu", "nvidia", "msi",
     "MSI N660 TF 2GD5/OC", "gpu_axial", 2, "box",
     SERIES[9]["source_url"], ("MSI N660 TF 2GD5/OC", "N660 TF 2GD5/OC")),
    # 1536 MB original Lightning, not the 3072 MB Xtreme Edition.
    ("msi-n580gtx-lightning", "gpu", "nvidia", "msi",
     "MSI N580GTX Lightning", "gpu_axial", 2, "box",
     SERIES[10]["source_url"], ("MSI N580GTX Lightning", "N580GTX Lightning")),
    ("msi-n480gtx-m2d15", "gpu", "nvidia", "msi",
     "MSI N480GTX-M2D15", "gpu_blower", 1, "box",
     SERIES[11]["source_url"], ("MSI N480GTX-M2D15", "N480GTX-M2D15")),
    # Original revision only. Rev2/Rev3 have separate product pages, so aliases
    # require Rev1.0; the ambiguous bare board code is intentionally excluded.
    ("gigabyte-gtx460-oc-1g-rev1", "gpu", "nvidia", "gigabyte",
     "GIGABYTE GV-N460OC-1GI Rev. 1.0", "gpu_axial", 2, "soft", _GTX460,
     ("GV-N460OC-1GI Rev. 1.0", "GIGABYTE GV-N460OC-1GI Rev. 1.0")),
    ("msi-n260gtx-lightning", "gpu", "nvidia", "msi",
     "MSI N260GTX Lightning", "gpu_axial", 2, "box",
     SERIES[13]["source_url"], ("MSI N260GTX Lightning", "N260GTX Lightning")),
    # Exact OC 320 MB G80 card; excludes the G92 512 MB and 640 MB models.
    ("msi-nx8800gts-320-oc", "gpu", "nvidia", "msi",
     "MSI NX8800GTS-T2D320E-HD-OC", "gpu_blower", 1, "soft",
     SERIES[14]["source_url"], ("MSI NX8800GTS-T2D320E-HD-OC", "NX8800GTS-T2D320E-HD-OC")),
    # Official product image shows one small active fan, NOT a passive FX card.
    ("gigabyte-fx5200-n52128d", "gpu", "nvidia", "gigabyte",
     "GIGABYTE GV-N52128D GeForce FX 5200", "gpu_axial", 1, "neutral", _FX5200,
     ("GV-N52128D", "GIGABYTE GV-N52128D GeForce FX 5200")),
)

MODEL_SERIES = dict(zip((row[0] for row in CATALOG), (row["id"] for row in SERIES)))

# Explicit ASIC identities from each official specification. Product labels
# such as N680GTX/NX8800GTS are board names, not chip-name word order; matching
# must not reinterpret their prefixes or mistake them for a conflicting ASIC.
MODEL_CHIPS = {
    "nvidia-gtx1080-founders": "NVIDIA GeForce GTX 1080",
    "msi-gtx1050-aero-itx-2g-oc": "NVIDIA GeForce GTX 1050",
    "msi-gtx1050ti-4gt-lp": "NVIDIA GeForce GTX 1050 Ti",
    "msi-gtx1080ti-gaming-x-11g": "NVIDIA GeForce GTX 1080 Ti",
    "msi-gtx1080ti-lightning-z": "NVIDIA GeForce GTX 1080 Ti",
    "gigabyte-gt1030-silent-lp-2g": "NVIDIA GeForce GT 1030",
    "msi-gtx980ti-gaming-6g": "NVIDIA GeForce GTX 980 Ti",
    "nvidia-gtx780ti-reference": "NVIDIA GeForce GTX 780 Ti",
    "msi-n680gtx-lightning": "NVIDIA GeForce GTX 680",
    "msi-n660-tf-2gd5-oc": "NVIDIA GeForce GTX 660",
    "msi-n580gtx-lightning": "NVIDIA GeForce GTX 580",
    "msi-n480gtx-m2d15": "NVIDIA GeForce GTX 480",
    "gigabyte-gtx460-oc-1g-rev1": "NVIDIA GeForce GTX 460",
    "msi-n260gtx-lightning": "NVIDIA GeForce GTX 260",
    "msi-nx8800gts-320-oc": "NVIDIA GeForce 8800 GTS",
    "gigabyte-fx5200-n52128d": "NVIDIA GeForce FX 5200",
}
