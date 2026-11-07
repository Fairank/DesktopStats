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
    from cooling_catalog import choices_coolers,choices_fans,get_cooler,get_fan
    from component_catalog import CATALOG as AUXILIARY
    from chassis_catalog import CASES
    from top_bar_config import HARDWARE_ICON_STYLES
    from tools.export_hardware_coverage import sources
    from cpu_catalog import MODELS as CPU_MODELS
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
    for kind,choices,getter in (('cooler',choices_coolers,get_cooler),('fan',choices_fans,get_fan)):
        for choice in choices():
            raw=getter(choice['id'])
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
    return dict(schema_version=1,market_exhaustive=False,machine_inventory=False,
        scope='Named selectable products, original schematic models; not manufacturing CAD or a fit guarantee.',
        styles=list(HARDWARE_ICON_STYLES),style_policy='Every product retains identical geometry and identity across all styles.',
        selection_policy='Unrecognized installed identities remain neutral; reference models never inherit another device’s measurements.',
        summary=dict(records=len(rows),products=sum(row['record_type']=='product' for row in rows),
            reference_combinations=sum(row['record_type']=='reference_combination' for row in rows),by_kind=dict(sorted(counts.items())),
            brands=len({row['brand'].casefold() for row in rows if row['brand'] and row['record_type']=='product'}),
            series_pending=sum(row['series'] is None for row in rows)),
        optional_summary=dict(cpu_products=len(optional_cpus),available_cpu_products=len(CPU_MODELS),
                              packs=2,installed_by_default=False,executable_content=False),
        optional_products=optional_cpus,products=rows)


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
