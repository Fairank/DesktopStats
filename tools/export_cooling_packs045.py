"""Deterministic, optional fan/cooler/radiator data, per class and per brand.

Authoring catalogs are used only by this tool. The app uses bounded pack data;
no source photo, mesh, image, shader, script or executable enters a model pack.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BRANCH='codex/cooling-library-v045'


def model_row(kind,reference):
    from cooling_pack_schema045 import validate_model
    reference=json.loads(json.dumps(reference,ensure_ascii=False,allow_nan=False))
    if kind=='fan':selector=dict(size_mm=reference['size_mm'],depth_mm=reference['depth_mm'],frame=reference['frame'],frameless=reference.get('frameless',False),mount_pitch_mm=reference.get('mount_pitch_mm'),mount_pitch_verified=reference.get('mount_pitch_verified',False))
    elif kind=='cooler':selector=dict(kind=reference['kind'],fan_size_mm=reference.get('fan_reference_mm'))
    else:selector={key:reference[key] for key in ('fan_size_mm','fan_count','fan_mount_pitch_mm','fan_mount_pitch_verified')}
    row=dict(id=reference['id'],label=reference['label'],vendor=reference['brand'],series=reference['series'],
        aliases=[reference['id']],sources=list(reference['sources']),reference=reference,selector=selector)
    return validate_model(kind,row)


def pack_models():
    from cooling_expansion045 import fan_records,cooler_records
    from liquid_radiator_expansion045 import records
    from cooling_catalog import _FAN_BY_ID
    fan_data=fan_records();fan_rows=list(fan_data.values()) if isinstance(fan_data,dict) else list(fan_data)
    cooler_data=cooler_records();cooler_rows=list(cooler_data.values()) if isinstance(cooler_data,dict) else list(cooler_data)
    rad_data=records();rad_rows=list(rad_data.values()) if isinstance(rad_data,dict) else list(rad_data)
    fans={**deepcopy(_FAN_BY_ID),**{row['id']:deepcopy(row) for row in fan_rows}}
    coolers=[]
    for source in cooler_rows:
        row=deepcopy(source);fan=fans.get(row.get('fan_model'))
        if row['fan_count']:
            if 'fan_reference_mm' not in row:
                if not fan:raise ValueError('Missing documented bundled fan size: '+row['id'])
                row['fan_reference_mm']=fan['size_mm']
            if fan:row['bundled_fan_reference']=fan
        else:row.setdefault('fan_reference_mm',None)
        coolers.append(row)
    return dict(fan=[model_row('fan',row) for row in fan_rows],
                cooler=[model_row('cooler',row) for row in coolers],
                radiator=[model_row('radiator',row) for row in rad_rows])


def export(destination):
    from hardware_packs import make_pack
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    library=pack_models();index=[]
    for kind,models in library.items():
        groups=[('collection','All '+kind+' models',models,'collection')]
        for brand in sorted({r['vendor'] for r in models}):
            slug=re.sub('[^a-z0-9]+','-',brand.casefold()).strip('-')
            groups.append((slug,brand+' '+kind,[r for r in models if r['vendor']==brand],'brand'))
        for suffix,label,rows,group in groups:
            pack_id=kind+'-'+suffix+'-045';filename='DesktopStats-'+pack_id+'-1.0.0.dspack'
            raw=make_pack(pack_id,label,rows,kind=kind);path=destination/filename
            if path.exists():
                if path.read_bytes()!=raw:raise FileExistsError('Model packs are immutable; bump data version: '+filename)
            else:
                with path.open('xb') as stream:stream.write(raw)
            relative=path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else filename
            index.append(dict(id=pack_id,label=label,kind=kind,group=group,file=relative,version='1.0.0',
                sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),products=len(rows),model_ids=[row['id'] for row in rows],
                minimum_app_version='0.45.0-preview.1',styles='all_13_shared',
                download_url='https://github.com/Fairank/DesktopStats/raw/refs/heads/'+BRANCH+'/'+relative,
                original_data=True,code=False,source_photos=False,persistent_meshes=0,background_workers=0))
    return dict(format=1,market_exhaustive=False,installed_by_default=False,
        unique_products=sum(len(rows) for rows in library.values()),by_kind={kind:len(rows) for kind,rows in library.items()},
        grouping_policy='Class collections and brand packs are alternatives with overlapping IDs; choose one per model. Overlapping installed inventories are rejected.',
        license='PolyForm-Noncommercial-1.0.0',packs=index)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'model-packs/v045');parser.add_argument('--index',type=Path,default=ROOT/'docs/COOLING_PACKS_INDEX.json');args=parser.parse_args()
    report=export(args.output);args.index.parent.mkdir(parents=True,exist_ok=True)
    args.index.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(packs=len(report['packs']),unique_products=report['unique_products'],by_kind=report['by_kind']),ensure_ascii=False))


if __name__=='__main__':main()
