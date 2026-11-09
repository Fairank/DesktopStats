"""Exact-model memory dimensions; PCB and complete envelopes stay separate.

Manufacturer specification/FAQ bindings cover27 of28 existing exact IDs;
Crucial remains unknown. ADATA's declared flat-module axes are retained and
the upright height mapping is explicitly derived, never a primary-H claim.
No Qt, disk, network, hardware, clocks, threads or runtime caches are used.
"""
from copy import deepcopy

_SOURCE_URLS=('https://www.corsair.com/uk/en/p/memory/cmk16gx4m2b3200c16/vengeancea-lpx-16gb-2-x-8gb-ddr4-dram-3200mhz-c16-memory-kit-black-cmk16gx4m2b3200c16',
 'https://help.corsair.com/hc/en-us/articles/34381966388881-RAM-Memory-Module-Dimensions',
 'https://www.corsair.com/us/en/p/memory/cmh32gx5m2b6000c30/vengeance-rgb-32gb-2x16gb-ddr5-dram-6000mt-s-c30-memory-kit-black-cmh32gx5m2b6000c30',
 'https://www.corsair.com/ww/en/p/memory/cmt32gx5m2b5600c36/dominatora-platinum-rgb-32gb-2x16gb-ddr5-dram-5600mhz-c36-memory-kit-a-black-cmt32gx5m2b5600c36',
 'https://www.gskill.com/product/165/184/1536110676/F4-3200C16D-16GVKB',
 'https://www.gskill.com/faq/1502180912/DRAM-Memory',
 'https://www.gskill.com/product/165/166/1536654268/F4-3200C16D-16GTZR',
 'https://www.gskill.com/specification/165/166/1536654268/F4-3200C16D-16GTZR-Specification',
 'https://www.gskill.com/product/165/299/1552461134/F4-3600C18D-16GTRS',
 'https://www.gskill.com/product/165/396/1673491242/F5-6000J3038F16GX2-FX5',
 'https://www.kingston.com/datasheets/KF560C36BBEK2-32.pdf',
 'https://www.kingston.com/datasheets/KF564C32RSK2-32.pdf',
 'https://www.kingston.com/datasheets/KVR32N22S8_16.pdf',
 'https://www.kingston.com/datasheets/KVR32S22S8_16.pdf',
 'https://images.teamgroupinc.com/products/memory/u-dimm/ddr5/delta-rgb/spec-sheet/delta-rgb-en.pdf',
 'https://images.teamgroupinc.com/products/memory/u-dimm/ddr5/vulcan/spec-sheet/vulcan-en.pdf',
 'https://webapi3.adata.com/storage/downloadfile/datasheet_xpg_lancer_rgb_ddr5_memory_20250402.pdf',
 'https://webapi3.adata.com/storage/downloadfile/datasheet_xpg_spectrix_d60g_ddr4_memory_v1.pdf',
 'https://www.corsair.com/us/en/p/memory/cmk16gx4m2b3200c16w/vengeancea-lpx-16gb-2-x-8gb-ddr4-dram-3200mhz-c16-memory-kit-a-white-cmk16gx4m2b3200c16w',
 'https://www.corsair.com/us/en/p/memory/cmh32gx5m2b6000c30w/vengeance-rgb-32gb-2x16gb-ddr5-dram-6000mt-s-cl30-memory-kit-white-cmh32gx5m2b6000c30w',
 'https://www.corsair.com/us/en/p/ddr5-ram/cmt32gx5m2b5600c36w/dominatora-platinum-rgb-32gb-2x16gb-ddr5-dram-5600mhz-c36-memory-kit-a-white-cmt32gx5m2b5600c36w',
 'https://www.gskill.com/qvl/165/299/1562728982/F4-3600C16D-16GTRG-EOL-QVL',
 'https://www.kingston.com/datasheets/KF560C36BBEAK2-32.pdf',
 'https://www.kingston.com/datasheets/KF564C32RSAK2-32.pdf',
 'https://www.kingston.com/datasheets/KVR32N22S8K2_32.pdf')

_FACTS={'corsair-cmk16gx4m2b3200c16': {'total_height_mm': 33.53,
                                'total_height_status': 'primary',
                                'total_height_source_url': _SOURCE_URLS[1],
                                'total_length_mm': 135.0,
                                'total_length_status': 'primary',
                                'total_length_source_url': _SOURCE_URLS[1],
                                'total_thickness_mm': 6.64,
                                'total_thickness_status': 'primary',
                                'total_thickness_source_url': _SOURCE_URLS[1],
                                'dimensions_sources': (_SOURCE_URLS[0], _SOURCE_URLS[1]),
                                'dimensions_model_binding_url': _SOURCE_URLS[0],
                                'dimensions_notes': ('Exact DDR generation/SKU binds official full-module '
                                                     'dimensions; PCB, heatsink and diffuser subdivisions '
                                                     'remain unknown.',)},
 'corsair-cmh32gx5m2b6000c30': {'total_height_mm': 44.0,
                                'total_height_status': 'primary',
                                'total_height_source_url': _SOURCE_URLS[1],
                                'total_length_mm': 135.0,
                                'total_length_status': 'primary',
                                'total_length_source_url': _SOURCE_URLS[1],
                                'total_thickness_mm': 8.0,
                                'total_thickness_status': 'primary',
                                'total_thickness_source_url': _SOURCE_URLS[1],
                                'dimensions_sources': (_SOURCE_URLS[2], _SOURCE_URLS[1]),
                                'dimensions_model_binding_url': _SOURCE_URLS[2],
                                'dimensions_notes': ('Exact DDR generation/SKU binds official full-module '
                                                     'dimensions; PCB, heatsink and diffuser subdivisions '
                                                     'remain unknown.',)},
 'corsair-cmt32gx5m2b5600c36': {'total_height_mm': 56.0,
                                'total_height_status': 'primary',
                                'total_height_source_url': _SOURCE_URLS[1],
                                'total_length_mm': 135.0,
                                'total_length_status': 'primary',
                                'total_length_source_url': _SOURCE_URLS[1],
                                'total_thickness_mm': 8.0,
                                'total_thickness_status': 'primary',
                                'total_thickness_source_url': _SOURCE_URLS[1],
                                'dimensions_sources': (_SOURCE_URLS[3], _SOURCE_URLS[1]),
                                'dimensions_model_binding_url': _SOURCE_URLS[3],
                                'dimensions_notes': ('Exact DDR generation/SKU binds official full-module '
                                                     'dimensions; PCB, heatsink and diffuser subdivisions '
                                                     'remain unknown.',)},
 'gskill-f4-3200c16d-16gvkb': {'total_height_mm': 42.0,
                               'total_height_status': 'primary',
                               'total_height_source_url': _SOURCE_URLS[5],
                               'dimensions_sources': (_SOURCE_URLS[4], _SOURCE_URLS[5]),
                               'dimensions_model_binding_url': _SOURCE_URLS[4],
                               'dimensions_notes': ('Exact manufacturer SKU binds the named family to its '
                                                    'official complete-module height; PCB dimensions remain '
                                                    'unknown.',)},
 'gskill-f4-3200c16d-16gtzr': {'total_height_mm': 44.0,
                               'total_height_status': 'primary',
                               'total_height_source_url': _SOURCE_URLS[5],
                               'dimensions_sources': (_SOURCE_URLS[6], _SOURCE_URLS[5], _SOURCE_URLS[7]),
                               'dimensions_model_binding_url': _SOURCE_URLS[6],
                               'dimensions_notes': ('Exact manufacturer SKU binds the named family to its '
                                                    'official complete-module height; PCB dimensions remain '
                                                    'unknown.',)},
 'gskill-f4-3600c18d-16gtrs': {'total_height_mm': 44.0,
                               'total_height_status': 'primary',
                               'total_height_source_url': _SOURCE_URLS[5],
                               'dimensions_sources': (_SOURCE_URLS[8], _SOURCE_URLS[5]),
                               'dimensions_model_binding_url': _SOURCE_URLS[8],
                               'dimensions_notes': ('Exact manufacturer SKU binds the named family to its '
                                                    'official complete-module height; PCB dimensions remain '
                                                    'unknown.',)},
 'gskill-f5-6000j3038f16gx2-fx5': {'total_height_mm': 33.0,
                                   'total_height_status': 'primary',
                                   'total_height_source_url': _SOURCE_URLS[5],
                                   'dimensions_sources': (_SOURCE_URLS[9], _SOURCE_URLS[5]),
                                   'dimensions_model_binding_url': _SOURCE_URLS[9],
                                   'dimensions_notes': ('Exact manufacturer SKU binds the named family to '
                                                        'its official complete-module height; PCB dimensions '
                                                        'remain unknown.',)},
 'kingston-kf560c36bbek2-32': {'total_height_mm': 34.9,
                               'total_height_status': 'primary',
                               'total_height_source_url': _SOURCE_URLS[10],
                               'total_length_mm': 133.35,
                               'total_length_status': 'primary',
                               'total_length_source_url': _SOURCE_URLS[10],
                               'total_thickness_mm': 6.62,
                               'total_thickness_status': 'primary',
                               'total_thickness_source_url': _SOURCE_URLS[10],
                               'total_height_tolerance_mm': 0.12,
                               'total_length_tolerance_mm': 0.12,
                               'total_thickness_tolerance_mm': 0.12,
                               'dimensions_sources': (_SOURCE_URLS[10],),
                               'dimensions_model_binding_url': _SOURCE_URLS[10],
                               'dimensions_notes': ('Manufacturer per-module dimensioned drawing and its '
                                                    'stated axis tolerances; no guaranteed mechanical '
                                                    'clearance follows from nominal dimensions.',)},
 'kingston-kf564c32rsk2-32': {'total_height_mm': 39.2,
                              'total_height_status': 'primary',
                              'total_height_source_url': _SOURCE_URLS[11],
                              'total_length_mm': 133.35,
                              'total_length_status': 'primary',
                              'total_length_source_url': _SOURCE_URLS[11],
                              'total_thickness_mm': 8.2,
                              'total_thickness_status': 'primary',
                              'total_thickness_source_url': _SOURCE_URLS[11],
                              'total_height_tolerance_mm': 0.15,
                              'total_length_tolerance_mm': 0.15,
                              'total_thickness_tolerance_mm': 0.15,
                              'dimensions_sources': (_SOURCE_URLS[11],),
                              'dimensions_model_binding_url': _SOURCE_URLS[11],
                              'dimensions_notes': ('Manufacturer per-module dimensioned drawing and its '
                                                   'stated axis tolerances; no guaranteed mechanical '
                                                   'clearance follows from nominal dimensions.',)},
 'kingston-kvr32n22s8-16': {'total_height_mm': 31.25,
                            'total_height_status': 'primary',
                            'total_height_source_url': _SOURCE_URLS[12],
                            'pcb_height_mm': 31.25,
                            'pcb_height_status': 'primary',
                            'pcb_height_source_url': _SOURCE_URLS[12],
                            'total_length_mm': 133.35,
                            'total_length_status': 'primary',
                            'total_length_source_url': _SOURCE_URLS[12],
                            'pcb_length_mm': 133.35,
                            'pcb_length_status': 'primary',
                            'pcb_length_source_url': _SOURCE_URLS[12],
                            'total_height_tolerance_mm': 0.12,
                            'pcb_height_tolerance_mm': 0.12,
                            'total_length_tolerance_mm': 0.12,
                            'pcb_length_tolerance_mm': 0.12,
                            'dimensions_sources': (_SOURCE_URLS[12],),
                            'dimensions_model_binding_url': _SOURCE_URLS[12],
                            'dimensions_notes': ('Manufacturer per-module dimensioned drawing and its stated '
                                                 'axis tolerances; no guaranteed mechanical clearance '
                                                 'follows from nominal dimensions.',
                                                 'Page1 specifies PCB height; page2 bare-module outline '
                                                 'shows its complete planar envelope at the same height, '
                                                 'without a heatspreader.')},
 'kingston-kvr32s22s8-16': {'total_height_mm': 30.0,
                            'total_height_status': 'primary',
                            'total_height_source_url': _SOURCE_URLS[13],
                            'pcb_height_mm': 30.0,
                            'pcb_height_status': 'primary',
                            'pcb_height_source_url': _SOURCE_URLS[13],
                            'total_length_mm': 69.6,
                            'total_length_status': 'primary',
                            'total_length_source_url': _SOURCE_URLS[13],
                            'pcb_length_mm': 69.6,
                            'pcb_length_status': 'primary',
                            'pcb_length_source_url': _SOURCE_URLS[13],
                            'pcb_thickness_mm': 1.2,
                            'pcb_thickness_status': 'primary',
                            'pcb_thickness_source_url': _SOURCE_URLS[13],
                            'max_total_thickness_mm': 3.7,
                            'max_total_thickness_status': 'primary',
                            'max_total_thickness_source_url': _SOURCE_URLS[13],
                            'total_height_tolerance_mm': 0.12,
                            'pcb_height_tolerance_mm': 0.12,
                            'total_length_tolerance_mm': 0.12,
                            'pcb_length_tolerance_mm': 0.12,
                            'dimensions_sources': (_SOURCE_URLS[13],),
                            'dimensions_model_binding_url': _SOURCE_URLS[13],
                            'dimensions_notes': ('Manufacturer per-module dimensioned drawing and its stated '
                                                 'axis tolerances; no guaranteed mechanical clearance '
                                                 'follows from nominal dimensions.',
                                                 'Page1 specifies PCB height; page2 bare-module outline '
                                                 'shows its complete planar envelope at the same height, '
                                                 'without a heatspreader.')},
 'teamgroup-ff3d532g6000hc30dc01': {'total_height_mm': 46.1,
                                    'total_height_status': 'primary',
                                    'total_height_source_url': _SOURCE_URLS[14],
                                    'total_length_mm': 144.2,
                                    'total_length_status': 'primary',
                                    'total_length_source_url': _SOURCE_URLS[14],
                                    'total_thickness_mm': 7.0,
                                    'total_thickness_status': 'primary',
                                    'total_thickness_source_url': _SOURCE_URLS[14],
                                    'dimensions_sources': (_SOURCE_URLS[14],),
                                    'dimensions_model_binding_url': _SOURCE_URLS[14],
                                    'dimensions_notes': ('Exact kit part number appears in the official '
                                                         'ordering table; H/L/W refer to one complete '
                                                         'module, not package or PCB dimensions.',)},
 'teamgroup-flbd532g6000hc38jdc01': {'total_height_mm': 32.7,
                                     'total_height_status': 'primary',
                                     'total_height_source_url': _SOURCE_URLS[15],
                                     'total_length_mm': 140.0,
                                     'total_length_status': 'primary',
                                     'total_length_source_url': _SOURCE_URLS[15],
                                     'total_thickness_mm': 7.5,
                                     'total_thickness_status': 'primary',
                                     'total_thickness_source_url': _SOURCE_URLS[15],
                                     'dimensions_sources': (_SOURCE_URLS[15],),
                                     'dimensions_model_binding_url': _SOURCE_URLS[15],
                                     'dimensions_notes': ('Exact kit part number appears in the official '
                                                          'ordering table; H/L/W refer to one complete '
                                                          'module, not package or PCB dimensions.',)},
 'adata-ax5u6000c3016g-dclarwh': {'total_height_mm': 43.56,
                                  'total_height_status': 'derived_nominal',
                                  'total_height_source_url': _SOURCE_URLS[16],
                                  'total_length_mm': 133.35,
                                  'total_length_status': 'primary',
                                  'total_length_source_url': _SOURCE_URLS[16],
                                  'total_thickness_mm': 8.0,
                                  'total_thickness_status': 'derived_nominal',
                                  'total_thickness_source_url': _SOURCE_URLS[16],
                                  'dimensions_sources': (_SOURCE_URLS[16],),
                                  'dimensions_model_binding_url': _SOURCE_URLS[16],
                                  'dimensions_notes': ('Manufacturer raw flat-module dimension order is '
                                                       'preserved; mapping its planar short axis to upright '
                                                       'height is derived_nominal.',
                                                       'No PCB, heatsink-only or diffuser-only dimension is '
                                                       'inferred from that complete-module envelope.'),
                                  'declared_dimension_order': 'L x W x H',
                                  'declared_dimensions_mm': [133.35, 43.56, 8.0],
                                  'standing_axis_map': {'length': 'publisher_L',
                                                        'height': 'publisher_W',
                                                        'thickness': 'publisher_H'},
                                  'axis_basis': 'Publisher dimension triplet describes the module flat: '
                                                'contact-edge/long planar length is133.35, short planar body '
                                                'axis is43.56/45.93, thickness is8/8.4. Mapping to upright '
                                                'scene axes is explicit interpretation, not a publisher '
                                                'H=scene height assertion.',
                                  'manufacturer_explicit_scene_axis_labels': False},
 'adata-ax4u32008g16a-st60': {'total_height_mm': 45.93,
                              'total_height_status': 'derived_nominal',
                              'total_height_source_url': _SOURCE_URLS[17],
                              'total_length_mm': 133.35,
                              'total_length_status': 'primary',
                              'total_length_source_url': _SOURCE_URLS[17],
                              'total_thickness_mm': 8.4,
                              'total_thickness_status': 'derived_nominal',
                              'total_thickness_source_url': _SOURCE_URLS[17],
                              'total_height_tolerance_mm': 1.0,
                              'total_length_tolerance_mm': 1.0,
                              'total_thickness_tolerance_mm': 1.0,
                              'dimensions_sources': (_SOURCE_URLS[17],),
                              'dimensions_model_binding_url': _SOURCE_URLS[17],
                              'dimensions_notes': ('Manufacturer raw flat-module dimension order is '
                                                   'preserved; mapping its planar short axis to upright '
                                                   'height is derived_nominal.',
                                                   'No PCB, heatsink-only or diffuser-only dimension is '
                                                   'inferred from that complete-module envelope.'),
                              'declared_dimension_order': 'L x W x H',
                              'declared_dimensions_mm': [133.35, 45.93, 8.4],
                              'standing_axis_map': {'length': 'publisher_L',
                                                    'height': 'publisher_W',
                                                    'thickness': 'publisher_H'},
                              'axis_basis': 'Publisher dimension triplet describes the module flat: '
                                            'contact-edge/long planar length is133.35, short planar body '
                                            'axis is43.56/45.93, thickness is8/8.4. Mapping to upright scene '
                                            'axes is explicit interpretation, not a publisher H=scene height '
                                            'assertion.',
                              'manufacturer_explicit_scene_axis_labels': False},
 'corsair-cmk16gx4m2b3200c16w': {'total_height_mm': 33.53,
                                 'total_height_status': 'primary',
                                 'total_height_source_url': _SOURCE_URLS[1],
                                 'total_length_mm': 135.0,
                                 'total_length_status': 'primary',
                                 'total_length_source_url': _SOURCE_URLS[1],
                                 'total_thickness_mm': 6.64,
                                 'total_thickness_status': 'primary',
                                 'total_thickness_source_url': _SOURCE_URLS[1],
                                 'dimensions_sources': (_SOURCE_URLS[18], _SOURCE_URLS[1]),
                                 'dimensions_model_binding_url': _SOURCE_URLS[18],
                                 'dimensions_notes': ('Exact DDR generation/SKU binds official full-module '
                                                      'dimensions; PCB, heatsink and diffuser subdivisions '
                                                      'remain unknown.',)},
 'corsair-cmh32gx5m2b6000c30w': {'total_height_mm': 44.0,
                                 'total_height_status': 'primary',
                                 'total_height_source_url': _SOURCE_URLS[1],
                                 'total_length_mm': 135.0,
                                 'total_length_status': 'primary',
                                 'total_length_source_url': _SOURCE_URLS[1],
                                 'total_thickness_mm': 8.0,
                                 'total_thickness_status': 'primary',
                                 'total_thickness_source_url': _SOURCE_URLS[1],
                                 'dimensions_sources': (_SOURCE_URLS[19], _SOURCE_URLS[1]),
                                 'dimensions_model_binding_url': _SOURCE_URLS[19],
                                 'dimensions_notes': ('Exact DDR generation/SKU binds official full-module '
                                                      'dimensions; PCB, heatsink and diffuser subdivisions '
                                                      'remain unknown.',)},
 'corsair-cmt32gx5m2b5600c36w': {'total_height_mm': 56.0,
                                 'total_height_status': 'primary',
                                 'total_height_source_url': _SOURCE_URLS[1],
                                 'total_length_mm': 135.0,
                                 'total_length_status': 'primary',
                                 'total_length_source_url': _SOURCE_URLS[1],
                                 'total_thickness_mm': 8.0,
                                 'total_thickness_status': 'primary',
                                 'total_thickness_source_url': _SOURCE_URLS[1],
                                 'dimensions_sources': (_SOURCE_URLS[20], _SOURCE_URLS[1]),
                                 'dimensions_model_binding_url': _SOURCE_URLS[20],
                                 'dimensions_notes': ('Exact DDR generation/SKU binds official full-module '
                                                      'dimensions; PCB, heatsink and diffuser subdivisions '
                                                      'remain unknown.',)},
 'gskill-f4-3600c16d-16gtrg': {'total_height_mm': 44.0,
                               'total_height_status': 'primary',
                               'total_height_source_url': _SOURCE_URLS[5],
                               'dimensions_sources': (_SOURCE_URLS[21], _SOURCE_URLS[5]),
                               'dimensions_model_binding_url': _SOURCE_URLS[21],
                               'dimensions_notes': ('Exact manufacturer SKU binds the named family to its '
                                                    'official complete-module height; PCB dimensions remain '
                                                    'unknown.',)},
 'kingston-kf560c36bbeak2-32': {'total_height_mm': 42.23,
                                'total_height_status': 'primary',
                                'total_height_source_url': _SOURCE_URLS[22],
                                'total_length_mm': 133.35,
                                'total_length_status': 'primary',
                                'total_length_source_url': _SOURCE_URLS[22],
                                'total_thickness_mm': 7.11,
                                'total_thickness_status': 'primary',
                                'total_thickness_source_url': _SOURCE_URLS[22],
                                'total_height_tolerance_mm': 0.12,
                                'total_length_tolerance_mm': 0.12,
                                'total_thickness_tolerance_mm': 0.3,
                                'dimensions_sources': (_SOURCE_URLS[22],),
                                'dimensions_model_binding_url': _SOURCE_URLS[22],
                                'dimensions_notes': ('Manufacturer per-module dimensioned drawing and its '
                                                     'stated axis tolerances; no guaranteed mechanical '
                                                     'clearance follows from nominal dimensions.',)},
 'kingston-kf564c32rsak2-32': {'total_height_mm': 44.0,
                               'total_height_status': 'primary',
                               'total_height_source_url': _SOURCE_URLS[23],
                               'total_length_mm': 133.35,
                               'total_length_status': 'primary',
                               'total_length_source_url': _SOURCE_URLS[23],
                               'total_thickness_mm': 8.3,
                               'total_thickness_status': 'primary',
                               'total_thickness_source_url': _SOURCE_URLS[23],
                               'total_height_tolerance_mm': 0.15,
                               'total_length_tolerance_mm': 0.15,
                               'total_thickness_tolerance_mm': 0.15,
                               'dimensions_sources': (_SOURCE_URLS[23],),
                               'dimensions_model_binding_url': _SOURCE_URLS[23],
                               'dimensions_notes': ('Manufacturer per-module dimensioned drawing and its '
                                                    'stated axis tolerances; no guaranteed mechanical '
                                                    'clearance follows from nominal dimensions.',)},
 'kingston-kvr32n22s8k2-32': {'total_height_mm': 31.25,
                              'total_height_status': 'primary',
                              'total_height_source_url': _SOURCE_URLS[24],
                              'pcb_height_mm': 31.25,
                              'pcb_height_status': 'primary',
                              'pcb_height_source_url': _SOURCE_URLS[24],
                              'total_length_mm': 133.35,
                              'total_length_status': 'primary',
                              'total_length_source_url': _SOURCE_URLS[24],
                              'pcb_length_mm': 133.35,
                              'pcb_length_status': 'primary',
                              'pcb_length_source_url': _SOURCE_URLS[24],
                              'total_height_tolerance_mm': 0.12,
                              'pcb_height_tolerance_mm': 0.12,
                              'total_length_tolerance_mm': 0.12,
                              'pcb_length_tolerance_mm': 0.12,
                              'dimensions_sources': (_SOURCE_URLS[24],),
                              'dimensions_model_binding_url': _SOURCE_URLS[24],
                              'dimensions_notes': ('Manufacturer per-module dimensioned drawing and its '
                                                   'stated axis tolerances; no guaranteed mechanical '
                                                   'clearance follows from nominal dimensions.',
                                                   'Page1 specifies PCB height; page2 bare-module outline '
                                                   'shows its complete planar envelope at the same height, '
                                                   'without a heatspreader.')},
 'teamgroup-ff4d532g6000hc30dc01': {'total_height_mm': 46.1,
                                    'total_height_status': 'primary',
                                    'total_height_source_url': _SOURCE_URLS[14],
                                    'total_length_mm': 144.2,
                                    'total_length_status': 'primary',
                                    'total_length_source_url': _SOURCE_URLS[14],
                                    'total_thickness_mm': 7.0,
                                    'total_thickness_status': 'primary',
                                    'total_thickness_source_url': _SOURCE_URLS[14],
                                    'dimensions_sources': (_SOURCE_URLS[14],),
                                    'dimensions_model_binding_url': _SOURCE_URLS[14],
                                    'dimensions_notes': ('Exact kit part number appears in the official '
                                                         'ordering table; H/L/W refer to one complete '
                                                         'module, not package or PCB dimensions.',)},
 'teamgroup-flrd532g6000hc38jdc01': {'total_height_mm': 32.7,
                                     'total_height_status': 'primary',
                                     'total_height_source_url': _SOURCE_URLS[15],
                                     'total_length_mm': 140.0,
                                     'total_length_status': 'primary',
                                     'total_length_source_url': _SOURCE_URLS[15],
                                     'total_thickness_mm': 7.5,
                                     'total_thickness_status': 'primary',
                                     'total_thickness_source_url': _SOURCE_URLS[15],
                                     'dimensions_sources': (_SOURCE_URLS[15],),
                                     'dimensions_model_binding_url': _SOURCE_URLS[15],
                                     'dimensions_notes': ('Exact kit part number appears in the official '
                                                          'ordering table; H/L/W refer to one complete '
                                                          'module, not package or PCB dimensions.',)},
 'adata-ax5u6000c3016g-dclarbk': {'total_height_mm': 43.56,
                                  'total_height_status': 'derived_nominal',
                                  'total_height_source_url': _SOURCE_URLS[16],
                                  'total_length_mm': 133.35,
                                  'total_length_status': 'primary',
                                  'total_length_source_url': _SOURCE_URLS[16],
                                  'total_thickness_mm': 8.0,
                                  'total_thickness_status': 'derived_nominal',
                                  'total_thickness_source_url': _SOURCE_URLS[16],
                                  'dimensions_sources': (_SOURCE_URLS[16],),
                                  'dimensions_model_binding_url': _SOURCE_URLS[16],
                                  'dimensions_notes': ('Manufacturer raw flat-module dimension order is '
                                                       'preserved; mapping its planar short axis to upright '
                                                       'height is derived_nominal.',
                                                       'No PCB, heatsink-only or diffuser-only dimension is '
                                                       'inferred from that complete-module envelope.'),
                                  'declared_dimension_order': 'L x W x H',
                                  'declared_dimensions_mm': [133.35, 43.56, 8.0],
                                  'standing_axis_map': {'length': 'publisher_L',
                                                        'height': 'publisher_W',
                                                        'thickness': 'publisher_H'},
                                  'axis_basis': 'Publisher dimension triplet describes the module flat: '
                                                'contact-edge/long planar length is133.35, short planar body '
                                                'axis is43.56/45.93, thickness is8/8.4. Mapping to upright '
                                                'scene axes is explicit interpretation, not a publisher '
                                                'H=scene height assertion.',
                                  'manufacturer_explicit_scene_axis_labels': False},
 'adata-ax5u6000c3016g-clarwh': {'total_height_mm': 43.56,
                                 'total_height_status': 'derived_nominal',
                                 'total_height_source_url': _SOURCE_URLS[16],
                                 'total_length_mm': 133.35,
                                 'total_length_status': 'primary',
                                 'total_length_source_url': _SOURCE_URLS[16],
                                 'total_thickness_mm': 8.0,
                                 'total_thickness_status': 'derived_nominal',
                                 'total_thickness_source_url': _SOURCE_URLS[16],
                                 'dimensions_sources': (_SOURCE_URLS[16],),
                                 'dimensions_model_binding_url': _SOURCE_URLS[16],
                                 'dimensions_notes': ('Manufacturer raw flat-module dimension order is '
                                                      'preserved; mapping its planar short axis to upright '
                                                      'height is derived_nominal.',
                                                      'No PCB, heatsink-only or diffuser-only dimension is '
                                                      'inferred from that complete-module envelope.'),
                                 'declared_dimension_order': 'L x W x H',
                                 'declared_dimensions_mm': [133.35, 43.56, 8.0],
                                 'standing_axis_map': {'length': 'publisher_L',
                                                       'height': 'publisher_W',
                                                       'thickness': 'publisher_H'},
                                 'axis_basis': 'Publisher dimension triplet describes the module flat: '
                                               'contact-edge/long planar length is133.35, short planar body '
                                               'axis is43.56/45.93, thickness is8/8.4. Mapping to upright '
                                               'scene axes is explicit interpretation, not a publisher '
                                               'H=scene height assertion.',
                                 'manufacturer_explicit_scene_axis_labels': False},
 'adata-ax4u32008g16a-dt60': {'total_height_mm': 45.93,
                              'total_height_status': 'derived_nominal',
                              'total_height_source_url': _SOURCE_URLS[17],
                              'total_length_mm': 133.35,
                              'total_length_status': 'primary',
                              'total_length_source_url': _SOURCE_URLS[17],
                              'total_thickness_mm': 8.4,
                              'total_thickness_status': 'derived_nominal',
                              'total_thickness_source_url': _SOURCE_URLS[17],
                              'total_height_tolerance_mm': 1.0,
                              'total_length_tolerance_mm': 1.0,
                              'total_thickness_tolerance_mm': 1.0,
                              'dimensions_sources': (_SOURCE_URLS[17],),
                              'dimensions_model_binding_url': _SOURCE_URLS[17],
                              'dimensions_notes': ('Manufacturer raw flat-module dimension order is '
                                                   'preserved; mapping its planar short axis to upright '
                                                   'height is derived_nominal.',
                                                   'No PCB, heatsink-only or diffuser-only dimension is '
                                                   'inferred from that complete-module envelope.'),
                              'declared_dimension_order': 'L x W x H',
                              'declared_dimensions_mm': [133.35, 45.93, 8.4],
                              'standing_axis_map': {'length': 'publisher_L',
                                                    'height': 'publisher_W',
                                                    'thickness': 'publisher_H'},
                              'axis_basis': 'Publisher dimension triplet describes the module flat: '
                                            'contact-edge/long planar length is133.35, short planar body '
                                            'axis is43.56/45.93, thickness is8/8.4. Mapping to upright scene '
                                            'axes is explicit interpretation, not a publisher H=scene height '
                                            'assertion.',
                              'manufacturer_explicit_scene_axis_labels': False}}

_UNKNOWN={'total_height_mm': None,
 'total_height_status': 'unknown',
 'total_height_source_url': None,
 'pcb_height_mm': None,
 'pcb_height_status': 'unknown',
 'pcb_height_source_url': None,
 'total_length_mm': None,
 'total_length_status': 'unknown',
 'total_length_source_url': None,
 'pcb_length_mm': None,
 'pcb_length_status': 'unknown',
 'pcb_length_source_url': None,
 'total_thickness_mm': None,
 'total_thickness_status': 'unknown',
 'total_thickness_source_url': None,
 'pcb_thickness_mm': None,
 'pcb_thickness_status': 'unknown',
 'pcb_thickness_source_url': None,
 'max_total_thickness_mm': None,
 'max_total_thickness_status': 'unknown',
 'max_total_thickness_source_url': None,
 'total_height_tolerance_mm': None,
 'pcb_height_tolerance_mm': None,
 'total_length_tolerance_mm': None,
 'pcb_length_tolerance_mm': None,
 'total_thickness_tolerance_mm': None,
 'pcb_thickness_tolerance_mm': None,
 'dimensions_sources': (),
 'dimensions_model_binding_url': None,
 'dimensions_scope': 'per_module_not_kit_package',
 'dimensions_manufacturing_fit_verified': False,
 'installed_height_above_motherboard_mm': None,
 'seat_insertion_depth_mm': None,
 'heatspreader_height_mm': None,
 'diffuser_height_mm': None,
 'dimensions_notes': (),
 'declared_dimension_order': None,
 'declared_dimensions_mm': None,
 'standing_axis_map': None,
 'axis_basis': None,
 'manufacturer_explicit_scene_axis_labels': None,
 'dimensions_model_id': None,
 'height_mm_describes': 'pcb'}


def records():
    """Return detached audit records, without expanding aliases or series."""
    return tuple(dict(deepcopy(_UNKNOWN),**deepcopy(row),id=identity,dimensions_model_id=identity)
                 for identity,row in _FACTS.items())


def _unknown(module):
    # Template values are immutable. Known nested axis maps are deep-copied
    # below, so two modules/callers never share mutable derived metadata.
    module.update(_UNKNOWN)


def enrich(memory):
    """Attach source facts only to exact model-confidence memory identities.

    Preserve every legacy PCB-scaling height_mm/length_mm/thickness_mm. Reset
    unknown registry fields so a previous match cannot survive identity loss.
    The aggregate memory map never borrows one DIMM's complete dimensions.
    """
    result=deepcopy(memory) if isinstance(memory,dict) else {}
    _unknown(result)
    modules=result.get('modules')
    if not isinstance(modules,(list,tuple)):return result
    for module in modules:
        if not isinstance(module,dict):continue
        _unknown(module)
        appearance=module.get('appearance')
        if not isinstance(appearance,dict) or appearance.get('confidence')!='model':continue
        if appearance.get('kind','memory')!='memory':continue
        identity=appearance.get('id')
        if not isinstance(identity,str) or identity not in _FACTS:continue
        module.update(deepcopy(_FACTS[identity]),dimensions_model_id=identity)
    return result
