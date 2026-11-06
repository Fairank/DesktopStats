"""Reviewed, offline fan appearance hints for exact representative boards.

Only a confirmed exact model selects these profiles. A series/brand name alone
never establishes blade count, physical fan count, diameter, speed or LEDs.
``hub_ratio`` is an artwork estimate, not a measured dimension. ``outer_ring``
means an actual complete blade-tip band; False includes unconfirmed rings.
Decorative chassis rings stay fixed. Shape curvature is simplified artwork.
An unknown blade count uses ``neutral`` with no invented five/six-blade pattern.
Layout separately owns fan positions/diameters and any hidden or optional fans.
``fans`` overrides visible front rotors from left to right. ``direction`` only
records a source-confirmed relative reversal; it is not a tachometer direction.
No file/network/hardware access, timers, mutable runtime caches or discovery.
"""


def _p(technology, label, source_url, *, blades=None, hub_ratio=None,
       outer_ring=False, shape="neutral", evidence="family_description",
       group_size=1, fans=(), hub_shape="circle", model_ids=(), representative=""):
    return dict(technology=technology, label=label, blades=blades,
                hub_ratio=hub_ratio, outer_ring=outer_ring, shape=shape,
                group_size=group_size, source_url=source_url, evidence=evidence,
                fans=fans, hub_shape=hub_shape, model_ids=model_ids,
                representative=representative)


# Exact representative images are linked on the cited official product pages.
# Equal technology names are deliberate; a new series does not invent a fan.
PROFILES = {
    'sapphire_pulse': _p('sapphire_hybrid', 'Hybrid Fan Blade',
        'https://nation.sapphiretech.com/en/news/pulse-rx-7600',
        model_ids=('sapphire-pulse-7600',), representative='SAPPHIRE PULSE RX 7600'
    ),
    'sapphire_nitro': _p('sapphire_aerocurve', 'AeroCurve',
        'https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-16g-gddr6',
        blades=7, hub_ratio=0.3, outer_ring=True, shape='wide', evidence='official_front_view',
        model_ids=('sapphire-nitro-9070xt-oc',), representative='SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC 16GB GDDR6'
    ),
    'powercolor_hellhound': _p('powercolor_ring', 'Ring-fan Blade',
        'https://www.powercolor.com/product-detail31.htm',
        blades=9, hub_ratio=0.3, outer_ring=True, shape='swept', evidence='explicit_count',
        model_ids=('powercolor-hellhound-7800xt-oc',), representative='PowerColor Hellhound AMD Radeon RX 7800 XT 16GB GDDR6'
    ),
    'powercolor_red_devil': _p('powercolor_ring', 'Ring-fan Blade',
        'https://www.powercolor.com/product-detail32.htm',
        blades=9, hub_ratio=0.3, outer_ring=True, shape='swept', evidence='explicit_count',
        model_ids=('powercolor-red-devil-7800xt-oc',), representative='PowerColor Red Devil AMD Radeon RX 7800 XT 16GB GDDR6'
    ),
    'asrock_phantom': _p('asrock_striped_ring', 'Striped Ring Fan',
        'https://pg.asrock.com/Graphics-Card/AMD/Radeon%20RX%207900%20XTX%20Phantom%20Gaming%2024GB%20OC/',
        outer_ring=True, fans=({'direction': 1}, {'direction': -1}, {'direction': 1}),
        model_ids=('asrock-phantom-7900xtx-oc',), representative='ASRock AMD Radeon RX 7900 XTX Phantom Gaming 24GB OC'
    ),
    'asrock_steel_legend': _p('asrock_striped_axial', 'Striped Axial Fan',
        'https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207800%20XT%20Steel%20Legend%2016GB%20OC/',
        model_ids=('asrock-steel-legend-7800xt-oc',), representative='ASRock AMD Radeon RX 7800 XT Steel Legend 16GB OC'
    ),
    'asrock_challenger': _p('asrock_striped_axial', 'Striped Axial Fan',
        'https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207600%20Challenger%208GB%20OC/',
        model_ids=('asrock-challenger-7600-oc',), representative='ASRock AMD Radeon RX 7600 Challenger 8GB OC'
    ),
    'asrock_taichi': _p('asrock_striped_ring', 'Striped Ring Fan',
        'https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%207900%20XTX%20Taichi%2024GB%20OC/',
        outer_ring=True, fans=({'direction': 1}, {'direction': -1}, {'direction': 1}),
        model_ids=('asrock-taichi-7900xtx-oc',), representative='ASRock AMD Radeon RX 7900 XTX Taichi 24GB OC'
    ),
    'xfx_merc': _p('xfx_axial', '轴流风扇',
        'https://www.xfxforce.com/shop/xfx-speedster-merc-310-7900xtx-black-edition',
        model_ids=('xfx-merc310-7900xtx-black',), representative='XFX Speedster MERC 310 AMD Radeon RX 7900 XTX Black Edition 24GB'
    ),
    'xfx_qick': _p('xfx_13_blade', '13 Blade Triple Dissipation',
        'https://www.xfxforce.com/shop/xfx-speedster-qick-319-amd-radeon-tm-rx-6750-xt-core-2',
        blades=13, hub_ratio=0.28, shape='swept', evidence='explicit_count',
        model_ids=('xfx-qick319-6750xt-core-jfdr',), representative='XFX Speedster QICK 319 AMD Radeon RX 6750 XT CORE 12GB'
    ),
    'xfx_swft': _p('xfx_axial', '轴流风扇',
        'https://www.xfxforce.com/shop/xfx-speedster-swft-210-amd-radeon-tm-rx-6600-core',
        model_ids=('xfx-swft210-6600-core-lfdq',), representative='XFX Speedster SWFT 210 AMD Radeon RX 6600 CORE 8GB'
    ),
    'pny_xlr8': _p('pny_axial', '9叶轴流风扇',
        'https://www.pny.com/pny-geforce-rtx-4070-12gb-xlr8-gaming-verto-epic-x-rgb-oc',
        blades=9, hub_ratio=0.33, shape='swept', evidence='official_front_view',
        model_ids=('pny-xlr8-4070-epicx-oc',), representative='PNY GeForce RTX 4070 12GB XLR8 Gaming VERTO EPIC-X RGB Overclocked Triple Fan'
    ),
    'pny_verto': _p('pny_axial', '9叶轴流风扇',
        'https://www.pny.com/geforce-rtx-4070-12gb-verto-dual-fan',
        blades=9, hub_ratio=0.33, shape='swept', evidence='official_front_view',
        model_ids=('pny-verto-4070-dual',), representative='PNY GeForce RTX 4070 12GB VERTO Dual Fan'
    ),
    'evga_ftw3': _p('evga_icx3', 'iCX3',
        'https://www.nvidia.com/en-us/geforce/news/rtx-3080-3090-custom-card-roundup/',
        blades=9, hub_ratio=0.32, shape='wide', evidence='official_front_view',
        model_ids=('evga-ftw3-3080-gaming-kr',), representative='EVGA GeForce RTX 3080 FTW3 GAMING 10GB'
    ),
    'evga_xc3': _p('evga_icx3', 'iCX3',
        'https://www.nvidia.com/en-us/geforce/news/rtx-3080-3090-custom-card-roundup/',
        blades=9, hub_ratio=0.32, shape='wide', evidence='official_front_view',
        model_ids=('evga-xc3-3080-black-kr',), representative='EVGA GeForce RTX 3080 XC3 BLACK GAMING 10GB'
    ),
    'leadtek_hurricane': _p('leadtek_hurricane', 'HURRICANE Vortex',
        'https://www.leadtek.com/eng/news/product_news_detail/1693',
        model_ids=('leadtek-hurricane-4090-24g',), representative='Leadtek WinFast GeForce RTX 4090 HURRICANE 24GB'
    ),
    'palit_gamerock': _p('palit_gale_hunter', 'Gale Hunter',
        'https://www.palit.com/palit/vgapro.php?id=4578&lang=en',
        blades=9, hub_ratio=0.28, shape='claw', evidence='official_front_view',
        model_ids=('palit-gamerock-4090-oc',), representative='Palit GeForce RTX 4090 GameRock OC'
    ),
    'palit_jetstream': _p('palit_gale_hunter', 'Gale Hunter',
        'https://www.palit.com/palit/vgapro.php?id=4818&lang=en',
        blades=9, hub_ratio=0.28, shape='claw', evidence='official_front_view',
        model_ids=('palit-jetstream-4070ti',), representative='Palit GeForce RTX 4070 Ti JetStream'
    ),
    'palit_gamingpro': _p('palit_gale_hunter', 'Gale Hunter',
        'https://www.palit.com/palit/vgapro.php?id=4698&lang=en',
        blades=9, hub_ratio=0.28, shape='claw', evidence='official_front_view',
        model_ids=('palit-gamingpro-4070ti-oc',), representative='Palit GeForce RTX 4070 Ti GamingPro OC'
    ),
    'gainward_phantom': _p('gainward_cyclone', 'Cyclone Fan',
        'https://www.gainward.com/main/vgapro.php?id=1163&lang=en',
        blades=9, hub_ratio=0.28, shape='claw', evidence='official_front_view',
        model_ids=('gainward-phantom-4090',), representative='Gainward GeForce RTX 4090 Phantom'
    ),
    'gainward_phoenix': _p('gainward_cyclone', 'Cyclone Fan',
        'https://www.gainward.com/main/vgapro.php?id=1210&lang=en',
        blades=9, hub_ratio=0.28, shape='claw', evidence='official_front_view',
        model_ids=('gainward-phoenix-4080super',), representative='Gainward GeForce RTX 4080 SUPER Phoenix'
    ),
    'gainward_ghost': _p('gainward_axial', '9叶轴流风扇',
        'https://www.gainward.com/main/vgapro.php?id=1191&lang=en',
        blades=9, hub_ratio=0.33, shape='swept', evidence='official_front_view',
        model_ids=('gainward-ghost-4060',), representative='Gainward GeForce RTX 4060 Ghost'
    ),
    'galax_hof': _p('galax_hof_extreme', 'HOF Extreme Cooling',
        'https://galax.com/en/news/press-release-5080-hof-extreme/',
        model_ids=('galax-hof-5080-extreme',), representative='GALAX GeForce RTX 5080 HOF Extreme'
    ),
    'galax_ex_gamer': _p('galax_wings', 'WINGS',
        'https://galax.com/en/product/geforce-rtx-4070-ex-gamer-d6/',
        blades=11, hub_ratio=0.29, shape='swept', evidence='official_front_view',
        model_ids=('galax-ex-gamer-4070-d6',), representative='GALAX GeForce RTX 4070 EX Gamer 1-Click OC D6'
    ),
    'galax_sg': _p('galax_wings2', 'WINGS 2.0',
        'https://galax.com/en/product/geforce-rtx-4070ti-super-sg-plus-1-click-oc/',
        model_ids=('galax-sg-plus-4070tis',), representative='GALAX GeForce RTX 4070 Ti SUPER SG Plus 1-Click OC'
    ),
    'inno3d_ichill_x3': _p('inno3d_scythe', 'Scythe Fan Blade',
        'https://www.inno3d.com/product/inno3d-geforce-rtx-4070-ichill-x3',
        model_ids=('inno3d-ichill-x3-4070',), representative='INNO3D GeForce RTX 4070 iCHILL X3'
    ),
    'inno3d_ichill_x4': _p('inno3d_scythe', 'Scythe Fan Blade',
        'https://inno3d.com/product/inno3d-geforce-rtx-3080-ichill-x4',
        model_ids=('inno3d-ichill-x4-3080',), representative='INNO3D GeForce RTX 3080 iCHILL X4'
    ),
    'inno3d_twin_x2': _p('inno3d_scythe', 'Scythe Fan Blade',
        'https://www.inno3d.com/product/inno3d-geforce-rtx-4070-twin-x2',
        model_ids=('inno3d-twin-x2-4070',), representative='INNO3D GeForce RTX 4070 TWIN X2'
    ),
    'inno3d_x3': _p('inno3d_scythe', 'Scythe Fan Blade',
        'https://www.inno3d.com/product/inno3d-geforce-rtx-4070-x3-oc',
        model_ids=('inno3d-x3-4070-oc',), representative='INNO3D GeForce RTX 4070 X3 OC'
    ),
    'colorful_vulcan': _p('colorful_hurricane_scythe', 'Hurricane Scythe Blade',
        'https://test.colorful.cn/en/home/product?id=89dc18fc-c42b-4bea-8e6b-11ad5e8400bc&mid=102',
        blades=9, hub_ratio=0.31, shape='swept', evidence='official_front_view',
        model_ids=('colorful-vulcan-4070ti-oc-v',), representative='Colorful iGame GeForce RTX 4070 Ti Vulcan OC-V'
    ),
    'colorful_ultra': _p('colorful_axial', '9叶轴流风扇',
        'https://www.colorfulgroup.com/en/home/product?id=c619c9ae-b48e-4618-b9b4-225e23c83140&mid=102',
        blades=9, hub_ratio=0.32, shape='wide', evidence='official_front_view',
        model_ids=('colorful-ultra-4070ti-super-w-oc-16g-v',), representative='Colorful iGame GeForce RTX 4070 Ti SUPER Ultra W OC 16GB-V'
    ),
    'colorful_advanced': _p('colorful_hurricane_scythe', 'Hurricane Scythe Blade',
        'https://test.colorful.cn/en/home/product?id=455a7ef6-46de-4fb5-9400-c11884c02991&mid=102',
        blades=9, hub_ratio=0.31, shape='swept', evidence='official_front_view', fans=({}, {'label': 'Hurricane Scythe Blade · Gravity Rim', 'hub_ratio': 0.3}, {}),
        model_ids=('colorful-advanced-4070ti-oc-v',), representative='Colorful iGame GeForce RTX 4070 Ti Advanced OC-V'
    ),
    'maxsun_icraft': _p('maxsun_axial', '11叶轴流风扇',
        'https://www.maxsun.com/products/ms-rtx5060-icraft-gt-oc8g-aiga',
        blades=11, hub_ratio=0.32, shape='swept', evidence='official_front_view',
        model_ids=('maxsun-icraft-5060-gt-oc8g-aiga',), representative='Maxsun MS-RTX5060 iCraft GT OC8G AIGA'
    ),
    'maxsun_terminator': _p('maxsun_axial', '11叶轴流风扇',
        'https://www.maxsun.com/products/ms-rtx5060ti-trbx3-16g',
        blades=11, hub_ratio=0.32, shape='swept', evidence='official_front_view',
        model_ids=('maxsun-terminator-5060ti-x3-16g',), representative='Maxsun MS-RTX5060Ti TerminatorX3 16G'
    ),
    'yeston_atlantis': _p('yeston_axial', '9叶轴流风扇',
        'https://yestonstore.com/products/yeston-sakura-atlantis-radeon-rx-9070-xt-16g-gddr6-256bit-4nm-video-cards-desktop-computer-pc-graphics-card',
        blades=9, hub_ratio=0.32, shape='wide', evidence='official_front_view',
        model_ids=('yeston-atlantis-rx9070xt-16g',), representative='Yeston Sakura Atlantis Radeon RX 9070 XT 16G GDDR6 256bit'
    ),
    'yeston_sakura': _p('yeston_axial', '9叶轴流风扇',
        'https://yestonstore.com/products/yeston-sakura-radeon-rx-7800-xt-16g-gddr6-256bit-desktop-computer-graphics-card',
        blades=9, hub_ratio=0.32, shape='wide', evidence='official_front_view',
        model_ids=('yeston-sakura-rx7800xt-16g',), representative='Yeston Sakura Radeon RX 7800 XT 16G GDDR6 256bit'
    ),
    'biostar_radeon': _p('unknown', '风扇细节未确认',
        'https://www.biostar.com.tw/app/en/vga/export/spec_export.php?S_ID=316',
        model_ids=('biostar-radeon-rx7600-va7606rm81',), representative='BIOSTAR Radeon RX 7600 VA7606RM81'
    ),
    'amd_reference': _p('amd_reference_axial', 'Radeon Reference',
        'https://www.amd.com/en/products/graphics/desktops/radeon/7000-series/amd-radeon-rx-7900xtx.html',
        blades=9, hub_ratio=0.37, shape='swept', evidence='official_front_view', hub_shape='triangle',
        model_ids=('amd-reference-rx7900xtx-24g',), representative='AMD Radeon RX 7900 XTX Reference 24GB'
    ),
    'intel_limited': _p('intel_axial', 'Arc Limited Edition',
        'https://game.intel.com/stories/intel-arc-graphics-overclocking-101/',
        model_ids=('intel-limited-arc-a770-16g',), representative='Intel Arc A770 Limited Edition 16GB'
    ),
    'sapphire_pure': _p('sapphire_angular_velocity', 'Angular Velocity Fan Blade',
        'https://www.sapphiretech.com/en/consumer/pure-radeon-rx-7800-xt-16g-gddr6',
        blades=9, hub_ratio=0.29, outer_ring=True, shape='wide', evidence='official_front_view',
        model_ids=('sapphire-pure-7800xt',), representative='SAPPHIRE PURE AMD Radeon RX 7800 XT 16G GDDR6'
    ),
    'powercolor_fighter': _p('powercolor_ring', 'Ring-fan Blade',
        'https://www.powercolor.com/product-detail33.htm',
        blades=9, hub_ratio=0.3, outer_ring=True, shape='swept', evidence='explicit_count',
        model_ids=('powercolor-fighter-7800xt',), representative='PowerColor Fighter AMD Radeon RX 7800 XT 16GB GDDR6'
    ),
    'powercolor_reaper': _p('powercolor_ring', 'High-Efficiency Ring Blade',
        'https://www.powercolor.com/product-detail212.htm',
        outer_ring=True,
        model_ids=('powercolor-reaper-9070xt',), representative='PowerColor Reaper AMD Radeon RX 9070 XT 16GB GDDR6'
    ),
    'sapphire_nitro_polaris': _p('sapphire_quick_connect', 'NITRO Quick Connect',
        'https://www.sapphiretech.com/en/consumer/nitro-rx-580-8g-g5',
        blades=9, hub_ratio=0.31, shape='wide', evidence='official_front_view',
        model_ids=('sapphire-nitro-rx580-8g-01',), representative='SAPPHIRE NITRO+ Radeon RX 580 8G G5 11265-01-20G'
    ),
    'asrock_challenger_rdna1': _p('asrock_axial', '轴流风扇',
        'https://asrock.com/Graphics-Card/AMD/Radeon%20RX%205500%20XT%20Challenger%20D%208G%20OC/',
        model_ids=('asrock-rx5500xt-challenger-d-8g',), representative='ASRock Radeon RX 5500 XT Challenger D 8G OC'
    ),
    'sapphire_pulse_rdna2_lp': _p('sapphire_axial', 'Axial Fan Cooling',
        'https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-6400-4g-gddr6',
        model_ids=('sapphire-pulse-rx6400-4g-lp',), representative='SAPPHIRE PULSE Radeon RX 6400 4GB 11315-01-20G'
    ),
    'sapphire_pulse_rdna3': _p('sapphire_angular_velocity', 'Angular Velocity Fan Blade',
        'https://www.sapphiretech.com/en/consumer/pulse-radeon-rx-7900-xt-20g-gddr6',
        blades=9, hub_ratio=0.29, outer_ring=True, shape='wide', evidence='official_front_view',
        model_ids=('sapphire-pulse-rx7900xt-20g',), representative='SAPPHIRE PULSE Radeon RX 7900 XT 20GB 11323-02-20G'
    ),
    'asrock_taichi_rdna4': _p('asrock_striped_ring', 'Striped Ring Fan',
        'https://www.asrock.com/Graphics-Card/AMD/Radeon%20RX%209070%20XT%20Taichi%2016GB%20OC/',
        outer_ring=True, fans=({'direction': 1}, {'direction': -1}, {'direction': 1}),
        model_ids=('asrock-taichi-rx9070xt-16g-oc',), representative='ASRock AMD Radeon RX 9070 XT Taichi 16GB OC'
    ),
    'asrock_challenger_arc_a380': _p('asrock_striped_axial', 'Striped Axial Fan',
        'https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20A380%20Challenger%20ITX%206GB%20OC/index.asp',
        model_ids=('asrock-a380-challenger-itx-6g',), representative='ASRock Intel Arc A380 Challenger ITX 6GB OC'
    ),
    'sparkle_titan_arc_a750': _p('sparkle_axl', 'TORN Cooling · AXL',
        'https://www.sparkle.com.tw/files/20240202122437352.pdf',
        model_ids=('sparkle-a750-titan-8g-oc',), representative='SPARKLE Intel Arc A750 TITAN OC Edition 8GB'
    ),
    'acer_bifrost_arc_a770': _p('acer_hybrid', 'AeroBlade 3D / FrostBlade 2.0',
        'https://www.acer.com/us-en/predator/desktops-and-all-in-ones/components/predator-bifrost-intel-arc-a770-oc',
        fans=({'technology': 'acer_aeroblade5', 'label': '5th Gen AeroBlade 3D', 'blades': None, 'hub_ratio': 0.64, 'outer_ring': False, 'shape': 'neutral', 'evidence': 'family_description'}, {'technology': 'acer_frostblade2', 'label': 'FrostBlade 2.0', 'blades': None, 'hub_ratio': 0.28, 'outer_ring': False, 'shape': 'neutral', 'evidence': 'family_description'}),
        model_ids=('acer-bifrost-a770-16g-oc',), representative='Acer Predator BiFrost Intel Arc A770 OC 16GB'
    ),
    'asrock_challenger_arc_b570': _p('asrock_striped_axial', 'Striped Axial Fan',
        'https://www.asrock.com/Graphics-Card/Intel/Intel%20Arc%20B570%20Challenger%2010GB%20OC/',
        blades=11, hub_ratio=0.29, shape='swept', evidence='official_front_view',
        model_ids=('asrock-b570-challenger-10g-oc',), representative='ASRock Intel Arc B570 Challenger 10GB OC'
    ),
    'sparkle_titan_arc_b580': _p('sparkle_axl2', 'TORN Cooling 2.0 · AXL',
        'https://www.sparkle.com.tw/files/20241203213858182.pdf',
        model_ids=('sparkle-b580-titan-12g-oc',), representative='SPARKLE Intel Arc B580 TITAN OC Edition 12GB'
    ),
}
