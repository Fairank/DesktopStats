"""Export four independent noncommercial SVG collections from real app artwork.

No Qt, hardware, 3D mesh generation or downloads. These are standalone artwork
collections, not executable extensions or CPU .dspack imports.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
KINDS={'case':'cases','cooler':'coolers','psu':'psus','fan':'fans'}


def export(destination):
    from accessory_art import builtin_choices as choices,art,clear_cache
    from product_version import VERSION
    from top_bar_config import HARDWARE_ICON_STYLES
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    catalog=choices();license_bytes=(ROOT/'LICENSE').read_bytes();packs=[]
    try:
        for kind,key in KINDS.items():
            rows=catalog[key];members={};models=[]
            for row in rows:
                files=[]
                for style in HARDWARE_ICON_STYLES:
                    result=art(kind,row['id'],style)
                    if not result or not result.get('svg'):raise ValueError('Missing artwork: '+row['id'])
                    raw=result['svg'].encode('utf8');name=row['id']+'/'+style+'.svg'
                    members[name]=raw;files.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                models.append(dict(id=row['id'],label=row['label'],brand=row['brand'],
                    record_type='reference_combination' if row['id']=='custom-loop-360-reference' else 'product',
                    reference_details=result.get('reference_details',True),sources=result.get('sources',[]),files=files))
            manifest=dict(format=1,version=VERSION,kind=kind,models=models,styles=list(HARDWARE_ICON_STYLES),
                license='PolyForm-Noncommercial-1.0.0',machine_inventory=False,market_exhaustive=False,
                artwork='Original schematic illustrations, not manufacturer assets or manufacturing CAD.',
                sensor_binding=False,animation='Static SVG exports. Explicit demonstration is available inside the app.')
            members['manifest.json']=(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
            members['LICENSE.md']=license_bytes
            members['NOTICE.txt']=(ROOT/'NOTICE').read_bytes()
            members['LICENSING.md']=(ROOT/'LICENSING.md').read_bytes()
            members['README.txt']=(
                'DesktopStats original SVG artwork / noncommercial use only.\n'
                'Product names and trademarks belong to their respective owners.\n'
                'These are standalone SVG illustrations, not application .dspack extensions.\n'
                'The app already includes these models and generates visible artwork on demand.\n'
                'Dimensions/appearance details may be schematic; see manifest.json source/status fields.\n').encode('utf8')
            name=f'DesktopStats-{VERSION}-{key}-SVG.zip';target=destination/name
            if target.exists():raise FileExistsError('Refuse to replace an existing artwork collection')
            with target.open('xb') as stream:
                with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
                    for path,raw in sorted(members.items()):
                        info=zipfile.ZipInfo(path,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                        info.external_attr=0o100644<<16;archive.writestr(info,raw,compresslevel=9)
            raw=target.read_bytes()
            packs.append(dict(kind=kind,models=len(models),svg_files=len(rows)*len(HARDWARE_ICON_STYLES),
                file=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                download_url='https://github.com/Fairank/DesktopStats/releases/download/models-v'+VERSION+'/'+name))
    finally:clear_cache()
    report=dict(version=VERSION,styles=len(HARDWARE_ICON_STYLES),models=sum(row['models'] for row in packs),
                svg_files=sum(row['svg_files'] for row in packs),market_exhaustive=False,collections=packs)
    target=destination/f'DesktopStats-{VERSION}-SVG-index.json'
    with target.open('xb') as stream:stream.write((json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8'))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'dist')
    print(json.dumps(export(parser.parse_args().output),ensure_ascii=False))


if __name__=='__main__':main()
