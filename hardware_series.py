"""Small, source-backed GPU series motifs; importing performs no discovery.

Match aliases as normalized boundary phrases only AFTER board_vendor has been
independently confirmed. A series word must never establish the board vendor.
Use product/model names, not a page's generic cooling or marketing description.

Features describe the design language illustrated by the cited official pages,
not exact geometry shared by every generation or SKU. They do not establish fan
count, dimensions, cooling type or physical colors. UI accents are decorative.
More specific series take precedence over generic GAMING/WINDFORCE wording.
"""

SERIES_CATALOG = (
    dict(
        id="asus_dual", board_vendor="asus", label="ASUS Dual", motif="asus_dual",
        aliases=("dual",),
        source_url="https://rog.asus.com/us/articles/gaming-graphics-cards/radeon-rx-6600-xt-graphics-cards-rog-strix-asus-dual/",
        features=("几何切线饰面", "简洁分区外壳"),
    ),
    dict(
        id="asus_tuf", board_vendor="asus", label="ASUS TUF Gaming", motif="asus_tuf",
        aliases=("tuf",),
        source_url="https://rog.asus.com/ca-en/articles/gaming-graphics-cards/check-out-all-of-our-buffed-up-geforce-rtx-3070-rtx-3080-and-rtx-3090-graphics-cards/",
        features=("硬朗工业外壳", "装甲折线"),
    ),
    dict(
        id="asus_rog_strix", board_vendor="asus", label="ASUS ROG Strix", motif="asus_rog_strix",
        aliases=("rog strix",),
        source_url="https://rog.asus.com/us/articles/gaming-graphics-cards/rog-strix-vs-tuf-vs-dual-and-beyond-which-asus-graphics-card-is-right-for-you/",
        features=("斜切装甲线条", "赛博文字饰面"),
    ),
    dict(
        id="msi_ventus", board_vendor="msi", label="MSI VENTUS", motif="msi_ventus",
        aliases=("ventus",),
        source_url="https://www.msi.com/Graphics-Card/GeForce-RTX-3050-VENTUS-2X-8G/Overview",
        features=("工业几何造型", "利落硬直线条"),
    ),
    dict(
        id="msi_suprim", board_vendor="msi", label="MSI SUPRIM", motif="msi_suprim",
        aliases=("suprim",),
        source_url="https://www.msi.com/Graphics-Card/GeForce-RTX-4090-SUPRIM-X-24G/Overview",
        features=("多边形切面", "拉丝金属饰面"),
    ),
    dict(
        id="msi_gaming", board_vendor="msi", label="MSI GAMING", motif="msi_gaming",
        aliases=("gaming",),
        source_url="https://www.msi.com/Graphics-Card/GeForce-RTX-5080-16G-GAMING-TRIO/Overview",
        features=("锐角动感线条", "龙纹装饰"),
    ),
    dict(
        id="gigabyte_aorus", board_vendor="gigabyte", label="GIGABYTE AORUS", motif="gigabyte_aorus",
        aliases=("aorus",),
        source_url="https://www.gigabyte.com/sg/press/news/2038",
        features=("装甲外壳轮廓", "环状灯效语言"),
    ),
    dict(
        id="gigabyte_aero", board_vendor="gigabyte", label="GIGABYTE AERO", motif="gigabyte_aero",
        aliases=("aero",),
        source_url="https://www.gigabyte.com/sg/press/news/2038",
        features=("简洁平直外壳", "侧边标志饰面"),
    ),
    dict(
        id="gigabyte_windforce", board_vendor="gigabyte", label="GIGABYTE WINDFORCE", motif="gigabyte_windforce",
        aliases=("windforce",),
        source_url="https://www.gigabyte.com/ca/press/news/2076",
        features=("简洁标准外壳", "金属背板轮廓"),
    ),
    dict(
        id="zotac_solo", board_vendor="zotac", label="ZOTAC SOLO", motif="zotac_solo",
        aliases=("solo",),
        source_url="https://www.zotac.com/download/mediadrivers/External/GraphicsCard/5060/Brochure/ZT-B50600G-10A-brochure.pdf",
        features=("简约外框轮廓",),
    ),
    dict(
        id="sapphire_pulse", board_vendor="sapphire", label="SAPPHIRE PULSE", motif="sapphire_pulse",
        aliases=("pulse",),
        source_url="https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-9070-16g-gddr6",
        features=("方正框架轮廓", "利落外壳分区"),
    ),
    dict(
        id="sapphire_nitro", board_vendor="sapphire", label="SAPPHIRE NITRO+", motif="sapphire_nitro",
        aliases=("nitro",),
        source_url="https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-16g-gddr6",
        features=("一体式框架", "长条灯带"),
    ),
    dict(
        id="powercolor_hellhound", board_vendor="powercolor", label="PowerColor Hellhound", motif="powercolor_hellhound",
        aliases=("hellhound",),
        source_url="https://www.powercolor.com/news-detail33.htm",
        features=("简洁低调护罩", "灯效饰面"),
    ),
    dict(
        id="powercolor_red_devil", board_vendor="powercolor", label="PowerColor Red Devil", motif="powercolor_red_devil",
        aliases=("red devil",),
        source_url="https://www.powercolor.com/news-detail64.htm",
        features=("棱角装甲饰面", "多面切割装饰"),
    ),
)
