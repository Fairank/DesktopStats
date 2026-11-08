"""Publish the actual offline assembly inventory, never a claim of market coverage.

No Qt, hardware discovery, current readings, source images or downloads are used.
Run with --check to verify the committed reproducible inventory.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DESTINATION=ROOT/'docs/ASSEMBLY_CATALOG.json'


def loop_pack_index(models,index_file='docs/LOOP_PACKS_INDEX.json',release_directory='model-packs/v046'):
    """Read the real exported package inventory; never invent download hashes."""
    from hardware_packs import _archive
    path=ROOT/index_file
    if not path.is_file():raise ValueError('Export the actual data packs before the catalog')
    index=json.loads(path.read_text(encoding='utf8'))
    expected={row['id']:row for row in models}
    counts=dict(sorted(Counter(row['reference']['part_kind'] for row in models).items()))
    if (index.get('unique_products')!=len(expected) or index.get('by_kind')!=counts or
            index.get('installed_by_default') is not False):
        raise ValueError('Loop package index disagrees with the authoring inventory')
    covered=set()
    for item in index['packs']:
        file=(ROOT/item['file']).resolve()
        if not file.is_relative_to((ROOT/release_directory).resolve()) or file.suffix!='.dspack':
            raise ValueError('Loop package path is outside the data-only release directory')
        raw=file.read_bytes()
        if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise ValueError('Loop package index hash or byte size is stale')
        manifest,contents=_archive(raw)
        identities=[row['id'] for row in contents]
        if (manifest['kind']!='loop' or manifest['id']!=item['id'] or
                set(identities)!=set(item['model_ids']) or len(identities)!=item['products'] or
                any(row!=expected.get(row['id']) for row in contents)):
            raise ValueError('Loop package model contents disagree with the catalog')
        covered.update(identities)
    if covered!=set(expected):raise ValueError('Loop package index omits an authoring product')
    return index


def build_report():
    from hardware_appearance import CATALOG,BRANDS,appearance_for
    from memory_appearance import CATALOG as MEMORY,BRANDS as MEMORY_BRANDS,appearance_for_memory
    from motherboard_catalog import MODELS
    from cooling_catalog import _COOLERS,_FANS
    from fan_mounting044 import apply_mounting_facts
    from copy import deepcopy
    from tools.export_cooling_packs045 import pack_models
    from tools.export_loop_packs046 import pack_models as loop_models
    from tools.export_gpu_block_packs047 import pack_models as gpu_block_models
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
    loops=loop_models();loop_index=loop_pack_index(loops)
    gpu_blocks=gpu_block_models()
    gpu_index=loop_pack_index(gpu_blocks,'docs/GPU_BLOCK_PACKS047_INDEX.json','model-packs/v047')
    loops=loops+gpu_blocks;optional_loops=[]
    for row in loops:
        raw=row['reference']
        optional_loops.append(dict(kind=raw['part_kind'],model_id=row['id'],label=row['label'],brand=row['vendor'],series=row['series'],
            delivery='optional_pack',pack_kind='loop',pack_collection_id='gpu-block-collection-047' if raw['part_kind']=='gpu_block' else 'loop-collection-046',
            dimensions_mm=raw['dimensions_mm'],reference_envelope_mm=raw['reference_envelope_mm'],
            dimensions_verified=raw['dimensions_verified'],dimensions_scope=raw.get('dimensions_scope','unknown'),
            body_dimensions_mm=raw.get('body_dimensions_mm'),body_dimensions_verified=raw.get('body_dimensions_verified',False),
            ports_count=raw['ports_count'],ports_geometry_complete=raw['ports_geometry_complete'],exact_port_positions_verified=False,
            contains_motor=raw.get('contains_motor'),requires_motor=raw.get('requires_motor'),
            source_urls=list(row['sources']),model_status='original_schematic',styles='all_listed_styles',
            geometry_scope='source_observed_reference_no_manufacturer_cad',telemetry='not_bound_to_installed_sensor',
            installed_hardware_inferred=False,manufacturer_fit_verified=False,
            **(dict(assembly_stage=raw['assembly_stage'],gpu_compatibility=raw['gpu_compatibility'],materials=raw['materials'],
                gpu_installation_supported=False,loop_connection_supported=False) if raw['part_kind']=='gpu_block' else {})))
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
                              cooling_pack_index='docs/COOLING_PACKS_INDEX.json',loop_products=len(optional_loops),
                              loop_by_kind=dict(sorted(Counter(r['kind'] for r in optional_loops).items())),
                              loop_package_artifacts=len(loop_index['packs'])+len(gpu_index['packs']),loop_pack_index='docs/LOOP_PACKS_INDEX.json',
                              gpu_block_products=len(gpu_blocks),gpu_block_package_artifacts=len(gpu_index['packs']),gpu_block_pack_index='docs/GPU_BLOCK_PACKS047_INDEX.json',
                              total_optional_products=len(optional_cpus)+len(optional_cooling)+len(optional_loops),
                              total_named_products=sum(row['record_type']=='product' for row in rows)+len(optional_cpus)+len(optional_cooling)+len(optional_loops),
                              installed_by_default=False,executable_content=False),
        artwork_2d=dict(kinds=['case','cooler','psu','fan'],
            records=sum(counts[kind] for kind in ('case','cooler','psu','fan')),
            styles=list(HARDWARE_ICON_STYLES),generator='on_demand_svg',cache_max_entries=16,
            motion='explicit_reference_demonstration',sensor_binding=False,
            download_format='standalone_svg_collections',market_exhaustive=False),
        optional_products=optional_cpus+optional_cooling+optional_loops,products=rows)


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
