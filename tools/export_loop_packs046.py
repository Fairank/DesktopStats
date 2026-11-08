"""Deterministic independent water-loop references, optional and data-only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def model_row(reference):
    from liquid_pack_schema046 import validate_reference,validate_model,selector_for
    reference=validate_reference(json.loads(json.dumps(reference,ensure_ascii=False,allow_nan=False)))
    row=dict(id=reference['id'],label=reference['label'],vendor=reference['brand'],series=reference['series'],
        aliases=[reference['id']],sources=reference['sources'],reference=reference,selector=selector_for(reference))
    return validate_model(row)

def pack_models():
    # These author catalogs are absent from the runtime import graph.
    from liquid_block_pump_expansion046 import records as blocks
    from liquid_fitting_tube_expansion046 import records as fittings
    rows=[model_row(r) for r in (*blocks(),*fittings())]
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate independent loop identity')
    return rows

def export(destination):
    from hardware_packs import make_pack
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    models=pack_models();groups=[('collection','All independent loop components',models,'collection')]
    for kind in sorted({r['reference']['part_kind'] for r in models}):
        groups.append((kind.replace('_','-'),kind,[r for r in models if r['reference']['part_kind']==kind],'category'))
    for brand in sorted({r['vendor'] for r in models}):
        slug=re.sub('[^a-z0-9]+','-',brand.casefold()).strip('-')
        groups.append(('brand-'+slug,brand+' loop references',[r for r in models if r['vendor']==brand],'brand'))
    packs=[]
    for suffix,label,rows,group in groups:
        pack_id='loop-'+suffix+'-046';filename='DesktopStats-'+pack_id+'-1.0.0.dspack'
        data=make_pack(pack_id,label,rows,kind='loop');path=destination/filename
        if path.exists():
            if path.read_bytes()!=data:raise FileExistsError('Published model data is immutable: '+filename)
        else:
            with path.open('xb') as stream:stream.write(data)
        relative=path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else filename
        packs.append(dict(id=pack_id,label=label,kind='loop',group=group,file=relative,bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),version='1.0.0',products=len(rows),model_ids=[r['id'] for r in rows],
            minimum_app_version='0.46.0-preview.1',styles='all_13_shared',
            download_url='https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/loop-components-v046/'+relative))
    return dict(format=1,unique_products=len(models),by_kind={k:sum(r['reference']['part_kind']==k for r in models) for k in sorted({r['reference']['part_kind'] for r in models})},
        installed_by_default=False,market_exhaustive=False,license='PolyForm-Noncommercial-1.0.0',
        grouping_policy='All/category/brand packs are overlapping alternatives; never install the same model twice.',packs=packs)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'model-packs/v046')
    parser.add_argument('--index',type=Path,default=ROOT/'docs/LOOP_PACKS_INDEX.json');args=parser.parse_args()
    report=export(args.output);args.index.parent.mkdir(parents=True,exist_ok=True)
    args.index.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(products=report['unique_products'],by_kind=report['by_kind'],packages=len(report['packs']))))

if __name__=='__main__':main()
