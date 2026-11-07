"""Reproducible nominal radiator/AIO sizes and real motherboard form factors."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def build_report():
    from liquid_cooling_catalog044 import records as base_radiators
    from liquid_radiator_expansion045 import records as optional_radiators
    from cooling_catalog import _COOLERS
    from cooling_expansion045 import cooler_records
    from motherboard_catalog import MODELS
    radiators=[]
    for delivery,rows in (('base',base_radiators()),('optional',optional_radiators())):
        for row in rows:
            radiators.append(dict(model_id=row['id'],label=row['label'],brand=row['brand'],series=row['series'],delivery=delivery,
                nominal_size_mm=row['fan_size_mm']*row['fan_count'],fan_size_mm=row['fan_size_mm'],capacity_per_face=row['fan_count'],
                dimensions_mm=row['dimensions_mm'],dimensions_verified=row['dimensions_verified'],sources=row['sources']))
    aio=[]
    for delivery,rows in (('base',_COOLERS),('optional',cooler_records().values())):
        for row in rows:
            if row['kind']!='aio':continue
            aio.append(dict(model_id=row['id'],label=row['label'],brand=row['brand'],delivery=delivery,
                nominal_size_mm=row['radiator_size'],fan_count=row['fan_count'],radiator_mm=row['radiator_mm'],
                radiator_dimensions_verified=row['radiator_dimensions_verified'],sealed=True,sources=row['sources']))
    boards=[dict(model_id=r['id'],label=r['label'],brand=r['brand'],form_factor=r['form_factor'],socket=r['socket'],memory_type=r['memory_type'],
        dimensions_mm=r['dimensions_mm'],layout_status=r['layout_status'],finish_status=r['finish_status'],sources=r['sources']) for r in MODELS]
    matrix=defaultdict(Counter)
    for row in radiators:matrix[row['brand']][str(row['nominal_size_mm'])]+=1
    return dict(schema=1,market_exhaustive=False,styles=['miniature','cartoon','notebook_color','notebook_line','sticker','papercut'],
        new_styles_enabled=False,reference_not_manufacturing_cad=True,
        radiator_nominal_counts=dict(sorted(Counter(r['nominal_size_mm'] for r in radiators).items())),
        radiator_brand_size_matrix={brand:dict(sorted(count.items(),key=lambda p:int(p[0]))) for brand,count in sorted(matrix.items())},
        aio_nominal_counts=dict(sorted(Counter(r['nominal_size_mm'] for r in aio).items())),
        board_form_counts=dict(Counter(r['form_factor'] for r in boards)),board_socket_counts=dict(Counter(r['socket'] for r in boards)),
        unresolved='A size class being present does not prove every brand/series/SKU is covered. Absent cells are not invented products.',
        radiators=radiators,aio=aio,boards=boards)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    output=ROOT/'docs/SIZE_COVERAGE.json';data=build_report();raw=json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    if args.check:
        if output.read_text(encoding='utf8')!=raw:raise SystemExit('Size coverage is stale')
    else:output.write_text(raw,encoding='utf8')
    print(json.dumps({key:data[key] for key in ('radiator_nominal_counts','aio_nominal_counts','board_form_counts','board_socket_counts')},ensure_ascii=False))


if __name__=='__main__':main()
