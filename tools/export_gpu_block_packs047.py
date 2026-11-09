"""Export12 independent GPU blocks as optional data-only047 packs, never overwrite046."""
import argparse,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def pack_models():
    from liquid_gpu_blocks047 import records
    from tools.export_loop_packs046 import model_row
    return [model_row(row) for row in records()]

def export(destination):
    from hardware_packs import make_pack
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    rows=pack_models();groups=[('collection','GPU block references',rows,'collection')]
    for brand in sorted({r['vendor'] for r in rows}):
        slug=re.sub('[^a-z0-9]+','-',brand.casefold()).strip('-')
        groups.append(('brand-'+slug,brand+' GPU block references',[r for r in rows if r['vendor']==brand],'brand'))
    packages=[]
    for suffix,label,models,group in groups:
        identity='gpu-block-'+suffix+'-047';filename='DesktopStats-'+identity+'-1.0.0.dspack'
        raw=make_pack(identity,label,models,kind='loop');target=destination/filename
        if target.exists():
            if target.read_bytes()!=raw:raise FileExistsError('Existing GPU model package has different bytes: '+filename)
        else:
            with target.open('xb') as stream:stream.write(raw)
        public_path=target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) and not target.is_relative_to(ROOT/'qa-private') else filename
        packages.append(dict(id=identity,label=label,kind='loop',part_kind='gpu_block',group=group,file=public_path,
            bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),version='1.0.0',minimum_app_version='0.47.0-preview.1',
            products=len(models),model_ids=[r['id'] for r in models],styles='all_13_shared',assembly_stage='standalone_reference_only',
            download_url='https://github.com/Fairank/DesktopStats/raw/refs/heads/codex/hardware-polish-v047/'+public_path if public_path.startswith('model-packs/') else None))
    return dict(format=1,unique_products=len(rows),by_kind={'gpu_block':len(rows)},installed_by_default=False,
        market_exhaustive=False,geometry_accuracy='original_reference_not_CAD',assembly_pose_verified=False,
        gpu_installation_supported=False,loop_connection_supported=False,held_rows_included=False,
        license='PolyForm-Noncommercial-1.0.0',third_party_notice='Product names/trademarks belong to their owners. Manufacturer photographs and manuals are not distributed.',
        grouping_policy='Collection/brand packages overlap; install one alternative for each model.',packs=packages)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'model-packs/v047')
    parser.add_argument('--index',type=Path,default=ROOT/'docs/GPU_BLOCK_PACKS047_INDEX.json')
    args=parser.parse_args();result=export(args.output)
    args.index.parent.mkdir(parents=True,exist_ok=True);args.index.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(products=result['unique_products'],packages=len(result['packs']))))

if __name__=='__main__':main()
