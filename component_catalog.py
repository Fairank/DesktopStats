"""Source-linked manual assembly references; no device discovery or assets.

Product envelopes and documented interfaces are facts. Internal package,
socket, screw and cable positions remain original schematic construction.
No logos, photographs, manufacturer CAD, availability or live prices.
Original code/art: PolyForm Noncommercial 1.0.0; see LICENSE/LICENSING.md.
"""
from copy import deepcopy
import math
import re

REVIEWED='2026-11-07'
CATEGORIES=('psu','storage','expansion')
_ID=re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z',re.ASCII)


def _record(identity,label,category,form,length,width,height,sources,**facts):
    series={'corsair-rm850x-2024':'RMx 2024','corsair-rm1000x-2024':'RMx 2024',
            'corsair-sf750-2024':'SF 2024','corsair-sf1000l':'SF-L','seasonic-focus-gx850-atx31':'FOCUS GX ATX 3.1',
            'seasonic-prime-fanless-tx700':'PRIME Fanless TX','samsung-870-evo-1tb':'870 EVO',
            'wd-blue-wd40ezax':'WD Blue','samsung-990-pro-2tb':'990 PRO','kingston-kc3000-1tb':'KC3000',
            'crucial-t500-1tb':'T500','tp-link-archer-tx3000e-v1':'Archer TX',
            'creative-audigy-fx-v2':'Sound Blaster Audigy Fx','elgato-4k-pro':'Game Capture 4K Pro'}[identity]
    return dict(id=identity,label=label,category=category,form_factor=form,
                dimensions_mm=dict(length=length,width=width,height=height),
                sources=list(sources),sources_reviewed=REVIEWED,
                dimensions_verified=True,selection_source='manual',
                geometry_accuracy='schematic',layout_schematic=True,series=series,**facts)


CATALOG=(
 _record('corsair-rm850x-2024','CORSAIR RM850x (2024)','psu','atx',160,150,86,
   ('https://www.corsair.com/us/en/p/psu/cp-9020270-na/rmx-series-rm850x-fully-modular-power-supply-cp-9020270-na',),
   brand='CORSAIR',model_number='CP-9020270',capacity_w=850,fan_count=1,fan_diameter_mm=140,
   modular=True,manual_fan_knob=True,grille_pattern='rounded_y',model_mark='RM850X',grille_schematic=True,
   appearance_sources=['https://assets.corsair.com/image/upload/c_pad,q_auto,h_1024,w_1024,f_auto/products/Power-Supply-Units/base-rmx-2024-config/gallery/black/850/RM850x_2024_01.webp']),
 _record('corsair-rm1000x-2024','CORSAIR RM1000x (2024)','psu','atx',160,150,86,
   ('https://www.corsair.com/us/en/p/psu/cp-9020271-na/rmx-series-rm1000x-fully-modular-power-supply-cp-9020271-na',),
   brand='CORSAIR',model_number='CP-9020271',capacity_w=1000,fan_count=1,fan_diameter_mm=140,
   modular=True,manual_fan_knob=True,grille_pattern='rounded_y',model_mark='RM1000X',grille_schematic=True,
   appearance_sources=['https://assets.corsair.com/image/upload/c_pad,q_auto,h_1024,w_1024,f_auto/products/Power-Supply-Units/base-rmx-2024-config/gallery/black/850/RM850x_2024_01.webp']),
 _record('corsair-sf750-2024','CORSAIR SF750 (2024)','psu','sfx',100,125,63.5,
   ('https://www.corsair.com/us/en/explorer/diy-builder/power-supply-units/corsair-sf-series/',
    'https://www.corsair.com/us/en/explorer/diy-builder/power-supply-units/sf750sf850sf1000-platinum-atx-31-everything-you-need-to-know/'),
   brand='CORSAIR',model_number='CP-9020284',capacity_w=750,fan_count=1,fan_diameter_mm=92,
   modular=True,manual_fan_knob=False,grille_pattern='triangle',model_mark='SF750',grille_schematic=True,
   appearance_sources=['https://assets.corsair.com/image/upload/c_pad,q_auto,h_1024,w_1024,f_auto/products/Power-Supply-Units/sf-platinum-series/Gallery/750/CP-9020284_01.webp']),
 _record('corsair-sf1000l','CORSAIR SF1000L','psu','sfx_l',130,125,63.5,
   ('https://www.corsair.com/us/en/p/psu/cp-9020246-na/sf-l-series-sf1000l-fully-modular-low-noise-sfx-power-supply-cp-9020246-na',
    'https://assets.corsair.com/image/upload/documents/49_002592_AB_WW_SFL_Series_QSG_Web_F.pdf'),
   brand='CORSAIR',model_number='CP-9020246',capacity_w=1000,fan_count=1,fan_diameter_mm=120,
   modular=True,manual_fan_knob=False,grille_pattern='triangle',model_mark='SF1000L',grille_schematic=True,
   appearance_sources=['https://assets.corsair.com/image/upload/c_pad,q_auto,h_1024,w_1024,f_auto/products/Power-Supply-Units/base-sfl-series-psu-config/CP-9020246/Gallery/CP-9020246_01.webp']),
 _record('seasonic-focus-gx850-atx31','Seasonic FOCUS GX-850 ATX 3.1','psu','atx',140,150,86,
   ('https://seasonic.com/focus-gx-atx-3/',),brand='Seasonic',model_number='FOCUS GX-850 ATX 3.1',
   capacity_w=850,fan_count=1,fan_diameter_mm=135,modular=True,manual_fan_knob=False,grille_pattern='quadrant_slots',model_mark='FOCUS GX850',grille_schematic=True,
   appearance_sources=['https://seasonic.com/wp-content/uploads/2024/07/ATX3.1-FOCUS-GX-850-PSU-Box-1462x1080.webp']),
 _record('seasonic-prime-fanless-tx700','Seasonic PRIME Fanless TX-700','psu','atx',170,150,86,
   ('https://seasonic.com/prime-fanless-tx/',
    'https://seasonic.com/wp-content/uploads/2024/04/PRIME-Fanless-TX-PX-TL-PL.pdf'),
   brand='Seasonic',model_number='SSR-700TL',capacity_w=700,fan_count=0,fan_diameter_mm=None,
   modular=True,manual_fan_knob=False,grille_pattern='honeycomb',model_mark='FANLESS TX700',grille_schematic=True,
   appearance_sources=['https://seasonic.com/wp-content/uploads/2024/04/PRIME-Fanless-TX-700-600-side-panel-1462x1080.webp']),
 _record('samsung-870-evo-1tb','Samsung 870 EVO 1TB','storage','sata_25_ssd',100,69.85,6.8,
   ('https://download.semiconductor.samsung.com/resources/data-sheet/Samsung_SSD_870_EVO_Data_Sheet_Rev1.1_230509_10129500053000.pdf',),
   brand='Samsung',model_number='MZ-77E1T0',interface='sata',capacity_gb=1000,model_mark='870 EVO',label_style='samsung_sata'),
 _record('wd-blue-wd40ezax','WD Blue WD40EZAX 4TB','storage','sata_35_hdd',147,101.6,26.1,
   ('https://documents.westerndigital.com/content/dam/doc-library/en_us/assets/public/western-digital/product/internal-drives/wd-blue-hdd/product-brief-western-digital-wd-blue-pc-hdd.pdf',),
   brand='Western Digital',model_number='WD40EZAX',interface='sata',capacity_gb=4000,
   factory_spindle_rpm=5400,spindle_rpm_is_live=False,model_mark='WD BLUE',label_style='wd_blue'),
 _record('samsung-990-pro-2tb','Samsung 990 PRO 2TB','storage','m2_nvme',80,22,2.3,
   ('https://download.semiconductor.samsung.com/resources/data-sheet/Samsung_NVMe_SSD_990_PRO_Datasheet_Rev.1.0_10119997003518.pdf',),
   brand='Samsung',model_number='MZ-V9P2T0',interface='nvme',capacity_gb=2000,
   m2_size='2280',factory_heatsink=False,package_layout_schematic=True,model_mark='990 PRO',label_style='samsung_990',pcb_color='black',
   appearance_sources=['https://download.semiconductor.samsung.com/resources/data-sheet/Samsung_NVMe_SSD_990_PRO_Datasheet_Rev.1.0_10119997003518.pdf']),
 _record('kingston-kc3000-1tb','Kingston KC3000 1024GB','storage','m2_nvme',80,22,2.21,
   ('https://www.kingston.com/datasheets/KC3000_en.pdf',),brand='Kingston',
   model_number='SKC3000S/1024G',interface='nvme',capacity_gb=1024,
   m2_size='2280',factory_heatsink=False,package_layout_schematic=True,model_mark='KC3000',label_style='kc3000',pcb_color='black',low_profile_heatspreader=True,
   appearance_sources=['https://www.kingston.com/datasheets/KC3000_en.pdf']),
 _record('crucial-t500-1tb','Crucial T500 1TB (without heatsink)','storage','m2_nvme',80.01,21.844,2.286,
   ('https://assets.micron.com/adobe/assets/urn%3Aaaid%3Aaem%3A6b046d5a-4382-4018-b81e-28421f19b2cc/renditions/original/as/crucial-T500-b2c-product-flyer-en-combination.pdf',),
   brand='Crucial',model_number='CT1000T500SSD8',interface='nvme',capacity_gb=1000,
   m2_size='2280',factory_heatsink=False,package_layout_schematic=True,model_mark='T500',label_style='t500_reference',appearance_unverified=True,
   dimensions_basis='Manufacturer rounded inches 3.15 x 0.86 x 0.09 converted at 25.4 mm/in; nominal M.2 2280'),
 _record('tp-link-archer-tx3000e-v1','TP-Link Archer TX3000E V1','expansion','wifi',95.2,21.5,120.8,
   ('https://static.tp-link.com/2019/201909/20190923/Archer%20TX3000E%28UN%29_1.0%20Datasheet.pdf',),
   brand='TP-Link',model_number='Archer TX3000E V1',host_interface='pcie_x1',
   ports=[dict(type='sma',count=2)],pcb_proportions_schematic=True,pcb_color='dark_red',heatsink_style='full_red_parallel',
   appearance_sources=['https://static.tp-link.com/2019/201909/20190923/Archer%20TX3000E%28UN%29_1.0%20Datasheet.pdf'],
   dimensions_basis='Listed hardware envelope 95.2 x 120.8 x 21.5 mm; antenna base not part of card model'),
 _record('creative-audigy-fx-v2','Creative Sound Blaster Audigy Fx V2','expansion','sound',117.4,21.6,121,
   ('https://uk.creative.com/p/sound-blaster/sound-blaster-audigy-fx-v2',
    'https://jp.creative.com/corporate/pressroom?id=13722'),
   brand='Creative',model_number='SB1870',host_interface='pcie_x1',
   ports=[dict(type='audio_3_5',count=5)],pcb_proportions_schematic=True,pcb_color='black',low_profile_bracket_included=True,
   appearance_sources=['https://img.creative.com/images/inline/japan/products/AudigyFxV2/PS_AgyFxV2.jpg'],
   dimensions_basis='Manufacturer main-card envelope including full-height bracket'),
 _record('elgato-4k-pro','Elgato Game Capture 4K Pro','expansion','capture',121.67,19.05,55.88,
   ('https://www.elgato.com/us/en/p/game-capture-4k-pro',
    'https://help.elgato.com/hc/en-us/articles/23710571317517-Elgato-Game-Capture-4K-Pro-Technical-Specifications'),
   brand='Elgato',model_number='10GBK9901',host_interface='pcie_x4',
   ports=[dict(type='hdmi',count=2)],pcb_proportions_schematic=True,pcb_color='black',shield_style='vented_full_cover',
   appearance_sources=['https://res.cloudinary.com/elgato-pwa/image/upload/q_auto,f_auto/v1704723871/Products/10GBK9901/ATF/4K_Pro_ATF_Desktop.jpg'],
   dimensions_basis='Current manufacturer listing 121.67 x 55.88 x 19.05 mm; bracket/PCB construction schematic'),
)

_BY_ID={row['id']:row for row in CATALOG}


def valid_component_id(value,category=None):
    return (isinstance(value,str) and len(value)<=64 and _ID.fullmatch(value) is not None
            and value in _BY_ID and (category is None or _BY_ID[value]['category']==category))


def get_component(identity):
    """Return only a registered manual reference, detached from catalog state."""
    return deepcopy(_BY_ID[identity]) if isinstance(identity,str) and identity in _BY_ID else None


def choices(kind):
    return [dict(id=row['id'],label=row['label'],category=row['category'],form_factor=row['form_factor'],brand=row['brand'],series=row['series'])
            for row in CATALOG if row['category']==kind]


def coverage():
    return {kind:sum(row['category']==kind for row in CATALOG) for kind in CATEGORIES}


def validate_catalog():
    if len(_BY_ID)!=len(CATALOG):raise ValueError('Duplicate auxiliary component identity')
    for row in CATALOG:
        if not valid_component_id(row['id']) or row['category'] not in CATEGORIES:raise ValueError('Invalid component identity')
        if (not row['sources'] or any(not isinstance(url,str) or not url.startswith('https://') for url in row['sources'])
                or any(type(value) not in (int,float) or not math.isfinite(value) or not 0<value<1000
                       for value in row['dimensions_mm'].values())):raise ValueError('Invalid component source/envelope')
    return True


validate_catalog()
