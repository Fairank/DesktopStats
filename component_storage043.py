"""Lazy, source-linked manual storage envelopes; no discovery or artwork assets.

Dimensions, interfaces and capacities are published product facts. Controller,
NAND, wiring, screw positions and unmeasured fin pitch remain schematic. The
24 products share 12 construction groups; they are not 24 independent shells.
Original construction/code: PolyForm Noncommercial 1.0.0; see LICENSE.
"""

REVIEWED = '2026-11-08'
_ROWS = None
IDS = (
    'wd-black-sn770m-1tb', 'kingston-nv3-2230-1tb', 'sabrent-rocket-2230-1tb',
    'transcend-mte300s-512gb', 'sabrent-rocket-nano-2242-1tb',
    'transcend-mte400s-512gb', 'transcend-mte452t-512gb', 'samsung-983-dct-960gb',
    'samsung-990-evo-plus-2tb', 'wd-black-sn850x-2tb', 'kingston-nv2-2tb',
    'kioxia-exceria-pro-2tb', 'samsung-990-pro-heatsink-2tb',
    'wd-black-sn850x-heatsink-2tb', 'seagate-firecuda-530-heatsink-2tb',
    'crucial-t705-heatsink-2tb', 'corsair-mp600-pro-lpx-2tb',
    'adata-su800-1tb', 'kingston-kc600-1024gb', 'teamgroup-cx2-1tb',
    'kioxia-exceria-sata-960gb', 'seagate-barracuda-st8000dm004',
    'wd-black-wd6004fzwx', 'toshiba-n300-hdwg480uzsva',
)


def _row(identity, label, brand, series, model, capacity, form, size, sources, **facts):
    return dict(id=identity, label=label, brand=brand, series=series,
                model_number=model, category='storage', form_factor=form,
                dimensions_mm=dict(zip(('length', 'width', 'height'), size)),
                dimensions_verified=True, dimensions_basis='Manufacturer published product envelope in millimetres.',
                capacity_gb=capacity, interface='nvme' if form=='m2_nvme' else 'sata',
                sources=list(sources), sources_reviewed=REVIEWED,
                selection_source='manual', geometry_accuracy='schematic',
                layout_schematic=True, package_layout_schematic=True,
                controller_layout_verified=False, nand_layout_verified=False,
                pcb_routing_verified=False, screw_positions_verified=False,
                appearance_unverified=True,
                palette_accuracy='illustrative_not_measured_factory_paint',
                body_color='#242b31', label_color='#293238', accent_color='#9ca8ae',
                model_mark=series.upper(), label_style='reference',
                factory_heatsink=False, heatsink_style='none', fin_axis='none',
                fin_count=None, fin_geometry_verified=False,
                **facts)


def _build():
    # Record dictionaries/lists are allocated only on demand. String literals
    # remain ordinary Python code constants; no zero-import-memory claim.
    sn850 = 'https://documents.sandisk.com/content/dam/asset-library/en_us/assets/public/western-digital/product/internal-drives/wd-black-ssd/data-sheet-wd-black-sn850x-nvme-ssd.pdf'
    samsung_hs = 'https://download.semiconductor.samsung.com/resources/data-sheet/Samsung_NVMe_SSD_990_PRO_with_Heatsink_Datasheet_Rev.1.0_10129514072625.pdf'
    fc530 = 'https://www.seagate.com/www-content/support-content/internal-products/ssd/firecuda-530-ssd/_shared/files/firecuda_530_product_manual_200432500_D.pdf'
    t705 = 'https://assets.micron.com/adobe/assets/urn%3Aaaid%3Aaem%3A8b31ab31-5c1c-4dbe-ad26-5bdc076d5ff3/renditions/original/as/crucial-t705-b2c-product-flyer-en.pdf'
    lpx = 'https://www.corsair.com/us/en/p/data-storage/cssd-f2000gbmp600plp/mp600-pro-lpx-2tb-pcie-gen4-x4-nvme-m-2-ssd-ps5-compatible-cssd-f2000gbmp600plp'
    m2 = dict(m2_key='m', m2_key_verified=True, connector_positions_schematic=True,
              pcb_thickness_verified=False, package_layout_schematic=True)

    def nv(identity, label, brand, series, model, capacity, size, sources, m2_size='2280', **facts):
        row=_row(identity, label, brand, series, model, capacity, 'm2_nvme', size, sources)
        row.update(m2, m2_size=m2_size, structure_group='m2_'+m2_size+'_m_flat',
                   interface_detail='PCIe NVMe', pcb_color='reference')
        row.update(facts)
        return row

    def sata(identity, label, brand, series, model, capacity, size, sources, **facts):
        row=_row(identity, label, brand, series, model, capacity, 'sata_25_ssd', size, sources)
        row.update(structure_group='sata_25_closed', interface_detail='SATA III 6 Gb/s',
                   connector_positions_schematic=True, internal_enclosure_verified=False)
        row.update(facts)
        return row

    def hdd(identity, label, brand, series, model, capacity, size, sources, rpm, **facts):
        row=_row(identity, label, brand, series, model, capacity, 'sata_35_hdd', size, sources)
        row.update(structure_group='sata_35_sealed', interface_detail='SATA III 6 Gb/s',
                   factory_spindle_rpm=rpm, spindle_rpm_is_live=False,
                   sealed_cover=True, internal_platters_visible=False,
                   connector_positions_schematic=True)
        row.update(facts)
        return row

    return (
        nv(IDS[0], 'WD_BLACK SN770M 1TB', 'Western Digital', 'WD_BLACK SN770M',
           'WDBDNH0010BBK-WRSN', 1000, (29.97,22.10,2.29),
           ('https://www.sandisk.com/en-au/products/ssd/internal-ssd/wd-black-sn770m-nvme-ssd',),
           '2230', interface_detail='PCIe 4.0 x4 NVMe', model_mark='SN770M',
           label_color='#20252b', pcb_color='black',
           notes='Current exact 1TB retail model dimensions; not an OEM SN740 or another 2230 module.'),
        nv(IDS[1], 'Kingston NV3 M.2 2230 1TB', 'Kingston', 'NV3 2230',
           'SNV3SM3/1T0', 1000, (30,22,2.3),
           ('https://www.kingston.com/datasheets/SNV3S_en.pdf',
            'https://www.kingston.com/en/company/press/article/76990'),
           '2230', interface_detail='PCIe 4.0 x4 NVMe', model_mark='NV3',
           label_color='#5d7c9d', single_sided=True,
           notes='The manufacturer separately lists 2230 and 2280. This identity is the short SNV3SM3/1T0.'),
        nv(IDS[2], 'Sabrent Rocket 2230 1TB', 'Sabrent', 'Rocket 2230',
           'SB-2130-1TB', 1000, (29.972,22.098,2.032),
           ('https://sabrent.com/products/sb-2130-1tb',), '2230',
           interface_detail='PCIe 4.0 x4 NVMe', model_mark='ROCKET 2230',
           dimensions_basis='Published rounded 1.18 x 0.87 x 0.08 inches converted at 25.4 mm/in; nominal M.2 2230. Not manufacturing tolerances.',
           label_color='#a78557'),
        nv(IDS[3], 'Transcend PCIe SSD 300S 512GB', 'Transcend', 'PCIe SSD 300S',
           'TS512GMTE300S', 512, (30,22,2.23),
           ('https://cdn.transcend-info.com/products/images/modelpic/1294/Transcend-MTE300S-1T.pdf',
            'https://us.transcend-info.com/product/internal-ssd/mte300s'),
           '2230', interface_detail='PCIe 3.0 x4 NVMe', model_mark='300S',
           single_sided=True, label_color='#d7dbd5', pcb_color='green'),
        nv(IDS[4], 'Sabrent Rocket nano 2242 Gen4 1TB', 'Sabrent', 'Rocket nano 2242 Gen4',
           'SB-2142-1TB', 1000, (41.91,22.098,2.032),
           ('https://sabrent.com/collections/internal-memory/products/sb-2142-1tb',),
           '2242', interface_detail='PCIe 4.0 x4 NVMe', model_mark='ROCKET NANO',
           dimensions_basis='Published rounded 1.65 x 0.87 x 0.08 inches converted at 25.4 mm/in; nominal M.2 2242. Not the older SB-1342 or SB-2742.',
           label_color='#a78557'),
        nv(IDS[5], 'Transcend PCIe SSD 400S 512GB', 'Transcend', 'PCIe SSD 400S',
           'TS512GMTE400S', 512, (42,22,2.23),
           ('https://cdn.transcend-info.com/products/images/modelpic/1293/Transcend-MTE400S-202311.pdf',),
           '2242', interface_detail='PCIe 3.0 x4 NVMe 1.3', model_mark='400S',
           single_sided=True, label_color='#d7dbd5', pcb_color='green'),
        nv(IDS[6], 'Transcend MTE452T 512GB', 'Transcend', 'MTE452T industrial',
           'TS512GMTE452T', 512, (42,22,3.58),
           ('https://cdn.transcend-info.com/products/images/modelpic/1048/Embedded_PS_MTE452TnI.pdf',),
           '2242', interface_detail='PCIe 3.0 x2 NVMe 1.3', model_mark='MTE452T',
           m2_key='b_m', structure_group='m2_2242_bm_double', single_sided=False,
           label_color='#e2e4dd', pcb_color='green',
           notes='Explicit manufacturer 2242-D2-B-M double-sided form factor; never draw an M-only notch or confuse with MTE452T2.'),
        nv(IDS[7], 'Samsung 983 DCT M.2 960GB', 'Samsung', '983 DCT',
           'MZ-1LB960NE', 960, (110.2,22,3.8),
           ('https://www.samsung.com/au/memory-storage/nvme-ssd/983-dct-nvme-m-2-ssd-mz-1lb960ne/',),
           '22110', interface_detail='PCIe 3.0 x4 NVMe 1.2b', model_mark='983 DCT',
           label_color='#e2e3dc', pcb_color='green',
           notes='Exact retail 983 DCT 960GB M.2 22110. Not PM983 OEM, 983 DCT U.2 or a 2280 boot drive; slot length must be checked separately.'),
        nv(IDS[8], 'Samsung 990 EVO Plus 2TB', 'Samsung', '990 EVO Plus',
           'MZ-V9S2T0BW', 2000, (80.15,22.15,2.38),
           ('https://download.semiconductor.samsung.com/resources/data-sheet/samsung_nvme_ssd_990_evo_plus_datasheet_rev.1.0_10139908981125.pdf',),
           interface_detail='PCIe 4.0 x4 / 5.0 x2 NVMe 2.0', model_mark='990 EVO PLUS', pcb_color='black',
           notes='Published maximum envelope. 990 EVO Plus is not the existing 990 PRO reference.'),
        nv(IDS[9], 'WD_BLACK SN850X 2TB (without heatsink)', 'Western Digital', 'WD_BLACK SN850X',
           'WDS200T2X0E-00BCA0', 2000, (80.15,22.15,2.38), (sn850,),
           interface_detail='PCIe 4.0 x4 NVMe', model_mark='SN850X', pcb_color='black',
           dimensions_basis='Current datasheet 1/2TB bare: 80 +/-0.15 x 22 +/-0.15 x 2.38 mm. This model uses the maximum envelope.'),
        nv(IDS[10], 'Kingston NV2 2TB', 'Kingston', 'NV2', 'SNV2S/2000G', 2000, (80,22,2.2),
           ('https://www.kingston.com/datasheets/snv2s_en.pdf',),
           interface_detail='PCIe 4.0 x4 NVMe', model_mark='NV2', single_sided=True,
           label_color='#6585a3', notes='Controller/NAND suppliers and IC positions are not assumed from product family.'),
        nv(IDS[11], 'KIOXIA EXCERIA PRO 2TB', 'KIOXIA', 'EXCERIA PRO', 'LSE10Z002TG8',
           2000, (80.15,22.15,2.23),
           ('https://europe.kioxia.com/content/dam/kioxia/shared/personal/support/download/ssd/asset/productbrief/KIOXIA_Exceria_Pro_Product_Brief.pdf',
            'https://europe.kioxia.com/en-europe/personal/ssd/exceria-pro.html'),
           interface_detail='PCIe 4.0 x4 NVMe 1.4', model_mark='EXCERIA PRO',
           single_sided=True, label_color='#d5dfdc', accent_color='#6eaaa6'),
        nv(IDS[12], 'Samsung 990 PRO with Heatsink 2TB', 'Samsung', '990 PRO with Heatsink',
           'MZ-V9P2T0CW', 2000, (80,24.3,8.2), (samsung_hs,),
           interface_detail='PCIe 4.0 x4 NVMe 2.0', model_mark='990 PRO',
           structure_group='heatsink_diagonal_channels', factory_heatsink=True,
           heatsink_style='diagonal_channels', fin_axis='length',
           body_color='#25282c', label_color='#141719', accent_color='#ad2727',
           appearance_unverified=False, appearance_sources=[samsung_hs],
           appearance_basis='Official datasheet cover photograph: interlocking diagonal panels, longitudinal channels and colored diffuser. Original proportional construction; no copied lettering.',
           factory_rgb=True, rgb_is_live=False),
        nv(IDS[13], 'WD_BLACK SN850X with Heatsink 2TB', 'Western Digital', 'WD_BLACK SN850X with Heatsink',
           'WDS200T2XHE-00BCA0', 2000, (80.2,23.8,9.3), (sn850,
            'https://www.sandisk.com/en-au/products/ssd/internal-ssd/wd-black-sn850x-nvme-ssd?sku=WDS200T2XHE-00BCA0'),
           interface_detail='PCIe 4.0 x4 NVMe', model_mark='SN850X',
           structure_group='heatsink_transverse_low', factory_heatsink=True,
           heatsink_style='transverse_low', fin_axis='width',
           body_color='#25282d', label_color='#25282d', accent_color='#d19a28',
           appearance_unverified=False,
           appearance_sources=['https://www.sandisk.com/content/dam/sandisk/en-us/assets/products/internal-storage/wd-black-sn850x-nvme-ssd/gallery/wd-black-sn850x-nvme-ssd-heatsink-front.png.wdthumb.1280.1280.webp',
                               'https://www.sandisk.com/content/dam/sandisk/en-us/assets/products/internal-storage/wd-black-sn850x-nvme-ssd/gallery/wd-black-sn850x-nvme-ssd-heatsink-angled.png.wdthumb.1280.1280.webp'],
           dimensions_basis='Current manufacturer datasheet 1/2TB HS: 80 +/-0.20 x 23.40 +/-0.40 x 8.90 +/-0.40 mm, maximum envelope used. Earlier marketing 8.8 mm is not used.',
           appearance_basis='Exact 1/2TB manufacturer gallery: transverse top ribs, triangular/trapezoid side apertures and small side diffuser. Not the wider 4/8TB housing.',
           factory_rgb=True, rgb_is_live=False),
        nv(IDS[14], 'Seagate FireCuda 530 with Heatsink 2TB', 'Seagate', 'FireCuda 530 with Heatsink',
           'ZP2000GM30023', 2000, (80.15,24.5,10.39), (fc530,),
           interface_detail='PCIe 4.0 x4 NVMe 1.4', model_mark='FIRECUDA 530',
           structure_group='heatsink_smooth_low', factory_heatsink=True,
           heatsink_style='smooth_low', fin_axis='none',
           body_color='#33373b', label_color='#25292d',
           appearance_unverified=False, appearance_sources=[fc530],
           appearance_basis='Official Rev D Figure8 for exact 2000GB: smooth top cover, clamp seam and two side fasteners. Screw geometry/positions remain schematic; no invented comb fins.',
           dimensions_basis='Manufacturer manual Rev D table8/figure8 maximum 2TB HS envelope. The 500GB/1TB height9.84 mm is not the 2TB height.'),
        nv(IDS[15], 'Crucial T705 with Heatsink 2TB', 'Crucial', 'T705 with Heatsink',
           'CT2000T705SSD5', 2000, (80.01,23.368,21.082), (t705,),
           interface_detail='PCIe 5.0 x4 NVMe', model_mark='T705',
           structure_group='heatsink_tall_reference', factory_heatsink=True,
           heatsink_style='reference', fin_axis='none', body_color='#252b2e',
           dimensions_basis='Manufacturer rounded HS dimensions 3.15 x 0.92 x 0.83 inches converted at25.4 mm/in; nominal2280. These are published rounded dimensions, not CAD tolerances.',
           heatsink_materials=['aluminium','copper'],
           notes='Official flyer confirms tall passive aluminium/copper heatsink and exact SSD5 part. Current photo download is rejected; fin axis/pitch and detailed exterior remain reference. No fan added.'),
        nv(IDS[16], 'CORSAIR MP600 PRO LPX 2TB (black heatsink)', 'CORSAIR', 'MP600 PRO LPX',
           'CSSD-F2000GBMP600PLP', 2000, (80,23,11), (lpx,
            'https://www.corsair.com/ww/cs/explorer/diy-builder/storage/how-to-install-the-corsair-mp600-pro-lpx-into-the-ps5/'),
           interface_detail='PCIe 4.0 x4 NVMe 1.4', model_mark='MP600 PRO LPX',
           structure_group='heatsink_parallel_low', factory_heatsink=True,
           heatsink_style='parallel_low', fin_axis='length',
           body_color='#24282b', label_color='#24282b', accent_color='#9da5aa',
           appearance_unverified=False,
           appearance_sources=['https://assets.corsair.com/image/upload/c_pad,q_auto,h_1024,w_1024,f_auto/products/Storage/base-mp600-pro-lpx-config/Gallery/MP600_PRO_LPX_02.webp'],
           appearance_basis='Exact black LPX official gallery: longitudinal low parallel fins and one flat spine. Fin count/pitch and screws are original LOD sampling, not measured.'),
        sata(IDS[17], 'ADATA Ultimate SU800 1TB', 'ADATA', 'Ultimate SU800',
             'ASU800SS-1TT-C', 1000, (100.45,69.85,7),
             ('https://webapi3.adata.com/storage/downloadfile/datasheet_su800_25_inch_sata_ssd_en_202410151728964641.pdf',),
             model_mark='SU800', label_color='#386080'),
        sata(IDS[18], 'Kingston KC600 1024GB', 'Kingston', 'KC600', 'SKC600/1024G',
             1024, (100.1,69.85,7),
             ('https://www.kingston.com/en/ssd/kc600-sata-solid-state-drive',
              'https://www.kingston.com/unitedkingdom/en/company/press/article/57000'),
             model_mark='KC600', label_color='#616769'),
        sata(IDS[19], 'TEAMGROUP CX2 1TB', 'TEAMGROUP', 'CX2', 'T253X6001T0C101',
             1000, (100,69.9,7),
             ('https://images.teamgroupinc.com/products/ssd/internal/cx2/spec-sheet/cx2-en.pdf',
              'https://www.teamgroupinc.com/en/product-detail/ssd/TEAMGROUP/cx2/cx2-T253X6001T0C101/'),
             model_mark='CX2', label_color='#486354'),
        sata(IDS[20], 'KIOXIA EXCERIA SATA 960GB', 'KIOXIA', 'EXCERIA SATA',
             'LTC10Z960GG8', 960, (100.45,70.1,7.2),
             ('https://apac.kioxia.com/content/dam/kioxia/shared/personal/support/download/ssd/asset/productbrief/KIOXIA-Exceria-SATA-SSD-Product-Brief.pdf',),
             model_mark='EXCERIA SATA', label_color='#8eb35f',
             dimensions_basis='Manufacturer published maximum 100.45 x70.10 x7.20 mm; nominal 2.5-inch7mm category is not substituted for maximum height.'),
        hdd(IDS[21], 'Seagate BarraCuda 8TB ST8000DM004', 'Seagate', 'BarraCuda',
            'ST8000DM004', 8000, (146.99,101.85,26.11),
            ('https://www.seagate.com/files/www-content/datasheets/pdfs/3-5-barracudaDS1900-14-2007GB-en_GB.pdf',),
            5400, model_mark='BARRACUDA', label_color='#d6ded7', accent_color='#87ad60'),
        hdd(IDS[22], 'WD_BLACK 6TB WD6004FZWX', 'Western Digital', 'WD_BLACK HDD',
            'WD6004FZWX', 6000, (147.07,101.6,26.16),
            ('https://www.westerndigital.com/en-ca/products/internal-drives/wd-black-desktop-sata-hdd?sku=WD6004FZWX',),
            7200, model_mark='WD BLACK', label_color='#30363b', accent_color='#adb4b9',
            notes='Current exact WD6004FZWX product envelope; do not substitute WD Blue cover identity or4TB label.'),
        hdd(IDS[23], 'Toshiba N300 8TB HDWG480UZSVA', 'Toshiba', 'N300',
            'HDWG480UZSVA', 8000, (147,101.85,26.1),
            ('https://www.toshiba-storage.com/wp-content/uploads/2021/12/toshiba-article-n300-nas-2021-12-en.pdf',),
            7200, model_mark='N300', label_color='#cfd5d8', accent_color='#ac4647'),
    )


def records():
    """Return the shared catalog tuple for one-time catalog composition; treat rows as read-only."""
    global _ROWS
    if _ROWS is None:
        _ROWS = _build()
    return _ROWS


def get_storage(identity):
    """A detached exact manual reference; invalid identities do not build the directory."""
    if not isinstance(identity,str) or identity not in IDS:
        return None
    from copy import deepcopy
    return deepcopy(next(row for row in records() if row['id']==identity))


def coverage():
    rows=records()
    return dict(products=len(rows), brands=len({row['brand'] for row in rows}),
                structure_groups=len({row['structure_group'] for row in rows}),
                nvme=sum(row['interface']=='nvme' for row in rows),
                sata_ssd=sum(row['form_factor']=='sata_25_ssd' for row in rows),
                hdd=sum(row['form_factor']=='sata_35_hdd' for row in rows))
