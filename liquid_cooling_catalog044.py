"""Lazy manual references for standalone custom-loop radiators.

Published envelopes/interfaces are separate from original schematic geometry.
Fan counts are mounting capacity on one side, never detected installed fans.
Port coordinates derived from photographs are explicitly reference positions.
No device I/O, images, CAD, clocks, graphics imports or manufacturing claims.
Original code: PolyForm Noncommercial 1.0.0; product names identify owners.
"""

REVIEWED = '2026-11-08'
_ROWS = None
IDS = (
    'corsair-xr5-240', 'corsair-xr5-360', 'corsair-xr7-360',
    'ek-quantum-surface-s240', 'ek-quantum-surface-p360m', 'ek-quantum-surface-x420m',
    'alphacool-st30-v2-360', 'alphacool-xt45-v2-280', 'alphacool-ut60-360',
    'xspc-tx240', 'xspc-ex280', 'xspc-rx360-v3',
    'hardwarelabs-nemesis-240gts', 'hardwarelabs-nemesis-360gtx', 'hardwarelabs-nemesis-420gts',
    'thermaltake-pacific-cld240', 'thermaltake-pacific-cl360', 'thermaltake-pacific-cl420',
    'watercool-heatkiller-rad-240-s', 'watercool-heatkiller-rad-360-l', 'watercool-heatkiller-rad-420-s',
    'aquacomputer-airplex-radical2-240', 'aquacomputer-airplex-radical2-360', 'aquacomputer-airplex-radical2-420',
)
PORT_LAYOUTS = ('same_end_face_pair', 'multiport_end', 'opposite_end', 'unknown')


def _pair(source, across=.28, along=.455):
    """Qualitative photo/drawing layout; these are not measured CAD coordinates."""
    return [dict(id='connection-'+str(n+1), face='front',
                 position_normalized=[sign*across, along, .5], role='connection',
                 positions_verified=False, source=source)
            for n,sign in enumerate((-1, 1))]


def _end_pair(source, across=.28):
    return [dict(id='alternative-'+str(n+1), face='end', end=1,
                 position_normalized=[sign*across, .5, 0.], role='connection',
                 positions_verified=False, source=source)
            for n,sign in enumerate((-1, 1))]


def _row(identity, label, brand, series, model, size, fan_size, fan_count,
         port_count, family, sources, **facts):
    row = dict(id=identity, label=label, brand=brand, series=series,
        model_number=model, category='radiator', selection_source='manual',
        loop_type='custom', aio_replacement_verified=False,
        dimensions_mm=dict(zip(('length', 'width', 'thickness'), size)),
        dimensions_verified=True,
        dimensions_basis='Manufacturer published standalone product envelope; not manufacturing CAD or a clearance guarantee.',
        fan_size_mm=fan_size, fan_count=fan_count, fan_count_is_installed=False,
        fan_mount_capacity_per_side=fan_count, fan_mount_sides=2,
        fan_mount_pitch_mm=None, fan_mount_pitch_verified=False,
        fan_center_spacing_mm=None, mounting_positions_verified=False,
        ports_count=port_count, active_port_count=2, port_thread='G1/4',
        port_thread_verified=True, port_layout='unknown', port_layout_verified=False,
        ports=[], ports_geometry_complete=False, port_positions_verified=False,
        default_caps_installed=False, shell_family=family, shell_features=[],
        shell_features_basis='reference', shell_geometry_verified=False,
        geometry_accuracy='original_reference', fin_count=None, fpi=None,
        fpi_verified=False, fin_geometry_is_sampling=True,
        materials={}, body_color='#24282b', frame_color='#303539', tank_color='#24282b',
        palette_accuracy='illustrative_not_measured_factory_paint',
        internal_channels_verified=False, sources=list(sources), reviewed=REVIEWED,
        live_flow_available=False, live_temperature_available=False,
        installed_hardware_inferred=False)
    row.update(facts)
    return row


def _build():
    # Record dictionaries/lists are constructed on demand. Source literals
    # remain Python code constants; this is not a zero-import-memory claim.
    corsair = 'https://www.corsair.com/us/en/p/custom-liquid-cooling/'
    c240 = corsair+'cx-9030002-ww/hydro-x-series-xr5-240mm-water-cooling-radiator-cx-9030002-ww'
    c360 = corsair+'cx-9030003-ww/hydro-x-series-xr5-360mm-water-cooling-radiator-cx-9030003-ww'
    c7 = 'https://www.corsair.com/ww/en/p/custom-liquid-cooling/cx-9030005-ww/hydro-x-series-xr7-360mm-water-cooling-radiator-cx-9030005-ww'
    ckit = corsair+'cx-9070018-ww/hydro-x-series-icue-link-xh505i-rx-360-rgb-custom-cooling-kit-cx-9070018-ww'
    ci = 'https://assets.corsair.com/image/upload/c_pad,q_auto,h_1024,w_1024,f_auto/products/Custom-Cooling/'
    ci240 = ci+'CX-9030002-WW/Gallery/XR5_240_01.webp'
    ci360 = ci+'CX-9030003-WW/Gallery/XR5_360_01.webp'
    ci7 = ci+'CX-9030005-WW/Gallery/XR7_360_01.webp'
    eks = 'https://www.ekwb.com/shop/ek-quantum-surface-s240-black'
    ekp = 'https://www.ekwb.com/shop/quantum/pc-water-cooling-radiators/p-series-radiators/ek-quantum-surface-p360m-black'
    ekx = 'https://www.ekwb.com/shop/ek-quantum-surface-x420m-black'
    ast = 'https://www.alphacool.com/download/ENG_1015507_NexXxoS_V2_ST30_360.pdf'
    axt = 'https://www.alphacool.com/download/ENG_1015516_NexXxoS_V2_XT45_280.pdf'
    aut = 'https://download.alphacool.com/datasheet/ENG_14174_Alphacool_NexXxoS_UT60_Full_Copper_360mm_Radiator_datasheet.pdf'
    tx = 'https://www.xs-pc.com/radiators-tx-series/tx240-ultrathin-radiator'
    ex = 'https://www.xs-pc.com/discontinued3/ex280-dual-fan-radiator'
    rx = 'https://www.xs-pc.com/radiators-rx-series/rx360-triple-fan-radiator-v2'
    xi = 'https://images.squarespace-cdn.com/content/v1/51998404e4b0ef02d1bd9c2c/'
    txdraw = xi+'1532587788803-W7S3VGZVBV6WUW5JLWRG/tx240-drawing.jpg'
    exdraw = xi+'1370302365903-ODEFIJ6E43LUVLQ29A6F/ex280-schematic.png'
    rxdraw = xi+'1390523796244-KYNKJWCTYZVEX604O4MB/V3-360.jpg'
    hl = 'https://hardwarelabs.com/2016/wp-content/uploads/2016/10/'
    tt = 'https://thermaltake.com/products/'
    cld = tt+'pacific-cld-240-radiator';cl = tt+'pacific-cl360-radiator';cl420 = tt+'pacific-cl420-radiator'
    tti = 'https://cdn.shopify.com/s/files/1/0985/3206/5560/files/'
    clphoto = tti+'key3_db_products_cooler_CL360_pic1.jpg?v=1786697912'
    cl420photo = tti+'key3_db_products_cooler_CL360_main_420.jpg?v=1786697924'
    cldphoto = 'https://thermaltake.com/cdn/shop/files/pacific_cld_240_1_3086a32d-8a2b-42c9-8d23-2e6f66806fb3.jpg?v=1786946735'
    wc = 'https://shop.watercool.de/'
    wcmanual = wc+'mediafiles/Manuals/MA_HEATKILLER_RAD.pdf'
    aq = 'https://shop.aquacomputer.de/Wasserkuehlung/Radiatoren-Zub/airplex-radical/'
    aq240 = aq+'airplex-radical-2-240-Alu-Lamellen%3A%3A3332.html'
    aq360 = aq+'airplex-radical-2-360-Alu-Lamellen%3A%3A3219.html'
    aq420 = aq+'airplex-radical-2-420-Alu-Lamellen%3A%3A3337.html'
    aqi = 'https://shop.aquacomputer.de/images/product_images/popup_images/'
    standard = dict(cooling_fins='copper', coolant_channels='copper_or_brass_reference')
    result = [
        _row(IDS[0], 'CORSAIR Hydro X XR5 240', 'CORSAIR', 'Hydro X XR5', 'CX-9030002-WW',
             (280,120,30),120,2,2,'corsair_xr_frame',(c240,),
             port_thread='G1/4 BSPP',port_layout='same_end_face_pair',port_layout_verified=True,
             ports=_pair(ci240),ports_geometry_complete=True,
             shell_features=['scalloped_mount_rails','split_shoulder_tanks'],shell_features_basis='observed_reference',
             appearance_sources=[ci240],materials=standard),
        _row(IDS[1], 'CORSAIR Hydro X XR5 360', 'CORSAIR', 'Hydro X XR5', 'CX-9030003-WW',
             (396,120,30),120,3,2,'corsair_xr_frame',(c360,ckit),
             dimensions_basis='Official XH505i component specification explicitly identifies XR5 360 and its396 x120 x30mm envelope; standalone page now omits overall length/width. Not the XR5 V2 revision.',
             port_thread='G1/4 BSPP',port_layout='same_end_face_pair',port_layout_verified=True,
             ports=_pair(ci360),ports_geometry_complete=True,
             shell_features=['scalloped_mount_rails','split_shoulder_tanks'],shell_features_basis='observed_reference',
             appearance_sources=[ci360],materials=standard),
        _row(IDS[2], 'CORSAIR Hydro X XR7 360', 'CORSAIR', 'Hydro X XR7', 'CX-9030005-WW',
             (395,120,55),120,3,2,'corsair_xr_frame',(c7,),
             dimensions_basis='Official technical table overall395 x120 x55mm; promotional core thickness54mm is not substituted for the55mm product envelope.',
             port_thread='G1/4 BSPP',port_layout='same_end_face_pair',port_layout_verified=True,
             ports=_pair(ci7),ports_geometry_complete=True,
             shell_features=['scalloped_mount_rails','split_shoulder_tanks'],shell_features_basis='observed_reference',
             appearance_sources=[ci7],materials=standard),
        _row(IDS[3], 'EK-Quantum Surface S240 · Black', 'EK', 'Quantum Surface S', '3831109838174',
             (285,130,30),120,2,2,'ek_surface_aluminium_caps',(eks,),
             fpi=20,fpi_verified=True,shell_features=['removable_side_plates','contrasting_aluminium_endcaps'],
             shell_features_basis='manufacturer_text_reference',
             materials=dict(fins='copper',tubes='copper',end_tanks='brass',side_plates='stainless_steel',end_covers='aluminium'),
             notes='Official specification read; direct photos/manual return403. Port coordinates and fan-hole pitch remain unknown.'),
        _row(IDS[4], 'EK-Quantum Surface P360M · Black', 'EK', 'Quantum Surface P Multiport', '3831109838419',
             (405,130,44),120,3,5,'ek_surface_aluminium_caps',(ekp,),
             fpi=18,fpi_verified=True,port_layout='multiport_end',port_layout_verified=True,
             shell_features=['removable_side_plates','contrasting_aluminium_endcaps'],shell_features_basis='manufacturer_text_reference',
             notes='Official text: four alternative connection ports plus one opposite-tank fill/drain. Exact positions unavailable; no extra ports invented from count.'),
        _row(IDS[5], 'EK-Quantum Surface X420M · Black', 'EK', 'Quantum Surface X Multiport', '3831109838891',
             (465,145,58),140,3,5,'ek_surface_aluminium_caps',(ekx,),
             fpi=18,fpi_verified=True,port_layout='multiport_end',port_layout_verified=True,
             shell_features=['removable_side_plates','contrasting_aluminium_endcaps'],shell_features_basis='manufacturer_text_reference',
             notes='Four alternative connections and one fill/drain are source facts. Five ports do not mean five active tube connections; precise positions remain unknown.'),
        _row(IDS[6], 'Alphacool NexXxoS ST30 V.2 360', 'Alphacool', 'NexXxoS ST30 V.2', '14345',
             (394.5,124,30),120,3,5,'alphacool_v2_flush_plugs',(ast,),
             fpi=15,fpi_verified=True,port_layout='multiport_end',ports=_pair(ast,.27,.458),
             shell_features=['flush_port_collars','split_shoulder_tanks','scalloped_mount_rails'],shell_features_basis='observed_reference',
             appearance_sources=[ast],materials=dict(fins='copper',tubes='copper',tanks='copper',housing='steel'),
             notes='Only front pair observed in official cover photo. Other three socket positions not assumed; caps not inferred as installed.'),
        _row(IDS[7], 'Alphacool NexXxoS XT45 V.2 280', 'Alphacool', 'NexXxoS XT45 V.2', '14286',
             (316.5,143,45.5),140,2,5,'alphacool_v2_flush_plugs',(axt,),
             fpi=15,fpi_verified=True,port_layout='multiport_end',ports=_pair(axt,.27,.455),
             shell_features=['flush_port_collars','split_shoulder_tanks','scalloped_mount_rails'],shell_features_basis='observed_reference',
             appearance_sources=[axt],materials=dict(fins='copper',tubes='copper',tanks='copper',housing='steel'),
             notes='45.5mm published envelope, not rounded series name45. Front pair observed; remaining three sockets not located.'),
        _row(IDS[8], 'Alphacool NexXxoS UT60 360 · Full Copper', 'Alphacool', 'NexXxoS UT60', '14174',
             (397,124,60),120,3,6,'alphacool_split_tanks',(aut,),
             fpi=10,fpi_verified=True,port_layout='multiport_end',port_layout_verified=True,
             ports=_pair(aut,.27,.455)+_end_pair(aut,.27),
             shell_features=['split_shoulder_tanks','scalloped_mount_rails'],shell_features_basis='observed_reference',
             appearance_sources=[aut],materials=dict(fins='copper',tubes='copper',housing='steel'),
             notes='Exact14174 standard UT60, not X-Flow/Dual-Flow/V2. Current official PDF six G1/4 ports; four visible socket locations only. Other sockets remain unlocated.'),
        _row(IDS[9], 'XSPC TX240 Ultrathin · Black', 'XSPC', 'TX Ultrathin', '5060596650015',
             (278,125,20.5),120,2,2,'xspc_tx_slim',(tx,txdraw),
             fpi=22,fpi_verified=True,port_layout='same_end_face_pair',port_layout_verified=True,
             ports=_pair(txdraw,45/125,.458),ports_geometry_complete=True,
             fan_mount_pitch_mm=105,fan_mount_pitch_verified=True,fan_center_spacing_mm=120,
             mount_dimensions_source=txdraw,port_center_spacing_mm=90,port_center_spacing_verified=True,
             shell_features=['scalloped_mount_rails','ultrathin_core'],shell_features_basis='observed_reference',
             appearance_sources=[txdraw],materials=dict(fins='copper',tubes='H90_copper',tanks='brass'),
             dimensions_tolerance_mm=.5),
        _row(IDS[10], 'XSPC EX280 Dual Fan · Black', 'XSPC', 'EX', 'EX280',
             (320.5,143,36),140,2,2,'xspc_ex_low',(ex,exdraw),
             dimensions_basis='Official product text nominal320mm length; linked mechanical diagram320.50+/-1mm and143+/-1mm width. Diagram nominal used;36mm maximum illustrated depth includes end features.',
             port_layout='same_end_face_pair',port_layout_verified=True,
             ports=_pair(exdraw,58/143,.466),ports_geometry_complete=True,
             fan_mount_pitch_mm=125,fan_mount_pitch_verified=True,fan_center_spacing_mm=140,
             mount_dimensions_source=exdraw,port_center_spacing_mm=116,port_center_spacing_verified=True,
             shell_features=['scalloped_mount_rails','rounded_tanks'],shell_features_basis='observed_reference',
             appearance_sources=[exdraw],materials=standard,
             notes='Official diagram explicitly says125mm fan mounting pitch; not substituted with a generic124.5mm140mm-fan standard.'),
        _row(IDS[11], 'XSPC RX360 Triple Fan V3 · Black', 'XSPC', 'RX V3', '5060175585066',
             (398.5,130,56),120,3,4,'xspc_rx_thick',(rx,rxdraw),
             dimensions_basis='Official V3 product page and linked mechanical diagram398.5+/-1.5 x130 x56mm; URL historically ends-v2 but visible title/SKU identify V3. Not older395mm reseller text.',
             fpi=13,fpi_verified=True,port_layout='multiport_end',port_layout_verified=True,
             ports=_pair(rxdraw,47.5/130,.47)+_end_pair(rxdraw,47.5/130),ports_geometry_complete=True,
             fan_mount_pitch_mm=105,fan_mount_pitch_verified=True,fan_center_spacing_mm=120,
             mount_dimensions_source=rxdraw,port_center_spacing_mm=95,port_center_spacing_verified=True,
             shell_features=['scalloped_mount_rails','rounded_tanks'],shell_features_basis='observed_reference',appearance_sources=[rxdraw],
             materials=standard,notes='Four-G1/4 drawing: face pair plus end-facing pair, same end. End ports are alternatives, not four required active connections.'),
    ]
    for identity,label,model,size,fan_size,count,pitch in (
        (IDS[12],'Hardware Labs Black Ice Nemesis 240GTS','N240GTS',(278,133,31.3),120,2,105),
        (IDS[13],'Hardware Labs Black Ice Nemesis 360GTX','N360GTX',(398,133,55.7),120,3,105),
        (IDS[14],'Hardware Labs Black Ice Nemesis 420GTS','N420GTS',(452,153,31.3),140,3,124.5),
    ):
        source=hl+model+'_MountingDiagram.pdf'
        result.append(_row(identity,label,'Hardware Labs','Black Ice Nemesis',model,size,fan_size,count,2,
            'hwlabs_nemesis',(source,),fan_mount_pitch_mm=pitch,fan_mount_pitch_verified=True,
            mount_dimensions_source=source,dimensions_tolerance_mm=1.,
            dimensions_basis='Manufacturer mechanical diagram OVERALL nominal dimensions +/-1mm, including protrusions; not the smaller marketed core thickness.',
            notes='Official indexed mechanical PDF text read; legacy download now404 after manufacturer website replacement. End-tank/port geometry not inspected, so ports=[] and shell detail stays reference.'))
    result.extend((
        _row(IDS[15], 'Thermaltake Pacific CLD240', 'Thermaltake', 'Pacific CLD', 'CL-W281-CU00BL-A',
             (285.4,119,40),120,2,5,'tt_pacific_stainless_panels',(cld,),fpi=25,fpi_verified=True,
             port_layout='multiport_end',ports=_pair(cldphoto,.27,.455),
             shell_features=['stainless_side_panels','double_fin_core','split_shoulder_tanks'],shell_features_basis='observed_reference',
             appearance_sources=[cldphoto],
             materials=dict(fins='copper',tanks='brass',side_panels='stainless_steel'),
             notes='CLD240 exists; CL240 is not substituted. Exact official CLD240 front pair observed; other three socket locations not assumed.'),
        _row(IDS[16], 'Thermaltake Pacific CL360', 'Thermaltake', 'Pacific CL', 'CL-W191-CU00BL-A',
             (405,132,64),120,3,5,'tt_pacific_stainless_panels',(cl,),fpi=14,fpi_verified=True,
             port_layout='multiport_end',ports=_pair(clphoto,.27,.45),
             shell_features=['stainless_side_panels','triple_row_core','split_shoulder_tanks'],shell_features_basis='observed_reference',
             appearance_sources=[clphoto],materials=dict(fins='copper',tanks='brass',side_panels='stainless_steel'),
             notes='Official exploded picture confirms split front tank and stainless rails. Two visible face sockets only; other three locations unverified.'),
        _row(IDS[17], 'Thermaltake Pacific CL420', 'Thermaltake', 'Pacific CL', 'CL-W193-CU00BL-A',
             (467.5,147.8,64),140,3,5,'tt_pacific_stainless_panels',(cl420,),fpi=14,fpi_verified=True,
             port_layout='multiport_end',ports=_pair(cl420photo,.27,.455),
             shell_features=['stainless_side_panels','triple_row_core','split_shoulder_tanks'],shell_features_basis='observed_reference',
             appearance_sources=[cl420photo],materials=dict(fins='copper',tanks='brass',side_panels='stainless_steel'),
             notes='Exact non-RGB CL420, not CL360 Plus RGB or a bundled loop. Total5 ports but only photographed face pair placed.'),
    ))
    for identity,size_name,model,size,fan_size,count in (
        (IDS[18],'240-S','24101',(278,120,30),120,2),
        (IDS[19],'360-L','24114',(398,120,48),120,3),
        (IDS[20],'420-S','24125',(460,140,30),140,3),
    ):
        source=wc+'HEATKILLER-RAD-'+size_name+'-Black'
        result.append(_row(identity,'Watercool HEATKILLER RAD '+size_name+' · Black','Watercool','HEATKILLER RAD',model,
            size,fan_size,count,2,'watercool_brushed_endplates',(source,wcmanual),
            port_layout='same_end_face_pair',port_layout_verified=True,
            ports=_pair(wcmanual,.30,.46),ports_geometry_complete=True,
            shell_features=['brushed_endplates','removable_side_plates'],shell_features_basis='observed_reference',appearance_sources=[wcmanual],
            materials=dict(fins='copper',tubes='brass',endplates='stainless_steel',side_panels='steel')))
    for identity,nominal,model,size,fan_size,count,source in (
        (IDS[21],240,'33703',(280,140,40),120,2,aq240),
        (IDS[22],360,'33707',(400,140,40),120,3,aq360),
        (IDS[23],420,'33709',(460,140,40),140,3,aq420),
    ):
        photo=aqi+model+'_2.jpg'
        result.append(_row(identity,'Aqua Computer airplex radical 2/'+str(nominal)+' · aluminium fins',
            'Aqua Computer','airplex radical 2',model,size,fan_size,count,2,'aqua_radical_tube_stack',(source,),
            port_layout='same_end_face_pair',port_layout_verified=True,
            ports=_pair(photo,.40,.455),ports_geometry_complete=True,
            shell_features=['silver_unsoldered_core','black_delrin_terminal','stainless_side_plates','insert_mount_guides'],
            shell_features_basis='observed_reference',appearance_sources=[photo],
            materials=dict(fins='aluminium',coolant_tubes='copper',terminal='Delrin',frame='stainless_steel'),
            body_color='#b3b8b8',frame_color='#a2a9ab',tank_color='#252a2c',
            notes='Aluminium-fins SKU, not copper-fins edition. Fin metal is distinct from coolant-contact copper/Delrin; no material-compatibility guarantee.360 primary page now410 but indexed official specification and exact33707 photo retained.'))
    return tuple(result)


def records():
    """Shared tuple for catalog composition; callers treat records as read-only."""
    global _ROWS
    if _ROWS is None:
        _ROWS = _build()
    return _ROWS


def get_radiator(identity):
    """Detached manual reference; invalid identities never allocate the directory."""
    if not isinstance(identity,str) or identity not in IDS:
        return None
    from copy import deepcopy
    return deepcopy(next(row for row in records() if row['id']==identity))


def coverage():
    rows=records()
    return dict(products=len(rows),brands=len({row['brand'] for row in rows}),
                shell_families=len({row['shell_family'] for row in rows}),
                observed_port_layouts=sum(row['port_layout_verified'] for row in rows),
                complete_reference_port_maps=sum(row['ports_geometry_complete'] for row in rows),
                exact_port_positions=0)
