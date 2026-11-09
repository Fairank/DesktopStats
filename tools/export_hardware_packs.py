"""Export deterministic, independent CPU data packs; no hardware or graphics IO."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def pack_models():
    from cpu_catalog import MODELS
    seeds={'intel-13700kf','amd-9950x','amd-7800x3d'}
    return {vendor:[dict(id=row['id'],label=row['label'],vendor=row['brand'],series=row['series'],
                        aliases=list(row['aliases']),sources=list(row['sources']),cpu_package=row['cpu_package'])
                    for row in MODELS if row['brand']==vendor and row['id'] not in seeds]
            for vendor in ('intel','amd')}


def export(destination):
    from hardware_packs import make_pack
    from product_version import VERSION
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    rows=[]
    for vendor,models in pack_models().items():
        identity='cpu-'+vendor+'-desktop';label={'intel':'Intel Desktop & HEDT','amd':'AMD Ryzen & Threadripper'}[vendor]
        raw=make_pack(identity,label,models)
        name='DesktopStats-'+identity+'-1.0.0.dspack'
        (destination/name).write_bytes(raw)
        rows.append(dict(id=identity,label=label,version='1.0.0',file=name,bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),products=len(models),kind='cpu',
            styles='all_13_shared',minimum_app_version='0.36.0-preview.1',
            download_url='https://github.com/Fairank/DesktopStats/releases/download/v'+VERSION+'/'+name,
            license='PolyForm-Noncommercial-1.0.0',background_workers=0,persistent_meshes=0))
    report=dict(format=1,market_exhaustive=False,base_cpu_products=3,optional_cpu_products=sum(row['products'] for row in rows),
                package_policy='Original shared package geometry; unverified mechanics remain explicitly unknown.',packs=rows)
    text=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    (destination/'hardware-packs-index.json').write_text(text,encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist'/'hardware-packs')
    args=parser.parse_args()
    print(json.dumps(export(args.output),ensure_ascii=False))


if __name__=='__main__':main()
