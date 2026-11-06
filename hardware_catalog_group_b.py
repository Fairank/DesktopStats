"""Reviewed Palit, Gainward, GALAX and INNO3D representative designs.

Pure data: import does not inspect hardware or perform I/O. Series features are
illustrative casing language, never a specification shared by every generation.
Only complete product names and unambiguous product codes are exact-model
aliases. Physical fan totals include installed auxiliary fans; VISIBLE_FANS
separately describes the confirmed front plane used by the static illustration.
Optional bundled/add-on fans do not establish an installed physical total.
"""

SERIES = (
    dict(id="palit_gamerock", board_vendor="palit", label="Palit GameRock",
         motif="palit_gamerock", aliases=("gamerock",),
         source_url="https://www.palit.com/palit/vgapro.php?id=4578&lang=en",
         features=("多面切割装饰", "几何切线饰面")),
    dict(id="palit_jetstream", board_vendor="palit", label="Palit JetStream",
         motif="palit_jetstream", aliases=("jetstream",),
         source_url="https://www.palit.com/palit/vgapro.php?id=4818&lang=en",
         features=("工业几何造型", "简洁平直外壳")),
    dict(id="palit_gamingpro", board_vendor="palit", label="Palit GamingPro",
         motif="palit_gamingpro", aliases=("gamingpro", "gaming pro"),
         source_url="https://www.palit.com/palit/vgapro.php?id=4698&lang=en",
         features=("硬朗工业外壳", "利落外壳分区")),
    dict(id="gainward_phantom", board_vendor="gainward", label="Gainward Phantom",
         motif="gainward_phantom", aliases=("phantom",),
         source_url="https://www.gainward.com/main/vgapro.php?id=1163&lang=en",
         features=("装甲外壳轮廓", "斜切装甲线条")),
    dict(id="gainward_phoenix", board_vendor="gainward", label="Gainward Phoenix",
         motif="gainward_phoenix", aliases=("phoenix",),
         source_url="https://www.gainward.com/main/vgapro.php?id=1210&lang=en",
         features=("多边形切面", "一体式框架")),
    dict(id="gainward_ghost", board_vendor="gainward", label="Gainward Ghost",
         motif="gainward_ghost", aliases=("ghost",),
         source_url="https://www.gainward.com/main/vgapro.php?id=1191&lang=en",
         features=("简洁平直外壳", "简洁分区外壳")),
    dict(id="galax_hof", board_vendor="galax", label="GALAX / KFA2 HOF",
         motif="galax_hof", aliases=("hof", "hall of fame"),
         source_url="https://galax.com/en/news/press-release-5080-hof-extreme/",
         features=("多面切割装饰", "一体式框架")),
    dict(id="galax_ex_gamer", board_vendor="galax", label="GALAX / KFA2 EX Gamer",
         motif="galax_ex_gamer", aliases=("ex gamer", "extreme gamer"),
         source_url="https://galax.com/en/product/geforce-rtx-4070-ex-gamer-d6/",
         features=("方正框架轮廓", "利落外壳分区")),
    dict(id="galax_sg", board_vendor="galax", label="GALAX / KFA2 SG",
         motif="galax_sg", aliases=("sg", "serious gaming"),
         source_url="https://galax.com/en/product/geforce-rtx-4070ti-super-sg-plus-1-click-oc/",
         features=("装甲外壳轮廓", "可选外接辅助风扇")),
    # Specific iCHILL phrases must precede the generic, boundary-matched X3.
    dict(id="inno3d_ichill_x3", board_vendor="inno3d", label="INNO3D iCHILL X3",
         motif="inno3d_ichill_x3", aliases=("ichill x3",),
         source_url="https://www.inno3d.com/product/inno3d-geforce-rtx-4070-ichill-x3",
         features=("装甲折线", "几何切线饰面")),
    dict(id="inno3d_ichill_x4", board_vendor="inno3d", label="INNO3D iCHILL X4",
         motif="inno3d_ichill_x4", aliases=("ichill x4",),
         source_url="https://inno3d.com/product/inno3d-geforce-rtx-3080-ichill-x4",
         features=("斜切装甲线条", "侧置辅助风扇")),
    dict(id="inno3d_twin_x2", board_vendor="inno3d", label="INNO3D TWIN X2",
         motif="inno3d_twin_x2", aliases=("twin x2",),
         source_url="https://www.inno3d.com/product/inno3d-geforce-rtx-4070-twin-x2",
         features=("简洁标准外壳", "拉丝金属饰面")),
    dict(id="inno3d_x3", board_vendor="inno3d", label="INNO3D X3",
         motif="inno3d_x3", aliases=("x3",),
         source_url="https://www.inno3d.com/product/inno3d-geforce-rtx-4070-x3-oc",
         features=("简洁平直外壳", "拉丝金属饰面")),
)

# id, kind, silicon vendor, board brand, label, style, physical fans, shroud,
# official source URL, strict complete model/SKU aliases.
CATALOG = (
    # Official front view: three fans. OC product code differs from non-OC.
    ("palit-gamerock-4090-oc", "gpu", "nvidia", "palit",
     "Palit GeForce RTX 4090 GameRock OC", "gpu_axial", 3, "angular",
     "https://www.palit.com/palit/vgapro.php?id=4578&lang=en",
     ("NED4090S19SB-1020G", "Palit GeForce RTX 4090 GameRock OC",
      "GeForce RTX 4090 GameRock OC")),
    # Official front view: three fans, exact 4070 Ti JetStream only.
    ("palit-jetstream-4070ti", "gpu", "nvidia", "palit",
     "Palit GeForce RTX 4070 Ti JetStream", "gpu_axial", 3, "box",
     "https://www.palit.com/palit/vgapro.php?id=4818&lang=en",
     ("NED407T019K9-1043J", "Palit GeForce RTX 4070 Ti JetStream",
      "GeForce RTX 4070 Ti JetStream")),
    # Official front view: three fans. NED407TT... is the OC edition.
    ("palit-gamingpro-4070ti-oc", "gpu", "nvidia", "palit",
     "Palit GeForce RTX 4070 Ti GamingPro OC", "gpu_axial", 3, "angular",
     "https://www.palit.com/palit/vgapro.php?id=4698&lang=en",
     ("NED407TT19K9-1043A", "Palit GeForce RTX 4070 Ti GamingPro OC",
      "GeForce RTX 4070 Ti GamingPro OC")),
    # Official front view/datasheet: three fans; excludes Phantom GS.
    ("gainward-phantom-4090", "gpu", "nvidia", "gainward",
     "Gainward GeForce RTX 4090 Phantom", "gpu_axial", 3, "angular",
     "https://www.gainward.com/main/vgapro.php?id=1163&lang=en",
     ("NED4090019SB-1020P", "Gainward GeForce RTX 4090 Phantom",
      "GeForce RTX 4090 Phantom")),
    # Official front view: three fans. The non-GS code contains S0, not ST.
    ("gainward-phoenix-4080super", "gpu", "nvidia", "gainward",
     "Gainward GeForce RTX 4080 SUPER Phoenix", "gpu_axial", 3, "angular",
     "https://www.gainward.com/main/vgapro.php?id=1210&lang=en",
     ("NED408S019T2-1032X", "Gainward GeForce RTX 4080 SUPER Phoenix",
      "GeForce RTX 4080 SUPER Phoenix")),
    # Official text: a pair of fans. Do not alias the code reused by Ghost V1.
    ("gainward-ghost-4060", "gpu", "nvidia", "gainward",
     "Gainward GeForce RTX 4060 Ghost", "gpu_axial", 2, "box",
     "https://www.gainward.com/main/vgapro.php?id=1191&lang=en",
     ("Gainward GeForce RTX 4060 Ghost", "GeForce RTX 4060 Ghost")),
    # Official release explicitly states 3 x 102 mm front + 1 x 92 mm rear.
    ("galax-hof-5080-extreme", "gpu", "nvidia", "galax",
     "GALAX GeForce RTX 5080 HOF Extreme", "gpu_axial", 4, "soft",
     "https://galax.com/en/news/press-release-5080-hof-extreme/",
     ("GALAX GeForce RTX 5080 HOF Extreme", "GeForce RTX 5080 HOF Extreme")),
    # Official specification: two 92 mm fans and one 102 mm fan (D6 edition).
    ("galax-ex-gamer-4070-d6", "gpu", "nvidia", "galax",
     "GALAX GeForce RTX 4070 EX Gamer 1-Click OC D6", "gpu_axial", 3, "box",
     "https://galax.com/en/product/geforce-rtx-4070-ex-gamer-d6/",
     ("47NOL7MD7JEX", "GALAX GeForce RTX 4070 EX Gamer 1-Click OC D6",
      "GeForce RTX 4070 EX Gamer 1-Click OC D6")),
    # Three installed front fans; a 1-Clip Booster is optional. An inventory
    # name cannot tell whether the user installed it, so physical total is None.
    ("galax-sg-plus-4070tis", "gpu", "nvidia", "galax",
     "GALAX GeForce RTX 4070 Ti SUPER SG Plus 1-Click OC",
     "gpu_axial", None, "angular",
     "https://galax.com/en/product/geforce-rtx-4070ti-super-sg-plus-1-click-oc/",
     ("47UZM5MDAWSG", "GALAX GeForce RTX 4070 Ti SUPER SG Plus 1-Click OC",
      "GeForce RTX 4070 Ti SUPER SG Plus 1-Click OC")),
    # Official product/launch description: three 98 mm fans.
    ("inno3d-ichill-x3-4070", "gpu", "nvidia", "inno3d",
     "INNO3D GeForce RTX 4070 iCHILL X3", "gpu_axial", 3, "angular",
     "https://www.inno3d.com/product/inno3d-geforce-rtx-4070-ichill-x3",
     ("C40703-126XX-186148H", "INNO3D GeForce RTX 4070 iCHILL X3",
      "GeForce RTX 4070 iCHILL X3")),
    # Official product: three 90 mm fans plus one 45 mm MOSFET side fan.
    # This source is the original 10 GB 3080, not Ti, 12 GB or an LHR variant.
    ("inno3d-ichill-x4-3080", "gpu", "nvidia", "inno3d",
     "INNO3D GeForce RTX 3080 iCHILL X4", "gpu_axial", 4, "angular",
     "https://inno3d.com/product/inno3d-geforce-rtx-3080-ichill-x4",
     ("C30804-106XX-1810VA36", "INNO3D GeForce RTX 3080 iCHILL X4",
      "GeForce RTX 3080 iCHILL X4")),
    # Official product/launch description: two 88 mm fans.
    ("inno3d-twin-x2-4070", "gpu", "nvidia", "inno3d",
     "INNO3D GeForce RTX 4070 TWIN X2", "gpu_axial", 2, "box",
     "https://www.inno3d.com/product/inno3d-geforce-rtx-4070-twin-x2",
     ("INNO3D GeForce RTX 4070 TWIN X2", "GeForce RTX 4070 TWIN X2")),
    # Official product/launch description: three 88 mm fans. Excludes non-OC.
    ("inno3d-x3-4070-oc", "gpu", "nvidia", "inno3d",
     "INNO3D GeForce RTX 4070 X3 OC", "gpu_axial", 3, "box",
     "https://www.inno3d.com/product/inno3d-geforce-rtx-4070-x3-oc",
     ("N40703-126XX-185252L", "INNO3D GeForce RTX 4070 X3 OC",
      "GeForce RTX 4070 X3 OC")),
)

MODEL_SERIES = {
    "palit-gamerock-4090-oc": "palit_gamerock",
    "palit-jetstream-4070ti": "palit_jetstream",
    "palit-gamingpro-4070ti-oc": "palit_gamingpro",
    "gainward-phantom-4090": "gainward_phantom",
    "gainward-phoenix-4080super": "gainward_phoenix",
    "gainward-ghost-4060": "gainward_ghost",
    "galax-hof-5080-extreme": "galax_hof",
    "galax-ex-gamer-4070-d6": "galax_ex_gamer",
    "galax-sg-plus-4070tis": "galax_sg",
    "inno3d-ichill-x3-4070": "inno3d_ichill_x3",
    "inno3d-ichill-x4-3080": "inno3d_ichill_x4",
    "inno3d-twin-x2-4070": "inno3d_twin_x2",
    "inno3d-x3-4070-oc": "inno3d_x3",
}

# Confirmed front plane, independent of physical total. Never turn an optional
# auxiliary configuration into a claim that exactly three fans are installed.
VISIBLE_FANS = {
    "galax-hof-5080-extreme": 3,
    "galax-sg-plus-4070tis": 3,
    "inno3d-ichill-x4-3080": 3,
}
