"""Reviewed exact-version exterior studies for group B and memory.

Only visible shells are described. Memory RGB covers are static diffusers;
none of these fields report live lighting, DRAM populations or internal PCB
identity. Sources and local inspection details live with VERSION_FAMILIES.
"""

_WHITE_RING = dict(
    technology='striped_ring', label='白色 Striped Ring · 11/13/11叶',
    blades=11, shape='swept', hub_ratio=.30, tone='light', hub_tone='light',
    outer_ring=True, group_size=1,
    fans=({'blades': 11, 'direction': 1, 'tone': 'light', 'hub_tone': 'light'},
          {'blades': 13, 'direction': -1, 'tone': 'light', 'hub_tone': 'light'},
          {'blades': 11, 'direction': 1, 'tone': 'light', 'hub_tone': 'light'}),
    evidence='official_front_view',
)

_WHITE_TWIN = dict(
    technology='inno3d_axial', label='TWIN X2 WHITE · 11叶双轴流',
    blades=11, shape='swept', hub_ratio=.36, tone='light', hub_tone='light',
    outer_ring=False, group_size=1,
    fans=({'blades': 11, 'direction': 1, 'tone': 'light', 'hub_tone': 'light'},
          {'blades': 11, 'direction': 1, 'tone': 'light', 'hub_tone': 'light'}),
    evidence='official_front_view',
)

ART = {
    'asrock-taichi-7900xtx-white-oc': dict(
        recipe='b_taichi7900_white', shroud_tone='light', fan_count=3,
        fan_profile=dict(_WHITE_RING,
            source_url='https://www.asrockchina.com.cn/Graphics-Card/photo/Radeon%20RX%207900%20XTX%20Taichi%20White%2024GB%20OC(L2).png',
            notes='Exact white front inspected: 11/13/11 leaves; translucent centre, white outer rotors and white caps. No live RGB colour is inferred.'),
        ports=({'type': 'DP', 'count': 3}, {'type': 'HDMI', 'count': 1}),
        power_connectors=({'type': '8pin', 'count': 3},),
        backplate=True,
    ),
    'asrock-taichi-rx9070xt-white-16g-oc': dict(
        recipe='b_taichi9070_white_lcd', shroud_tone='light', fan_count=3,
        fan_profile=dict(_WHITE_RING,
            source_url='https://www.asrockchina.com.cn/Graphics-Card/photo/Radeon%20RX%209070%20XT%20Taichi%20White%2016GB%20OC(L2).png',
            notes='Exact white front and L3 inspected: 11/13/11 white leaves and light caps; equal 100 mm diameter is separately specified. Relative centre reversal is official.'),
        ports=({'type': 'DP', 'count': 3}, {'type': 'HDMI', 'count': 1}),
        power_connectors=({'type': '16pin', 'count': 1},),
        host_interface=dict(bus='pcie', generation=5, lanes=16, connector_shape='pcie_standard'),
        # Regional exact-product dimension tables disagree. Do not borrow black.
        dimensions_mm=dict(length=None, height=None, thickness=None),
        slot_width=3.0, backplate=True, lcd=True,
    ),
    'inno3d-twin-x2-4070-oc-white': dict(
        recipe='b_inno4070_white', shroud_tone='light', fan_count=2,
        dimensions_mm=dict(length=250, height=118, thickness=42),
        fan_profile=dict(_WHITE_TWIN,
            source_url='https://www.inno3d.com/sites/default/files/2024-03/LP_4070_TWIN_X2_OC_WHITE_main_card.png',
            notes='Exact white main-card image inspected: both rotors have eleven swept leaves, white round caps and no continuous moving tip ring.'),
        ports=({'type': 'DP', 'count': 3}, {'type': 'HDMI', 'count': 1}),
        power_connectors=({'type': '8pin', 'count': 1},),
        power_position='top', backplate=True,
    ),
    'inno3d-twin-x2-4070-oc-white-stealth': dict(
        recipe='b_inno4070_white_stealth', backplate_recipe='b_inno_stealth_back',
        shroud_tone='light', fan_count=2,
        dimensions_mm=dict(length=250, height=118, thickness=42),
        fan_profile=dict(_WHITE_TWIN,
            source_url='https://www.inno3d.com/sites/default/files/2024-03/4070_TWIN_X2_OC_WHITE_stealth_set.png',
            notes='Exact STEALTH package/card photo inspected independently of ordinary WHITE. Eleven white leaves per rotor and light caps.'),
        ports=({'type': 'DP', 'count': 3}, {'type': 'HDMI', 'count': 1}),
        power_connectors=({'type': '8pin', 'count': 1},),
        power_position='rear', backplate=True,
    ),
    'biostar-radeon-rx7600-oc-va76s6rm81': dict(
        # The manufacturer export identifies the two-fan footprint, but its
        # full bitmap is unavailable. This is an explicit technical schematic,
        # not a claim that a reviewed photograph established this cover shape.
        recipe='b_biostar7600_oc', shroud_tone='unknown', fan_count=2,
        illustration_status='schematic_unverified_exterior',
        dimensions_mm=dict(length=235, height=150, thickness=45),
        fan_profile=dict(technology='unknown', label='双风扇示意 · 叶片外形待核实',
            blades=None, shape='neutral', tone='unknown', hub_tone='unknown',
            outer_ring=None, evidence='manufacturer_export_summary',
            source_url='https://www.biostar.com.tw/app/en/vga/export/spec_export.php?S_ID=334',
            notes='Cached exact manufacturer export identifies a dual-fan card, but original bitmap endpoints return 403. No blade count, hub ratio, fan paint or detailed shroud contour has been established.'),
        ports=({'type': 'DP', 'count': 3}, {'type': 'HDMI', 'count': 1}),
        power_connectors=({'type': '8pin', 'count': 1},),
        power_position='unknown', backplate=None, slot_width=None,
        host_interface=dict(bus='pcie', generation=4, lanes=None, connector_shape='pcie_standard'),
    ),
    'kingston-kf560c36bbeak2-32': dict(
        recipe='b_beast_rgb', form='dimm', generation='ddr5', pins=288,
        presentation='rgb', tone='dark', shroud_tone='dark', pcb_tone='dark',
        memory_rgb_cover=True, heat_spreader=True, diffuser=True,
        dimensions_mm=dict(length=133.35, height=42.23, thickness=7.11),
        features=('凸起分段扩散罩', '斜切深色散热盖'),
    ),
    'kingston-kf564c32rsak2-32': dict(
        recipe='b_renegade_rgb', form='dimm', generation='ddr5', pins=288,
        presentation='rgb', tone='mixed', shroud_tone='mixed', pcb_tone='dark',
        memory_rgb_cover=True, heat_spreader=True, diffuser=True,
        dimensions_mm=dict(length=133.35, height=44.0, thickness=8.3),
        features=('凹凸扩散罩', '银黑 X 形散热盖'),
    ),
    'kingston-kvr32n22s8k2-32': dict(
        recipe='b_valueram_kit', form='dimm', generation='ddr4', pins=288,
        presentation='bare', tone='green', pcb_tone='green',
        memory_rgb_cover=False, heat_spreader=False, diffuser=False,
        dimensions_mm=dict(length=133.35, height=31.25, thickness=None),
        features=('裸露绿色 PCB', '标准长条模块'),
    ),
    'teamgroup-ff4d532g6000hc30dc01': dict(
        recipe='b_delta_white', form='dimm', generation='ddr5', pins=288,
        presentation='rgb', tone='light', shroud_tone='light',
        memory_rgb_cover=True, heat_spreader=True, diffuser=True,
        dimensions_mm=dict(length=144.2, height=46.1, thickness=7.0),
        features=('不对称宽扩散罩', '白色折线散热盖'),
    ),
    'teamgroup-flrd532g6000hc38jdc01': dict(
        recipe='b_vulcan_red', form='dimm', generation='ddr5', pins=288,
        presentation='low', tone='red', shroud_tone='red',
        memory_rgb_cover=False, heat_spreader=True, diffuser=False,
        dimensions_mm=dict(length=140, height=32.7, thickness=7.5),
        features=('红色矮散热盖', '折线压纹'),
    ),
    'adata-ax5u6000c3016g-clarwh': dict(
        recipe='b_lancer_white_single', form='dimm', generation='ddr5', pins=288,
        presentation='rgb', tone='light', shroud_tone='light', pcb_tone='dark',
        memory_rgb_cover=True, heat_spreader=True, diffuser=True,
        dimensions_mm=dict(length=133.35, height=40, thickness=8),
        features=('三角形实体扩散罩', '白色斜纹平面盖'),
    ),
    'adata-ax4u32008g16a-dt60': dict(
        recipe='b_d60g_kit', form='dimm', generation='ddr4', pins=288,
        presentation='rgb', tone='mixed', shroud_tone='mixed',
        memory_rgb_cover=True, heat_spreader=True, diffuser=True,
        dimensions_mm=dict(length=133.35, height=45.93, thickness=8.4),
        features=('大面积切面扩散罩', '中央金属腰线'),
    ),
}
