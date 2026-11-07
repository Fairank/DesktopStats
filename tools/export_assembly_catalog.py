"""Publish the actual offline assembly inventory, never a claim of market coverage.

No Qt, hardware discovery, current readings, source images or downloads are used.
Run with --check to verify the committed reproducible inventory.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DESTINATION=ROOT/'docs/ASSEMBLY_CATALOG.json'


def build_report():
    from hardware_appearance import CATALOG,BRANDS,appearance_for
    from memory_appearance import CATALOG as MEMORY,BRANDS as MEMORY_BRANDS,appearance_for_memory
    from motherboard_catalog import MODELS
    from cooling_catalog import _COOLERS,_FANS
    from fan_mounting044 import apply_mounting_facts
    from copy import deepcopy
    from tools.export_cooling_packs045 import pack_models
    from component_catalog import CATALOG as AUXILIARY
    from chassis_catalog import CASES
    from top_bar_config import HARDWARE_ICON_STYLES
    from tools.export_hardware_coverage import sources
    from cpu_catalog import MODELS as CPU_MODELS
    from liquid_cooling_catalog044 import records as radiator_records
    rows=[]

    def add(kind,raw,brand,series='',**status):
        brand='CORSAIR' if brand.casefold()=='corsair' else brand
        rows.append(dict(kind=kind,model_id=raw['id'],label=raw['label'],brand=brand,
            record_type='reference_combination' if brand=='Reference combination' else 'product',
            series=series or None,taxonomy_status='classified' if series else 'series_pending',
            model_status='original_schematic',styles='all_listed_styles',
            source_urls=sources(raw.get('sources') or raw.get('source_url') or (),raw.get('appearance_sources')),
            dimensions_mm=raw.get('dimensions_mm') or None,**status))

    for raw in CATALOG:
        identity,kind,vendor,board,label,*_=raw
        appearance=appearance_for(kind,raw[-1][0])
        details=appearance.get('board_details') or {}
        add(kind,dict(id=identity,label=label,source_url=raw[-2],dimensions_mm=details.get('dimensions_mm')),
            BRANDS[board if board!='unknown' else vendor][0],appearance.get('series_label','') or
            {'intel-13700kf':'Core 13th Gen','amd-9950x':'Ryzen 9000','amd-7800x3d':'Ryzen 7000'}.get(identity,''),
            geometry_scope='existing_hardware_profile',telemetry='installed_identity_only',
            internal_pcb_routing='unverified')
    for raw in MEMORY:
        appearance=appearance_for_memory(model=raw['aliases'][0])
        add('memory',raw,MEMORY_BRANDS[raw['brand']][0],appearance.get('series_label',''),
            geometry_scope='existing_hardware_profile',telemetry='whole_system_not_per_module')
    for raw in CASES:
        add('case',raw,raw['brand'],raw.get('series',''),
            geometry_scope='exterior_and_reference_installation',firmware_mapping='unverified',
            native_io_status='reviewed' if raw.get('exterior_details') else 'unverified')
    for raw in MODELS:
        add('board',raw,raw['brand'],raw.get('series',''),
            layout_status=raw.get('layout_status','manual_reviewed'),
            finish_status=raw.get('finish_status','unverified_reference'),
            internal_pcb_routing='unverified',small_package_placement='schematic')
    for kind,base in (('cooler',_COOLERS),('fan',_FANS)):
        for original in base:
            raw=apply_mounting_facts(deepcopy(original)) if kind=='fan' else original
            add(kind,raw,raw['brand'],raw.get('series',''),
                geometry_scope='documented_envelope_and_original_detail',
                dimensions_verified=raw.get('dimensions_verified',False),
                blade_geometry_reviewed=raw.get('blade_geometry_reviewed',False),
                rotation_direction_verified=False,telemetry='explicit_channel_mapping_only')
    for raw in AUXILIARY:
        add(raw['category'],raw,raw.get('brand',''),raw.get('series',''),
            geometry_scope='documented_envelope_and_original_detail',
            finish_status='unverified_reference' if raw.get('appearance_unverified') else
                'photo_observed_schematic' if raw.get('appearance_sources') else 'reference',
            telemetry='not_bound_to_installed_sensor')
    for raw in radiator_records():
        add('radiator',raw,raw['brand'],raw['series'],geometry_scope='standalone_custom_loop_body',
            dimensions_verified=raw['dimensions_verified'],ports_count=raw['ports_count'],
            port_layout_verified=raw['port_layout_verified'],ports_geometry_complete=raw['ports_geometry_complete'],
            exact_port_positions_verified=False,fan_mount_capacity_per_side=raw['fan_count'],
            fan_size_mm=raw['fan_size_mm'],installed_fans_inferred=False,telemetry='not_bound_to_installed_sensor')
    rows.sort(key=lambda row:(row['kind'],row['brand'].casefold(),row['series'] or '',row['model_id']))
    keys=[(row['kind'],row['model_id']) for row in rows]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate assembly product identity')
    counts=Counter(row['kind'] for row in rows)
    base_cpu_ids={row['model_id'] for row in rows if row['kind']=='cpu'}
    optional_cpus=[dict(kind='cpu',model_id=row['id'],label=row['label'],brand=BRANDS[row['brand']][0],
        series=row['series'],delivery='optional_pack',pack_id='cpu-'+row['brand']+'-desktop',
        socket=row['socket'],package_family=row['package_family'],dimensions_mm=row['dimensions_mm'],
        dimensions_status=row['dimensions_status'],source_urls=list(row['sources']),
        model_status='original_schematic',styles='all_listed_styles',
        internal_layout_verified=False,telemetry='installed_identity_only') for row in CPU_MODELS if row['id'] not in base_cpu_ids]
    optional_cooling=[]
    for kind,models in pack_models().items():
        for row in models:
            raw=row['reference']
            optional_cooling.append(dict(kind=kind,model_id=row['id'],label=row['label'],brand=row['vendor'],series=row['series'],delivery='optional_pack',
                pack_collection_id=kind+'-collection-045',dimensions_mm=raw.get('dimensions_mm') or raw.get('radiator_mm'),source_urls=list(row['sources']),
                model_status='original_schematic',styles='all_listed_styles',dimensions_verified=raw.get('dimensions_verified',raw.get('radiator_dimensions_verified',False)),
                blade_count_verified=raw.get('blade_count_verified',False),blade_geometry_reviewed=raw.get('blade_geometry_reviewed',False),
                geometry_scope='shared_generator_and_source_observed_reference',telemetry='not_bound_to_installed_sensor'))
    return dict(schema_version=1,market_exhaustive=False,machine_inventory=False,
        scope='Named selectable products, original schematic models; not manufacturing CAD or a fit guarantee.',
        styles=list(HARDWARE_ICON_STYLES),style_policy='Every product retains identical geometry and identity across all styles.',
        selection_policy='Unrecognized installed identities remain neutral; reference models never inherit another device’s measurements.',
        summary=dict(records=len(rows),products=sum(row['record_type']=='product' for row in rows),
            reference_combinations=sum(row['record_type']=='reference_combination' for row in rows),by_kind=dict(sorted(counts.items())),
            brands=len({row['brand'].casefold() for row in rows if row['brand'] and row['record_type']=='product'}),
            series_pending=sum(row['series'] is None for row in rows)),
        optional_summary=dict(cpu_products=len(optional_cpus),available_cpu_products=len(CPU_MODELS),
                              packs=2,cooling_products=len(optional_cooling),cooling_by_kind=dict(Counter(r['kind'] for r in optional_cooling)),
                              cooling_pack_index='docs/COOLING_PACKS_INDEX.json',installed_by_default=False,executable_content=False),
        artwork_2d=dict(kinds=['case','cooler','psu','fan'],
            records=sum(counts[kind] for kind in ('case','cooler','psu','fan')),
            styles=list(HARDWARE_ICON_STYLES),generator='on_demand_svg',cache_max_entries=16,
            motion='explicit_reference_demonstration',sensor_binding=False,
            download_format='standalone_svg_collections',market_exhaustive=False),
        optional_products=optional_cpus+optional_cooling,products=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();report=build_report()
    encoded=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding='utf8')!=encoded:
            raise SystemExit('Assembly catalog is stale; run tools/export_assembly_catalog.py')
    else:DESTINATION.write_text(encoded,encoding='utf8')
    print(json.dumps(dict(checked=args.check,**report['summary']),ensure_ascii=False))


if __name__=='__main__':main()
