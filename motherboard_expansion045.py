"""Twelve source-reviewed, distinct ITX/mATX/ATX motherboard layouts.

Only original proportional observations ship, never vendor photos or CAD.
The manual establishes connector locations/counts; small ICs, routing, mating
details and heatsink depth remain reference geometry. A missing primary photo
is explicitly pending rather than dressed with another board's heatspreaders.
Original code/art: PolyForm Noncommercial 1.0.0. Product names retain owners.
"""

REVIEWED = '2026-11-08'
MANUALS = {
    'b650e-i': 'https://dlcdnets.asus.com/pub/ASUS/mb/Socket%20AM5/ROG_STRIX_B650E-I_GAMING_WIFI/E20253_ROG_STRIX_B650E-I_GAMING_WIFI_UM_WEB.pdf',
    'b650i-edge': 'https://download.msi.com/archive/mnu_exe/mb/MPGB650IEDGEWIFI.pdf',
    'b550m-itx': 'https://download.asrock.com/Manual/B550M-ITXac.pdf',
    'h670m-itx': 'https://download.asrock.com/Manual/H670M-ITXax.pdf',
    'b650m-tuf': 'https://dlcdnets.asus.com/pub/ASUS/mb/Socket%20AM5/TUF_GAMING_B650M-PLUS_WIFI/E20197_TUF_GAMING_B650M-PLUS_WIFI_UM_WEB.pdf',
    'b760m-prime': 'https://dlcdnets.asus.com/pub/ASUS/mb/LGA1700/PRIME_B760M-A_WIFI_D4/E20870_PRIME_B760M-A_WIFI_D4_UM_WEB.pdf',
    'b550m-pro-vdh': 'https://download-2.msi.com/archive/mnu_exe/mb/B550MPRO-VDHWIFI_B550MPRO-VDHWIFI6.pdf',
    'b550m-ds3h': 'https://download.gigabyte.com/FileList/Manual/mb_manual_b550m-ds3h_e_1503.pdf?v=f48dcfee919cb5657d13fb0b7ff08940',
    'b550-tomahawk': 'https://download.msi.com/archive/mnu_exe/mb/MAGB550TOMAHAWK.pdf',
    'z690-tuf': 'https://dlcdnets.asus.com/pub/ASUS/mb/LGA1700/TUF_GAMING_Z690-PLUS_WIFI_D4/E19393_TUF_GAMING_Z690-PLUS_WIFI_D4_UM_V3_WEB.pdf',
    'b650-pg-lightning': 'https://download.asrock.com/Manual/B650%20PG%20Lightning.pdf',
    'x870-pro-rs': 'https://download.asrock.com/Manual/X870%20Pro%20RS.pdf',
}
PHOTOS = {
    'b650e-i': 'https://dlcdnwebimgs.asus.com/files/media/B21F5C75-0BAA-4FEB-8CFF-0116FE56039F/v1/img/spec/performance.png',
    'b650i-edge': 'https://storage-asset.msi.com/datasheet/mb/us/MPG-B650I-EDGE-WIFI.pdf',
    'b650m-tuf': 'https://dlcdnwebimgs.asus.com/files/media/887b3ca1-93e0-4a35-9771-c4c8153e55cc/V1/img/spec-performance.png',
    'b760m-prime': 'https://dlcdnwebimgs.asus.com/files/media/a42e7284-3844-4cb9-b48d-9a2e8d9763d2/img/new_product_imgs/00_spec/spec_pc.png',
    'b550m-pro-vdh': 'https://storage-asset.msi.com/datasheet/mb/us/B550M-PRO-VDH-WIFI.pdf',
    'b550-tomahawk': 'https://storage-asset.msi.com/datasheet/mb/us/MAG-B550-TOMAHAWK.pdf',
    'z690-tuf': 'https://dlcdnwebimgs.asus.com/files/media/f80add71-70c2-46cc-9722-1ddd47ae64ea/img/component_product.png',
    'b550m-itx': 'https://www.asrock.com/mb/photo/B550M-ITXac(L2).png',
    'h670m-itx': 'https://www.asrock.com/mb/photo/H670M-ITXax(L2).png',
    'b550m-ds3h': 'https://static.gigabyte.com/StaticFile/Image/Global/88e20304d808c65f240b6b77f66c044e/ProductRemoveBg/35433',
    'b650-pg-lightning': 'https://www.asrock.com/mb/photo/B650%20PG%20Lightning(L2).png',
    'x870-pro-rs': 'https://www.asrock.com/mb/photo/X870%20Pro%20RS(L2).png',
}
MSI_FAN_PHOTO = 'https://storage-asset.msi.com/global/picture/product/product_1678348227e9a55fe78aa866f278abec97de2aa859.webp'
ASUS_VENT_PHOTO = 'https://dlcdnwebimgs.asus.com/gain/FE82325B-98A9-4D55-B0FA-E8E168C2FB6B/w1000/h732'


def records(make, slot, m2, connector, cover, rect, rear_observation):
    """Return fresh rows using the catalog's existing, injected constructors."""
    result = []

    def helpers(bounds):
        x0, y0, x1, y1 = bounds

        def uv(x, y):
            return (round((x-x0)/(x1-x0), 5), round((y-y0)/(y1-y0), 5))

        def s(kind, x, y, reinforced=False, lanes=None):
            row = slot(kind, *uv(x, y), reinforced)
            if lanes is not None:
                row['electrical_lanes'] = lanes
            return row

        def drive(x, y, along=(-1, 0), length=80., lengths=(42., 60., 80.), side='front'):
            return m2(*uv(x, y), along, length, side, lengths=lengths)

        def c(kind, x, y, count=1, orientation='front', along=(1, 0), label=''):
            row = connector(kind, *uv(x, y), count, orientation)
            row['along'] = along
            if label:
                row['label'] = label
            return row

        return uv, s, drive, c

    def finish(row, key, series, mark, rear_bounds, rear_items, rear_page, *, mounts=(), notes=(), aliases=()):
        counts = {}
        for kind, _, _ in rear_items:
            counts[kind] = counts.get(kind, 0)+1
        if counts != row['rear_ports']:
            raise ValueError('Rear count/layout mismatch: '+row['id'])
        row.update(series=series, silkscreen_label=mark, reviewed=REVIEWED,
                   rear_layout=rear_observation(rear_bounds, rear_items),
                   rear_layout_source=row['manual'], rear_layout_page=rear_page,
                   mount_uv=tuple(mounts), mount_page=row['layout_page'],
                   mount_method='official_manual_layout_diagram_observed' if mounts else 'not_verified_no_holes_inferred',
                   connector_axis_method='official_manual_observed_proportions',
                   heatsink_depths_verified=False, native_m2_only=True,
                   accessory_cards_assumed_installed=False, aliases=tuple(aliases), notes=tuple(notes))
        row['battery_placement_status']='unverified_not_rendered' if row['battery_uv'] is None else 'manual_observed'
        for port in row['rear_layout']:
            if port['kind'] == 'dvi':
                port['rotated'] = True
        if key not in PHOTOS:
            row.update(finish_status='pending_primary_photo',
                       finish_method='manual_layout_only_primary_photo_not_observed',
                       heatsink_polygons_method='not_added_without_primary_photo')
        else:
            row['heatsink_polygons_method'] = 'primary_photo_observed_reference_depth'
            row.update(finish_status='photo_reviewed', finish_method='official_photo_observed',
                       sources=tuple(dict.fromkeys((*row['sources'],PHOTOS[key]))))
        result.append(row)

    def observed_cover(name, polygon, depth, grooves=0, *, along=None, screws=()):
        """Original photo proportions; depths/channel sampling are reference."""
        value=cover(name,polygon,depth,grooves)
        if along is not None:value['groove_along']=along
        value['fasteners_uv']=tuple(screws)
        return value

    # Mini-ITX: four individual layouts, not reduced ATX coordinate templates.
    # ASUS page14, front PCB (185,223)-(750,785) at1500px; rear view is mirrored.
    uv, s, drive, c = helpers((185, 223, 750, 785))
    row = make('asus-rog-strix-b650e-i-wifi', 'ASUS ROG STRIX B650E-I GAMING WIFI', 'ASUS',
               'itx', 'AM5', 'DDR5', (170., 170.), uv(474, 454),
               (uv(655, 482), uv(688, 482)), (s('x16', 330, 759, True, 16),),
               (drive(562, 693),
                m2(.691, .841, (-1, 0), 80., 'rear', lengths=(42., 60., 80.))),
               (c('eps8', 245, 245, label='ATX_12V'), c('atx24', 726, 351, along=(0, 1), label='ATX_PWR'),
                c('sata', 710, 525, along=(0, 1)), c('sata', 737, 525, along=(0, 1)), c('usb_c', 728, 579, along=(0, 1)),
                c('usb3', 728, 653, along=(0, 1)), c('usb2', 728, 474, along=(0, 1)),
                c('front_io', 729, 715), c('audio', 254, 729),
                c('fan', 463, 234, label='CPU_FAN'), c('fan', 497, 234, label='AIO_PUMP'),
                c('fan', 532, 234, label='CHA_FAN'), c('argb', 577, 234), c('rgb', 619, 234)),
               (cover('vrm-io', ((.008,.025),(.170,.025),(.281,.180),(.276,.689),(.163,.788),(.008,.788)), 26., 6),
                cover('m2-front', ((.152,.763),(.805,.763),(.863,.850),(.863,.912),(.161,.912)), 14., 3)),
               dict(usb_a=6, usb_c=2, hdmi=1, lan=1, audio_3_5=3, spdif=1, antenna=2, buttons=2),
               MANUALS['b650e-i'], 14,
               'https://rog.asus.com/motherboards/rog-strix/rog-strix-b650e-i-gaming-wifi-model/',
               photo=PHOTOS['b650e-i'], battery=None)
    row['io_clear_inset']=False
    row['unplaced_source_features']=('onboard_auxiliary_heatsink_fan_geometry',)
    row['heatsinks'][0]['surface_vent']=dict(
        polygon=((.025,.218),(.143,.120),(.167,.144),(.167,.355),(.138,.400),(.138,.502),(.025,.407)),
        source=ASUS_VENT_PHOTO, method='official_photo_observed_shroud_region',
        hole_map_verified=False, internal_fan_position_verified=False)
    row['onboard_fans']=(dict(id='vrm',placement_status='concealed_under_shroud_unverified',
        blade_count=None,rotation_direction=None,rpm_source=None,source=ASUS_VENT_PHOTO,
        geometry='visible_shroud_vent_only',dimensions_verified=False),)
    row['sources']=(*row['sources'],ASUS_VENT_PHOTO)
    finish(row, 'b650e-i', 'ROG STRIX', 'B650E-I GAMING WIFI', (212,319,1040,520), [
        ('usb_a',311,382),('usb_a',311,431),('hdmi',311,497),
        ('usb_a',566,358),('usb_a',566,403),('usb_a',566,448),('usb_c',566,501),
        ('lan',677,389),('usb_a',677,448),('usb_c',677,501),
        ('antenna',766,344),('antenna',766,487),
        ('audio_3_5',826,422),('audio_3_5',886,422),('audio_3_5',946,422),
        ('buttons',826,504),('buttons',876,504),('spdif',936,489)], 54,
        mounts=tuple(uv(x,y) for x,y in ((295,245),(730,245),(219,764),(730,764))),
        notes=('Rear M.2 observed on mirrored bottom view, mapped into front-view UV.',
               'VRM/M.2 auxiliary heatsink fan is documented, but its unreviewed rotor is not fabricated.',
               'Bundled ROG STRIX HIVE external accessory is not assumed installed.'))

    uv, s, drive, c = helpers((320,355,667,700))
    row = make('msi-mpg-b650i-edge-wifi', 'MSI MPG B650I EDGE WIFI', 'MSI', 'itx', 'AM5', 'DDR5',
        (170.,170.), uv(495,477), (uv(606,504),uv(623,504)), (s('x16',412,684,True,16),),
        (drive(563,637,lengths=(60.,80.)), m2(.754,.835,(-1,0),80.,'rear',lengths=(60.,80.))),
        (c('eps8',359,369,label='CPU_PWR1'),c('atx24',652,456,along=(0,1),label='ATX_PWR1'),
         *[c('sata',x,y,along=(0,1)) for x,y in ((646,533),(659,533),(646,564),(659,564))],
         c('usb_c',655,600,along=(0,1),label='JUSB1'),c('usb3',655,650,along=(0,1),label='JUSB2'),
         c('usb2',447,665,label='JUSB3'),c('front_io',494,666,label='JFP1'),c('audio',408,666,label='JAUD1'),
         c('fan',644,366,label='CPU_FAN1'),c('fan',660,392,along=(0,1),label='PUMP_FAN1'),
         c('fan',586,659,along=(0,1),label='SYS_FAN1'),c('argb',632,663,along=(0,1))),
        (cover('vrm-io',((.008,.070),(.159,.044),(.227,.171),(.235,.744),(.173,.852),(.008,.852)),25.,4),
         cover('m2-front',((.215,.807),(.315,.708),(.698,.708),(.761,.770),(.761,.941),(.372,.941),(.340,.901),(.296,.901)),13.,3)),
        dict(usb_a=5,usb_c=1,hdmi=1,lan=1,antenna=2,audio_3_5=3,buttons=2),MANUALS['b650i-edge'],26,
        'https://www.msi.com/Motherboard/MPG-B650I-EDGE-WIFI/Specification',finish='#bfc2c6',photo=PHOTOS['b650i-edge'],battery=None)
    # The exact board's straight front photo shows a round opening in the
    # right half of the lower M.2 cover. This is an image proportion, not a
    # manufacturer-specified fan diameter or an identified replacement fan.
    row['heatsinks'][1]['static_fan']=dict(id='m2',uv=(.618,.850),diameter_mm=28.,hub_ratio=.52,
        source=MSI_FAN_PHOTO,placement_status='primary_photo_observed_proportions',
        blade_count=None,rotation_direction=None,rpm_source=None,dimensions_verified=False,
        leaf_geometry='not_rendered_unknown',operating_state='unknown_static_reference')
    row['heatsinks'][1]['fasteners_uv']=((.473,.920),(.703,.732))
    row['onboard_fans']=(dict(row['heatsinks'][1]['static_fan']),)
    row['unplaced_source_features']=('onboard_m2_fan_leaf_shape_direction_and_tachometer',)
    row['sources']=(*row['sources'],MSI_FAN_PHOTO)
    finish(row,'b650i-edge','MPG EDGE','B650I EDGE WIFI',(160,333,1041,615),[
        ('buttons',220,543),('buttons',220,586),('hdmi',336,563),
        ('usb_a',493,508),('usb_a',493,564),('usb_a',620,508),('usb_a',620,564),
        ('lan',755,422),('usb_a',755,514),('usb_c',755,582),
        ('antenna',865,395),('antenna',865,533),('audio_3_5',962,377),('audio_3_5',962,473),('audio_3_5',962,582)],22,
        notes=('Onboard M.2 fan opening and hub are photo-observed; blades/direction/tachometer remain unknown and static.',
               'Back-view M2_2 uses mirrored front coordinates.'))

    uv,s,drive,c=helpers((157,389,819,1030))
    row=make('asrock-b550m-itx-ac','ASRock B550M-ITX/ac','ASRock','itx','AM4','DDR4',(170.,170.),uv(481,633),
        (uv(696,671),uv(730,671)),(s('x16',320,1002,False,16),),(drive(654,923,lengths=(80.,)),),
        (c('eps8',210,517,label='ATX12V1'),c('atx24',785,529,along=(0,1),label='ATXPWR1'),
         *[c('sata',x,y,along=(0,1)) for x,y in ((771,663),(800,663),(771,731),(800,731))],
         c('usb3',789,811,along=(0,1)),c('usb2',801,893,along=(0,1)),c('front_io',770,893,along=(0,1)),
         c('audio',181,942,along=(0,1)),c('fan',482,414,label='CPU_FAN1'),
         c('fan',664,413,label='CHA_FAN1/WP'),c('fan',780,963,along=(0,1),label='CHA_FAN2/WP'),
         c('argb',550,413),c('rgb',610,413)),
        (observed_cover('vrm-io',((.120,.064),(.213,.064),(.213,.689),(.168,.671),(.168,.546),(.120,.497)),19.,5),
         observed_cover('m2-front',((.204,.757),(.792,.757),(.792,.880),(.822,.880),(.822,.920),(.204,.920)),6.,3,
                        along=(1.,.32),screws=((.287,.847),(.807,.891)))),
        dict(usb_a=5,usb_c=1,hdmi=1,displayport=1,ps2=1,lan=1,audio_3_5=3,antenna=2),MANUALS['b550m-itx'],11,
        'https://www.asrock.com/mb/AMD/B550M-ITXac/index.asp',finish='#aab0b4',photo=PHOTOS['b550m-itx'],battery=None)
    finish(row,'b550m-itx','ITX/ac','B550M-ITX AC',(157,310,1019,495),[
        ('displayport',238,400),('hdmi',238,450),('usb_a',457,420),('usb_a',457,465),
        ('usb_a',567,352),('usb_a',567,398),('ps2',567,453),
        ('lan',766,364),('usb_a',766,415),('usb_c',766,464),
        ('audio_3_5',875,359),('audio_3_5',875,408),('audio_3_5',875,457),('antenna',966,347),('antenna',966,395)],13,
        notes=('Single front storage M.2; M2_WIFI1 is not a second SSD socket.',
               'Battery is a wired upright assembly in the manual; no unsupported planar coin cell is placed.'))

    uv,s,drive,c=helpers((107,323,842,1036))
    row=make('asrock-h670m-itx-ax','ASRock H670M-ITX/ax','ASRock','itx','LGA1700','DDR4',(170.,170.),uv(487,540),
        (uv(696,644),uv(735,644)),(s('x16',282,1004,True,16),),
        (drive(603,811,lengths=(80.,)),drive(615,912,lengths=(80.,))),
        (c('eps8',253,402,label='ATX12V1'),c('atx24',804,459,along=(0,1),label='ATXPWR1'),
         *[c('sata',x,y,along=(0,1)) for x,y in ((790,736),(818,736),(790,809),(818,809))],
         c('usb3',818,638,along=(0,1)),c('usb2',785,663,along=(0,1)),c('usb_c',792,871,along=(0,1)),
         c('front_io',816,942,along=(0,1)),c('audio',149,987),c('fan',157,348,label='CHA_FAN1/WP'),
         c('fan',338,355,along=(0,1),label='CPU_FAN1'),c('fan',648,780,label='CHA_FAN2'),
         c('argb',664,890,along=(0,1)),c('rgb',767,353,along=(0,1))),
        (observed_cover('vrm-io',((.005,.175),(.228,.175),(.228,.628),(.114,.628),(.005,.568)),23.,4,along=(1.,.70)),
         observed_cover('m2-front',((.150,.643),(.729,.643),(.729,.903),(.770,.903),(.770,.933),(.238,.933),(.213,.907),(.213,.847),(.150,.847)),7.,4,
                        along=(1.,.80),screws=((.204,.665),(.751,.915)))),
        dict(usb_a=6,usb_c=1,hdmi=1,displayport=1,lan=2,audio_3_5=3,antenna=2,buttons=1),MANUALS['h670m-itx'],15,
        'https://www.asrock.com/mb/Intel/H670M-ITXax/index.asp',finish='#bcc1c6',photo=PHOTOS['h670m-itx'],battery=None)
    finish(row,'h670m-itx','ITX/ax','H670M-ITX AX',(150,337,1007,540),[
        ('displayport',248,453),('hdmi',248,513),('buttons',384,380),('usb_a',366,438),
        ('usb_a',485,451),('usb_a',485,498),('lan',620,399),('usb_a',620,455),('usb_a',620,501),
        ('lan',754,399),('usb_a',754,455),('usb_c',754,511),
        ('audio_3_5',867,389),('audio_3_5',867,445),('audio_3_5',867,500),('antenna',951,385),('antenna',951,469)],17,
        notes=('Two LAN jacks; two front storage M.2 sockets. No rear M.2 invented.',))

    # Micro-ATX: actual manual drawings contain different socket and slot tiers.
    uv,s,drive,c=helpers((295,765,714,1184))
    row=make('asus-tuf-b650m-plus-wifi','ASUS TUF GAMING B650M-PLUS WIFI','ASUS','matx','AM5','DDR5',(244.,244.),uv(515,919),
        tuple(uv(x,920) for x in (614,629,645,660)),
        (s('x16',366,1082,True,16),s('x1',367,1115,False,1),s('x16',366,1151,False,4)),
        (drive(554,1043,lengths=(42.,60.,80.)),drive(554,1117,lengths=(42.,60.,80.))),
        (c('atx24',702,908,along=(0,1)),c('eps8',400,776),c('eps4',375,776),
         c('sata',704,1094,2,'edge'),c('sata',577,1177,orientation='edge'),c('sata',609,1177,orientation='edge'),
         c('usb3',703,984,along=(0,1)),c('usb_c',702,1018,along=(0,1)),
         c('usb2',513,1177),c('usb2',544,1177),c('front_io',690,1177),c('audio',372,1177),
         c('fan',591,794,label='CPU_FAN'),c('fan',591,808,label='CPU_OPT'),c('fan',605,775,label='AIO_PUMP'),
         c('fan',390,1046,along=(0,1),label='CHA_FAN1'),c('fan',443,1165,label='CHA_FAN2'),c('fan',443,1178,label='CHA_FAN3'),
         c('argb',653,774),c('argb',684,774),c('argb',653,1177),c('rgb',628,1177)),
        (cover('vrm-top',rect(.172,.020,.742,.145),21.,5),
         cover('vrm-io',((.005,.015),(.102,.015),(.260,.125),(.260,.647),(.080,.670),(.005,.670)),26.,7),
         cover('m2-upper',rect(.257,.639,.831,.696),5.,4),cover('m2-lower',rect(.257,.811,.831,.873),5.,3),
         cover('chipset',((.721,.735),(.852,.735),(.880,.790),(.880,.945),(.720,.945)),8.,3)),
        dict(usb_a=7,usb_c=1,hdmi=1,displayport=1,lan=1,audio_3_5=5,spdif=1,antenna=2,buttons=1),
        MANUALS['b650m-tuf'],11,'https://www.asus.com/motherboards-components/motherboards/tuf-gaming/tuf-gaming-b650m-plus-wifi/',
        photo=PHOTOS['b650m-tuf'],battery=uv(353,1054))
    finish(row,'b650m-tuf','TUF GAMING','TUF B650M-PLUS WIFI',(157,219,852,395),[
        ('displayport',231,304),('hdmi',231,373),('usb_a',327,329),('usb_a',327,369),
        ('usb_a',423,329),('usb_a',423,369),('usb_a',508,329),('usb_c',508,375),
        ('lan',594,276),('usb_a',594,329),('usb_a',594,369),('antenna',672,241),('antenna',672,366),
        ('buttons',672,389),('audio_3_5',740,253),('audio_3_5',740,306),('audio_3_5',796,253),
        ('audio_3_5',796,306),('audio_3_5',796,361),('spdif',749,376)],17,
        mounts=tuple(uv(x,y) for x,y in ((351,775),(577,775),(704,775),(311,1048),(577,1048),(704,1048),(311,1127),(577,1160))),
        notes=('8+4-pin CPU power, not two EPS8 sockets. Four SATA connectors include two bottom-facing singles.',))

    uv,s,drive,c=helpers((358,273,904,820))
    row=make('asus-prime-b760m-a-wifi-d4','ASUS PRIME B760M-A WIFI D4','ASUS','matx','LGA1700','DDR4',(244.,244.),uv(623,455),
        tuple(uv(x,463) for x in (745,767,787,807)),
        (s('x16',453,638,True,16),s('x16',453,726,False,4),s('x16',453,772,False,1)),
        (drive(473,593,(1,0)),drive(676,771,(1,0))),
        (c('atx24',885,420,along=(0,1)),c('eps8',466,288),
         c('sata',886,689,2,'edge'),c('sata',780,810,orientation='edge'),c('sata',816,810,orientation='edge'),
         c('usb3',886,521,along=(0,1)),c('usb3',661,808),c('usb_c',887,582,along=(0,1)),
         c('usb2',579,809),c('usb2',617,809),c('front_io',872,809),c('audio',411,809),
         c('fan',664,283,label='CPU_FAN'),c('fan',689,283,label='CPU_OPT'),c('fan',866,419,along=(0,1),label='CHA_FAN1'),
         c('fan',415,613,along=(0,1),label='CHA_FAN2'),c('argb',885,340,along=(0,1)),
         c('argb',885,362,along=(0,1)),c('argb',885,382,along=(0,1)),c('rgb',704,808)),
        (cover('vrm-top',rect(.190,.035,.651,.145),18.,5),
         cover('vrm-io',((.010,.055),(.170,.055),(.204,.146),(.204,.505),(.150,.559),(.010,.559)),22.,6),
         cover('m2-upper',rect(.180,.603,.680,.660),5.,3),cover('chipset',rect(.713,.722,.835,.854),6.,3)),
        dict(usb_a=6,hdmi=2,displayport=1,ps2=1,lan=1,audio_3_5=3,antenna=2),MANUALS['b760m-prime'],12,
        'https://www.asus.com/motherboards-components/motherboards/prime/prime-b760m-a-wifi-d4/',
        finish='#c8cbd0',photo=PHOTOS['b760m-prime'],battery=uv(537,677))
    finish(row,'b760m-prime','PRIME','PRIME B760M-A WIFI D4',(157,266,1046,479),[
        ('displayport',242,370),('hdmi',242,451),('hdmi',395,456),('ps2',515,339),
        ('usb_a',515,404),('usb_a',515,452),('usb_a',649,402),('usb_a',649,452),
        ('lan',782,332),('usb_a',782,404),('usb_a',782,452),('antenna',902,302),('antenna',902,431),
        ('audio_3_5',992,302),('audio_3_5',992,368),('audio_3_5',992,436)],17,
        mounts=tuple(uv(x,y) for x,y in ((429,288),(723,288),(887,288),(379,641),(723,641),(887,641),(379,744),(723,789))),
        notes=('All three expansion connectors are physical x16 length; their electrical modes are x16/x4/x1.',
               'Two rear HDMI outputs and no rear USB-C; internal Type-C header is separate.'))

    uv,s,drive,c=helpers((264,416,751,902))
    row=make('msi-b550m-pro-vdh-wifi','MSI B550M PRO-VDH WIFI','MSI','matx','AM4','DDR4',(244.,244.),uv(508,565),
        tuple(uv(x,568) for x in (627,645,663,681)),
        (s('x16',349,739,True,16),s('x1',349,820,False,1),s('x1',349,862,False,1)),
        (drive(522,704),drive(566,811)),
        (c('eps8',359,430,label='CPU_PWR1'),c('atx24',737,554,along=(0,1),label='ATX_PWR1'),
         c('sata',737,770,2,'edge'),c('sata',737,806,2,'edge'),c('usb_c',736,675,along=(0,1),label='JUSB1'),
         c('usb3',736,850,along=(0,1),label='JUSB2'),c('usb2',512,891,label='JUSB4'),c('usb2',566,891,label='JUSB3'),
         c('front_io',642,891,label='JFP1'),c('audio',310,891,label='JAUD1'),
         c('fan',572,427,label='CPU_FAN1'),c('fan',714,426,label='PUMP_FAN1'),
         c('fan',743,461,along=(0,1),label='SYS_FAN1'),c('fan',743,635,along=(0,1),label='SYS_FAN2'),
         c('fan',415,891,label='SYS_FAN3'),c('argb',693,428,along=(0,1)),c('argb',711,891),c('rgb',350,891),c('rgb',385,891)),
        (cover('vrm-io',rect(.008,.065,.161,.515),20.,7),cover('m2-upper',rect(.173,.588,.569,.636),5.,6),
         cover('chipset',rect(.746,.747,.873,.859),7.,6)),
        dict(usb_a=6,vga=1,hdmi=1,displayport=1,ps2=1,lan=1,antenna=2,audio_3_5=3,buttons=1),MANUALS['b550m-pro-vdh'],25,
        'https://www.msi.com/Motherboard/B550M-PRO-VDH-WIFI/Specification',photo=PHOTOS['b550m-pro-vdh'],battery=uv(326,782))
    finish(row,'b550m-pro-vdh','PRO','B550M PRO-VDH WIFI',(139,323,1054,570),[
        ('buttons',183,544),('vga',328,438),('displayport',328,542),('usb_a',515,393),('usb_a',515,444),('hdmi',515,542),
        ('ps2',647,400),('usb_a',647,479),('usb_a',647,531),('lan',786,411),('usb_a',786,477),('usb_a',786,531),
        ('antenna',899,391),('antenna',899,514),('audio_3_5',988,366),('audio_3_5',988,443),('audio_3_5',988,521)],22,
        notes=('Shared official manual covers WIFI and WIFI6; this record is the original WIFI SKU, not a WiFi6 identification alias.',))

    uv,s,drive,c=helpers((134,297,902,1063))
    row=make('gigabyte-b550m-ds3h-rev15','GIGABYTE B550M DS3H (rev. 1.5)','GIGABYTE','matx','AM4','DDR4',(244.,244.),uv(498,552),
        tuple(uv(x,550) for x in (694,722,751,779)),
        (s('x16',269,873,False,16),s('x1',269,935,False,1),s('x16',269,999,False,1)),
        (drive(585,809,length=110.,lengths=(80.,110.)),drive(614,934,lengths=(80.,))),
        (c('eps8',290,328,label='ATX_12V'),c('atx24',870,537,along=(0,1),label='ATX'),
         *[c('sata',859,y,orientation='edge') for y in (896,982,1010,1039)],
         c('usb3',607,1042,label='F_U32'),c('usb2',517,1042,label='F_USB1'),c('front_io',704,1042,label='F_PANEL'),
         c('audio',206,1039,label='F_AUDIO'),c('fan',615,334,label='CPU_FAN'),c('fan',340,1042,label='SYS_FAN1'),
         c('fan',764,1042,label='SYS_FAN2')),
        (observed_cover('vrm-io',rect(.176,.083,.279,.429,.008),19.,6),
         observed_cover('chipset',rect(.735,.732,.861,.857,.008),6.,4)),
        dict(usb_a=8,dvi=1,displayport=1,hdmi=1,ps2=1,lan=1,audio_3_5=3),MANUALS['b550m-ds3h'],4,
        'https://www.gigabyte.com/Motherboard/B550M-DS3H-rev-15/sp',finish='#33363a',photo=PHOTOS['b550m-ds3h'],battery=uv(840,658))
    row['requires_revision']=True
    row['finish_revision_association']='photo_linked_by_exact_revision_product_page_not_etched_revision_readback'
    finish(row,'b550m-ds3h','Ultra Durable','B550M DS3H REV 1 5',(182,195,1012,392),[
        ('usb_a',222,251),('usb_a',222,298),('ps2',222,358),('dvi',389,364),
        ('displayport',574,321),('hdmi',574,373),*[('usb_a',687,y) for y in (219,267,315,363)],
        ('lan',877,258),('usb_a',877,311),('usb_a',877,358),
        ('audio_3_5',975,230),('audio_3_5',975,292),('audio_3_5',975,354)],13,
        aliases=('B550M DS3H (rev. 1.5)','B550M DS3H rev. 1.5'),
        notes=('Exact PCB revision1.5 only; unversioned B550M DS3H cannot establish this revision.',
               'No Wi-Fi module/antenna fitted: shared manual AC-only features are excluded.',
               'PCIEX1_2 is physically x16 length but electrically x1 (manual page8).',
               'Circular symbols in layout are temperature sensors/M.2 standoffs, not invented chassis mounting holes.'))

    # ATX: AM4, AM5 and Intel LGA1700 designs with model-specific tiers.
    uv,s,drive,c=helpers((244,384,768,1037))
    row=make('msi-mag-b550-tomahawk','MSI MAG B550 TOMAHAWK','MSI','atx','AM4','DDR4',(304.8,243.84),uv(517,581),
        tuple(uv(x,583) for x in (637,657,677,697)),
        (s('x16',337,775,True,16),s('x1',337,864,False,1),s('x16',337,907,False,4),s('x1',337,995,False,1)),
        (drive(562,731,length=110.,lengths=(42.,60.,80.,110.)),drive(575,954)),
        (c('eps8',350,398,label='CPU_PWR1'),c('atx24',747,600,along=(0,1)),
         c('sata',749,846,2,'edge'),c('sata',749,886,2,'edge'),c('sata',749,928,2,'edge'),
         c('usb_c',750,693,along=(0,1),label='JUSB4'),c('usb3',639,1025,label='JUSB3'),
         c('usb2',595,1025,label='JUSB2'),c('usb2',559,1025,label='JUSB1'),c('front_io',727,1025,label='JFP1'),c('audio',294,1025),
         c('fan',635,394,label='CPU_FAN1'),c('fan',665,394,label='PUMP_FAN1'),
         c('fan',752,439,along=(0,1),label='SYS_FAN1'),c('fan',752,471,along=(0,1),label='SYS_FAN2'),
         c('fan',728,967,along=(0,1),label='SYS_FAN3'),c('fan',516,1025,label='SYS_FAN4'),
         c('fan',397,1025,label='SYS_FAN5'),c('fan',359,694,label='SYS_FAN6'),
         c('argb',713,394),c('argb',713,1001),c('rgb',355,1025),c('rgb',659,1002)),
        (cover('vrm-io',((.008,.030),(.167,.030),(.213,.097),(.213,.483),(.167,.533),(.008,.533)),24.,7),
         cover('vrm-top',rect(.180,.030,.658,.141),19.,4),cover('m2-upper',rect(.176,.510,.635,.563),5.,3),
         cover('m2-lower',rect(.244,.840,.664,.897),5.,3),
         cover('chipset',((.644,.675),(.940,.655),(.948,.835),(.757,.887),(.644,.835)),9.,5)),
        dict(usb_a=5,usb_c=1,displayport=1,hdmi=1,ps2=1,lan=2,audio_3_5=5,spdif=1,buttons=1),MANUALS['b550-tomahawk'],26,
        'https://www.msi.com/Motherboard/MAG-B550-TOMAHAWK/Specification',photo=PHOTOS['b550-tomahawk'],battery=None)
    finish(row,'b550-tomahawk','MAG TOMAHAWK','MAG B550 TOMAHAWK',(164,283,856,470),[
        ('buttons',211,449),('ps2',277,342),('usb_a',277,397),('usb_a',277,444),
        ('displayport',375,374),('hdmi',375,438),('lan',482,346),('usb_a',482,397),('usb_a',482,438),
        ('lan',586,346),('usb_a',586,397),('usb_c',586,441),
        ('audio_3_5',740,311),('audio_3_5',740,371),('audio_3_5',799,311),('audio_3_5',799,371),
        ('audio_3_5',799,432),('spdif',744,435)],23,
        notes=('Two LAN jacks; one8-pin CPU power connector. Two x1 slots remain physically short.',
               'Battery location is not unambiguously labelled in the manual overview; no guessed coin-cell position.'))

    uv,s,drive,c=helpers((187,203,818,989))
    row=make('asus-tuf-z690-plus-wifi-d4','ASUS TUF GAMING Z690-PLUS WIFI D4','ASUS','atx','LGA1700','DDR4',(305.,244.),uv(511,419),
        tuple(uv(x,420) for x in (648,672,697,721)),
        (s('x16',297,674,True,16),s('x1',297,728,False,1),s('x4',297,779,False,4),s('x1',297,833,False,1),s('x16',297,935,False,4)),
        (drive(300,620,(1,0),110.,(42.,60.,80.,110.)),drive(613,810),
         drive(553,884,length=110.,lengths=(42.,60.,80.,110.)),drive(592,884,(1,0))),
        (c('eps8',343,217),c('eps4',302,217),c('atx24',798,426,along=(0,1)),
         c('sata',801,689,2,'edge'),c('sata',648,975,orientation='edge'),c('sata',689,975,orientation='edge'),
         c('usb_c',798,521,along=(0,1)),c('usb3',798,575,along=(0,1)),c('usb2',535,975),c('usb2',575,975),
         c('front_io',777,975),c('audio',309,978),c('fan',545,211,label='CPU_FAN'),c('fan',574,211,label='CPU_OPT'),
         c('fan',416,569,along=(0,1),label='CHA_FAN1'),c('fan',435,569,along=(0,1),label='AIO_PUMP'),
         c('fan',399,978,label='CHA_FAN3'),c('fan',609,978,label='CHA_FAN4'),c('fan',729,975,label='CHA_FAN2'),
         c('argb',765,211),c('argb',469,975),c('argb',434,975),c('rgb',730,211)),
        (cover('vrm-io',((.005,.022),(.111,.020),(.204,.092),(.214,.445),(.145,.477),(.005,.477)),27.,7),
         cover('vrm-top',((.190,.020),(.663,.020),(.708,.102),(.650,.151),(.190,.151)),20.,5),
         cover('m2-upper',rect(.171,.490,.738,.566),5.,4),
         cover('chipset',((.737,.566),(.949,.566),(.950,.821),(.829,.845),(.638,.720),(.638,.650)),8.,5),
         cover('m2-lower',((.170,.821),(.946,.821),(.946,.913),(.896,.936),(.170,.900)),6.,4)),
        dict(usb_a=6,usb_c=2,hdmi=1,displayport=1,lan=1,audio_3_5=5,spdif=1,antenna=2),MANUALS['z690-tuf'],14,
        'https://www.asus.com/motherboards-components/motherboards/tuf-gaming/tuf-gaming-z690-plus-wifi-d4/',
        photo=PHOTOS['z690-tuf'],battery=uv(259,779))
    finish(row,'z690-tuf','TUF GAMING','TUF Z690-PLUS WIFI D4',(177,244,822,419),[
        ('displayport',232,330),('hdmi',232,397),('usb_a',340,290),('usb_a',340,329),('usb_c',340,400),
        ('usb_a',436,351),('usb_a',436,390),('lan',527,295),('usb_a',527,351),('usb_a',527,390),
        ('usb_c',606,399),('antenna',672,273),('antenna',672,375),
        ('audio_3_5',731,273),('audio_3_5',731,330),('audio_3_5',789,273),('audio_3_5',789,330),('audio_3_5',789,387),('spdif',736,388)],54,
        mounts=((.138,.022),(.678,.022),(.974,.022),(.042,.538),(.678,.538),(.974,.538),(.042,.944),(.678,.944),(.974,.944)),
        notes=('Five distinct physical PCIe connectors include one x4 and two x1; no template slot count.',
               '8+4-pin CPU power. Four onboard M.2; no Hyper M.2 accessory card assumed.',))
    row['mount_page']=47

    uv,s,drive,c=helpers((172,315,827,1130))
    row=make('asrock-b650-pg-lightning','ASRock B650 PG Lightning','ASRock','atx','AM5','DDR5',(305.,244.),uv(523,560),
        tuple(uv(x,560) for x in (674,700,724,750)),
        (s('x16',300,805,True,16),s('x1',300,909,False,1),s('x16',300,967,False,2),s('x1',300,1074,False,1)),
        (drive(553,753,lengths=(80.,)),drive(359,850,(1,0),lengths=(80.,)),drive(521,1023,lengths=(80.,))),
        (c('eps8',305,337,label='ATX12V1'),c('eps8',359,337,label='ATX12V2'),c('atx24',803,510,along=(0,1)),
         c('sata',813,850,orientation='edge'),c('sata',813,896,orientation='edge'),
         c('sata',649,1111,orientation='edge'),c('sata',696,1111,orientation='edge'),
         c('usb_c',803,606,along=(0,1)),c('usb3',809,698,along=(0,1)),c('usb2',604,1111),c('usb2',562,1111),
         c('front_io',775,1111),c('audio',243,1111),
         c('fan',650,331,label='CPU_FAN1/WP'),c('fan',650,351,label='CPU_FAN1'),
         c('fan',778,331,label='CHA_FAN1/WP'),c('fan',783,750,along=(0,1),label='CHA_FAN2/WP'),
         c('fan',354,704,label='CHA_FAN3/WP'),c('fan',439,1111,label='CHA_FAN4/WP'),
         c('argb',366,1111),c('argb',404,1111),c('rgb',325,1111)),
        (observed_cover('vrm-io',((.064,.059),(.302,.059),(.302,.432),(.064,.432)),26.,8),
         observed_cover('vrm-top',rect(.320,.005,.664,.073,.007),20.,4,along=(1.,0.)),
         observed_cover('m2-upper',rect(.229,.490,.651,.569,.012),5.,2,along=(1.,0.),screws=((.251,.529),(.627,.529))),
         observed_cover('chipset',rect(.712,.608,.923,.811,.010),8.,6)),
        dict(usb_a=11,usb_c=1,hdmi=1,lan=1,audio_3_5=3,buttons=1),MANUALS['b650-pg-lightning'],10,
        'https://pg.asrock.com/mb/AMD/B650%20PG%20Lightning/index.asp',finish='#303438',photo=PHOTOS['b650-pg-lightning'],battery=uv(261,1031))
    finish(row,'b650-pg-lightning','Phantom Gaming','B650 PG LIGHTNING',(172,278,856,430),[
        ('hdmi',223,410),('usb_a',322,364),('usb_a',322,400),*[('usb_a',417,y) for y in (295,331,368,405)],
        ('lan',507,323),('usb_a',507,364),('usb_a',507,400),('usb_a',597,364),('usb_a',597,400),
        ('usb_a',686,364),('usb_c',686,405),('audio_3_5',771,313),('audio_3_5',771,355),('audio_3_5',771,397),('buttons',827,412)],12,
        notes=('Four PCIe slots, three storage M.2; Key-E M2_WIFI1 is not a fourth SSD slot.',
               'Bottom physical x16 connector has documented x2 electrical mode. No Wi-Fi/antennas assumed.',))

    uv,s,drive,c=helpers((153,303,840,1163))
    row=make('asrock-x870-pro-rs','ASRock X870 Pro RS','ASRock','atx','AM5','DDR5',(305.,244.),uv(525,549),
        tuple(uv(x,559) for x in (678,703,727,752)),
        (s('x16',277,805,True,16),s('x16',277,988,False,4)),
        (drive(490,752,lengths=(80.,)),drive(466,1041,lengths=(80.,)),drive(515,1041,(1,0),lengths=(80.,))),
        (c('eps8',292,327,label='ATX12V1'),c('eps8',343,327,label='ATX12V2'),c('atx24',811,535,along=(0,1)),
         c('sata',820,930,2,'edge'),c('sata',820,984,2,'edge'),c('usb3',815,655,along=(0,1)),
         c('usb_c',815,708,along=(0,1)),c('usb2',486,1139),c('usb2',578,842),
         c('front_io',785,1140),c('audio',218,1140),
         c('fan',685,327,label='CPU_FAN1'),c('fan',714,327,label='CPU_FAN2'),c('fan',745,327,label='AIO_PUMP'),
         c('fan',208,756,along=(0,1),label='CHA_FAN4'),c('fan',588,1142,label='CHA_FAN3'),
         c('fan',657,1142,label='CHA_FAN2'),c('fan',689,1142,label='CHA_FAN1'),
         c('argb',369,1140),c('argb',420,1140),c('argb',805,383,along=(0,1)),c('rgb',312,1140)),
        (observed_cover('vrm-io',((.003,.002),(.137,.002),(.337,.099),(.337,.501),(.005,.501)),28.,4,along=(1.,.63)),
         observed_cover('vrm-top',rect(.311,.002,.724,.111,.012),20.,3,along=(1.,0.)),
         observed_cover('m2-upper',((.102,.502),(.621,.502),(.621,.581),(.171,.581),(.102,.550)),7.,3,along=(1.,.45),screws=()),
         observed_cover('chipset',((.700,.595),(.852,.595),(.948,.636),(.948,.816),(.700,.816)),9.,3,along=(1.,.5)),
         observed_cover('m2-lower',((.061,.821),(.928,.821),(.989,.858),(.989,.903),(.061,.903)),7.,3,
                        along=(1.,0.),screws=((.093,.861),(.902,.861)))),
        dict(usb_a=10,usb_c=2,hdmi=1,lan=1,audio_3_5=2,spdif=1,buttons=1),MANUALS['x870-pro-rs'],11,
        'https://www.asrock.com/mb/AMD/X870%20Pro%20RS/index.asp',finish='#c5c9cc',photo=PHOTOS['x870-pro-rs'],battery=uv(365,932))
    row['pcb_color']='#d6d8d7'
    finish(row,'x870-pro-rs','Pro RS','X870 PRO RS',(90,1083,889,1238),[
        ('buttons',130,1217),('hdmi',215,1219),('usb_a',314,1165),('usb_c',314,1211),
        ('usb_a',436,1165),('usb_c',436,1211),*[('usb_a',554,y) for y in (1116,1149,1180,1215)],
        ('lan',656,1131),('usb_a',656,1173),('usb_a',656,1210),('usb_a',753,1173),('usb_a',753,1210),
        ('audio_3_5',834,1113),('audio_3_5',834,1155),('spdif',834,1210)],13,
        notes=('Non-WiFi SKU: no antenna ports. Common manual separately depicts both rear panels.',
               'Three storage M.2; M2_WIFI1 is an unpopulated optional Key-E location.',
               'Shared-lane restrictions depend on CPU/M.2 population; this appearance does not infer operating configuration.'))
    return tuple(result)
