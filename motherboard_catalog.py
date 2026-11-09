"""Reviewed motherboard envelopes/counts and manually observed layout landmarks.

No photos, logos, CAD, device probes or downloaded content are shipped here.
UV coordinates use the official manual's top view: rear I/O left, DIMMs right,
top edge up. They are observed proportions, not manufacturer's CAD dimensions.
"""
import copy
import re


ASUS_Z790_MANUAL='https://dlcdnets.asus.com/pub/ASUS/mb/LGA1700/ROG_STRIX_Z790-A_GAMING_WIFI_D4/E20739_ROG_STRIX_Z790-A_GAMING_WIFI_D4_UM_WEB.pdf'
ASUS_X670_MANUAL='https://dlcdnets.asus.com/pub/ASUS/mb/Socket%20AM5/ROG_STRIX_X670E-E_GAMING_WIFI/E21210_ROG_STRIX_X670E-E_GAMING_WIFI_UM_V3_WEB.pdf'
MSI_B760_MANUAL='https://download-2.msi.com/archive/mnu_exe/mb/B760MMORTAR_WIFI_MAXWIFI.pdf'
MSI_B650_MANUAL='https://download.msi.com/archive/mnu_exe/mb/MAGB650MMORTARWIFI.pdf'
ASROCK_Z790_MANUAL='https://download.asrock.com/Manual/Z790%20PG-ITXTB4.pdf'
ASROCK_B650_MANUAL='https://download.asrock.com/Manual/B650I%20Lightning%20WiFi.pdf'


def _slot(kind,u,v,reinforced=False):return dict(kind=kind,uv=(u,v),length_mm={'x16':89.,'x4':39.,'x1':25.}[kind],reinforced=reinforced)
def _m2(u,v,along=(1,0),length=80.,side='front',lengths=None):return dict(uv=(u,v),along=along,max_length_mm=length,side=side,
    allowed_lengths_mm=tuple(lengths or ((42.,60.,80.,110.) if length==110. else (42.,60.,80.))))
def _connector(kind,u,v,count=1,orientation='front'):return dict(kind=kind,uv=(u,v),count=count,orientation=orientation)
def _cover(name,points,depth=7.,grooves=0):return dict(name=name,polygon=tuple(points),depth_mm=depth,grooves=grooves)
def _rect(u0,v0,u1,v1,cut=.015):return ((u0+cut,v0),(u1-cut,v0),(u1,v0+cut),(u1,v1-cut),(u1-cut,v1),(u0+cut,v1),(u0,v1-cut),(u0,v0+cut))


def _record(identity,label,brand,form,socket,memory,size,cpu,dimms,pcie,m2,connectors,covers,
            ports,manual,manual_page,product,*,finish='#383b40',photo='',battery=(.12,.69),diagnostics=(),
            pcb_color=None,static_finish_regions=()):
    row=dict(id=identity,label=label,brand=brand,form_factor=form,socket=socket,memory_type=memory,
        dimensions_mm=dict(height=size[0],width=size[1]),cpu_uv=cpu,dimm_uv=tuple(dimms),pcie=tuple(pcie),
        m2=tuple(m2),connectors=tuple(connectors),heatsinks=tuple(covers),rear_ports=dict(ports),
        pcb_color='#242a2d',heatsink_color=finish,battery_uv=battery,diagnostics=tuple(diagnostics),
        sources=tuple(dict.fromkeys((manual,product,*((photo,) if photo else ())))),manual=manual,
        layout_page=manual_page,layout_method='official_manual_observed_proportions',
        finish_method='official_photo_observed' if photo else 'reference_finish_not_photo_verified',
        cad_verified=False,pcb_routing_verified=False,small_package_positions_schematic=True,
        series='',layout_status='manual_reviewed',finish_status='photo_reviewed' if photo else 'unverified_reference',
        market_coverage='named_model_only')
    if pcb_color is not None:
        row.update(pcb_color=pcb_color,pcb_color_accuracy='qualitative_reference_not_colorimetry',
            heatsink_polygons_method='primary_photo_observed_reference_depth',heatsink_depths_verified=False,
            source_finish_model=identity)
    if static_finish_regions:row['static_finish_regions']=tuple(copy.deepcopy(static_finish_regions))
    return row


MODELS=(
 _record('asus-rog-strix-z790-a-wifi-d4','ASUS ROG STRIX Z790-A GAMING WIFI D4','ASUS','atx','LGA1700','DDR4',(305.,244.),(.551,.281),
    ((.773,.283),(.810,.283),(.847,.283),(.884,.283)),
    (_slot('x16',.171,.599,True),_slot('x1',.171,.734),_slot('x16',.171,.801),_slot('x16',.171,.934)),
    (_m2(.176,.532,length=110.),_m2(.646,.782),_m2(.586,.866,(-1,0),110.),_m2(.635,.866)),
    (_connector('atx24',.974,.265),_connector('eps8',.211,.021),_connector('eps8',.294,.021),
     _connector('sata',.968,.643,2,'edge'),_connector('sata',.968,.696,2,'edge'),
     _connector('usb_c',.971,.387),_connector('usb3',.974,.469),_connector('front_io',.943,.983),
     _connector('usb2',.565,.981),_connector('usb2',.665,.981),_connector('audio',.190,.985),
     _connector('fan',.355,.014),_connector('fan',.625,.014),_connector('fan',.372,.466),
     _connector('fan',.404,.466),_connector('fan',.274,.985),_connector('fan',.724,.985),
     _connector('fan',.819,.985),_connector('fan',.862,.985),_connector('argb',.865,.011)),
    (_cover('vrm-top',_rect(.175,.035,.695,.150),22.,6),
     _cover('vrm-io',((.009,.033),(.110,.018),(.185,.090),(.190,.374),(.150,.494),(.004,.494)),28.,5),
     # Official ROG-Strix-Z790-A-Gaming.png: the raised right tab starts
     # outside the DIMM row, not beneath its four sockets. Fractions are an
     # original photo reference, not CAD/manufacturing coordinates. Preserve
     # the main strip, overall envelope and every CPU/DIMM anchor.
     _cover('m2-upper',((.164,.506),(.902,.506),(.920,.486),(.974,.486),(.974,.549),(.922,.577),(.164,.577)),6.,4),
     _cover('chipset',((.607,.618),(.979,.605),(.979,.779),(.724,.813),(.424,.813)),7.,5),
     _cover('m2-middle',_rect(.631,.790,.971,.837),5.,3),
     _cover('m2-lower',((.163,.839),(.974,.839),(.974,.905),(.940,.925),(.163,.925)),6.,4)),
    dict(usb_a=8,usb_c=2,hdmi=1,displayport=1,lan=1,audio_3_5=5,spdif=1,antenna=2,buttons=2),
    ASUS_Z790_MANUAL,14,'https://rog.asus.com/motherboards/rog-strix/rog-strix-z790-a-gaming-wifi-d4-model/spec/',
    finish='#c7cbd0',photo='https://dlcdnwebimgs.asus.com/files/media/BE216201-D173-4850-A7D3-60B0F2319E27/v1/img/kv/ROG-Strix-Z790-A-Gaming.png',
    battery=(.119,.655),diagnostics=(('q-led',.977,.061),('q-release',.969,.541))),
 _record('msi-mag-b760m-mortar-wifi','MSI MAG B760M MORTAR WIFI','MSI','matx','LGA1700','DDR5',(244.,244.),(.516,.316),
    ((.752,.329),(.789,.329),(.826,.329),(.863,.329)),
    (_slot('x16',.171,.668,True),_slot('x1',.171,.832),_slot('x16',.171,.913)),
    (_m2(.509,.586,(-1,0)),_m2(.617,.831,(-1,0))),
    (_connector('atx24',.973,.289),_connector('eps8',.197,.030),_connector('eps8',.273,.030),
     _connector('sata',.963,.885,2,'edge'),_connector('sata',.725,.976),_connector('sata',.795,.976),
     _connector('usb_c',.974,.483),_connector('usb3',.971,.584),_connector('front_io',.968,.977),
     _connector('usb2',.515,.976),_connector('usb2',.637,.976),_connector('audio',.106,.976),
     _connector('fan',.925,.018),_connector('fan',.983,.086),_connector('fan',.281,.516),
     _connector('fan',.215,.976),_connector('fan',.270,.976),_connector('fan',.968,.935),_connector('argb',.717,.024)),
    (_cover('vrm-top',_rect(.183,.057,.662,.161),21.,4),
     _cover('vrm-io',((.009,.037),(.172,.037),(.223,.114),(.218,.481),(.168,.509),(.004,.509)),27.,5),
     _cover('m2-upper',_rect(.159,.560,.541,.625),6.,3),
     _cover('chipset',((.692,.713),(.913,.713),(.950,.763),(.950,.913),(.692,.913)),8.,5)),
    dict(usb_a=7,usb_c=1,hdmi=1,displayport=1,lan=1,audio_3_5=5,spdif=1,antenna=2),
    MSI_B760_MANUAL,27,'https://www.msi.com/Motherboard/MAG-B760M-MORTAR-WIFI/Specification',
    finish='#b9bdc2',photo='https://storage-asset.msi.com/datasheet/mb/us/MAG-B760M-MORTAR-WIFI.pdf',battery=(.127,.752)),
 _record('asrock-z790-pg-itx-tb4','ASRock Z790 PG-ITX/TB4','ASRock','itx','LGA1700','DDR5',(170.,170.),(.518,.426),
    ((.827,.459),(.876,.459)),(_slot('x16',.247,.952,True),),
    (_m2(.714,.805,(0,-1)),_m2(.774,.804,(0,-1),side='rear'),_m2(.443,.811,(1,0),side='rear')),
    (_connector('atx24',.952,.309),_connector('eps8',.266,.045),
     _connector('sata',.931,.777),_connector('sata',.974,.777),_connector('sata',.782,.751),
     _connector('usb_c',.955,.870),_connector('usb3',.970,.650),_connector('front_io',.971,.524),
     _connector('usb2',.330,.896),_connector('audio',.242,.896),_connector('fan',.635,.026),
     _connector('fan',.704,.026),_connector('fan',.775,.026),_connector('argb',.558,.026)),
    ({'name': 'vrm-io',
      'polygon': ((-0.03069, -0.02107),
                  (0.08995, -0.02107),
                  (0.17037, 0.05796),
                  (0.17037, 0.55954),
                  (0.21799, 0.60695),
                  (0.21799, 0.79874),
                  (0.13439, 0.87882),
                  (-0.02857, 0.87882)),
      'depth_mm': 23.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#28292c',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/Z790%20PG-ITXTB4(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'vrm-top',
      'polygon': ((0.31852, 0.0411),
                  (0.79365, 0.0411),
                  (0.79365, 0.11064),
                  (0.71111, 0.17914),
                  (0.32063, 0.17914)),
      'depth_mm': 18.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#2b2c30',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/Z790%20PG-ITXTB4(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-front',
      'polygon': ((0.23704, 0.72708),
                  (0.33545, 0.72708),
                  (0.37566, 0.70917),
                  (0.74286, 0.70917),
                  (0.74286, 0.88936),
                  (0.67407, 0.93467),
                  (0.23598, 0.93467)),
      'depth_mm': 12.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#303135',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/Z790%20PG-ITXTB4(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False}),
    dict(usb_a=6,usb_c=2,hdmi=1,displayport=1,lan=1,audio_3_5=2,spdif=1,antenna=2),
    ASROCK_Z790_MANUAL,10,'https://pg.asrock.com/mb/Intel/Z790%20PG-ITXTB4/index.asp',battery=(.252,.815),
    photo='https://www.asrock.com/mb/photo/Z790%20PG-ITXTB4(L2).png',
    pcb_color='#27282b',
    static_finish_regions=({'id': 'io-silver-border',
      'polygon': ((-0.02434, 0.41307),
                  (0.21376, 0.66702),
                  (0.21376, 0.79663),
                  (0.13228, 0.87777),
                  (-0.02434, 0.87777)),
      'parent_cover': 'vrm-io',
      'finish_color': '#b7bcc0',
      'depth_mm': 0.25,
      'depth_verified': False,
      'finish_color_accuracy': 'qualitative_reference',
      'source': 'https://www.asrock.com/mb/photo/Z790%20PG-ITXTB4(L2).png',
      'emissive': False},
     {'id': 'm2-silver-chevron',
      'polygon': ((0.35661, 0.77345),
                  (0.40847, 0.71549),
                  (0.7418, 0.71549),
                  (0.7418, 0.88409),
                  (0.4709, 0.88409)),
      'parent_cover': 'm2-front',
      'finish_color': '#b9bec2',
      'depth_mm': 0.25,
      'depth_verified': False,
      'finish_color_accuracy': 'qualitative_reference',
      'source': 'https://www.asrock.com/mb/photo/Z790%20PG-ITXTB4(L2).png',
      'emissive': False})),
 _record('asus-rog-strix-x670e-e-wifi','ASUS ROG STRIX X670E-E GAMING WIFI','ASUS','atx','AM5','DDR5',(305.,244.),(.530,.302),
    ((.757,.293),(.794,.293),(.831,.293),(.868,.293)),
    (_slot('x16',.171,.599,True),_slot('x16',.171,.801,True),_slot('x16',.171,.934)),
    (_m2(.612,.533,(-1,0)),_m2(.634,.782),_m2(.586,.866,(-1,0),110.),_m2(.635,.866)),
    (_connector('atx24',.973,.272),_connector('eps8',.211,.021),_connector('eps8',.294,.021),
     _connector('sata',.968,.643,2,'edge'),_connector('sata',.968,.696,2,'edge'),
     _connector('usb_c',.973,.393),_connector('usb3',.976,.469),_connector('front_io',.949,.983),
     _connector('usb2',.544,.981),_connector('usb2',.601,.981),_connector('usb2',.664,.981),
     _connector('audio',.180,.985),_connector('fan',.724,.014),_connector('fan',.782,.014),
     _connector('fan',.826,.014),_connector('fan',.983,.150),_connector('fan',.239,.985),
     _connector('fan',.474,.985),_connector('fan',.751,.985),_connector('fan',.794,.985)),
    (_cover('vrm-top',_rect(.175,.035,.695,.150),24.,7),
     _cover('vrm-io',((.009,.033),(.110,.018),(.185,.090),(.190,.374),(.150,.494),(.004,.494)),30.,7),
     _cover('m2-upper',_rect(.164,.506,.974,.577),8.,4),
     _cover('chipset',((.365,.650),(.978,.610),(.978,.777),(.781,.825),(.164,.825)),9.,8),
     _cover('m2-middle',_rect(.631,.790,.971,.837),6.,4),_cover('m2-lower',_rect(.163,.839,.974,.925),8.,6)),
    dict(usb_a=10,usb_c=3,hdmi=1,displayport=1,lan=1,audio_3_5=5,spdif=1,antenna=2,buttons=2),
    ASUS_X670_MANUAL,16,'https://rog.asus.com/us/motherboards/rog-strix/rog-strix-x670e-e-gaming-wifi-model/spec/',
    finish='#35383e',photo='https://dlcdnwebimgs.asus.com/files/media/B51D103D-2941-412E-8479-AF994957093B/v1/img/kv/ROG-Strix-X670E-E-Gaming.png',
    battery=(.850,.945),diagnostics=(('q-code',.917,.023),('start',.967,.104),('q-release',.965,.541))),
 _record('msi-mag-b650m-mortar-wifi','MSI MAG B650M MORTAR WIFI','MSI','matx','AM5','DDR5',(244.,244.),(.509,.386),
    ((.750,.381),(.788,.381),(.826,.381),(.864,.381)),
    (_slot('x16',.171,.746,True),_slot('x1',.171,.834),_slot('x16',.171,.914)),
    (_m2(.272,.650),_m2(.323,.829)),
    (_connector('atx24',.973,.362),_connector('eps8',.197,.028),_connector('eps8',.273,.028),
     _connector('sata',.972,.873,2,'edge'),_connector('sata',.972,.938,2,'edge'),
     _connector('sata',.832,.978),_connector('sata',.902,.978),
     _connector('usb_c',.974,.548),_connector('usb3',.971,.791),_connector('front_io',.726,.977),
     _connector('usb2',.530,.976),_connector('usb2',.639,.976),_connector('audio',.106,.976),
     _connector('fan',.705,.073),_connector('fan',.738,.021),_connector('fan',.792,.021),
     _connector('fan',.084,.663),_connector('fan',.463,.976),_connector('argb',.983,.075)),
    (_cover('vrm-top',_rect(.183,.057,.662,.161),21.,6),
     _cover('vrm-io',((.009,.037),(.172,.037),(.223,.114),(.218,.481),(.168,.509),(.004,.509)),27.,7),
     _cover('m2-upper',_rect(.158,.616,.677,.698),6.,4),
     _cover('m2-lower',_rect(.323,.789,.696,.865),6.,4),
     _cover('chipset',((.692,.725),(.913,.725),(.950,.770),(.950,.913),(.692,.913)),8.,6)),
    dict(usb_a=7,usb_c=1,hdmi=1,displayport=1,lan=1,audio_3_5=5,spdif=1,antenna=2,buttons=1),
    MSI_B650_MANUAL,28,'https://www.msi.com/Motherboard/MAG-B650M-MORTAR-WIFI/Specification',
    finish='#393c40',photo='https://storage-asset.msi.com/global/picture/image/feature/mb/B650M/MAG-B650M-MORTAR-WIFI/mag-b650m-mortar-wifi.png',battery=(.127,.752)),
 _record('asrock-b650i-lightning-wifi','ASRock B650I Lightning WiFi','ASRock','itx','AM5','DDR5',(170.,170.),(.511,.374),
    ((.827,.446),(.876,.446)),(_slot('x16',.234,.965,True),),
    (_m2(.273,.845),_m2(.805,.820,(0,-1),side='rear')),
    (_connector('atx24',.952,.207),_connector('eps8',.123,.045),
     _connector('sata',.960,.406),_connector('sata',.960,.510),
     _connector('usb_c',.955,.878),_connector('usb3',.961,.676),_connector('front_io',.973,.792),
     _connector('usb2',.927,.792),_connector('audio',.065,.872),_connector('fan',.700,.025),
     _connector('fan',.780,.025),_connector('fan',.183,.872),_connector('argb',.548,.026),_connector('argb',.621,.026)),
    ({'name': 'vrm-io',
      'polygon': ((-0.03287, 0.0555),
                  (0.12725, 0.0555),
                  (0.16331, 0.09178),
                  (0.16331, 0.81323),
                  (-0.03075, 0.81323)),
      'depth_mm': 23.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#202124',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650I%20Lightning%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'vrm-left-bank',
      'polygon': ((0.16331, 0.09178),
                  (0.2333, 0.09178),
                  (0.27784, 0.13661),
                  (0.27784, 0.72785),
                  (0.16225, 0.72785)),
      'depth_mm': 19.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#26272a',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650I%20Lightning%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-front',
      'polygon': ((0.23436, 0.78442),
                  (0.7667, 0.78442),
                  (0.79003, 0.81217),
                  (0.79003, 0.91676),
                  (0.23648, 0.91676)),
      'depth_mm': 13.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#27292c',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650I%20Lightning%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False}),
    dict(usb_a=7,usb_c=1,hdmi=1,lan=1,audio_3_5=3,antenna=2,buttons=1),
    ASROCK_B650_MANUAL,10,'https://pg.asrock.com/mb/AMD/B650I%20Lightning%20WiFi/index.asp',battery=(.118,.763),
    photo='https://www.asrock.com/mb/photo/B650I%20Lightning%20WiFi(L2).png',
    pcb_color='#27292a',
    static_finish_regions=({'id': 'io-diagonal-insert',
      'polygon': ((-0.02015, 0.29989), (0.01273, 0.29989), (0.11453, 0.40128), (0.09438, 0.42369)),
      'parent_cover': 'vrm-io',
      'finish_color': '#b6bdc1',
      'depth_mm': 0.25,
      'depth_verified': False,
      'finish_color_accuracy': 'qualitative_reference',
      'source': 'https://www.asrock.com/mb/photo/B650I%20Lightning%20WiFi(L2).png',
      'emissive': False},)),
)


def _rear_observation(bounds,items,vertical=False):
    x0,y0,x1,y1=bounds
    # A portrait rear-panel photograph is already viewed from outside the
    # case. The case's +X points left in that exterior -Z camera. Horizontal
    # manual diagrams instead show the PCB along their lower baseline.
    return tuple(dict(kind=kind,x_mm=(.5-(x-x0)/(x1-x0))*45. if vertical else ((y-y0)/(y1-y0)-.5)*45.,
        y_mm=(.5-(y-y0)/(y1-y0))*158. if vertical else (.5-(x-x0)/(x1-x0))*158.,
        rotated=kind in ('usb_a','usb_c','hdmi','displayport')) for kind,x,y in items)


# Individual visible jack centers observed from official rear-panel diagrams.
# Physical shield dimensions are nominal; these are not connector CAD positions.
_REAR={
 'asus-rog-strix-z790-a-wifi-d4':((179,99,380,768),True,
    [('hdmi',218,188),('displayport',281,188),('buttons',215,264),('buttons',215,301),
     ('usb_a',277,285),('usb_a',313,285),('usb_a',218,367),('usb_a',254,367),('usb_a',289,367),('usb_a',325,367),
     ('usb_c',216,455),('usb_a',254,455),('usb_c',216,544),('usb_a',254,544),('lan',306,544),
     ('antenna',235,617),('antenna',334,617),('spdif',227,671),('audio_3_5',277,671),('audio_3_5',321,671),
     ('audio_3_5',230,720),('audio_3_5',276,720),('audio_3_5',321,720)],
    'https://dlcdnwebimgs.asus.com/files/media/BE216201-D173-4850-A7D3-60B0F2319E27/v1/img/spec/connectivity.png'),
 'asus-rog-strix-x670e-e-wifi':((175,112,368,770),True,
    [('hdmi',210,196),('displayport',272,196),('usb_c',210,286),('usb_a',247,286),('usb_a',282,286),('usb_a',318,286),
     ('usb_c',210,374),('usb_a',247,374),('usb_a',282,374),('usb_a',318,374),('usb_c',210,467),('usb_a',247,467),('lan',295,467),
     ('usb_a',247,552),('usb_a',282,552),('usb_a',318,552),('buttons',205,532),('buttons',205,569),
     ('antenna',227,614),('antenna',322,614),('spdif',218,674),('audio_3_5',267,674),('audio_3_5',312,674),
     ('audio_3_5',221,723),('audio_3_5',267,723),('audio_3_5',312,723)],
    'https://dlcdnwebimgs.asus.com/files/media/B51D103D-2941-412E-8479-AF994957093B/v1/img/spec/connectivity.png'),
 'msi-mag-b760m-mortar-wifi':((142,1497,511,1607),False,
    [('usb_a',190,1525),('usb_a',190,1544),('usb_a',190,1563),('usb_a',190,1582),('displayport',245,1560),('hdmi',245,1580),
     ('usb_a',304,1564),('usb_c',304,1582),('lan',365,1534),('usb_a',365,1560),('usb_a',365,1582),
     ('antenna',419,1529),('antenna',419,1576),('audio_3_5',450,1526),('audio_3_5',450,1550),('audio_3_5',480,1526),
     ('audio_3_5',480,1550),('audio_3_5',480,1574),('spdif',450,1583)],
    'https://storage-asset.msi.com/datasheet/mb/us/MAG-B760M-MORTAR-WIFI.pdf'),
 'msi-mag-b650m-mortar-wifi':((146,300,986,516),False,
    [('buttons',227,489),('displayport',317,401),('hdmi',317,475),('lan',436,365),('usb_a',436,428),('usb_a',436,477),
     ('usb_a',545,440),('usb_c',545,489),('usb_a',650,338),('usb_a',650,386),('usb_a',650,434),('usb_a',650,482),
     ('antenna',744,357),('antenna',744,456),('audio_3_5',834,339),('audio_3_5',834,402),('spdif',834,477),
     ('audio_3_5',905,339),('audio_3_5',905,402),('audio_3_5',905,470)],MSI_B650_MANUAL),
 'asrock-z790-pg-itx-tb4':((178,320,932,512),False,
    [('displayport',237,436),('hdmi',237,489),('usb_a',342,350),('usb_a',342,393),('usb_a',342,437),('usb_a',342,484),
     ('lan',461,376),('usb_a',461,433),('usb_c',461,482),('usb_a',575,433),('usb_c',575,482),
     ('antenna',756,370),('antenna',756,445),('audio_3_5',867,364),('audio_3_5',867,418),('spdif',867,474)],ASROCK_Z790_MANUAL),
 'asrock-b650i-lightning-wifi':((254,326,884,504),False,
    [('lan',315,382),('usb_a',315,432),('usb_c',315,475),('usb_a',470,382),('usb_a',470,421),('hdmi',470,471),
     ('usb_a',590,347),('usb_a',590,388),('usb_a',590,428),('usb_a',590,471),
     ('audio_3_5',700,374),('audio_3_5',700,421),('audio_3_5',700,471),('buttons',767,482),
     ('antenna',832,378),('antenna',832,443)],ASROCK_B650_MANUAL),
}
for _model in MODELS:
    _bounds,_vertical,_items,_source=_REAR[_model['id']]
    _model['rear_layout']=_rear_observation(_bounds,_items,_vertical)
    _model['rear_layout_source']=_source
    _model['sources']=tuple(dict.fromkeys((*_model['sources'],_source)))
    _model['series']='ROG STRIX' if _model['brand']=='ASUS' else 'MAG MORTAR' if _model['brand']=='MSI' else 'Phantom Gaming'
    if _model['form_factor']=='itx':
        for _slot_row in _model['m2']:_slot_row['allowed_lengths_mm']=(80.,)
    if _model['id']=='msi-mag-b650m-mortar-wifi':
        for _slot_row in _model['m2']:_slot_row['allowed_lengths_mm']=(60.,80.)
    if _model['id']=='asus-rog-strix-z790-a-wifi-d4':
        _model['mount_uv']=((.137,.022),(.676,.022),(.972,.022),(.043,.538),(.676,.538),(.972,.538),(.043,.946),(.676,.946),(.972,.946))
        _model['mount_method']='official_manual_installation_diagram_observed'
        _model['mount_page']=50
        # E20739 layout p1-2 (PDF14): CPU_OPT and CPU_FAN are distinct;
        # the adjacent middle pair is CHA_FAN2 / AIO_PUMP, not two case fans.
        _fan_labels=('CPU_OPT','CPU_FAN','CHA_FAN2','AIO_PUMP','CHA_FAN1','CHA_FAN3','CHA_FAN4','CHA_FAN5')
        for _header,_label in zip((_row for _row in _model['connectors'] if _row['kind']=='fan'),_fan_labels):
            _header.update(label=_label,role='cpu_fan' if _label=='CPU_FAN' else 'cpu_opt' if _label=='CPU_OPT' else 'aio_pump' if _label=='AIO_PUMP' else 'case_fan',
                role_verified=True,role_source=ASUS_Z790_MANUAL,role_source_page=14)
    else:
        _model['mount_uv']=tuple((u,v) for u in (.045,.955) for v in (.035,.965))
        _model['mount_method']='reference_unverified_hole_centers'
    if _model['id'].startswith('asus-'):
        _model['connectors']+=(_connector('argb',.325,.985),_connector('argb',.381,.985),
            _connector('rgb',.922,.011),_connector('thermal',.221,.973),_connector('thunderbolt',.447,.985),_connector('cpu_ov',.773,.011))
        if 'x670' in _model['id']:_model['connectors']+=(_connector('argb',.972,.073),)
    elif _model['id']=='msi-mag-b760m-mortar-wifi':
        _model['connectors']+=(_connector('argb',.418,.976),_connector('rgb',.171,.976))
    elif _model['id']=='msi-mag-b650m-mortar-wifi':
        _model['connectors']+=(_connector('argb',.755,.976),_connector('rgb',.904,.011),_connector('rgb',.172,.976))
    elif _model['id']=='asrock-z790-pg-itx-tb4':
        _model['connectors']+=(_connector('rgb',.927,.531),)


# Additional named boards keep their own manually reviewed landmarks. A model
# with an unavailable primary product photo explicitly retains reference finish.
_TUF_MANUAL='https://dlcdnets.asus.com/pub/ASUS/mb/LGA1700/TUF_GAMING_Z790-PLUS_WIFI/E21279_TUF_GAMING_Z790-PLUS_WIFI_UM_WEB.pdf'
_PRIME_MANUAL='https://dlcdnets.asus.com/pub/ASUS/mb/SocketAM5/PRIME_B650M-A_WIFI_II/E21432_PRIME_B650M-A_WIFI_II_UM_WEB.pdf'
_HERO_MANUAL='https://dlcdnets.asus.com/pub/ASUS/mb/LGA1700/ROG_MAXIMUS_Z790_HERO/E21512_ROG_MAXIMUS_Z790_HERO_UM_V3_WEB.pdf'
_TAICHI_MANUAL='https://download.asrock.com/Manual/X670E%20Taichi_English.pdf'
_STEEL_MANUAL='https://download.asrock.com/Manual/B650E%20Steel%20Legend%20WiFi.pdf'
_RIPTIDE_MANUAL='https://download.asrock.com/Manual/B650M%20PG%20Riptide%20WiFi.pdf'
_EXTRA=(
 _record('asus-tuf-z790-plus-wifi','ASUS TUF GAMING Z790-PLUS WIFI','ASUS','atx','LGA1700','DDR5',(305.,244.),(.524,.268),
    tuple((u,.278) for u in (.744,.781,.819,.857)),
    (_slot('x16',.176,.599,True),_slot('x1',.176,.668),_slot('x4',.176,.737),_slot('x1',.176,.802),_slot('x16',.176,.934)),
    (_m2(.185,.532,length=110.),_m2(.680,.782,(-1,0)),_m2(.587,.866,(-1,0),110.),_m2(.638,.866)),
    (_connector('atx24',.975,.282),_connector('eps8',.211,.023),_connector('eps8',.294,.023),
     _connector('sata',.969,.625,1,'edge'),_connector('sata',.969,.676,1,'edge'),_connector('sata',.725,.984),_connector('sata',.803,.984),
     _connector('usb_c',.974,.405),_connector('usb3',.974,.475),_connector('front_io',.949,.984),
     _connector('usb2',.538,.984),_connector('usb2',.609,.984),_connector('audio',.190,.984),
     _connector('fan',.592,.010),_connector('fan',.627,.010),_connector('fan',.930,.010),_connector('fan',.393,.469),
     _connector('fan',.340,.984),_connector('fan',.665,.984),_connector('fan',.863,.984),
     _connector('argb',.865,.010),_connector('argb',.325,.984),_connector('argb',.382,.984),_connector('rgb',.919,.010)),
    (_cover('vrm-top',_rect(.166,.028,.690,.144),21.,7),
     _cover('vrm-io',((.010,.028),(.192,.028),(.241,.120),(.231,.440),(.190,.492),(.005,.492)),27.,7),
     _cover('m2-upper',_rect(.172,.506,.886,.578),7.,3),
     _cover('chipset',((.756,.655),(.973,.655),(.982,.694),(.982,.822),(.904,.851),(.756,.816)),8.,5),
     _cover('m2-lower',_rect(.171,.842,.976,.917),6.,4)),
    dict(usb_a=6,usb_c=2,hdmi=1,displayport=1,lan=1,audio_3_5=5,spdif=1,antenna=2),
    _TUF_MANUAL,14,'https://www.asus.com/motherboards-components/motherboards/tuf-gaming/tuf-gaming-z790-plus-wifi/techspec/',
    finish='#373c40',photo='https://dlcdnwebimgs.asus.com/files/media/848c744e-84df-40b3-8f01-f9c66ed99227/V1/img/kv-main.png',
    battery=(.117,.648),diagnostics=(('q-led',.975,.073),)),
 _record('asus-prime-b650m-a-wifi-ii','ASUS PRIME B650M-A WIFI II','ASUS','matx','AM5','DDR5',(244.,244.),(.542,.305),
    tuple((u,.298) for u in (.770,.807,.845,.884)),
    (_slot('x16',.173,.665),_slot('x16',.173,.834),_slot('x16',.173,.915)),
    (_m2(.505,.595,(-1,0)),_m2(.959,.887,(-1,0))),
    (_connector('atx24',.975,.337),_connector('eps8',.250,.029),_connector('eps4',.189,.029),
     *(_connector('sata',u,.984) for u in (.690,.760,.830,.900)),
     _connector('usb3',.973,.506),_connector('usb_c',.976,.586),_connector('front_io',.968,.983),
     _connector('audio',.110,.982),_connector('usb2',.492,.982),_connector('usb2',.552,.982),
     _connector('fan',.727,.014),_connector('fan',.727,.047),_connector('fan',.128,.613),_connector('fan',.239,.978),_connector('fan',.199,.978),
     _connector('argb',.976,.078),_connector('argb',.976,.115),_connector('argb',.410,.982),_connector('rgb',.335,.982)),
    (_cover('vrm-io',((.180,.042),(.300,.042),(.310,.124),(.310,.481),(.273,.531),(.180,.531)),17.,5),
     _cover('chipset',_rect(.758,.727,.920,.858),6.,4)),
    dict(usb_a=8,hdmi=1,displayport=1,vga=1,ps2=1,lan=1,audio_3_5=3,antenna=2,buttons=1),
    _PRIME_MANUAL,12,'https://www.asus.com/motherboards-components/motherboards/prime/prime-b650m-a-wifi-ii/techspec/',
    finish='#bbc0c4',photo='https://dlcdnwebimgs.asus.com/files/media/b9eed304-2d06-4485-9507-da139b9937a1/img/kv/kv_pd_light.png',battery=(.565,.753)),
 _record('asus-rog-maximus-z790-hero','ASUS ROG MAXIMUS Z790 HERO','ASUS','atx','LGA1700','DDR5',(305.,244.),(.551,.312),
    tuple((u,.316) for u in (.768,.806,.843,.880)),
    (_slot('x16',.171,.599,True),_slot('x16',.171,.801,True),_slot('x16',.171,.934)),
    (_m2(.180,.534,length=110.),_m2(.544,.865,(-1,0)),_m2(.598,.865)),
    (_connector('atx24',.974,.286),_connector('eps8',.210,.021),_connector('eps8',.293,.021),_connector('aux6',.974,.436),
     _connector('sata',.969,.707,2,'edge'),_connector('sata',.969,.760,2,'edge'),_connector('sata',.969,.811,2,'edge'),
     _connector('usb_c',.973,.487),_connector('usb3',.975,.642),_connector('usb3',.975,.891),_connector('front_io',.956,.983),
     _connector('usb2',.616,.982),_connector('usb2',.714,.982),_connector('audio',.211,.983),
     _connector('fan',.728,.012),_connector('fan',.772,.012),_connector('fan',.817,.012),_connector('fan',.859,.012),
     _connector('fan',.450,.983),_connector('fan',.490,.983),_connector('fan',.535,.983),_connector('fan',.845,.983),
     _connector('argb',.911,.012),_connector('argb',.331,.984),_connector('argb',.388,.984),_connector('rgb',.965,.012),
     _connector('thermal',.781,.985),_connector('thunderbolt',.730,.984)),
    (_cover('vrm-top',_rect(.178,.028,.703,.153),25.,8),
     _cover('vrm-io',((.005,.028),(.177,.028),(.238,.087),(.235,.427),(.187,.497),(.005,.497)),30.,7),
     _cover('m2-upper',_rect(.168,.508,.675,.579),8.,3),
     _cover('chipset',((.167,.652),(.698,.627),(.978,.648),(.978,.807),(.771,.825),(.167,.806)),10.,7),
     _cover('m2-lower',((.169,.839),(.976,.839),(.976,.916),(.924,.932),(.169,.932)),7.,4),
     _cover('audio-shield',_rect(.012,.533,.124,.977),7.,3)),
    dict(usb_a=9,usb_c=3,hdmi=1,lan=1,audio_3_5=5,spdif=1,antenna=2,buttons=2),
    _HERO_MANUAL,16,'https://rog.asus.com/uk/motherboards/rog-maximus/rog-maximus-z790-hero-model/spec/',
    finish='#34383d',photo='https://dlcdnwebimgs.asus.com/files/media/29C004F7-7B1F-4EBF-9099-7168B520A0EE/v1/img/spec/cooling.jpg',
    battery=(.820,.943),diagnostics=(('q-code',.913,.025),('start',.974,.156),('q-led',.975,.093),('q-release',.971,.543))),
 _record('asrock-x670e-taichi','ASRock X670E Taichi','ASRock','eatx','AM5','DDR5',(305.,267.),(.506,.329),
    tuple((u,.327) for u in (.717,.756,.794,.835)),(_slot('x16',.168,.667,True),_slot('x16',.168,.867,True)),
    (_m2(.463,.606,(-1,0),lengths=(80.,)),_m2(.898,.464,(0,1),110.,lengths=(30.,42.,60.,80.,110.)),
     _m2(.463,.726,(-1,0),lengths=(80.,)),_m2(.463,.806,(-1,0),lengths=(80.,))),
    (_connector('atx24',.967,.289),_connector('eps8',.185,.030),_connector('eps8',.266,.030),
     *(_connector('sata',.956,v,2,'edge') for v in (.733,.786,.841,.893)),
     _connector('usb3',.967,.510),_connector('usb_c',.965,.601),_connector('usb3',.581,.978),
     _connector('front_io',.925,.978),_connector('usb2',.440,.978),_connector('usb2',.512,.978),_connector('audio',.120,.978),
     _connector('fan',.722,.033),_connector('fan',.838,.033),_connector('fan',.967,.033),_connector('fan',.974,.412),
     _connector('fan',.681,.575),_connector('fan',.776,.978),_connector('fan',.320,.978),_connector('fan',.820,.978),
     _connector('argb',.908,.034),_connector('argb',.217,.978),_connector('argb',.270,.978),_connector('rgb',.190,.978)),
    ({'name': 'vrm-io',
      'polygon': ((-0.01185, -0.01554),
                  (0.03791, -0.01554),
                  (0.27014, 0.12953),
                  (0.27014, 0.51606),
                  (-0.01066, 0.51606)),
      'depth_mm': 28.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#282a2d',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'vrm-top',
      'polygon': ((0.25474, -0.00725),
                  (0.68128, -0.00725),
                  (0.69194, 0.06218),
                  (0.65521, 0.11813),
                  (0.26659, 0.11813)),
      'depth_mm': 22.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#2c2d30',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-upper',
      'polygon': ((0.09834, 0.52124),
                  (0.56043, 0.52124),
                  (0.66351, 0.6),
                  (0.58768, 0.64974),
                  (0.09834, 0.64974)),
      'depth_mm': 5.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#303135',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-middle',
      'polygon': ((0.1019, 0.69223), (0.58175, 0.69223), (0.58175, 0.84041), (0.1019, 0.84041)),
      'depth_mm': 5.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#292b2e',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-lower',
      'polygon': ((0.1019, 0.88497), (0.92773, 0.88497), (0.92773, 0.93575), (0.1019, 0.93575)),
      'depth_mm': 5.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#2c2e31',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'chipset',
      'polygon': ((0.58294, 0.59067),
                  (0.8673, 0.59067),
                  (0.93602, 0.65492),
                  (0.93602, 0.93575),
                  (0.81398, 0.93575),
                  (0.75829, 0.83938),
                  (0.58294, 0.83938)),
      'depth_mm': 8.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#2c2e31',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False}),
    dict(usb_a=8,usb_c=2,hdmi=1,lan=1,audio_3_5=2,spdif=1,antenna=2,buttons=2),
    _TAICHI_MANUAL,11,'https://www.asrock.com/mb/AMD/X670E%20Taichi/index.asp',battery=(.678,.934),
    diagnostics=(('q-code',.795,.937),('start',.911,.964)),
    photo='https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
    pcb_color='#252628',
    static_finish_regions=({'id': 'io-bronze-rail',
      'polygon': ((-0.01066, -0.01451), (0.0237, -0.01451), (0.0237, 0.51295), (-0.01066, 0.51295)),
      'parent_cover': 'vrm-io',
      'finish_color': '#9a7b48',
      'depth_mm': 0.25,
      'depth_verified': False,
      'finish_color_accuracy': 'qualitative_reference',
      'source': 'https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
      'emissive': False},
     {'id': 'lower-bronze-rail',
      'polygon': ((0.00237, 0.53057), (0.03436, 0.53057), (0.03436, 0.93472), (0.00237, 0.93472)),
      'parent_cover': None,
      'finish_color': '#9a7b48',
      'depth_mm': 0.25,
      'depth_verified': False,
      'finish_color_accuracy': 'qualitative_reference',
      'source': 'https://www.asrock.com/mb/photo/X670E%20Taichi(L2).png',
      'emissive': False})),
 _record('asrock-b650e-steel-legend-wifi','ASRock B650E Steel Legend WiFi','ASRock','atx','AM5','DDR5',(305.,244.),(.528,.318),
    tuple((u,.293) for u in (.772,.810,.847,.884)),(_slot('x16',.169,.599,True),_slot('x16',.169,.800)),
    (_m2(.505,.542,(-1,0),lengths=(60.,80.)),_m2(.467,.868,(-1,0)),_m2(.545,.868,lengths=(30.,42.,60.,80.))),
    (_connector('atx24',.973,.281),_connector('eps8',.197,.027),_connector('eps8',.280,.027),
     _connector('sata',.968,.740,1,'edge'),_connector('sata',.968,.795,1,'edge'),
     _connector('usb3',.973,.419),_connector('usb_c',.971,.490),_connector('usb3',.815,.979),_connector('front_io',.925,.979),
     _connector('usb2',.555,.979),_connector('usb2',.625,.979),_connector('audio',.120,.979),
     _connector('fan',.855,.017),_connector('fan',.900,.017),_connector('fan',.973,.887),
     _connector('fan',.360,.983),_connector('fan',.410,.983),_connector('fan',.710,.983),
     _connector('argb',.976,.091),_connector('argb',.235,.983),_connector('argb',.291,.983),_connector('rgb',.179,.983)),
    ({'name': 'vrm-io',
      'polygon': ((-0.02846, -0.0103),
                  (0.05692, -0.0103),
                  (0.13195, 0.06076),
                  (0.34541, 0.11432),
                  (0.34541, 0.50669),
                  (-0.00129, 0.5829),
                  (-0.02846, 0.52935)),
      'depth_mm': 25.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#c6c8ca',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650E%20Steel%20Legend%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'vrm-top',
      'polygon': ((0.30789, -0.00103),
                  (0.72186, -0.00103),
                  (0.75679, 0.0896),
                  (0.73997, 0.11329),
                  (0.34023, 0.11329),
                  (0.30789, 0.07827)),
      'depth_mm': 20.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#c8cacc',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650E%20Steel%20Legend%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-upper',
      'polygon': ((0.0, 0.50669), (0.60543, 0.50669), (0.60543, 0.55819), (0.56533, 0.58702), (0.0, 0.58702)),
      'depth_mm': 9.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#cbd0d1',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650E%20Steel%20Legend%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-lower',
      'polygon': ((0.01164, 0.8311),
                  (0.94308, 0.8311),
                  (0.94308, 0.89701),
                  (0.91979, 0.91246),
                  (0.01164, 0.91246)),
      'depth_mm': 6.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#c6cacc',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650E%20Steel%20Legend%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'chipset',
      'polygon': ((0.68952, 0.57364),
                  (0.87063, 0.57364),
                  (0.9379, 0.62925),
                  (0.9379, 0.77961),
                  (0.87193, 0.8311),
                  (0.68564, 0.8311),
                  (0.62096, 0.77961),
                  (0.62096, 0.62925)),
      'depth_mm': 7.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#c3c6c8',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650E%20Steel%20Legend%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False}),
    dict(usb_a=7,usb_c=1,hdmi=1,displayport=1,lan=1,audio_3_5=2,spdif=1,antenna=2,buttons=1),
    _STEEL_MANUAL,10,'https://www.asrock.com/mb/AMD/B650E%20Steel%20Legend%20WiFi/index.asp',battery=(.133,.703),
    photo='https://www.asrock.com/mb/photo/B650E%20Steel%20Legend%20WiFi(L2).png',
    pcb_color='#292a2c',
    static_finish_regions=()),
 _record('asrock-b650m-pg-riptide-wifi','ASRock B650M PG Riptide WiFi','ASRock','matx','AM5','DDR5',(244.,244.),(.541,.294),
    tuple((u,.323) for u in (.775,.812,.850,.887)),
    (_slot('x16',.177,.665,True),_slot('x1',.184,.748),_slot('x1',.184,.831),_slot('x16',.177,.915)),
    (_m2(.505,.598,(-1,0),lengths=(60.,80.)),_m2(.966,.903,(-1,0),lengths=(60.,80.))),
    (_connector('atx24',.974,.319),_connector('eps8',.220,.035),_connector('eps4',.286,.035),
     _connector('sata',.979,.535),_connector('sata',.979,.609),_connector('sata',.973,.755,2,'edge'),
     _connector('usb3',.945,.587),_connector('usb3',.730,.977),_connector('usb_c',.970,.450),_connector('front_io',.970,.977),
     _connector('usb2',.484,.977),_connector('usb2',.550,.977),_connector('audio',.118,.977),
     _connector('fan',.490,.023),_connector('fan',.129,.616),_connector('fan',.350,.976),_connector('fan',.410,.976),_connector('fan',.587,.976),
     _connector('argb',.968,.104),_connector('argb',.218,.977),_connector('argb',.276,.977),_connector('rgb',.965,.035)),
    ({'name': 'vrm-io',
      'polygon': ((-0.02366, -0.00936),
                  (0.07202, -0.00936),
                  (0.33539, 0.18087),
                  (0.33539, 0.53846),
                  (-0.02263, 0.53846)),
      'depth_mm': 24.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#2b2d30',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650M%20PG%20Riptide%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'm2-upper',
      'polygon': ((0.14198, 0.55405),
                  (0.55144, 0.55405),
                  (0.57099, 0.58212),
                  (0.55041, 0.64657),
                  (0.14198, 0.64657)),
      'depth_mm': 8.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#292c30',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650M%20PG%20Riptide%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False},
     {'name': 'chipset',
      'polygon': ((0.72634, 0.64449), (0.92181, 0.64449), (0.92181, 0.84927), (0.72634, 0.84927)),
      'depth_mm': 7.0,
      'depth_verified': False,
      'grooves': 0,
      'finish_color': '#272a2e',
      'finish_color_accuracy': 'qualitative_reference',
      'outline_source': 'https://www.asrock.com/mb/photo/B650M%20PG%20Riptide%20WiFi(L2).png',
      'outline_method': 'official_photo_observed_reference_proportions',
      'cad_verified': False}),
    dict(usb_a=7,usb_c=1,hdmi=1,displayport=1,lan=1,audio_3_5=3,antenna=2,buttons=1),
    _RIPTIDE_MANUAL,10,'https://pg.asrock.com/mb/AMD/B650M%20PG%20Riptide%20WiFi/index.asp',battery=(.610,.755),
    photo='https://www.asrock.com/mb/photo/B650M%20PG%20Riptide%20WiFi(L2).png',
    pcb_color='#25272a',
    static_finish_regions=({'id': 'io-blue-insert',
      'polygon': ((0.25514, 0.18919), (0.27058, 0.20062), (0.27058, 0.53742), (0.25514, 0.53742)),
      'parent_cover': 'vrm-io',
      'finish_color': '#3c8cae',
      'depth_mm': 0.25,
      'depth_verified': False,
      'finish_color_accuracy': 'qualitative_reference',
      'source': 'https://www.asrock.com/mb/photo/B650M%20PG%20Riptide%20WiFi(L2).png',
      'emissive': False},)),
)

_EXTRA_REAR={
 'asus-tuf-z790-plus-wifi':((237,286,907,463),False,
    [('displayport',283,376),('hdmi',283,446),('usb_a',384,360),('usb_a',384,397),('usb_c',384,449),
     ('usb_a',479,400),('usb_a',479,444),('lan',574,345),('usb_a',574,406),('usb_a',574,446),('usb_c',655,450),
     ('antenna',741,322),('antenna',741,425),('audio_3_5',820,319),('audio_3_5',878,319),('audio_3_5',820,375),
     ('audio_3_5',878,375),('audio_3_5',878,434),('spdif',827,431)]),
 'asus-prime-b650m-a-wifi-ii':((164,239,907,424),False,
    [('vga',261,283),('hdmi',199,406),('displayport',312,406),('buttons',393,413),('ps2',477,303),
     ('usb_a',477,357),('usb_a',477,397),('usb_a',587,272),('usb_a',587,313),('usb_a',587,356),('usb_a',587,398),
     ('lan',694,296),('usb_a',694,357),('usb_a',694,398),('antenna',806,272),('antenna',806,384),
     ('audio_3_5',875,271),('audio_3_5',875,331),('audio_3_5',875,391)]),
 'asrock-x670e-taichi':((217,328,946,501),False,
    [('buttons',244,401),('buttons',244,458),('antenna',318,372),('antenna',318,444),('hdmi',401,466),
     ('lan',479,383),('usb_a',479,438),('usb_a',479,477),('audio_3_5',563,374),('audio_3_5',563,422),('spdif',563,469),
     ('usb_a',660,433),('usb_c',660,477),('usb_a',784,433),('usb_c',784,477),
     ('usb_a',899,351),('usb_a',899,392),('usb_a',899,433),('usb_a',899,473)]),
 'asrock-b650e-steel-legend-wifi':((243,334,950,508),False,
    [('hdmi',280,489),('displayport',372,491),('antenna',452,383),('antenna',452,450),('buttons',517,489),
     ('usb_a',596,438),('usb_a',596,479),('usb_a',715,358),('usb_a',715,400),('usb_a',715,440),('usb_a',715,481),
     ('lan',826,389),('usb_a',826,439),('usb_c',826,483),('audio_3_5',916,383),('audio_3_5',916,429),('spdif',916,478)]),
 'asrock-b650m-pg-riptide-wifi':((214,298,972,470),False,
    [('displayport',250,450),('hdmi',350,449),('buttons',447,449),('usb_a',544,403),('usb_c',544,449),
     ('usb_a',655,323),('usb_a',655,360),('usb_a',655,400),('usb_a',655,441),('lan',764,347),
     ('usb_a',765,405),('usb_a',765,449),('antenna',861,349),('antenna',861,416),
     ('audio_3_5',941,346),('audio_3_5',941,391),('audio_3_5',941,436)]),
}
for _model in _EXTRA:
    _identity=_model['id']
    _model['series']={'asus-tuf-z790-plus-wifi':'TUF GAMING','asus-prime-b650m-a-wifi-ii':'PRIME',
        'asus-rog-maximus-z790-hero':'ROG MAXIMUS','asrock-x670e-taichi':'Taichi',
        'asrock-b650e-steel-legend-wifi':'Steel Legend','asrock-b650m-pg-riptide-wifi':'Phantom Gaming'}[_identity]
    _model['silkscreen_label']={'asus-tuf-z790-plus-wifi':'TUF Z790 PLUS','asus-prime-b650m-a-wifi-ii':'PRIME B650M A II',
        'asus-rog-maximus-z790-hero':'MAXIMUS Z790 HERO','asrock-x670e-taichi':'X670E TAICHI',
        'asrock-b650e-steel-legend-wifi':'B650E STEEL LEGEND','asrock-b650m-pg-riptide-wifi':'B650M PG RIPTIDE'}[_identity]
    _model['mount_uv']=()
    _model['mount_method']='not_verified_no_holes_inferred'
    if _identity=='asus-tuf-z790-plus-wifi':
        _model['mount_uv']=((.130,.020),(.678,.020),(.973,.020),(.044,.540),(.678,.540),(.973,.540),(.044,.948),(.678,.948),(.973,.948))
        _model['front_panel_positions']=20;_model['front_panel_missing']=((0,4),(1,8),(1,9))
    elif _identity=='asus-prime-b650m-a-wifi-ii':
        _model['mount_uv']=((.134,.028),(.675,.028),(.978,.028),(.043,.671),(.678,.671),(.978,.671),(.043,.858),(.678,.943))
        _model['front_panel_positions']=10;_model['front_panel_missing']=((1,4),)
    if _model['mount_uv']:_model['mount_method']='official_manual_layout_diagram_observed';_model['mount_page']=_model['layout_page']
    if _identity=='asus-rog-maximus-z790-hero':
        _model['bundled_m2_accessory_slots']=2;_model['bundled_m2_accessory_installed']=False
        _model['rear_layout']=_rear_observation((258,65,459,759),
            [('buttons',327,140),('buttons',379,140),('hdmi',322,192),('usb_a',301,266),('usb_a',337,266),('usb_a',373,266),('usb_a',410,266),
             ('usb_c',296,350),('usb_a',338,350),('usb_c',296,438),('usb_a',338,438),('usb_a',337,528),('usb_a',374,528),('usb_a',411,528),('usb_c',296,528),
             ('lan',386,439),('antenna',318,598),('antenna',418,598),('spdif',310,655),('audio_3_5',359,655),('audio_3_5',407,655),
             ('audio_3_5',311,709),('audio_3_5',359,709),('audio_3_5',407,709)],True)
        _model['rear_layout_source']='https://dlcdnwebimgs.asus.com/files/media/29C004F7-7B1F-4EBF-9099-7168B520A0EE/v1/img/spec/connectivity.jpg'
    else:
        _bounds,_vertical,_items=_EXTRA_REAR[_identity]
        _model['rear_layout']=_rear_observation(_bounds,_items,_vertical);_model['rear_layout_source']=_model['manual']
    if _identity=='asrock-x670e-taichi':
        _model['unplaced_source_features']=('active_vrm_cooling_fan_dimensions_and_position_unverified',)
        _model['optional_m2_fan_sink_installed']=False
    _model['sources']=tuple(dict.fromkeys((*_model['sources'],_model['rear_layout_source'])))
MODELS+=_EXTRA

# The actual right-edge front USB housings run along the board height. These
# reviewed rows are explicit; no unknown connector is oriented by a heuristic.
for _model in MODELS:
    for _row in _model['connectors']:
        if _row['kind'] in ('usb3','usb_c') and _row['uv'][0]>.9:_row['along']=(0,1)
    if _model['id'] in ('asrock-z790-pg-itx-tb4','asrock-b650i-lightning-wifi'):
        for _row in _model['connectors']:
            if _row['kind'] in ('front_io','usb2') and _row['uv'][0]>.9:_row['along']=(0,1)

from motherboard_expansion_b import records as _additional_records
MODELS+=_additional_records(_record,_slot,_m2,_connector,_cover,_rect,_rear_observation)
from motherboard_expansion045 import records as _records045
MODELS+=_records045(_record,_slot,_m2,_connector,_cover,_rect,_rear_observation)


def normalize(value):return re.sub(r'[^a-z0-9]+','',value.casefold()) if isinstance(value,str) else ''


def get_model(identity):
    model=next((row for row in MODELS if row['id']==identity),None)
    return copy.deepcopy(model) if model else None


def choices():
    return [{key:row[key] for key in ('id','label','brand','series','form_factor','socket','layout_status','finish_status')} for row in MODELS]


def identify(manufacturer,product,manual_id=''):
    if manual_id:
        model=get_model(manual_id)
        return dict(model=model,state='manual' if model else 'unidentified')
    maker=normalize(manufacturer);name=normalize(product)
    makers={'ASUS':{'asus','asustekcomputerinc'},'MSI':{'msi','microstarinternationalcoltd'},
            'ASRock':{'asrock','asrockinc'},'GIGABYTE':{'gigabyte','gigabytetechnologycoltd'}}
    aliases={'msi-mag-b760m-mortar-wifi':('MAG B760M MORTAR WIFI (MS-7E01)',),
             'msi-mag-b650m-mortar-wifi':('MAG B650M MORTAR WIFI (MS-7D76)',)}
    for row in MODELS:
        short=row['label'].removeprefix(row['brand']+' ')
        names={normalize(short),normalize(row['label']),*(normalize(x) for x in (*aliases.get(row['id'],()),*row.get('aliases',())))}
        if maker in makers[row['brand']] and name in names:return dict(model=copy.deepcopy(row),state='detected')
    return dict(model=None,state='unidentified')


def resolve(board):
    if not isinstance(board,dict):return None
    model=get_model(board.get('model_id'))
    if model:return model
    if board.get('detail_profile')=='asus_z790_a_d4':return get_model('asus-rog-strix-z790-a-wifi-d4')
    profile=board.get('model_profile')
    if isinstance(profile,dict):
        model=get_model(profile.get('id'))
        if model:return model
    return identify(board.get('manufacturer'),board.get('label'))['model']
