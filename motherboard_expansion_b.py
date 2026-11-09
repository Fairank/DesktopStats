"""Four exact motherboard layouts, transcribed from primary manuals.

All pixel landmarks were observed on the specified original PDF page. UV and
rear-jack coordinates are proportional observations, never CAD measurements.
Only original geometry facts ship; no photographs, vendor logos or assets.
Unknown mounting-hole centers are omitted. GIGABYTE rev1.0 cover outlines and
qualitative finish use its exact official gallery; depths remain reference.
Original code/art: PolyForm Noncommercial 1.0.0. Product names retain owners.
"""

REVIEWED='2026-11-07'
GIG_MANUAL='https://download.gigabyte.com/FileList/Manual/mb_manual_z790-aorus-master_1003_e.pdf?v=1f20e5dc0c9024d7deb15884b210f135'
TOMAHAWK_MANUAL='https://download.msi.com/archive/mnu_exe/mb/MAGX670ETOMAHAWKWIFI.pdf'
PRO_MANUAL='https://download-2.msi.com/archive/mnu_exe/mb/PROB760M-AWIFI.pdf'
GODLIKE_MANUAL='https://download-2.msi.com/archive/mnu_exe/mb/MEGX670EGODLIKE.pdf'


def records(make,slot,m2,connector,cover,rect,rear_observation):
    """Factory injection keeps this reviewed leaf table free of import cycles."""
    result=[]

    def helpers(bounds):
        x0,y0,x1,y1=bounds
        def uv(x,y):return (round((x-x0)/(x1-x0),5),round((y-y0)/(y1-y0),5))
        def s(kind,x,y,reinforced=False,lanes=None):
            row=slot(kind,*uv(x,y),reinforced)
            if lanes is not None:row['electrical_lanes']=lanes
            return row
        def drive(x,y,along=(-1,0),length=80.,lengths=(60.,80.)):
            return m2(*uv(x,y),along,length,'front',lengths=lengths)
        def c(kind,x,y,count=1,orientation='front',along=(1,0),label=''):
            row=connector(kind,*uv(x,y),count,orientation);row['along']=along
            if label:row['label']=label
            return row
        return uv,s,drive,c

    def finish(row,series,mark,rear_bounds,rear_items,rear_page,*,aliases=(),notes=()):
        counts={}
        for kind,x,y in rear_items:counts[kind]=counts.get(kind,0)+1
        if counts!=row['rear_ports']:raise ValueError('Rear count/layout mismatch: '+row['id'])
        row.update(series=series,silkscreen_label=mark,rear_layout=rear_observation(rear_bounds,rear_items),
            rear_layout_source=row['manual'],rear_layout_page=rear_page,reviewed=REVIEWED,
            mount_uv=(),mount_method='not_verified_no_holes_inferred',
            connector_axis_method='official_manual_observed_right_angle_proportions',
            heatsink_depths_verified=False,heatsink_polygons_method='primary_photo_observed_reference_depth',
            aliases=tuple(aliases),notes=tuple(notes),native_m2_only=True,accessory_cards_assumed_installed=False)
        result.append(row)

    # GIGABYTE page4, PCB bounds(149,351)-(1194,1578) on 2000px render.
    uv,s,drive,c=helpers((149,351,1194,1578))
    row=make('gigabyte-z790-aorus-master','GIGABYTE Z790 AORUS MASTER (rev.1.0)','GIGABYTE','eatx','LGA1700','DDR5',(305.,260.),uv(714,730),
        tuple(uv(x,733) for x in (931,967,1002,1038)),
        (s('x16',320,1086,True,16),s('x16',320,1412,False,1),s('x16',320,1494,False,4)),
        (drive(755,1009,length=110.,lengths=(80.,110.)),drive(755,1156,length=110.,lengths=(80.,110.)),
         drive(755,1248,length=110.,lengths=(80.,110.)),drive(635,1341),drive(1008,1341)),
        (c('atx24',1153,668,along=(0,1),label='ATX'),c('eps8',378,375,label='ATX_12V_2X4_1'),c('eps8',449,375,label='ATX_12V_2X4_2'),
         c('sata',1165,1243,2,'edge',label='SATA3_4_5'),c('sata',1165,1311,2,'edge',label='SATA3_6_7'),
         c('usb3',1162,860,along=(0,1),label='F_U32_1'),c('usb3',1113,860,along=(0,1),label='F_U32_2'),
         c('usb_c',1093,948,along=(0,1),label='F_U32C'),c('usb2',653,1546,label='F_USB2'),c('usb2',735,1546,label='F_USB1'),
         c('audio',248,1546,label='F_AUDIO'),c('front_io',1109,1546,label='F_PANEL'),
         c('fan',319,376,along=(0,1),label='SYS_FAN1'),c('fan',365,422,label='SYS_FAN2'),
         c('fan',966,378,label='CPU_OPT'),c('fan',1012,378,label='CPU_FAN'),c('fan',1058,378,label='SYS_FAN6_PUMP'),
         c('fan',587,1550,label='SYS_FAN3'),c('fan',880,1550,label='SYS_FAN4'),c('fan',930,1550,label='SYS_FAN5_PUMP'),
         c('fan',1163,1363,along=(0,1),label='SYS_FAN7_PUMP'),c('fan',1163,1407,along=(0,1),label='SYS_FAN8_PUMP'),
         c('argb',1170,402,label='D_LED2'),c('argb',374,1550,label='D_LED1'),
         c('rgb',1170,372,label='LED_C2'),c('rgb',450,1550,label='LED_C1')),
        ({'name': 'vrm-io',
      'polygon': ((-0.00644, -0.0232),
                  (0.10425, -0.0232),
                  (0.31789, 0.17348),
                  (0.31789, 0.42431),
                  (0.11583, 0.49834),
                  (-0.00644, 0.49834)),
      'depth_mm': 28.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#34373c',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'vrm-left-fin-bank',
      'polygon': ((0.24968, 0.06519),
                  (0.31017, 0.06519),
                  (0.35779, 0.11934),
                  (0.35779, 0.4884),
                  (0.31789, 0.4884),
                  (0.31789, 0.17127)),
      'depth_mm': 24.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#23262a',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'vrm-top',
      'polygon': ((0.33076, -0.01215),
                  (0.6242, -0.01215),
                  (0.6242, 0.0221),
                  (0.73488, 0.0221),
                  (0.73488, 0.10497),
                  (0.36165, 0.10497),
                  (0.33076, 0.08177)),
      'depth_mm': 22.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#34373d',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-upper',
      'polygon': ((0.0, 0.4884), (0.73488, 0.4884), (0.73488, 0.56685), (0.0, 0.56685)),
      'depth_mm': 12.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#b7bbc0',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-lower-shared',
      'polygon': ((0.06435, 0.6221),
                  (0.92021, 0.6221),
                  (0.93951, 0.64641),
                  (0.93951, 0.84309),
                  (0.06435, 0.84309)),
      'depth_mm': 6.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#b7bbc0',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'chipset-lower-right',
      'polygon': ((0.60489, 0.76243), (0.93951, 0.64641), (0.93951, 0.9326), (0.60489, 0.9326)),
      'depth_mm': 8.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#373c42',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'audio-side-cover',
      'polygon': ((0.0, 0.56685), (0.06435, 0.56685), (0.06435, 0.9337), (0.0, 0.9337)),
      'depth_mm': 4.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#aeb4ba',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False}),dict(usb_a=11,usb_c=3,displayport=1,lan=1,audio_3_5=2,spdif=1,antenna=2,buttons=2),
        GIG_MANUAL,4,'https://www.gigabyte.com/Motherboard/Z790-AORUS-MASTER-rev-10/sp',battery=uv(954,1458),
        diagnostics=(('debug-code',*uv(1153,461)),('power-button',*uv(1088,454))),
    photo='https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
    pcb_color='#2a2b2d',
    static_finish_regions=({'id': 'io-left-silver-rail',
      'polygon': ((-0.00129, 0.0221), (0.06435, 0.0221), (0.06435, 0.47845), (-0.00129, 0.47845)),
      'parent_cover': 'vrm-io',
      'finish_color': '#b9bec4',
      'depth_mm': 0.25,
      'depth_verified': False,
      'finish_color_accuracy': 'qualitative_reference',
      'source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'emissive': False},
     {'id': 'io-silver-shoulder',
      'polygon': ((0.15058, 0.0442), (0.19305, 0.05746), (0.31789, 0.17348), (0.31789, 0.21436)),
      'parent_cover': 'vrm-io',
      'finish_color': '#b9bec4',
      'depth_mm': 0.25,
      'depth_verified': False,
      'finish_color_accuracy': 'qualitative_reference',
      'source': 'https://static.gigabyte.com/StaticFile/Image/Global/cfdc92a87adda3585c6f1e67b49d9a58/ProductRemoveBg/32069',
      'emissive': False}))
    row['sources']=tuple(dict.fromkeys((*row['sources'],
        'https://www.aorus.com/motherboards/z790-aorus-master-rev-10/gallery')))
    finish(row,'AORUS MASTER','Z790 AORUS MASTER',(203,220,1129,440),[
        ('buttons',238,321),('buttons',238,383),('antenna',335,298),('antenna',335,399),
        *[('usb_a',430,y) for y in (258,308,357,410)],
        ('usb_a',558,295),('usb_a',558,344),('displayport',558,414),
        ('usb_a',702,295),('usb_a',702,344),('usb_c',702,421),('usb_a',839,295),('usb_a',839,344),('usb_c',839,421),
        ('lan',976,298),('usb_a',976,358),('usb_c',976,421),('audio_3_5',1087,261),('audio_3_5',1087,330),('spdif',1087,395)],16,
        aliases=('Z790 AORUS MASTER','Z790 AORUS MASTER (rev. 1.0)'),
        notes=('All3 PCIe connectors are physically full length; electrical lanes16/1/4 are not connector length.',
               'M2C_CPU supports25110/2280; PCIEX16 shares its CPU bandwidth. No operating mode inferred.',
               'Four SATA connectors, not six. Official rev1.0 photo-observed armor and qualitative finish are reference, not CAD.'))
    row['heatsink_polygons_method']='primary_photo_observed_reference_depth'

    # MSI X670E TOMAHAWK page28. Four onboardM2; no accessory inferred.
    uv,s,drive,c=helpers((288,548,985,1421))
    row=make('msi-mag-x670e-tomahawk-wifi','MSI MAG X670E TOMAHAWK WIFI','MSI','atx','AM5','DDR5',(304.8,243.84),uv(640,804),
        tuple(uv(x,810) for x in (811,838,865,891)),
        (s('x16',409,1069,True,16),s('x1',409,1184,False,1),s('x16',409,1240,False,4),s('x16',409,1355,False,2)),
        (drive(710,1013,length=110.,lengths=(80.,110.)),drive(492,1124,(1,0)),drive(721,1185),drive(697,1299)),
        (c('atx24',962,842,along=(0,1)),c('eps8',427,566),c('eps8',480,566),
         c('sata',963,1197,2,'edge'),c('sata',963,1249,2,'edge'),
         c('usb3',963,966,along=(0,1)),c('usb3',963,1319,along=(0,1)),c('usb_c',849,1400),
         c('usb2',730,1401),c('usb2',781,1401),c('front_io',947,1401),c('audio',354,1401),
         c('fan',776,611,label='CPU_FAN1'),c('fan',797,561,label='PUMP_FAN1'),c('fan',834,561,label='SYS_FAN1'),
         c('fan',961,704,along=(0,1),label='SYS_FAN2'),c('fan',961,740,along=(0,1),label='SYS_FAN3'),
         c('fan',659,1401,label='SYS_FAN4'),c('fan',611,1401,label='SYS_FAN5'),c('fan',346,1013,along=(0,1),label='SYS_FAN6'),
         c('argb',978,598,along=(0,1)),c('argb',929,1368),c('rgb',410,1401),c('rgb',915,555)),
        (cover('vrm-top',rect(.185,.055,.670,.170),21.,5),
         cover('vrm-io',((.012,.045),(.175,.035),(.225,.135),(.224,.452),(.167,.502),(.008,.480)),27.,7),
         cover('m2-upper',((.157,.501),(.590,.501),(.622,.520),(.622,.568),(.157,.568)),6.,4),
         cover('m2-middle',((.277,.628),(.633,.628),(.677,.670),(.662,.766),(.277,.766)),6.,4),
         cover('m2-lower',rect(.245,.829,.604,.887),5.,3),
         cover('chipset',((.690,.612),(.905,.612),(.946,.661),(.946,.894),(.742,.894),(.690,.840)),8.,6)),
        dict(usb_a=6,usb_c=2,displayport=1,hdmi=1,lan=1,audio_3_5=5,spdif=1,antenna=2,buttons=1),
        TOMAHAWK_MANUAL,28,'https://www.msi.com/Motherboard/MAG-X670E-TOMAHAWK-WIFI/Specification',finish='#353b40',
        photo='https://storage-asset.msi.com/datasheet/mb/global/MAG-X670E-TOMAHAWK-WIFI.pdf',battery=uv(398,1312),
        diagnostics=(('ez-debug',*uv(978,675)),))
    finish(row,'MAG TOMAHAWK','MAG X670E',(173,336,1160,590),[
        ('buttons',268,560),('displayport',369,459),('hdmi',369,546),('usb_a',518,488),('usb_c',518,546),
        *[('usb_a',652,y) for y in (379,435,490,548)],('lan',785,421),('usb_a',785,490),('usb_c',785,546),
        ('antenna',906,408),('antenna',906,523),('audio_3_5',1004,381),('audio_3_5',1087,381),
        ('audio_3_5',1004,458),('audio_3_5',1087,458),('audio_3_5',1087,537),('spdif',1004,536)],24,
        notes=('M2_4 and PCI_E4 share bandwidth; available electrical lanes depend on processor and selected devices.',))

    # MSI PRO B760M-A WIFI DDR5 page27; DDR4 board is a different record.
    uv,s,drive,c=helpers((307,521,1015,1227))
    row=make('msi-pro-b760m-a-wifi','MSI PRO B760M-A WIFI (DDR5)','MSI','matx','LGA1700','DDR5',(243.84,243.84),uv(669,759),
        tuple(uv(x,759) for x in (844,870,897,922)),
        (s('x16',431,993,True,16),s('x1',431,1110,False,1),s('x16',431,1170,False,4)),
        (drive(668,935,lengths=(42.,60.,80.)),drive(741,1110,lengths=(42.,60.,80.))),
        (c('atx24',997,739,along=(0,1)),c('eps8',450,541),c('eps8',503,541),
         c('sata',705,1212),c('sata',757,1212),c('sata',825,1212),c('sata',878,1212),
         c('usb_c',997,867,along=(0,1)),c('usb3',997,936,along=(0,1)),c('usb3',997,1065,along=(0,1)),
         c('usb2',652,1212),c('usb2',564,1212),c('front_io',985,1212),c('audio',375,1212),
         c('fan',805,570,label='CPU_FAN1'),c('fan',997,594,along=(0,1),label='PUMP_FAN1'),
         c('fan',400,945,along=(0,1),label='SYS_FAN1'),c('fan',470,1212,label='SYS_FAN2'),
         c('argb',958,539),c('argb',958,1181),c('rgb',429,1212)),
        (cover('vrm-top',((.264,.042),(.670,.042),(.690,.071),(.674,.161),(.264,.161)),18.,5),
         cover('vrm-left',((.048,.063),(.220,.073),(.296,.170),(.290,.420),(.239,.449),(.048,.411)),20.,6),
         cover('chipset',rect(.704,.715,.817,.846),7.,6)),
        dict(usb_a=6,displayport=2,hdmi=2,lan=1,audio_3_5=3,antenna=2,ps2=1),
        PRO_MANUAL,27,'https://www.msi.com/Motherboard/PRO-B760M-A-WIFI/Specification',finish='#363b40',
        photo='https://storage-asset.msi.com/datasheet/mb/global/PRO-B760M-A-WIFI.pdf',battery=None,
        diagnostics=(('ez-debug',*uv(996,640)),))
    row['battery_placement_status']='unverified_not_rendered'
    finish(row,'PRO','PRO B760M-A',(175,425,1160,690),[
        ('ps2',251,505),('usb_a',252,592),('usb_a',252,650),('displayport',410,554),('hdmi',410,646),
        ('displayport',570,554),('hdmi',570,646),('usb_a',730,585),('usb_a',730,643),('lan',865,510),
        ('usb_a',865,587),('usb_a',865,645),('antenna',990,486),('antenna',990,607),
        ('audio_3_5',1092,465),('audio_3_5',1092,548),('audio_3_5',1092,639)],23,
        aliases=('PRO B760M-A WIFI',),notes=('Exact DDR5 version; not PRO B760M-A WIFI DDR4.',
            'No integrated rear I/O cosmetic shroud inferred. M2 heatsink coverage not assumed where unclear in primary photo.'))

    # MSI GODLIKE page31. Four nativeM2, not six from bundled Xpander card.
    uv,s,drive,c=helpers((252,546,954,1288))
    row=make('msi-meg-x670e-godlike','MSI MEG X670E GODLIKE','MSI','eatx','AM5','DDR5',(304.8,288.),uv(586,803),
        tuple(uv(x,818) for x in (695,723,751,779)),
        (s('x16',358,992,True,16),s('x16',358,1140,True,8),s('x16',358,1235,True,4)),
        (drive(843,875,(0,-1)),drive(604,1043),drive(551,1099),drive(551,1190)),
        (c('atx24',931,832,orientation='edge',along=(0,1)),c('eps8',742,565),c('eps8',793,565),
         c('sata',931,1107,2,'edge'),c('sata',931,1157,2,'edge'),c('sata',931,1190,2,'edge'),c('sata',931,1238,2,'edge'),
         c('usb_c',939,1005,orientation='edge',along=(0,1)),c('usb_c',939,1052,orientation='edge',along=(0,1)),
         c('usb3',939,900,orientation='edge',along=(0,1)),c('usb3',939,941,orientation='edge',along=(0,1)),
         c('usb2',689,1274),c('usb2',737,1274),c('front_io',931,1274),c('audio',309,1274),
         c('fan',853,560,label='CPU_FAN1'),c('fan',889,560,label='PUMP_FAN1'),c('fan',361,560,label='PUMP_FAN2'),
         c('fan',943,613,orientation='edge',along=(0,1),label='SYS_FAN1'),c('fan',943,646,orientation='edge',along=(0,1),label='SYS_FAN2'),
         c('fan',649,1275,label='SYS_FAN3'),c('fan',613,1275,label='SYS_FAN4'),c('fan',578,1275,label='SYS_FAN5'),c('fan',859,1275,label='SYS_FAN6'),
         c('argb',889,1275),c('argb',943,679,orientation='edge',along=(0,1)),c('argb',943,699,orientation='edge',along=(0,1)),
         c('rgb',346,1275),c('aux6',517,1274,label='PCI_E_PWR1'),c('aux6',931,731,orientation='edge',along=(0,1),label='PD_PWR1')),
        (cover('vrm-top',((.180,.045),(.574,.045),(.590,.079),(.560,.156),(.180,.156)),24.,8),
         cover('vrm-io',((.012,.030),(.178,.042),(.211,.130),(.211,.454),(.155,.479),(.008,.453)),31.,7),
         cover('m2-right-armor',((.801,.049),(.887,.075),(.925,.181),(.925,.461),(.866,.515),(.801,.484)),10.,5),
         cover('m2-wide-middle',((.153,.634),(.744,.634),(.897,.684),(.897,.767),(.678,.782),(.153,.782)),8.,7),
         cover('chipset-armor',((.678,.606),(.945,.606),(.945,.925),(.675,.925),(.608,.864),(.675,.820)),10.,7),
         cover('m2-lower',((.153,.838),(.667,.838),(.738,.889),(.738,.909),(.153,.909)),7.,5)),
        dict(usb_a=7,usb_c=2,lan=2,audio_3_5=5,spdif=1,antenna=2,buttons=3),
        GODLIKE_MANUAL,31,'https://www.msi.com/Motherboard/MEG-X670E-GODLIKE/Specification',finish='#41464b',
        photo='https://storage-asset.msi.com/datasheet/mb/global/MEG-X670E-GODLIKE.pdf',battery=uv(921,774),
        diagnostics=(('debug-code',*uv(928,566)),('reset',*uv(789,1276)),('power',*uv(823,1276))))
    finish(row,'MEG GODLIKE','MEG X670E',(173,344,1160,607),[
        ('buttons',299,410),('buttons',299,486),('buttons',299,562),('usb_c',395,486),
        ('lan',517,437),('usb_a',517,507),('usb_a',517,557),('lan',644,437),('usb_a',644,507),('usb_a',644,557),
        ('usb_a',773,393),('usb_a',773,451),('usb_a',773,506),('usb_c',773,570),('antenna',884,424),('antenna',884,540),
        ('audio_3_5',970,396),('audio_3_5',1056,396),('audio_3_5',970,477),('audio_3_5',1056,477),('audio_3_5',1056,555),('spdif',970,556)],25,
        notes=('Four native M2 sockets. Bundled M2 XPANDER-Z GEN5 DUAL and M-Vision display are accessories, not assumed installed.',
            'Right-angle peripheral headers observed; depth/angles/heatsink thickness remain schematic.',
            'Official page contains stale Z690 text below correct AM5 table; only X670E manual/current top specification table used.'))
    row['sources']=(*row['sources'],'https://www.msi.com/faq/8834')
    return tuple(result)
