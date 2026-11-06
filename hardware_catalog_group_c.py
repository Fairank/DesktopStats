"""Reviewed Group C series and representative models; pure import-time data.

Series artwork is an original simplified illustration, not a factory drawing
shared by every generation. Aliases require a separately confirmed board brand.
Physical fan counts belong only to the exact model aliases below. No discovery,
driver calls, files, network or background work runs when this module imports.

Reference-board aliases deliberately retain Founders Edition, Reference / Made
by AMD, or Limited Edition. A silicon model alone never identifies its board.
Atlantis precedes the broader Sakura family because its full name contains both.
"""

SERIES = (
    dict(
        id="colorful_vulcan", board_vendor="colorful", label="Colorful iGame Vulcan",
        motif="colorful_vulcan", aliases=("vulcan",),
        source_url="https://test.colorful.cn/en/home/product?id=89dc18fc-c42b-4bea-8e6b-11ad5e8400bc&mid=102",
        features=("斜切装甲线条", "独立侧屏模块"),
    ),
    dict(
        id="colorful_ultra", board_vendor="colorful", label="Colorful iGame Ultra W",
        motif="colorful_ultra", aliases=("ultra w",),
        source_url="https://www.colorfulgroup.com/en/home/product?id=c619c9ae-b48e-4618-b9b4-225e23c83140&mid=102",
        features=("几何切线饰面", "简洁分区外壳"),
    ),
    dict(
        id="colorful_advanced", board_vendor="colorful", label="Colorful iGame Advanced",
        motif="colorful_advanced", aliases=("advanced",),
        source_url="https://test.colorful.cn/en/home/product?id=455a7ef6-46de-4fb5-9400-c11884c02991&mid=102",
        features=("合金装甲外壳", "中央环形饰框"),
    ),
    dict(
        id="maxsun_icraft", board_vendor="maxsun", label="Maxsun iCraft",
        motif="maxsun_icraft", aliases=("icraft",),
        source_url="https://www.maxsun.com/products/ms-rtx5060-icraft-gt-oc8g-aiga",
        features=("简洁平直外壳", "长条灯带"),
    ),
    dict(
        id="maxsun_terminator", board_vendor="maxsun", label="Maxsun Terminator",
        motif="maxsun_terminator", aliases=("terminator", "terminatorx3", "终结者"),
        source_url="https://www.maxsun.com/products/ms-rtx5060ti-trbx3-16g",
        features=("多边形切面", "斜向连接桥"),
    ),
    dict(
        id="yeston_atlantis", board_vendor="yeston", label="Yeston Sakura Atlantis",
        motif="yeston_atlantis", aliases=("sakura atlantis", "atlantis"),
        source_url="https://yestonstore.com/products/yeston-sakura-atlantis-radeon-rx-9070-xt-16g-gddr6-256bit-4nm-video-cards-desktop-computer-pc-graphics-card",
        features=("分层飘带框架", "弧形端部开口"),
    ),
    dict(
        id="yeston_sakura", board_vendor="yeston", label="Yeston SAKURA",
        motif="yeston_sakura", aliases=("sakura",),
        source_url="https://yestonstore.com/products/yeston-sakura-radeon-rx-7800-xt-16g-gddr6-256bit-desktop-computer-graphics-card",
        features=("交叉飘带护罩", "弧形连接框架"),
    ),
    dict(
        # BIOSTAR's official index groups this product by its Radeon RX family;
        # no separate marketing-series name is inferred from box slogans.
        id="biostar_radeon", board_vendor="biostar", label="BIOSTAR Radeon",
        motif="biostar_radeon", aliases=("radeon",), product_line=True,
        source_url="https://www.biostar.com.tw/app/en/vga/export/spec_export.php?S_ID=316",
        features=("简洁标准外壳", "方正框架轮廓"),
    ),
    dict(
        id="nvidia_founders", board_vendor="nvidia", label="NVIDIA Founders Edition",
        motif="nvidia_founders", aliases=("founders edition",),
        source_url="https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/",
        features=("交叉金属框架", "贯通风道"),
    ),
    dict(
        id="amd_reference", board_vendor="amd", label="AMD Radeon Reference",
        motif="amd_reference", aliases=("reference", "made by amd"),
        source_url="https://www.amd.com/en/products/graphics/desktops/radeon/7000-series/amd-radeon-rx-7900xtx.html",
        features=("硬朗工业外壳", "波折装甲边框"),
    ),
    dict(
        id="intel_limited", board_vendor="intel", label="Intel Arc Limited Edition",
        motif="intel_limited", aliases=("limited edition",),
        source_url="https://game.intel.com/stories/intel-arc-graphics-overclocking-101/",
        features=("圆润一体护罩", "环状灯效语言"),
    ),
)

# id, kind, silicon vendor, board brand, label, style, total physical fans,
# shroud, official URL, complete model/SKU aliases.
CATALOG = (
    # Official description explicitly says three Hurricane Scythe Blade fans.
    # Do not extend this to 5080 Vulcan W: its official page lists 3 front +
    # 1 reverse back fan, so that different model is deliberately absent.
    ("colorful-vulcan-4070ti-oc-v", "gpu", "nvidia", "colorful",
     "Colorful iGame GeForce RTX 4070 Ti Vulcan OC-V", "gpu_axial", 3, "angular",
     "https://test.colorful.cn/en/home/product?id=89dc18fc-c42b-4bea-8e6b-11ad5e8400bc&mid=102",
     ("Colorful iGame GeForce RTX 4070 Ti Vulcan OC-V",
      "iGame GeForce RTX 4070 Ti Vulcan OC-V")),
    # Official exact SUPER / OC / W / 16GB-V product says triple-fan cooler.
    ("colorful-ultra-4070ti-super-w-oc-16g-v", "gpu", "nvidia", "colorful",
     "Colorful iGame GeForce RTX 4070 Ti SUPER Ultra W OC 16GB-V", "gpu_axial", 3, "angular",
     "https://www.colorfulgroup.com/en/home/product?id=c619c9ae-b48e-4618-b9b4-225e23c83140&mid=102",
     ("Colorful iGame GeForce RTX 4070 Ti SUPER Ultra W OC 16GB-V",
      "iGame GeForce RTX 4070 Ti SUPER Ultra W OC 16GB-V")),
    # Official description: three fans, with a larger central Gravity Rim fan.
    ("colorful-advanced-4070ti-oc-v", "gpu", "nvidia", "colorful",
     "Colorful iGame GeForce RTX 4070 Ti Advanced OC-V", "gpu_axial", 3, "angular",
     "https://test.colorful.cn/en/home/product?id=455a7ef6-46de-4fb5-9400-c11884c02991&mid=102",
     ("Colorful iGame GeForce RTX 4070 Ti Advanced OC-V",
      "iGame GeForce RTX 4070 Ti Advanced OC-V")),
    # Official cooling spec: 3x90mm fans; front view checked separately.
    ("maxsun-icraft-5060-gt-oc8g-aiga", "gpu", "nvidia", "maxsun",
     "Maxsun MS-RTX5060 iCraft GT OC8G AIGA", "gpu_axial", 3, "soft",
     "https://www.maxsun.com/products/ms-rtx5060-icraft-gt-oc8g-aiga",
     ("Maxsun MS-RTX5060 iCraft GT OC8G AIGA", "MS-RTX5060 iCraft GT OC8G AIGA")),
    # Official product front view: three physical fans. Exact 16G only.
    ("maxsun-terminator-5060ti-x3-16g", "gpu", "nvidia", "maxsun",
     "Maxsun MS-RTX5060Ti TerminatorX3 16G", "gpu_axial", 3, "angular",
     "https://www.maxsun.com/products/ms-rtx5060ti-trbx3-16g",
     ("Maxsun MS-RTX5060Ti TerminatorX3 16G", "MS-RTX5060Ti TerminatorX3 16G",
      "MS-RTX5060Ti TRBX3 16G")),
    # Official store front and angled views show three physical front fans.
    ("yeston-atlantis-rx9070xt-16g", "gpu", "amd", "yeston",
     "Yeston Sakura Atlantis Radeon RX 9070 XT 16G GDDR6 256bit", "gpu_axial", 3, "soft",
     "https://yestonstore.com/products/yeston-sakura-atlantis-radeon-rx-9070-xt-16g-gddr6-256bit-4nm-video-cards-desktop-computer-pc-graphics-card",
     ("Yeston Sakura Atlantis Radeon RX 9070 XT 16G GDDR6 256bit",
      "Yeston Sakura Atlantis Radeon RX 9070 XT 16G GDDR6 256bit 4nm")),
    ("yeston-sakura-rx7800xt-16g", "gpu", "amd", "yeston",
     "Yeston Sakura Radeon RX 7800 XT 16G GDDR6 256bit", "gpu_axial", 3, "soft",
     "https://yestonstore.com/products/yeston-sakura-radeon-rx-7800-xt-16g-gddr6-256bit-desktop-computer-graphics-card",
     ("Yeston Sakura Radeon RX 7800 XT 16G GDDR6 256bit",
      "Yeston Sakura Radeon RX 7800 XT 16G GDDR6 256bit 5nm")),
    # The official indexed spec confirms this SKU. Its direct image endpoint
    # returned HTTP 403 during review: cooling stays unknown, rather than
    # turning a search-index image caption into a physical-fan assertion.
    ("biostar-radeon-rx7600-va7606rm81", "gpu", "amd", "biostar",
     "BIOSTAR Radeon RX 7600 VA7606RM81", "gpu_neutral", None, "box",
     "https://www.biostar.com.tw/app/en/vga/export/spec_export.php?S_ID=316",
     ("BIOSTAR Radeon RX 7600 VA7606RM81", "BIOSTAR VA7606RM81", "VA7606RM81")),
    # Official 5090 gallery shows both physical fans on the same side.
    # 4090 FE's opposed layout is not an alias and does not inherit this view.
    ("nvidia-founders-rtx5090-32g", "gpu", "nvidia", "nvidia",
     "NVIDIA GeForce RTX 5090 Founders Edition 32GB", "gpu_axial", 2, "reference",
     "https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/",
     ("NVIDIA GeForce RTX 5090 Founders Edition 32GB",
      "NVIDIA GeForce RTX 5090 Founders Edition", "GeForce RTX 5090 Founders Edition")),
    # Official AMD product image: three physical fans. Reference identity is
    # required in every alias even though the official silicon page omits it.
    ("amd-reference-rx7900xtx-24g", "gpu", "amd", "amd",
     "AMD Radeon RX 7900 XTX Reference 24GB", "gpu_axial", 3, "reference",
     "https://www.amd.com/en/products/graphics/desktops/radeon/7000-series/amd-radeon-rx-7900xtx.html",
     ("AMD Radeon RX 7900 XTX Reference 24GB", "AMD Radeon RX 7900 XTX Reference",
      "AMD Radeon RX 7900 XTX Made by AMD", "AMD Radeon RX 7900 XTX Made by AMD 24GB")),
    # Intel's A770 Limited Edition teardown explicitly describes dual axial
    # fans, 16 GB memory and a matte rounded enclosure with diffused LED edges.
    ("intel-limited-arc-a770-16g", "gpu", "intel", "intel",
     "Intel Arc A770 Limited Edition 16GB", "gpu_axial", 2, "soft",
     "https://game.intel.com/stories/intel-arc-graphics-overclocking-101/",
     ("Intel Arc A770 Limited Edition 16GB", "Intel Arc A770 Limited Edition")),
)

MODEL_SERIES = {
    "colorful-vulcan-4070ti-oc-v": "colorful_vulcan",
    "colorful-ultra-4070ti-super-w-oc-16g-v": "colorful_ultra",
    "colorful-advanced-4070ti-oc-v": "colorful_advanced",
    "maxsun-icraft-5060-gt-oc8g-aiga": "maxsun_icraft",
    "maxsun-terminator-5060ti-x3-16g": "maxsun_terminator",
    "yeston-atlantis-rx9070xt-16g": "yeston_atlantis",
    "yeston-sakura-rx7800xt-16g": "yeston_sakura",
    "biostar-radeon-rx7600-va7606rm81": "biostar_radeon",
    "nvidia-founders-rtx5090-32g": "nvidia_founders",
    "amd-reference-rx7900xtx-24g": "amd_reference",
    "intel-limited-arc-a770-16g": "intel_limited",
}
