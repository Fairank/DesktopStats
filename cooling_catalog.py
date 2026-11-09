"""Reviewed cooling references, not hardware detection or manufacturing CAD.

Only an explicit user selection installs a part in the schematic assembly.
Dimensions are manufacturer facts where marked; stock envelopes, internal
construction and unmeasured placement are explicitly reference geometry.
No images, fonts, CAD, network calls, clocks or sensor access are included.
Original code/art: PolyForm Noncommercial 1.0.0. Product names identify owners.
"""
from copy import deepcopy

REVIEWED = '2026-11-07'


def _fan(model_id, label, size, depth, family, blades, source, *, frame='square',
         frame_color='#20272d', blade_color='#343d43', pads=False, rgb=False,
         blade_verified=False, width=None, hub=.25, ring=False, notes='',**extra):
    return dict(id=model_id,label=label,size_mm=size,width_mm=width or size,depth_mm=depth,
                family=family,blades=blades,blade_count_verified=blade_verified,shape='wide' if blades<=7 else 'swept',
                frame=frame,frame_color=frame_color,blade_color=blade_color,pads=pads,rgb=rgb,
                hub_ratio=hub,outer_ring=ring,dimensions_verified=True,sources=[source],reviewed=REVIEWED,
                geometry_accuracy='original_reference',rotation_direction_verified=False,notes=notes,**extra)


_FANS = (
    _fan('noctua-nf-a8-pwm','Noctua NF-A8 PWM · 80mm',80,25,'noctua-a',7,
         'https://noctua.at/pub/media/blfa_files/infosheet/noctua_nf_a8_pwm_datasheet_en.pdf',
         frame_color='#c3b493',blade_color='#725549',pads=True),
    _fan('noctua-nf-a9-pwm','Noctua NF-A9 PWM · 92mm',92,25,'noctua-a',9,
         'https://www.noctua.at/en/products/nf-a9-pwm/specifications',
         frame_color='#c3b493',blade_color='#725549',pads=True),
    _fan('noctua-nf-a9x14-pwm','Noctua NF-A9x14 PWM · 92mm slim',92,14,'noctua-a',9,
         'https://www.noctua.at/en/products/nh-l9i-17xx/specifications',
         frame_color='#c3b493',blade_color='#725549',pads=True),
    _fan('noctua-nf-a12x25-pwm','Noctua NF-A12x25 PWM · 120mm',120,25,'noctua-sterrox',9,
         'https://www.noctua.at/en/products/nf-a12x25-pwm/specifications',
         frame_color='#c3b493',blade_color='#725549',pads=True,hub=.22),
    _fan('noctua-nf-a14-pwm','Noctua NF-A14 PWM · 140mm',140,25,'noctua-a',7,
         'https://www.noctua.at/en/products/nf-a14-pwm/specifications',
         frame_color='#c3b493',blade_color='#725549',pads=True),
    _fan('noctua-nf-a15-pwm','Noctua NF-A15 PWM · round 140mm',140,25,'noctua-a',7,
         'https://noctua.at/pub/media/blfa_files/infosheet/noctua_nh_d15_datasheet_en_web_4.pdf',
         frame='round',width=150,frame_color='#c3b493',blade_color='#725549',pads=True),
    _fan('noctua-nf-a14x25r-g2-pwm','Noctua NF-A14x25r G2 · round 140mm',140,25,'noctua-g2',9,
         'https://www.noctua.at/en/products/nf-a14x25r-g2-pwm/specifications',
         frame='round',frame_color='#c3b493',blade_color='#725549',pads=True,hub=.23),
    _fan('noctua-nf-a14x25-g2-pwm','Noctua NF-A14x25 G2 · 140mm',140,25,'noctua-g2',9,
         'https://cdn.noctua.at/media/noctua_nf_a14x25_g2_pwm_infosheet_en_web.pdf?download=true',
         frame_color='#c3b493',blade_color='#725549',pads=True,hub=.23),
    _fan('noctua-nf-a20-pwm','Noctua NF-A20 PWM · 200mm',200,30,'noctua-a',9,
         'https://www.noctua.at/en/products/nf-a20-pwm/specifications',
         frame_color='#c3b493',blade_color='#725549',pads=True),
    _fan('arctic-p12-pwm','ARCTIC P12 PWM · 120mm',120,25,'arctic-pressure',5,
         'https://support.arctic.de/en/p12-pwm/docs',hub=.28),
    _fan('arctic-p14-pwm','ARCTIC P14 PWM · 140mm',140,27,'arctic-pressure',5,
         'https://support.arctic.de/en/p14-pwm/docs',hub=.28),
    _fan('corsair-sp120-rgb-elite','Corsair SP120 RGB ELITE · 120mm',120,25,'corsair-airguide',7,
         'https://www.corsair.com/us/en/p/cpu-coolers/cw-9060064-ww2/icue-h60x-rgb-elite-liquid-cpu-cooler-cw-9060064-ww2',
         blade_color='#b7c7cf',pads=True,rgb=True),
    _fan('corsair-af120-rgb-elite','Corsair AF120 RGB ELITE · 120mm',120,25,'corsair-airguide',9,
         'https://www.corsair.com/ww/en/p/case-fans/co-9050158-ww/icue-af120-rgb-elite-120mm-pwm-triple-fan-kit-white-co-9050158-ww',
         blade_color='#b7c7cf',pads=True,rgb=True),
    _fan('nzxt-f120p-2022','NZXT F120P (2022) · 120mm',120,26,'nzxt-pressure',7,
         'https://support.nzxt.com/hc/en-us/articles/38273703470363-F120P-Static-Pressure-Fan-2022-Specs',
         pads=True,hub=.23),
    _fan('lian-li-uni-sl120-v2','Lian Li UNI FAN SL120 V2 · 120mm',120,28,'lian-li-sl',7,
         'https://lian-li.com/product/uni-fan-sl-v2/',pads=True,rgb=True),
    _fan('lian-li-lancool-216-160','Lian Li LANCOOL 216 ARGB · 160mm',160,30,'lian-li-216',9,
         'https://lian-li.com/product/lancool-216/',blade_color='#adbec7',rgb=True,
         notes='160mm size and dual lighting zones documented; depth/leaf layout remain schematic reference, not a retail replacement compatibility claim.'),
    _fan('fractal-dynamic-x2-gp18','Fractal Dynamic X2 GP-18 PWM · 180mm',180,38,'fractal-notched',7,
         'https://www.fractal-design.com/products/fans/dynamic/dynamic-x2-gp-18-pwm/',
         blade_verified=True,hub=.23,notes='Seven blades, hub-side trailing-edge notches, 165×165mm mounting pattern documented.'),
)

for _row in _FANS:
    if _row['id']=='lian-li-lancool-216-160':
        _row['dimensions_verified']=False
        _row['depth_verified']=False
        _row['frame_rgb_ring']=True
    # Reviewed primary product photos/technical front views. The curves remain
    # original parametric references, never a claim of exact aerodynamic CAD.
    if _row['id'] in ('noctua-nf-a12x25-pwm','noctua-nf-a14x25-g2-pwm','arctic-p12-pwm','corsair-sp120-rgb-elite'):
        _row['blade_count_verified']=True
        _row['blade_geometry_reviewed']=True
        _row['leaf_contour_accuracy']='photo_reviewed_parametric'
        _row['photo_observations']={
            'noctua-nf-a12x25-pwm':'Nine swept Sterrox leaves; broad curved tip, three raised acceleration channels, brown hub/cream pierced frame and corner pads.',
            'noctua-nf-a14x25-g2-pwm':'Nine progressive-bend leaves with outer winglets/channels; patterned central hub, cream square frame and brown pads.',
            'arctic-p12-pwm':'Five very broad strongly swept leaves; open tip gaps, black circular inlet in square frame, large round hub; no blade-joining ring.',
            'corsair-sp120-rgb-elite':'Seven broad translucent swept leaves, central hub diffusion ring, black clipped-corner frame and corner dampers; no blade-joining ring.'}[_row['id']]
        _row['sources'].append({
            'noctua-nf-a12x25-pwm':'https://cdn.noctua.at/media/noctua_nf_a12x25_pwm_infosheet_en_web.pdf',
            'noctua-nf-a14x25-g2-pwm':'https://cdn.noctua.at/media/noctua_nf_a14x25_g2_pwm_infosheet_en_web.pdf?download=true',
            'arctic-p12-pwm':'https://www.arctic.de/media/8c/5d/bd/1693305992/Spec_Sheet_P12_PWM_EN.pdf',
            'corsair-sp120-rgb-elite':'https://assets.corsair.com/image/upload/c_limit%2Cf_auto%2Cq_85%2Cw_1600%2Ch_1600/products/Fans/base-sp-elite-config/Gallery/MIC_SP120_RGB_ELITE_TRIPLE_01.webp'}[_row['id']])


def _air(model_id,label,kind,dimensions,fan,fan_count,pipes,sources,**extra):
    return dict(id=model_id,label=label,kind=kind,dimensions_mm=dict(zip(('width','height','depth'),dimensions)),
                dimensions_verified=True,fan_model=fan,fan_count=fan_count,heatpipes=pipes,
                sources=list(sources),reviewed=REVIEWED,geometry_accuracy='original_reference',**extra)


def _aio(model_id,label,radiator,fan,count,source,*,pump='round',tube=450,extra_sources=(),fan_size=None,fan_depth=25,fan_rgb=False,**extra):
    size=fan_size or (140 if isinstance(fan,str) and 'p14' in fan else 120)
    return dict(id=model_id,label=label,kind='aio',radiator_mm=dict(zip(('length','width','thickness'),radiator)),
                radiator_size=count*size,radiator_dimensions_verified=True,
                fan_model=fan,fan_count=count,tube_length_mm=tube,pump_style=pump,
                fan_reference_mm=size,fan_reference_depth_mm=fan_depth,fan_reference_rgb=fan_rgb,
                pump_dimensions_verified=False,pump_reference_mm=dict(width=70,height=55,depth=70),
                sources=[source,*extra_sources],reviewed=REVIEWED,geometry_accuracy='original_reference',**extra)


_COOLERS = [
    _air('intel-laminar-rm1','Intel Laminar RM1 · 原装下压','stock_intel',(100,47,100),None,1,0,
         ('https://www.intel.com/content/www/us/en/support/articles/000089190/processors/intel-core-processors.html',),
         envelope_is_upper_bound=True,fan_reference_mm=80,fin_style='radial',accent='#377fa8'),
    _air('amd-wraith-stealth','AMD Wraith Stealth · 原装下压','stock_amd',(100,55,100),None,1,0,
         ('https://www.amd.com/en/products/processors/ecosystem/cpu-cooler-solutions.html',),
         envelope_is_reference=True,fan_reference_mm=92,fin_style='radial',accent='#303a41'),
    _air('amd-wraith-prism','AMD Wraith Prism · 原装 RGB','stock_prism',(110,96,110),None,1,4,
         ('https://www.amd.com/en/products/processors/ecosystem/cpu-cooler-solutions.html',
          'https://ir.amd.com/news-events/press-releases/detail/827/2nd-generation-amd-ryzen-desktop-processors-deliver-best-in-class-compute-performance-and-even-faster-gaming-framerates-than-previous-generation'),
         envelope_is_reference=True,fan_reference_mm=92,fin_style='square',accent='#8bc4bd'),
    _air('noctua-nh-l9i-17xx','Noctua NH-L9i-17xx · 37mm 下压','low_profile',(95,37,95),
         'noctua-nf-a9x14-pwm',1,2,('https://www.noctua.at/en/products/nh-l9i-17xx/specifications',),
         documented_fin_count=54,fin_style='parallel'),
    _air('noctua-nh-u12a','Noctua NH-U12A · 单塔双风扇','single_tower',(125,158,112),
         'noctua-nf-a12x25-pwm',2,7,('https://www.noctua.at/en/products/nh-u12a/specifications',),
         heatsink_depth_mm=58,documented_fin_count=50,top_style='exposed_caps'),
    _air('noctua-nh-d15','Noctua NH-D15 · 初代双塔','dual_tower',(150,165,161),
         'noctua-nf-a15-pwm',2,6,('https://noctua.at/pub/media/blfa_files/infosheet/noctua_nh_d15_datasheet_en_web_4.pdf',),
         heatsink_depth_mm=135,documented_fin_count=45,top_style='exposed_caps',ram_clearance_mm=32,
         notes='Classic NH-D15 original infosheet165mm, not G2. Current website168mm conflicts with named original datasheet; fan-raising/RAM fit is not inferred.'),
    _air('noctua-nh-d15-g2','Noctua NH-D15 G2 · 八热管双塔','dual_tower',(150,168,152),
         'noctua-nf-a14x25r-g2-pwm',2,8,('https://noctua.at/pub/media/blfa_files/infosheet/NH-D15_G2_-_-_.pdf',
          'https://cdn.noctua.at/media/noctua_nh_d15_g2_hbc_infosheet_en_web.pdf?download=true'),
         heatsink_depth_mm=127,top_style='asymmetric_caps',asymmetric=True),
    _air('deepcool-ak620','DeepCool AK620 · 矩阵双塔','dual_tower',(129,160,138),
         None,2,6,('https://www.deepcool.com/products/Cooling/cpuaircoolers/AK620-High-Performance-CPU-Cooler-1851-1700-AM5/2024/13067.shtml',),
         fan_reference_mm=120,heatsink_depth_mm=110,top_style='matrix_caps',fin_style='checker_cut'),
    _air('thermalright-peerless-assassin-120-se','Thermalright Peerless Assassin 120 SE · 六热管','dual_tower',(125,155,135),
         None,2,6,('https://www.thermalright.com/product/peerless-assassin-120-se/',),
         envelope_is_reference=True,heatsink_dimensions_mm=dict(width=125,height=155,depth=110),
         fan_reference_mm=120,top_style='exposed_caps',fan_family='thermalright-c12'),
    _air('thermalright-phantom-spirit-120-se','Thermalright Phantom Spirit 120 SE · 七热管','dual_tower',(125,154,135),
         None,2,7,('https://www.thermalright.com/product/phantom-spirit-120-se/',),
         envelope_is_reference=True,heatsink_dimensions_mm=dict(width=125,height=154,depth=110),
         fan_reference_mm=120,top_style='dark_caps',fan_family='thermalright-c12'),
    _aio('corsair-h60x-rgb-elite','Corsair H60x RGB ELITE · 120 AIO',(156,120,27),
         'corsair-sp120-rgb-elite',1,
         'https://www.corsair.com/us/en/p/cpu-coolers/cw-9060064-ww2/icue-h60x-rgb-elite-liquid-cpu-cooler-cw-9060064-ww2',
         pump='corsair_square',tube=350),
    _aio('arctic-liquid-freezer-iii-240','ARCTIC Liquid Freezer III · 240 AIO',(277,120,38),
         'arctic-p12-pwm',2,'https://www.arctic.de/media/1c/af/b3/1708429821/Spec_Sheet_Liquid_Freezer_III_240_Black_EN.pdf',pump='arctic_vrm'),
    _aio('arctic-liquid-freezer-iii-280','ARCTIC Liquid Freezer III · 280 AIO',(317,138,38),
         'arctic-p14-pwm',2,'https://www.arctic.de/Liquid-Freezer-III-280/ACFRE00135A',pump='arctic_vrm'),
    _aio('arctic-liquid-freezer-iii-360','ARCTIC Liquid Freezer III · 360 AIO',(398,120,38),
         'arctic-p12-pwm',3,'https://www.arctic.de/media/16/63/19/1708429821/Spec_Sheet_Liquid_Freezer_III_360_Black_EN.pdf',pump='arctic_vrm'),
    _aio('arctic-liquid-freezer-iii-420','ARCTIC Liquid Freezer III · 420 AIO',(458,138,38),
         'arctic-p14-pwm',3,'https://www.arctic.de/en/Liquid-Freezer-III-420',pump='arctic_vrm'),
    _aio('corsair-h150i-elite-capellix-xt','Corsair H150i ELITE CAPELLIX XT · 360 AIO',(397,120,27),
         'corsair-af120-rgb-elite',3,'https://www.corsair.com/ww/en/p/cpu-coolers/cw-9060070-ww/icue-h150i-elite-capellix-xt-liquid-cpu-cooler',pump='corsair_octagon'),
    _aio('nzxt-kraken-360-2023','NZXT Kraken 360 (2023) · 360 AIO',(394,121,30),
         'nzxt-f120p-2022',3,'https://support.nzxt.com/hc/en-us/articles/47207322896923-Kraken-2023-Specs',pump='nzxt_lcd',tube=400),
]

for _row in _COOLERS:
    _row['heatpipe_count_verified']=not _row['id'].startswith('amd-')
    if _row.get('envelope_is_reference'):
        _row['dimensions_verified']=False
    if _row.get('envelope_is_upper_bound'):
        _row['dimensions_verified']=False
        _row['dimension_bounds_verified']=True
        _row['notes']='Intel documents upper bounds up to100×100×47mm, not a measured exact envelope; fan/fin construction is an original reference.'
    if _row['id']=='corsair-h60x-rgb-elite':
        _row['radiator_dimensions_verified']=False
        _row['notes']='Official page gives length156/width120 and120mm class;27mm radiator thickness and350mm tubing here are reference, not documented exact dimensions.'
    if _row['id']=='nzxt-kraken-360-2023':
        _row['pump_reference_mm']=dict(width=74.7,height=55.97,depth=74.7)
        _row['pump_dimensions_verified']=True
    if _row.get('pump_style')=='arctic_vrm':
        _row['vrm_fan']=True
        _row['pump_reference_mm']=dict(width=91,height=68.5,depth=108.5)
        _row['pump_dimensions_verified']=True
        _row['pump_dimensions_scope']='manufacturer_dimension_diagram_shared_LFIII_reference_including_elbows'
        _row['vrm_fan_diameter_mm']=60
        _row['visible_crown']='photo_observed_radial_vent_crown'
        _row['crown_motion_verified']=False
        _row['internal_vrm_impeller_verified']=False
        _row['sources'].extend([
            'https://www.arctic.de/Liquid-Freezer-III-360/ACFRE00136A',
            'https://www.arctic.de/media/1f/c8/23/1710936380/Liquid_Freezer_III_360_Dimensions_2000x2000.jpg',
            'https://www.arctic.de/media/12/55/3d/1707469623/Liquid_Freezer_III_360_Black_G04_2.jpg'])
        _row['notes']='Original LF III, not Pro. Manufacturer drawing gives91×108.5×68.5mm incl.elbows; exterior crown/undercuts/twin elbows photo-reviewed.60mm VRM fan documented; internal leaves and sampled vent-rib count are reference, not independent RPM measurement.'

_COOLERS.append(dict(id='custom-loop-360-reference',label='自组 CPU 水冷参考 · 360 冷排 + D5 水箱泵',kind='custom_loop',
    radiator_mm=dict(length=396,width=120,thickness=30),radiator_size=360,radiator_dimensions_verified=False,
    fan_model='arctic-p12-pwm',fan_count=3,pump_style='xc7_block',pump_dimensions_verified=True,
    pump_reference_mm=dict(width=87,height=36,depth=78),reservoir_mm=dict(diameter=60,height=200),
    reservoir_model='EK-Quantum Kinetic TBE 200 D5 PWM D-RGB Acetal',radiator_model='Corsair Hydro X XR5 360',
    cpu_block_model='Corsair iCUE LINK XC7 RGB ELITE',gpu_block=False,
    sources=['https://www.ekwb.com/shop/quantum/ek-quantum-kinetic-tbe-200-d5-pwm-d-rgb-acetal',
             'https://www.corsair.com/ww/en/p/custom-liquid-cooling/cx-9030003-ww/hydro-x-series-xr5-360mm-water-cooling-radiator-cx-9030003-ww',
             'https://www.corsair.com/ww/en/p/custom-liquid-cooling/cx-9010021-ww/icue-link-XC7-rgb-elite-water-block-cx-9010021-ww'],
    reviewed=REVIEWED,geometry_accuracy='explicit_reference_parts_combination',
    notes='Not a sold kit or detected equipment. CPU-only loop; no GPU waterblock. Reservoir60mm/200mm and CPU block87×78×36 documented; radiator envelope/tube routing are schematic. Full D5 combo, not the pumpless Body variant.'))

_FANS+= (
    _fan('bequiet-silent-wings-pro4-120','be quiet! Silent Wings Pro 4 · 120mm',120,25,'bequiet-grooved',7,
         'https://bequiet.com/en/casefans/3705',pads=True),
    _fan('bequiet-silent-wings4-120','be quiet! Silent Wings 4 · 120mm',120,25,'bequiet-grooved',7,
         'https://www.bequiet.com/en/cpucooler/4466',pads=True),
    _fan('deepcool-ft12-se','DeepCool FT12 SE · 120mm',120,25,'deepcool-pressure',9,
         'https://deepcool.com/products/Cooling/cpuliquidcoolers/MYSTIQUE-360-5th-Gen-Liquid-Cooler-with-LCD-1851-1700-AM5/2024/18059.shtml',pads=True),
    _fan('lian-li-uni-slinf120','Lian Li UNI FAN SL-INF · 120mm 单包装线材',120,25,'lian-li-infinity',7,
         'https://lian-li.com/product/uni-fan-sl-infinity/',width=122.1,rgb=True,pads=True),
    _fan('lian-li-uni-p28','Lian Li UNI FAN P28 · 120mm',120,28,'lian-li-p28',7,
         'https://lian-li.com/product/uni-fan-p28/',pads=True),
    _fan('lian-li-ga2-performance-lcp','Lian Li GA II Performance 配套 LCP · 120mm',120,28,'lian-li-p28',7,
         'https://lian-li.com/product/galahad-ii-trinity-performance/',pads=True,
         notes='Bundled GA II Performance fan, not relabelled as retail P28; leaf layout remains reference.'),
    _fan('thermaltake-swafan-ex12-argb','Thermaltake SWAFAN EX12 ARGB Sync · 标准叶片',120,25,'thermaltake-swafan',9,
         'https://thermaltake.com/products/swafan-ex12-argb-sync-pc-cooling-fan-tt-premium-edition-3-fan-pack',rgb=True,pads=True,
         notes='Standard preinstalled blade set shown; user direction flips installation, does not claim the alternate reverse-blade set is installed.'),
    _fan('thermaltake-toughfan12','Thermaltake TOUGHFAN 12 · 120mm',120,25,'thermaltake-toughfan',9,
         'https://thermaltake.com/products/toughliquid-360-argb-sync-all-in-one-liquid-cooler',blade_color='#727d79',pads=True),
    _fan('noctua-nff12-industrialppc2000-pwm','Noctua NF-F12 industrialPPC-2000 PWM',120,25,'noctua-focused',7,
         'https://www.noctua.at/en/products/nf-f12-industrialppc-2000-pwm/specifications',pads=True),
)
for _row in _FANS:
    if _row['family']=='thermaltake-swafan':_row['frame_rgb_ring']=True
    if _row['family']=='noctua-focused':_row['stator_vanes']=11
    if _row['id'] in ('lian-li-uni-slinf120','thermaltake-swafan-ex12-argb'):
        _row['lighting_connector']='argb3'
        _row['lighting_connector_verified']=True

_COOLERS.extend([
    _air('bequiet-dark-rock-pro5','be quiet! Dark Rock Pro 5 · 黑色七热管双塔','dual_tower',(136,168,145),
         'bequiet-silent-wings4-120',2,7,('https://www.bequiet.com/en/cpucooler/4466',),
         heatsink_depth_mm=119.5,fan_sizes=[120,135],top_style='mesh_bridge',fin_color='#303a40'),
    _air('bequiet-dark-rock-elite','be quiet! Dark Rock Elite · 双135mm风扇','dual_tower',(136,168,145),
         None,2,7,('https://www.bequiet.com/en/cpucooler/4468',),fan_reference_mm=135,fan_sizes=[135,135],
         fan_family='bequiet-grooved',heatsink_depth_mm=120,top_style='mesh_bridge_rgb',fin_color='#303a40'),
    _air('deepcool-assassin-iv','DeepCool ASSASSIN IV · 包覆双塔','dual_tower',(147,164,144),
         None,2,7,('https://deepcool.com/products/Cooling/cpuaircoolers/Assassin-IV-Premium-CPU-Air-Cooler-1851-1700-AM5/2024/17129.shtml',),
         fan_reference_mm=140,fan_sizes=[140,120],fan_family='deepcool-pressure',fan_layout='center_rear',
         heatsink_depth_mm=119,top_style='assassin_shell',fin_color='#35424a'),
    _aio('deepcool-mystique360','DeepCool MYSTIQUE 360 · 方形 LCD 冷头',(402,120,27),'deepcool-ft12-se',3,
         'https://deepcool.com/products/Cooling/cpuliquidcoolers/MYSTIQUE-360-5th-Gen-Liquid-Cooler-with-LCD-1851-1700-AM5/2024/18059.shtml',pump='deepcool_lcd',tube=410),
    _aio('lian-li-galahad-ii-trinity360','Lian Li GA II Trinity SL-INF 360',(397.5,119.2,27),'lian-li-uni-slinf120',3,
         'https://lian-li.com/product/galahad-ii-trinity/',pump='lianli_infinity',tube=385),
    _aio('lian-li-galahad-ii-performance360','Lian Li GA II Trinity Performance 360',(396,130,32),'lian-li-ga2-performance-lcp',3,
         'https://lian-li.com/product/galahad-ii-trinity-performance/',pump='lianli_infinity',tube=385),
    _aio('thermaltake-toughliquid360-argb','Thermaltake TOUGHLIQUID 360 ARGB Sync',(395,120,27),'thermaltake-toughfan12',3,
         'https://thermaltake.com/products/toughliquid-360-argb-sync-all-in-one-liquid-cooler',pump='thermaltake_mirror',tube=400),
    _aio('asus-rog-ryujin-iii360','ASUS ROG RYUJIN III 360 · 3.5英寸 LCD',(399.5,120,30),'noctua-nff12-industrialppc2000-pwm',3,
         'https://rog.asus.com/fr/cooling/cpu-liquid-coolers/rog-ryujin/rog-ryujin-iii-360/spec/',pump='asus_lcd',tube=400),
])
_PUMP_DIMENSIONS={
    'deepcool-mystique360':(93,66,77),'lian-li-galahad-ii-trinity360':(74,69,74),
    'lian-li-galahad-ii-performance360':(74,79,74),'asus-rog-ryujin-iii360':(89,101,91)}
for _row in _COOLERS:
    if _row['id'] in _PUMP_DIMENSIONS:
        _row['pump_reference_mm']=dict(zip(('width','height','depth'),_PUMP_DIMENSIONS[_row['id']]))
        _row['pump_dimensions_verified']=True
    if _row['id']=='asus-rog-ryujin-iii360':_row['vrm_fan']=True
    if _row['id']=='thermaltake-toughliquid360-argb':
        _row['notes']='Pump exterior envelope is schematic; documented radiator395×120×27 and TOUGHFAN12 fan model/count retained.'

# Additional named references cover small, entry, classic and premium families.
# A bundled fan is labelled as such; it is never silently substituted by a
# superficially similar retail model. Primary photos remain external links.
_FANS+=(
    _fan('coolermaster-silencio-fp120-pwm','Cooler Master Silencio FP 120 PWM',120,25,'cm-silencio',5,
         'https://legacy.coolermaster.com/en-global/products/silencio-fp-120-pwm/',pads=False,hub=.29,
         blade_verified=True,power_connector_verified=True,
         appearance_sources=['https://a.storyblok.com/f/281110/845a24b4da/sfp120pwm_g1.png']),
    _fan('coolermaster-mobius120','Cooler Master Mobius 120 · 叶尖联环',120,25,'cm-mobius',7,
         'https://www.coolermaster.com/en-us/products/mobius-120.html',pads=True,ring=True,hub=.28,
         blade_verified=True,power_connector_verified=True,
         appearance_sources=['https://www.coolermaster.com/on/demandware.static/-/Sites-cooler-master-main/default/dw31bcba12/Assets/mobius-120/large/mobius-120-01-gallery-01.png']),
    _fan('coolermaster-sickleflow120-rgb','Cooler Master SickleFlow 120 RGB · 12V RGB',120,25,'cm-sickleflow',7,
         'https://www.coolermaster.com/en-my/products/sickleflow-120-rgb.html',pads=True,rgb=True,blade_color='#a8b8bf',
         power_connector_verified=True,lighting_connector='rgb12v4',lighting_connector_verified=True,
         notes='This is the four-pin12V RGB variant, not the three-pin5V ARGB or reverse edition. Leaves remain a reference until a stationary primary front view is reviewed.'),
    _fan('idcooling-is55-argb-bundled12015','ID-COOLING IS-55 ARGB 配套薄扇参考',120,15,'idcooling-slim',9,
         'https://www.idcooling.com/product/detail?id=307&name=IS-55+ARGB',pads=True,rgb=True,blade_color='#aabcc4',
         power_connector_verified=True,lighting_connector='argb3',lighting_connector_verified=True,
         marketed_separately_verified=False,notes='Named cooler bundled120×120×15mm fan; no independently verified retail SKU or exact leaf outline. Primary gallery is motion-blurred.'),
    _fan('thermalright-tl9015r','Thermalright TL-9015R · 92mm 薄扇',92,15,'thermalright-slim',9,
         'https://www.thermalright.com/product/axp90-x47-full/',frame_color='#742e38',blade_color='#ce8a4b',hub=.30,
         blade_verified=True,power_connector_verified=True,
         appearance_sources=['https://www.thermalright.com/wp-content/uploads/2021/07/AXP90-X47-FULL-1.png']),
    _fan('thermalright-tlc12c','Thermalright TL-C12C · 120mm',120,25,'thermalright-c12',7,
         'https://www.thermalright.com/product/tl-c12c/',pads=True,blade_verified=True,power_connector_verified=True,
         appearance_sources=['https://www.thermalright.com/wp-content/uploads/2026/08/tl-c12c.png']),
    _fan('msi-meg-silent-gale-p12','MSI MEG SILENT GALE P12 · 27.5mm',120,27.5,'msi-lcp',9,
         'https://us.msi.com/PC-Component/MEG-SILENT-GALE-P12/Specification',pads=True,hub=.29,
         blade_verified=True,power_connector_verified=True,
         appearance_sources=['https://storage-asset.msi.com/datasheet/pccs/global/MEG-SILENT-GALE-P12.pdf']),
    _fan('phanteks-d30-120-regular','Phanteks D30-120 · 正叶 30mm',120,30,'phanteks-d30',7,
         'https://phanteks.com/product/d30-120-black/',pads=True,rgb=True,blade_color='#afc1c9',
         blade_verified=True,power_connector_verified=True,frame_rgb_outline='square',interlock_bridges=True,
         lighting_connector='argb3',lighting_connector_verified=True,
         appearance_sources=['https://phanteks.com/wp-content/uploads/2024/02/02_PH-F120D30_DRGB_PWM_BK01_Regular.webp'],
         notes='Regular PH-F120D30 model, not the reversed PH-F120D30R. Standard motherboard D-RGB endpoint uses the documented included adapter; bridge/lead placement is schematic.'),
    _fan('phanteks-t30-120','Phanteks T30-120 · LCP 30mm',120,30,'phanteks-t30',7,
         'https://phanteks.com/product/t30-120/',frame_color='#4b5051',blade_color='#626969',pads=True,
         blade_verified=True,power_connector_verified=True,
         appearance_sources=['https://phanteks.com/wp-content/uploads/2024/02/PH-F120T30_BG-2.webp']),
    _fan('asus-rog-strix-xf120','ASUS ROG Strix XF120 · 磁悬浮',120,25,'asus-maglev',7,
         'https://rog.asus.com/us/cooling/fans/rog-strix-xf-120-model/spec/',pads=True,hub=.30,
         power_connector_verified=True,notes='Envelope and PWM interface documented; no inferred bearing speed, leaf count or spin direction from the product name.'),
    _fan('enermax-squa-rgb-adv120','ENERMAX SquA RGB ADV · 26mm 配套扇',120,26,'enermax-squa',9,
         'https://www.enermax.com/en/products/aquafusion-adv-series-360mm-cpu-liquid-cooler',pads=True,rgb=True,blade_color='#b6c6cd',
         power_connector_verified=True,frame_rgb_outline='square',lighting_connector='argb3',lighting_connector_verified=True,
         notes='Documented AQUAFUSION ADV bundled fan. PWM4 is known; lighting adapter/leaf outline are not inferred from the RGB name.'),
    _fan('gigabyte-aorus120-argb','GIGABYTE AORUS 120 ARGB · GP-AR120RFAN',120,25,'gigabyte-aorus',9,
         'https://www.gigabyte.com/CPU-Cooler/AORUS-120-ARGB-FAN/sp',pads=True,rgb=True,blade_color='#a8bac3',hub=.31,
         power_connector_verified=True,notes='Retail GP-AR120RFAN, not the faster2500RPM bundled WATERFORCE X fan. Official packshot is motion-blurred; blade contour/count remain reference.'),
)

_COOLERS.extend([
    _air('coolermaster-hyper212-black-r2','Cooler Master Hyper 212 Black Edition R2 · 经典单塔','single_tower',(123,158.8,77),
         'coolermaster-silencio-fp120-pwm',1,4,('https://www.coolermaster.com/en-us/products/hyper-212-black-edition-with-lga1700.html',),
         heatsink_depth_mm=52,top_style='brushed_caps',fin_color='#3d454a',
         notes='RR-212S-20PK-R2 with LGA1700; not the newer152mm Hyper212 Black or3DHP. AM5 kit inclusion depends on production revision.'),
    _air('coolermaster-ma824-stealth','Cooler Master MA824 Stealth · 八热管异径双塔','dual_tower',(150.6,165.6,162.2),
         'coolermaster-mobius120',2,8,('https://www.coolermaster.com/en-au/products/masterair-ma824-stealth.html',),
         heatsink_depth_mm=137.2,fan_sizes=[120,135],fan_depths=[25,26],top_style='stealth_caps',fin_color='#303a40',
         notes='Two fans established by official dual-Mobius description and images; generic specification field incorrectly says1PC.135mm centre fan is a documented bundled reference, not retail Mobius140.'),
    _air('idcooling-is55-argb','ID-COOLING IS-55 ARGB · 55mm 下压','low_profile',(120,55,120),
         'idcooling-is55-argb-bundled12015',1,5,('https://www.idcooling.com/product/detail?id=307&name=IS-55+ARGB',),
         fin_color='#37424a',pipe_color='#3b454a'),
    _air('idcooling-se214xt-black','ID-COOLING SE-214-XT BLACK · 151mm 单塔','single_tower',(124,151,72),
         None,1,4,('https://www.idcooling.com/product/detail?id=482',),fan_reference_mm=120,fan_reference_depth_mm=25,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='idcooling-pressure',heatsink_depth_mm=47,
         fin_color='#35414a',top_style='dark_caps'),
    _air('thermalright-axp90-x47-full','Thermalright AXP90-X47 FULL · 47mm 全铜','low_profile',(95,47,94.5),
         'thermalright-tl9015r',1,4,('https://www.thermalright.com/product/axp90-x47-full/',),
         fin_color='#b9825b',pipe_color='#b9825b',heatsink_dimensions_mm=dict(width=95,height=32,depth=94.5),
         notes='Manufacturer32mm heatsink plus15mm TL-9015R;47mm installed stack. FULL copper variant, not aluminium X47 or53mm model.'),
    _air('thermalright-assassinx120-refined-se','Thermalright Assassin X120 Refined SE · 入门单塔','single_tower',(120,148,71),
         'thermalright-tlc12c',1,4,('https://www.thermalright.com/product/assassin-x-120-refined-se/',),
         heatsink_depth_mm=46,heatsink_dimensions_mm=dict(width=120,height=148,depth=46),envelope_is_reference=True,
         notes='Official dimensions are the120×46×148mm heatsink only.71mm reference depth combines that sink with documented25mm fan; clip overhang is unverified.'),
    _air('deepcool-ag400','DeepCool AG400 · 四热管矩阵单塔','single_tower',(125,150,92),None,1,4,
         ('https://www.deepcool.com/products/Cooling/cpuaircoolers/GAMMAXX-AG400-Single-Tower-CPU-Cooler-1700-AM5/2022/15898.shtml',),
         fan_reference_mm=120,fan_reference_depth_mm=25,fan_dimensions_verified=True,fan_power_connector_verified=True,
         fan_family='deepcool-pressure',heatsink_depth_mm=67,fin_style='checker_cut'),
    _aio('coolermaster-ml240l-v2-rgb','Cooler Master MasterLiquid ML240L V2 RGB · 240',(277,119.6,27.2),
         'coolermaster-sickleflow120-rgb',2,'https://legacy.coolermaster.com/en-global/products/masterliquid-ml240l-v2-rgb/',
         pump='cm_dual_chamber',tube=400,tube_length_verified=False),
    _aio('idcooling-frostflow-x240','ID-COOLING FROSTFLOW X 240 · 白光冷头',(276,120,27),None,2,
         'https://www.idcooling.com/product/detail?id=146&name=FROSTFLOW+X+240',pump='id_white_ring',tube=400,
         fan_depth=25,fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='idcooling-pressure'),
    _aio('enermax-aquafusion-adv360','ENERMAX AQUAFUSION ADV 360 · 方形镜面',(394,120,27),
         'enermax-squa-rgb-adv120',3,'https://www.enermax.com/en/products/aquafusion-adv-series-360mm-cpu-liquid-cooler',
         pump='enermax_square_mirror',tube=400,tube_length_verified=True,
         extra_sources=('https://www.enermax.com/archive/products/item/LiquidCooler/AQUAFUSION_ADV/AQUAFUSION_ADV_360_04.png',)),
    _aio('msi-mag-coreliquid240r-v2','MSI MAG CORELIQUID 240R V2 · 冷排内泵',(274,120,27),None,2,
         'https://es.msi.com/Liquid-Cooling/MAG-CORELIQUID-240R-V2/Specification',pump='msi_radiator_pump',tube=400,
         extra_sources=('https://us.msi.com/Liquid-Cooling/MAG-CORELIQUID-240R-V2',),fan_depth=25,fan_rgb=True,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='msi-argb',pump_location='radiator'),
    _aio('msi-meg-coreliquid-s360','MSI MEG CORELIQUID S360 · IPS 冷头',(394,120,27),
         'msi-meg-silent-gale-p12',3,'https://www.msi.com/Liquid-Cooling/MEG-CORELIQUID-S360/Specification',
         pump='msi_lcd',tube=400,tube_length_verified=False,vrm_fan=True,vrm_fan_diameter_mm=60,
         extra_sources=('https://www.msi.com/Liquid-Cooling/MEG-CORELIQUID-S360',)),
    _aio('gigabyte-aorus-waterforce-x360','GIGABYTE AORUS WATERFORCE X360 · 圆形 LCD',(394,119,27),None,3,
         'https://www.gigabyte.com/eu/CPU-Cooler/AORUS-WATERFORCE-X-360/sp',pump='aorus_round_lcd',tube=400,
         fan_depth=25,fan_rgb=True,fan_family='gigabyte-aorus',fan_dimensions_verified=False,tube_length_verified=False,
         notes='Official page states three120mm ARGB fans, not25mm depth. Pump82×82×74mm and circular60×60mm LCD documented; bundled2500RPM fan is not the retail1700RPM GP-AR120RFAN.'),
    _aio('phanteks-glacier-one360d30','Phanteks Glacier One 360D30 · 30mm 厚扇',(397,120,27),
         'phanteks-d30-120-regular',3,'https://phanteks.com/product/glacier-one-360d30-black/',pump='phanteks_bridge',tube=400),
    _aio('asus-tuf-lc240-argb','ASUS TUF Gaming LC 240 ARGB · 入门240',(272,121,27),None,2,
         'https://www.asus.com/in/motherboards-components/cooling/tuf-gaming/tuf-gaming-lc-240-argb/techspec/',
         pump='asus_tuf_hex',tube=380,fan_depth=25,fan_rgb=True,fan_dimensions_verified=True,fan_power_connector_verified=True,
         fan_family='asus-tuf',extra_sources=('https://www.asus.com/microsite/all-in-one-liquid-cooling/websites/download/AIO_coolers_SPEC_20211125.pdf',),
         notes='2021 TUF LC240 ARGB, not TUF LCII. Original manufacturer PDF confirms272×121×27; a regional120-class table erroneously lists150mm length.'),
    _aio('deepcool-ls720','DeepCool LS720 · FC120 镜面360',(402,120,27),None,3,
         'https://global.deepcool.com/products/Cooling/cpuliquidcoolers/LS720-High-Performance-360mm-Liquid-CPU-Cooler/2022/15826.shtml',
         pump='deepcool_square_mirror',tube=410,fan_depth=25,fan_rgb=True,fan_dimensions_verified=True,fan_power_connector_verified=True,
         fan_family='deepcool-fc120'),
])

_NEW_PUMPS={
    'coolermaster-ml240l-v2-rgb':(79.9,47.1,76),'idcooling-frostflow-x240':(72,47.3,72),
    'enermax-aquafusion-adv360':(69.5,54.5,68.5),
    'msi-mag-coreliquid240r-v2':(80.57,48.58,66.82),'msi-meg-coreliquid-s360':(95,83.53,95),
    'gigabyte-aorus-waterforce-x360':(82,74,82),'phanteks-glacier-one360d30':(64,51.4,76),
    'asus-tuf-lc240-argb':(80,45,80),'deepcool-ls720':(86,57,74)}
for _row in _COOLERS:
    if _row['id'] in _NEW_PUMPS:
        _row['pump_reference_mm']=dict(zip(('width','height','depth'),_NEW_PUMPS[_row['id']]))
        _row['pump_dimensions_verified']=True
    if _row.get('envelope_is_reference'):_row['dimensions_verified']=False
for _row in _FANS:
    if _row['id'] in ('coolermaster-silencio-fp120-pwm','coolermaster-mobius120','thermalright-tl9015r','thermalright-tlc12c',
                      'msi-meg-silent-gale-p12','phanteks-d30-120-regular','phanteks-t30-120'):
        _row['blade_geometry_reviewed']=True
        _row['leaf_contour_accuracy']='photo_reviewed_parametric'

# 0.39 additions: one shared catalogue for every drawing style. These are
# original parameterised references, never manufacturer CAD or live sensors.
_FANS+=(
    _fan('noctua-nf-a12x15-pwm','Noctua NF-A12x15 PWM · 15mm 薄扇',120,15,'noctua-a',7,
         'https://www.noctua.at/en/products/nf-a12x15-pwm/specifications',pads=True,frame_color='#cdb99a',blade_color='#80604d',
         power_connector_verified=True,notes='Official120×120×15 bare-frame size; pads make16mm. Seven-leaf contour is an original reference, not verified tooling.'),
    _fan('arctic-p12-max','ARCTIC P12 Max · 加固叶尖环',120,25,'arctic-max',5,
         'https://www.arctic.de/en/P12-Max/ACFAN00280A/',pads=True,ring=True,hub=.25,power_connector_verified=True,
         notes='Manufacturer documents the stabilising rotor ring. Five-leaf count and fine contour remain reference pending isolated packshot review.'),
    _fan('arctic-p12-slim-pwm-pst','ARCTIC P12 Slim PWM PST · 15mm',120,15,'arctic-slim',7,
         'https://www.arctic.de/en/P12-Slim-PWM-PST/',power_connector_verified=True,
         notes='Current manufacturer15mm variant; seven-leaf contour/count remain reference. PST is a cable splitter, not a rigid frame interlock.'),
    _fan('scythe-kaze-flex-ii120','Scythe Kaze Flex II 120 PWM · KFS1225FD15-P',120,26,'scythe-kaze2',9,
         'https://www.scytheus.com/kazeflexii-120',pads=True,blade_verified=True,hub=.28,power_connector_verified=True,
         appearance_sources=['https://static.wixstatic.com/media/9ccab7_68364a7953504fd3a7502cc3d71b1991~mv2.png'],
         notes='26mm includes rubber pads. Nine leaves counted in official still packshot; blade camber/shaft direction are schematic.1500RPM variant matches Fuma3 centre fan.'),
    _fan('scythe-kaze-flex-ii120-slim','Scythe Kaze Flex II 120 Slim PWM · KFS1215FD15-P',120,15,'scythe-kaze2-slim',11,
         'https://www.scytheus.com/kaze-flex-ii-120-slim',pads=True,blade_verified=True,hub=.32,power_connector_verified=True,
         appearance_sources=['https://static.wixstatic.com/media/9ccab7_6224139beb9b4e5e864d2e2299c4c3a0~mv2.png'],
         notes='Eleven leaves counted in official still packshot.15mm includes pads; absolute rotation is unverified.1500RPM model, not the1800RPM BigShuriken bundled revision.'),
    _fan('lian-li-uni-tllcd120','Lian Li UNI FAN TL LCD 120 · 中央屏幕',120,28,'lian-li-tl-lcd',7,
         'https://lian-li.com/product/uni-fan-TL-LCD/',width=124,pads=True,rgb=True,hub=.37,
         hub_display=True,hub_display_inches=1.6,hub_display_resolution=[400,400],interlock_bridges=True,frame_rgb_outline='square',
         notes='Normal-blade12TLLCD1B.124×120×28 includes side interlock; seven-leaf count/contour remain reference. Proprietary P-7P controller cable; no direct PWM4 plug is claimed.'),
    _fan('phanteks-d30-120-reverse','Phanteks D30-120 Reverse · 30mm 反叶',120,30,'phanteks-d30',9,
         'https://phanteks.com/product/d30-120-black/',pads=True,rgb=True,blade_color='#bacbd1',hub=.28,
         reverse_blade=True,interlock_bridges=True,frame_rgb_outline='square',power_connector_verified=True,
         lighting_connector='phanteks_drgb3',lighting_connector_verified=True,
         notes='PH-F120D30R_DRGB_PWM_BK01. Reverse airflow/leaf type is documented; absolute shaft rotation and nine-leaf count are unverified. Never infer reverse RPM direction from intake airflow.'),
    _fan('bequiet-light-wings120-hs','be quiet! Light Wings 120 PWM high-speed · 双面光环',120,25,'bequiet-grooved',9,
         'https://www.bequiet.com/de/casefans/3454',pads=True,rgb=True,blade_verified=True,hub=.28,
         frame_rgb_ring=True,power_connector_verified=True,lighting_connector='argb3',lighting_connector_verified=True,
         notes='BL073 high-speed, documented nine leaves; ordinary seven-leaf120PWM is a different variant. RGB ring is stationary frame lighting, not a rotor tip ring.'),
    _fan('silverstone-ap183','SilverStone Air Penetrator AP183 · 定向导流网',180,32,'silverstone-penetrator',7,
         'https://silverstone.en.taiwantrade.com/product/ap183-1787350.html',hub=.27,power_connector_verified=True,directional_grille=True,
         extra_sources=['https://www.silverstonetek.com/en/product/info/fans/AP183/'],
         notes='Manufacturer-owned SilverStone Technology export listing confirms180×180×32 and fixed Air Penetrator grille. Main site blocks retrieval. Seven-leaf rotor count and grille vane count/curve remain original references.'),
    _fan('xpg-vento-pro120-pwm','XPG VENTO PRO 120 PWM · Gentle Typhoon 衍生',120,25,'xpg-typhoon',9,
         'https://www.xpg.com/tw/xpg/691?tab=spec',pads=True,hub=.32,power_connector_verified=True,
         notes='Manufacturer documents Nidec Gentle Typhoon-based design; nine-leaf count and curvature remain unverified references, not an exact reproduction.'),
    _fan('fractal-prisma-al18-pwm','Fractal Design Prisma AL-18 PWM · 180×38',180,38,'fractal-notched',7,
         'https://www.fractal-design.com/products/fans/prisma/prisma-al-18-pwm/white-rgb',pads=True,rgb=True,blade_verified=True,blade_color='#c6d2d6',
         frame_rgb_ring=True,power_connector_verified=True,lighting_connector='argb3',lighting_connector_verified=True,
         notes='Official specification explicitly lists seven leaves and38mm thickness. Lit outer frame is stationary; blade Trip Wire detail remains a qualitative reference.'),
    _fan('coolermaster-mobius120-oc','Cooler Master Mobius 120 OC · 27mm 金属轴心',120,27,'cm-mobius',7,
         'https://www.coolermaster.com/en-my/products/mobius-120-oc.html',pads=True,ring=True,hub=.28,metal_hub=True,
         power_connector_verified=True,notes='OC has a27mm frame and metal motor hub, distinct from the25mm Mobius120. Seven-leaf count/contour remain reference; speed-toggle positions are not telemetry.'),
    _fan('thermalright-tlb12-extrem-lcp','Thermalright TL-B12 Extrem LCP · 25.6mm',120,25.6,'thermalright-lcp',9,
         'https://www.thermalright.com/product/tl-b12-extrem-lcp/',pads=True,hub=.28,power_connector_verified=True,
         notes='LCP2150RPM catalogue version, not3150RPM TL-B12 EXTREM. Nine-leaf count/curvature remain schematic; no speed is emitted as a live reading.'),
    _fan('thermaltake-ct120','Thermaltake CT120 · 四角圆形减震',120,25,'thermaltake-ct',7,
         'https://thermaltake.com/products/ct120-pc-cooling-fan-2-pack.html',pads=True,blade_verified=True,hub=.27,
         power_connector_verified=True,pad_style='round',notes='CL-F147-PL12BL-A, seven leaves documented. Cable daisy-chain only; no rigid interlock and no ARGB.'),
    _fan('ek-loop-fpt120-drgb','EK-Loop FPT 120 D-RGB · 全框压力扇',120,27,'ek-fpt',7,
         'https://www.ekwb.com/shop/ek-loop-fan-fpt-120-d-rgb-black-550-2300rpm',pads=True,rgb=True,blade_verified=True,blade_color='#bdcdd2',hub=.26,
         power_connector_verified=True,lighting_connector='argb3',lighting_connector_verified=True,
         notes='Retail27mm FPT with OmniLink8-pin and included PWM4/ARGB3 extender. Nucleus bundled fans are specified25mm; this retail record is intentionally not substituted for them.'),
    _fan('alphacool-rise-aurora120','Alphacool Rise Aurora 120 · 框轴双区光',120,25,'alphacool-rise',9,
         'https://shop.alphacool.com/en/shop/fans/pc-fans/l12-alphacool-rise-aurora-120-mm-fan-120x120x25mm-pht-eol',pads=True,rgb=True,
         blade_color='#c3d1d5',hub=.28,frame_rgb_ring=True,power_connector_verified=True,
         lighting_connector='jst_argb3',lighting_connector_verified=True,
         notes='24836 uses a JST3 lighting plug, not a direct motherboard ARGB3. Official frame12/hub8 LEDs; nine-leaf count/curve remain references.'),
)

_COOLERS.extend([
    _air('noctua-nh-p1','Noctua NH-P1 · 无扇被动塔','passive_tower',(154,158,152),None,0,6,
         ('https://www.noctua.at/en/products/nh-p1/specifications','https://www.noctua.at/en/products/nh-p1'),
         fin_count=13,documented_fin_count=13,perforated_fins=True,fin_style='passive_perforated',top_style='exposed_caps',
         notes='Factory passive configuration: zero fans. Official dimensions and13 fins are verified; perforation pattern/heatpipe bends are an original schematic, not engineering CAD.'),
    _air('scythe-fuma3','Scythe Fuma 3 · 异厚双扇偏置双塔','dual_tower',(138,154,128),
         'scythe-kaze-flex-ii120',2,6,('https://www.scytheus.com/fuma-3',),fan_sizes=[120,120],fan_depths=[15,26],
         fan_models=['scythe-kaze-flex-ii120-slim','scythe-kaze-flex-ii120'],asymmetric=True,top_style='dark_caps',
         notes='SCFM-3000 includes15mm front and26mm centre fans. Manufacturer documents contra-rotation, but absolute directions are not specified here. Tower bank positions remain schematic.'),
    _air('scythe-mugen6','Scythe Mugen 6 · 六热管偏置单塔','single_tower',(132,154,106),None,1,6,
         ('https://www.scytheus.com/mugen6',),fan_reference_mm=120,fan_reference_depth_mm=26,fan_dimensions_verified=True,
         fan_power_connector_verified=True,fan_family='scythe-tornado',asymmetric=True,top_style='brushed_caps',
         notes='SCMG-6000 single-fan WonderTornado version; not the two-fan132mm-deep DBE. Fin density is schematic, not guessed from the45% marketing comparison.'),
    _air('scythe-bigshuriken3-revb','Scythe Big Shuriken 3 Rev.B · 67mm 偏置下压','low_profile',(122,67,122),None,1,5,
         ('https://www.scythe.co.jp/product/cpu-cooler/air-cooling/low-profile/scbsk-3100/','https://www.scytheus.com/bigshuriken3-rev-b'),
         fan_reference_mm=120,fan_reference_depth_mm=15,fan_dimensions_verified=True,fan_power_connector_verified=True,
         fan_family='scythe-kaze2-slim',fan_reference_blades=11,fan_blade_count_verified=True,asymmetric=True,
         notes='SCBSK-3100 with1800RPM bundled KazeFlexII Slim, not1500RPM Fuma3 fan.67mm total includes projecting screw heads; individual fin/pipe offsets remain reference.'),
    _air('arctic-freezer36','ARCTIC Freezer 36 · 双风扇单塔','single_tower',(126,159,104),'arctic-p12-pwm',2,4,
         ('https://www.arctic.de/us/Freezer-36',),documented_fin_count=59,top_style='brushed_caps',
         notes='Two P12 PWM PST supplied; rotor geometry matches the P12 reference, while PST adds the documented cable splitter.59 physical fins are source metadata; low-detail rendering remains bounded.'),
    _air('thermalright-axp120-x67','Thermalright AXP120-X67 · 六热管薄扇下压','low_profile',(120,67,123.5),None,1,6,
         ('https://www.thermalright.com/product/axp120-x67/',),fan_reference_mm=120,fan_reference_depth_mm=15,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='thermalright-slim',
         heatsink_dimensions_mm=dict(width=120,height=52,depth=123.5),envelope_is_reference=True,
         notes='Official sink123.5L×120W×52H plus15mm TL-C12015.67mm stack is derived, with clip/screw protrusion unverified; envelope deliberately not marked verified.'),
    _air('thermalright-si100','Thermalright SI-100 · 悬高六热管下压','low_profile',(120,99.8,120),None,1,6,
         ('https://www.thermalright.com/product/si-100/',),fan_reference_mm=120,fan_reference_depth_mm=25,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='thermalright-e12',
         heatsink_dimensions_mm=dict(width=108,height=74.8,depth=120),envelope_is_reference=True,
         notes='Manufacturer specifies120L×108W×74.8H heatsink plus120×120×25 TL-E12.99.8mm assembled stack is derived, not a verified retail100mm envelope.'),
    _air('deepcool-an600','DeepCool AN600 · 62鳍片薄扇下压','low_profile',(120,67,122),None,1,6,
         ('https://global.deepcool.com/products/Cooling/cpuaircoolers/AN600-Top-Flow-Low-Profile-Cooler-1700-AM5/2023/16837.shtml',),
         fan_reference_mm=120,fan_reference_depth_mm=15,fan_dimensions_verified=True,fan_power_connector_verified=True,
         fan_family='deepcool-slim',heatsink_dimensions_mm=dict(width=120,height=52,depth=121),documented_fin_count=62,ram_clearance_mm=40,
         notes='Official122L×120W×67H overall;62 aluminium fins. Bundled thin white-LED fan is a reference and is not mislabelled ARGB.'),
    _air('zalman-cnps10x-performa-black','Zalman CNPS10X Performa Black · 135mm 环叶单塔','single_tower',(135,155,95),None,1,4,
         ('https://www.zalman.com/EN/Product/ProductDetail.do?productSeq=1182',),fan_reference_mm=135,fan_reference_depth_mm=25,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='zalman-turbine',top_style='dark_caps',fin_color='#323b40',
         notes='Manufacturer specifies135×95×155H, four heatpipes,135×135×25 fan. Blade outline and exact top-surface cuts remain original references.'),
    _aio('alphacool-core-ocean-t38-360','Alphacool Core Ocean T38 360 · 38mm 厚排',(397,120,38),None,3,
         'https://www.alphacool.com/download/datasheet/ENG_13052_Alphacool_Core_Ocean_T38_AIO_360mm_datasheet.pdf',
         pump='alphacool_square',tube=400,tube_length_verified=True,fan_dimensions_verified=True,fan_power_connector_verified=True,
         fan_family='alphacool-core',notes='13052 uses three120×25 black fans, not RiseAurora RGB retail fans.38mm radiator body excludes the25mm fan stack.'),
    _aio('ek-nucleus-cr360-lux-drgb','EK Nucleus CR360 Lux D-RGB · 分区旋转顶盖',(400,124,27),None,3,
         'https://www.ekwb.com/solutions/all-in-one/',pump='ek_nucleus',tube=400,tube_length_verified=True,fan_rgb=True,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='ek-fpt',fan_reference_blades=7,fan_blade_count_verified=True,
         extra_sources=('https://www.ekwb.com/shop/EK-IM/EK-IM-3831109851661.pdf',),
         notes='Nucleus manual specifies bundled120×120×25 fans; retail EK-Loop FPT is27mm and is not substituted. Rotatable fan-like lighting is a static illustration, not a physical pump fan.'),
    _aio('tryx-panorama-se360','TRYX PANORAMA SE 360 ARGB · 曲面屏冷头',(394,120,27),None,3,
         'https://www.tryxzone.com/api/product-models/1',pump='tryx_panorama',tube=450,tube_length_verified=True,
         fan_rgb=True,fan_dimensions_verified=True,fan_family='tryx-reference',screen_style='curved_l',screen_diagonal_inches=6.67,
         notes='Official public product model API id1, black360 variant: PANORAMA SE, not original8th-gen PANORAMA or SE V2. Fan120×120×25 verified; leaf count, absolute rotation and pump-envelope axis orientation remain unverified.'),
])

_PUMPS039={'alphacool-core-ocean-t38-360':(70.2,46,70.2),'ek-nucleus-cr360-lux-drgb':(82.3,61.6,69.2)}
for _row in _COOLERS[-12:]:
    if _row['id'] in _PUMPS039:
        _row['pump_reference_mm']=dict(zip(('width','height','depth'),_PUMPS039[_row['id']]))
        _row['pump_dimensions_verified']=True
    if _row['id']=='tryx-panorama-se360':
        _row['pump_reference_mm']=dict(width=125,height=92,depth=94)
        _row['pump_axis_orientation_verified']=False
    if _row.get('envelope_is_reference'):_row['dimensions_verified']=False

# 0.40: signs use one common front-to-rear viewing axis for both Fuma fans.
# This expresses documented relative contra-rotation only, never a measured
# speed, an absolute CW/CCW direction, or the view from each fan's own face.
for _row in _COOLERS:
    if _row['id']=='scythe-fuma3':
        _row['fan_relative_directions']=[1,-1]
        _row['relative_rotation_verified']=True

_FANS+=(
    _fan('noctua-nfp12-redux1700-pwm','Noctua NF-P12 redux-1700 PWM · 九叶缺口',120,25,'noctua-redux-p',9,
         'https://www.noctua.at/en/products/nf-p12-redux-1700-pwm/specifications',blade_verified=True,
         frame_color='#aeb1b4',blade_color='#666b70',hub=.28,power_connector_verified=True,vortex_notches=True,
         appearance_sources=['https://noctua.at/pub/media/blfa_files/infosheet/noctua_nf_p12_redux_1700_pwm_datasheet_en_web_2.pdf'],
         notes='Official Nine Blade Design with VCN; bundled redux fan has no anti-vibration pads. Not the seven-leaf A-series or Sterrox A12 rotor. Absolute viewing convention is not inferred from marketing CW/CCW.'),
    _fan('arctic-f8-pwm-pst','ARCTIC F8 PWM PST · 80mm 机箱扇',80,25,'arctic-flow',9,
         'https://www.arctic.de/media/f9/28/58/1654783278/Spec_Sheet_F8_PWM_PST_EN.pdf',hub=.28,power_connector_verified=True,
         notes='F airflow family, not P pressure family. Manufacturer80×80×25; nine-leaf count/curve remain an original reference; PST is the cable splitter.'),
    _fan('arctic-f14-pwm-pst','ARCTIC F14 PWM PST · 27mm 风量型',140,27,'arctic-flow',9,
         'https://www.arctic.de/media/40/77/52/1690271547/Spec_Sheet_F14_PWM_PST_EN.pdf',hub=.27,power_connector_verified=True,
         notes='Official140×140×27, not25mm P14. Nine-leaf count/curve remain reference; this is the FDB PWM PST version, not CO dual-ball variant.'),
    _fan('scythe-kazeflex140-square','Scythe Kaze Flex 140 Square PWM · 27mm 方框',140,27,'scythe-kaze140',11,
         'https://www.scytheus.com/kazeflex-140-square',pads=True,hub=.28,power_connector_verified=True,
         notes='27mm includes anti-vibration rubber. Non-RGB140 square version, distinct from the round-frame140 and 12V four-pin lighting version. Eleven-leaf count/curve remain reference.'),
    _fan('cryorig-qf120-led-balance','CRYORIG QF120 LED Balance · 四角侧进气',120,25.4,'cryorig-qf',11,
         'https://en.cryorig.com/news_detail/28',pads=True,blade_color='#c6d2d6',hub=.26,side_air_inlets=True,
         fixed_led_color='#dbe8ee',notes='Documented120×120×25.4, white LED Balance, not RGB. Quad Air Inlet geometry is documented qualitatively; eleven-leaf count/curvature remain reference.'),
    _fan('silverstone-airslimmer120','SilverStone Air Slimmer 120 · 15.6mm 弯刀九叶',120,15.6,'silverstone-scimitar',9,
         'https://www.silverstonetek.com/en/product/info/fans/AirSlimmer120/',blade_verified=True,hub=.29,power_connector_verified=True,
         notes='SST-AS120B. Manufacturer explicitly specifies15.6mm and nine scimitar leaves; rear bevelled grille is not an AirPenetrator column grille. Leaf curvature remains a schematic reference.'),
    _fan('coolermaster-mf200r-argb','Cooler Master MasterFan MF200R ARGB · 200mm',200,25,'cm-mf200',9,
         'https://legacy.coolermaster.com/en-global/products/masterfan-mf200r-argb/?tab=tech_spec',rgb=True,blade_color='#becdd2',hub=.25,
         power_connector_verified=True,lighting_connector='argb3',lighting_connector_verified=True,
         notes='R4-200R-08FA-R1,200×200×25 addressable RGB. Not the12V RGB model; nine-leaf count/contour and frame corner cuts remain original references.'),
    _fan('thermaltake-pure20-argb','Thermaltake Pure 20 ARGB Sync · 200×30 十一叶',200,30,'thermaltake-pure',11,
         'https://thermaltake.com/products/pure-20-argb-sync-case-fan-tt-premium-edition-1-fan-pack',frame='round',rgb=True,
         blade_color='#bacbd0',hub=.23,blade_verified=True,power_connector_verified=True,lighting_connector='argb3',lighting_connector_verified=True,
         notes='Official11 Fan Blade Design and200×200×30 envelope. ARGB Sync TT Premium Edition, not the plain200mm Pure20; curved leaf outline/mount ears remain schematic.'),
    _fan('corsair-lx120r-rgb','Corsair iCUE LINK LX120-R RGB · 反叶双光环',120,25,'corsair-lx',9,
         'https://www.corsair.com/us/en/p/case-fans/co-9051049-ww/icue-link-lx120-r-rgb-120mm-pwm-reverse-fan-expansion-co-9051049-ww',
         pads=True,rgb=True,blade_color='#c4d1d5',hub=.28,reverse_blade=True,frame_rgb_ring=True,interlock_bridges=True,
         notes='CO-9051049-WW proprietary iCUE LINK connection; no direct PWM4/ARGB3 plug is claimed. Reverse rotor and dual light loops verified; nine-leaf count/curvature and absolute shaft direction remain reference.'),
    _fan('antec-fusion120-argb-white','Antec Fusion 120 ARGB White · 十二边光环',120,25,'antec-fusion',9,
         'https://www.antec.com/product/cooling/fusion120-argb-white',pads=True,rgb=True,frame_color='#d8e0e2',blade_color='#c6d4d9',hub=.26,
         frame_rgb_polygon=12,power_connector_verified=True,lighting_connector='argb3',lighting_connector_verified=True,
         notes='Manufacturer dodecagon stationary16-LED frame ring. Nine-leaf count/contour remains reference; polygonal ring does not rotate with the rotor.'),
    _fan('montech-ax120-pwm','Montech AX120 PWM · 六角光环',120,25,'montech-ax',9,
         'https://www.montechpc.com/ax120-pwm',pads=True,rgb=True,blade_color='#b6cbd3',hub=.27,frame_rgb_polygon=6,pad_style='round',
         power_connector_verified=True,lighting_connector='argb3',lighting_connector_verified=True,
         notes='Normal AX120, not reverse-airflow RX120. Official120×120×25 and hexagon20-LED frame ring; nine-leaf count/contour reference. Round pads stay attached to the frame.'),
    _fan('apnx-fp1-120','APNX FP1-120 PWM ARGB · 30mm 厚框',120,30,'apnx-fp1',9,
         'https://www.apnx.com/product/fp1/',pads=True,rgb=True,blade_color='#c6d4d9',hub=.27,power_connector_verified=True,
         lighting_connector='argb3',lighting_connector_verified=True,
         notes='120mm variant is74.6CFM;86.9CFM marketing headline belongs to140mm. Official30mm frame; nine-leaf count/shape and corner-pad profile remain reference.'),
    _fan('fractal-aspect14-pwm','Fractal Design Aspect 14 PWM · 七叶风量型',140,25,'fractal-aspect',7,
         'https://www.fractal-design.com/app/uploads/2021/05/Aspect_Product-Sheet_EN.pdf',blade_verified=True,hub=.25,power_connector_verified=True,
         notes='Non-RGB PWM140×140×25. Official seven leaves; Trip Wire and aerodynamic stator detail are qualitative references, not the38mm Prisma AL18 geometry.'),
    _fan('thermalright-ty147a','Thermalright TY-147A · 152×140 异形框',140,26.5,'thermalright-ty',7,
         'https://www.thermalright.com/product/macho-rev-b/',width=152,frame='round',hub=.27,power_connector_verified=True,
         notes='Official152×140×26.5 fan envelope, MachoRevB supplied model. Seven-leaf count/contour and orientation of the152mm dimension on the motherboard remain reference.'),
    _fan('bequiet-tf2-upper135','be quiet! Dark Rock TF2 上扇 · Silent Wings3 135',135,25,'bequiet-grooved',7,
         'https://www.bequiet.com/en/cpucooler/3351',frame='round',hub=.28,power_connector_verified=True,marketed_separately_verified=False,
         notes='Documented135×135×25 upper bundled fan with funnel inlet. Not a retail140mm fan. Seven-leaf count/curvature remain reference; no retail availability is claimed.'),
    _fan('bequiet-tf2-lower135','be quiet! Dark Rock TF2 夹层扇 · Silent Wings135',135,22,'bequiet-grooved',9,
         'https://www.bequiet.com/tw/cpucooler/3351',frame='round',hub=.29,blade_verified=True,power_connector_verified=True,marketed_separately_verified=False,
         notes='Official135×135×22 lower bundled fan; Chinese manufacturer description explicitly gives nine leaves. Positioned between two fin banks, not beneath both. Fine contour remains reference.'),
)

_COOLERS.extend([
    _air('noctua-nh-l12s','Noctua NH-L12S · 底置薄扇C形下压','low_profile',(128,70,146),'noctua-nf-a12x15-pwm',1,4,
         ('https://www.noctua.at/en/products/nh-l12s/specifications','https://noctua.at/en/nh-l12s?c=70'),
         c_shape=True,fan_placement='under',documented_fin_count=58,
         notes='Low-profile factory arrangement: fan below fin stack,70mm total. Top-mounted mode is86/87mm across official revisions and is not this record. C-bend radius, offsets and inner RAM clearance remain reference.'),
    _air('noctua-nh-c14s','Noctua NH-C14S · 上置140扇C形下压','low_profile',(140,142,163),'noctua-nf-a14-pwm',1,6,
         ('https://www.noctua.at/en/products/nh-c14s/specifications',),c_shape=True,fan_placement='above',documented_fin_count=66,
         notes='High-clearance arrangement with one fan above the fins,142mm. Underslung115mm mode and optional dual-fan142mm arrangement are not represented as installed fans.'),
    _air('bequiet-dark-rock-tf2','be quiet! Dark Rock TF 2 · 双水平鳍片双扇','dual_top_flow',(140,134,163),
         'bequiet-tf2-upper135',2,6,('https://www.bequiet.com/en/cpucooler/3351','https://www.bequiet.com/es/insidebequiet/5033'),
         fan_models=['bequiet-tf2-upper135','bequiet-tf2-lower135'],fan_sizes=[135,135],fan_depths=[25,22],
         fan_placements=['above','between'],horizontal_fin_banks=2,c_shape=True,fin_color='#30393e',pipe_color='#3d4449',top_style='brushed_caps',
         notes='Official cooler guide confirms134mm total height; current product table swaps107mm overall and134mm heatsink rows. Two135mm fans are25/22mm thick, upper and between the fin banks. Individual bank height/spacing remain reference.'),
    _air('cryorig-h7-quad-lumi','CRYORIG H7 Quad Lumi · 蜂巢鳍片灯塔','single_tower',(123,145,98),
         'cryorig-qf120-led-balance',1,4,('https://www.cryorig.com/news_detail/13',),fin_style='honeycomb',top_style='dark_caps',base_led=True,
         notes='Quad Lumi has four6mm pipes and QF120 Balanced LED fan, unlike original three-pipe H7. Official98L×123W×145H. Honeycomb channel depths and RGB edge layout remain schematic, with no logos.'),
    _air('cryorig-c7','CRYORIG C7 · 47mm 四管紧凑下压','low_profile',(97,47,97),None,1,4,
         ('https://www.cryorig.com/news_detail/10',),fan_reference_mm=92,fan_reference_depth_mm=15,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='cryorig-c7',
         notes='Original aluminium-fin C7, not copper C7Cu or graphene C7G. Official47mm overall and92×92×15 dedicated QuadAirInlet fan; leaf count and fin cuts remain reference.'),
    _air('zalman-cnps9900-max','Zalman CNPS9900 MAX · 镀镍双环鳍片','radial_tower',(131,152,94),None,1,3,
         ('https://www.zalman.com/US/Product/ProductDetail.do?productSeq=324',),fan_reference_mm=125,fan_reference_depth_mm=25,
         fan_dimensions_verified=False,fan_family='zalman-radial',frameless_fan=True,heatpipe_count_verified=False,
         radial_fin_banks=2,radial_outer_reference_mm=126,radial_inner_reference_mm=74,radial_geometry_verified=False,
         fin_color='#6c7478',pipe_color='#8d969b',
         notes='Official131W×152H×94D overall is verified. Two curved copper fin banks with black-pearl nickel plating and middle frameless rotor are qualitative exterior references. Ring126/74mm, fan125×25 and three heatpipes are explicitly schematic values, not measured/model-specific specifications.'),
    _air('scythe-ninja5','Scythe Ninja 5 · 巨型静音单塔双扇','single_tower',(138.5,155,180),None,2,6,
         ('https://www.scythe.co.jp/product/cpu-cooler/scnj-5000/',),fan_reference_mm=120,fan_reference_depth_mm=27,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='scythe-kaze-original',top_style='dark_caps',
         notes='SCNJ-5000 original with two800RPM KazeFlex120×27mm, not RevB or KazeFlexII26mm. Wide square fin block and stepped RAM cuts remain schematic; two fans are opposite sides of one tower.'),
    _air('thermalright-macho-revb','Thermalright Macho Rev.B · 偏置穿孔宽塔','single_tower',(152,162,128.5),'thermalright-ty147a',1,6,
         ('https://www.thermalright.com/product/macho-rev-b/',),asymmetric=True,perforated_fins=True,top_style='exposed_caps',
         heatsink_dimensions_mm=dict(width=140,height=162,depth=102),envelope_is_reference=True,
         notes='Manufacturer140×102×162 is heatsink only; supplied TY147A is152×140×26.5.152W/128.5D envelope is a conservative schematic combination, not a verified installed measurement. Factory includes one fan despite fanless-design marketing.'),
    _air('thermaltake-toughair510','Thermaltake TOUGHAIR 510 · 四管推挽单塔','single_tower',(123.6,159.5,98.8),None,2,4,
         ('https://thermaltake.com/products/toughair-510-cpu-cooler',),fan_reference_mm=120,fan_reference_depth_mm=25,
         fan_dimensions_verified=True,fan_power_connector_verified=True,fan_family='thermaltake-toughfan',asymmetric=True,top_style='dark_caps',
         notes='Official123.6×98.8×159.5 L×W×H; catalog front width follows123.6mm fan face. Two supplied120×25 fans leverage Toughfan design but are not substituted with retail Toughfan12 performance data.'),
    _aio('fractal-lumen-s28-v2','Fractal Design Lumen S28 v2 · 冷排内泵280',(313,140,27),'fractal-aspect14-pwm',2,
         'https://www.fractal-design.com/products/water-cooling/lumen-series/lumen-s28/lumen-s28-v2/',
         pump='fractal_lumen',tube=400,fan_size=140,tube_length_verified=True,pump_location='radiator',
         notes='V2 FD-W-L1-S2811, not recalled original Lumen generation. Round illuminated CPU block cap is not the pump location. Official313mm radiator; CPU block dimensions and internal impeller remain reference.'),
    _aio('xpg-levante-x360','XPG LEVANTE X 360 · 方形无限镜冷头',(394,121,27),None,3,
         'https://www.xpg.com/zw/xpg/pc-component-levante-x-360?tab=spec',pump='xpg_infinity',tube=400,
         tube_length_verified=True,fan_rgb=True,fan_dimensions_verified=True,fan_family='xpg-levante',
         notes='LEVANTE X, not plain LEVANTE. Official394×121×27 radiator,400mm tube,120×25 fans; block72.5×72.5×50 is documented with contradictory H/W/D labels across languages, so block-axis mapping remains reference.'),
    _aio('deepcool-lt720','DeepCool LT720 · 多维无限镜冷头',(402,120,27),None,3,
         'https://www.deepcool.com/products/Cooling/cpuliquidcoolers/LT720-360mm-Liquid-CPU-Cooler-1700-AM5/2022/16286.shtml',
         pump='deepcool_lt_mirror',tube=410,tube_length_verified=True,fan_dimensions_verified=True,fan_power_connector_verified=True,
         fan_family='deepcool-fk120',notes='Original LT720 with non-RGB FK120 fans, not LT720WH or newer LX display models. Multidimensional mirror top is lit; fan blades remain dark.'),
])

for _row in _COOLERS[-12:]:
    if _row['id']=='deepcool-lt720':
        _row['pump_reference_mm']=dict(width=80,height=68,depth=94)
        _row['pump_dimensions_verified']=True
    if _row['id']=='xpg-levante-x360':
        _row['pump_reference_mm']=dict(width=72.5,height=50,depth=72.5)
        _row['pump_axis_orientation_verified']=False
    if _row.get('envelope_is_reference'):_row['dimensions_verified']=False

_BRANDS={'intel':'Intel','amd':'AMD','noctua':'Noctua','deepcool':'DeepCool','thermalright':'Thermalright',
         'arctic':'ARCTIC','corsair':'Corsair','nzxt':'NZXT','lian':'Lian Li','fractal':'Fractal Design',
         'bequiet':'be quiet!','thermaltake':'Thermaltake','asus':'ASUS','custom':'Reference combination',
         'coolermaster':'Cooler Master','idcooling':'ID-COOLING','enermax':'ENERMAX','msi':'MSI',
         'gigabyte':'GIGABYTE','phanteks':'Phanteks','scythe':'Scythe','zalman':'Zalman','alphacool':'Alphacool',
         'ek':'EK Water Blocks','tryx':'TRYX','silverstone':'SilverStone','xpg':'XPG','cryorig':'CRYORIG',
         'antec':'Antec','montech':'Montech','apnx':'APNX'}
for _row in (*_FANS,*_COOLERS):
    _row['brand']=_BRANDS[_row['id'].split('-')[0]]
    _row['series']=_row['label'].split(' · ')[0]
    if 'kind' in _row:_row.setdefault('heatpipe_count_verified',True)

_FAN_BY_ID={row['id']:row for row in _FANS}
_COOLER_BY_ID={row['id']:row for row in _COOLERS}


def get_fan(model_id):
    from fan_mounting044 import apply_mounting_facts
    if not isinstance(model_id,str):return {}
    if model_id in _FAN_BY_ID:return apply_mounting_facts(deepcopy(_FAN_BY_ID[model_id]))
    from hardware_packs import runtime_store
    row=runtime_store().get_model('fan',model_id)
    return deepcopy(row['reference']) if row else {}


def get_cooler(model_id):
    if not isinstance(model_id,str):return {}
    if model_id in _COOLER_BY_ID:return deepcopy(_COOLER_BY_ID[model_id])
    from hardware_packs import runtime_store
    row=runtime_store().get_model('cooler',model_id)
    return deepcopy(row['reference']) if row else {}


def choices_coolers():
    from hardware_packs import runtime_store
    extra=tuple(dict(id=row['id'],label=row['label'],brand=row['vendor'],series=row['series'],pack_id=row['pack_id'],
        **row['selector']) for row in runtime_store().choices('cooler') if row['id'] not in _COOLER_BY_ID)
    return tuple(dict(id=row['id'],label=row['label'],kind=row['kind'],brand=row['brand'],series=row['series'],
        fan_size_mm=row.get('fan_reference_mm') or _FAN_BY_ID.get(row.get('fan_model'),{}).get('size_mm')) for row in _COOLERS)+extra


def choices_fans():
    from hardware_packs import runtime_store
    extra=tuple(dict(id=row['id'],label=row['label'],brand=row['vendor'],series=row['series'],pack_id=row['pack_id'],
        **row['selector']) for row in runtime_store().choices('fan') if row['id'] not in _FAN_BY_ID)
    return tuple(dict(id=row['id'],label=row['label'],size_mm=row['size_mm'],brand=row['brand'],series=row['series'],
        frame=row.get('frame'),frameless=bool(row.get('frameless')),
        mount_pitch_mm=row.get('mount_pitch_mm'),mount_pitch_verified=row.get('mount_pitch_verified',False))
        for row in (get_fan(item['id']) for item in _FANS))+extra
