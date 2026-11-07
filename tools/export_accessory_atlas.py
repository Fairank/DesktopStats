"""Export the real artwork as a self-contained, noncommercial offline atlas.

Uses only the standard library and pure artwork catalogs. No browser, device,
network, Qt, renderer, installer or background process is started.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
KINDS={'case':'cases','cooler':'coolers','psu':'psus','fan':'fans'}
STYLE_NAMES={'miniature':'1 · 原版','cartoon':'2 · 可爱笑脸','notebook_color':'3 · 彩色手绘',
    'notebook_line':'4 · 纯线条','sticker':'5 · 奶油贴纸','papercut':'6 · 拼色剪纸','inkwash':'7 · 蓝墨手账',
    'classic':'经典通用','outline':'结构线稿','solid':'精简实物','soft':'柔和双色',
    'sketch':'手绘线稿','notebook_smile':'笑脸手绘'}
_ID=re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z',re.ASCII)
_SVG='{http://www.w3.org/2000/svg}'


def _json(value):
    # Safe both inside a classic script file and the inline catalog data tag.
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).replace(
        '<','\\u003c').replace('>','\\u003e').replace('&','\\u0026').replace(
        '\u2028','\\u2028').replace('\u2029','\\u2029').encode('utf8')


def _validate(result,kind,identity,style):
    if (not result or (result['kind'],result['id'],result['style'])!=(kind,identity,style)
            or not result.get('reference_details')):raise ValueError('Missing reference artwork: '+identity)
    for name in ('svg','body_svg','foreground_svg'):
        if not result[name] and name=='foreground_svg':continue
        _validate_svg(result[name])
    for rotor in result['rotors']:_validate_svg(rotor['svg'])
    if any(not isinstance(url,str) or not url.startswith('https://') for url in result['sources']):
        raise ValueError('Reference sources must be public HTTPS URLs')


def _validate_svg(source):
    root=ET.fromstring(source)
    if root.tag!=_SVG+'svg':raise ValueError('Expected project SVG artwork')
    for node in root.iter():
        if node.tag.removeprefix(_SVG) in ('script','foreignObject','image','use','a','style'):
            raise ValueError('External or executable SVG content is not permitted')
        if any(key.lower().startswith('on') or key.endswith('href') for key in node.attrib):
            raise ValueError('External SVG references are not permitted')


def export(destination):
    from product_version import VERSION
    if not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z._-]{0,79}',VERSION):raise ValueError('Invalid product version')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    name=f'DesktopStats-{VERSION}-Model-Atlas.zip';target=destination/name
    if target.exists():raise FileExistsError('Refuse to replace an existing model atlas')
    from accessory_art import STYLES,art,choices,clear_cache
    catalog=choices();styles=tuple(STYLES)
    if set(styles)!=set(STYLE_NAMES):raise ValueError('Atlas labels must cover all artwork styles')
    for key,rows in catalog.items():
        if key not in KINDS.values() or any(not _ID.fullmatch(row['id']) for row in rows):
            raise ValueError('Invalid model catalog')
    counts={kind:len(catalog[key]) for kind,key in KINDS.items()}
    index=dict(version=VERSION,models={kind:[{key:row[key] for key in ('id','label','brand')}
                   for row in catalog[group]] for kind,group in KINDS.items()},counts=counts,
               styles=[dict(id=style,label=STYLE_NAMES[style]) for style in styles],
               slices={kind:{style:'data/'+kind+'/'+style+'.js' for style in styles} for kind in KINDS})
    template=(ROOT/'tools/templates/accessory-atlas.html').read_text(encoding='utf8')
    html=template.replace('@@CATALOG@@',_json(index).decode('utf8')).replace('@@VERSION@@',VERSION).encode('utf8')
    summaries=[];sources={};created=False
    try:
        with target.open('xb') as stream:
            created=True
            with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                def write(path,chunks):
                    info=zipfile.ZipInfo(path,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                    info.create_system=3;info.external_attr=0o100644<<16
                    digest=hashlib.sha256();size=0
                    with archive.open(info,'w') as output:
                        for chunk in chunks:output.write(chunk);digest.update(chunk);size+=len(chunk)
                    summaries.append(dict(path=path,bytes=size,sha256=digest.hexdigest()))
                write('index.html',(html,))
                for license_name in ('LICENSE','NOTICE','LICENSING.md','THIRD_PARTY_NOTICES.md'):
                    write(license_name,((ROOT/license_name).read_bytes(),))
                readme=('DesktopStats offline model atlas / '+VERSION+'\n\n'
                    'Unzip the complete folder, then open index.html in a browser. No server, install or network is needed.\n'
                    'Keep the data folder beside index.html. A browser must permit local classic JavaScript files.\n'
                    'Only the selected category/style and up to12 cards are displayed; fan demonstration defaults off.\n'
                    'All motion is reference demonstration, not measured speed or direction. No devices are detected.\n'
                    'Models are original schematic illustrations, not manufacturer photographs, logos or CAD.\n'
                    'The named catalog is not exhaustive of the market; one custom-loop entry is a reference combination.\n'
                    'OLED screens are unbound and blank; RGB colors are static illustrations, not live lighting readings.\n'
                    'Original code and artwork: PolyForm Noncommercial1.0.0. No commercial use without separate permission.\n'
                    'Preserve LICENSE, NOTICE, LICENSING.md and source notices when sharing.\n'
                    'No Qt/Python/sensor libraries are included; their general project notices are retained for context.\n'
                    'SOURCES.json lists the public specification/appearance references. No vendor assets are included.\n'
                    'manifest.json describes payload hashes; SHA256SUMS.txt covers every other file, including the manifest.\n').encode('utf8')
                write('README.txt',(readme,))
                for kind,group in KINDS.items():
                    for style in styles:
                        def chunks():
                            yield b'window.DesktopStatsAtlas.receive({"kind":'+_json(kind)+b',"style":'+_json(style)+b',"models":['
                            for number,row in enumerate(catalog[group]):
                                result=art(kind,row['id'],style);_validate(result,kind,row['id'],style)
                                sources.setdefault(row['id'],dict(id=row['id'],kind=kind,label=row['label'],brand=row['brand'],
                                    sources=result['sources'],reference_details=result['reference_details'],
                                    record_type='reference_combination' if row['id']=='custom-loop-360-reference' else 'product'))
                                record={key:result[key] for key in ('id','svg','body_svg','foreground_svg','rotors','art_details',
                                    'reference_details','motion_source','rotation_direction_verified','original_face')}
                                if number:yield b','
                                yield _json(record)
                            yield b']});\n'
                        write('data/'+kind+'/'+style+'.js',chunks())
                        clear_cache()
                write('SOURCES.json',(_json(dict(version=VERSION,models=sorted(sources.values(),key=lambda row:row['id'])))+b'\n',))
                manifest=dict(format=1,version=VERSION,counts=counts,models=sum(counts.values()),styles=list(styles),
                    combinations=sum(counts.values())*len(styles),data_shards=len(KINDS)*len(styles),files=list(summaries),
                    license='PolyForm-Noncommercial-1.0.0',machine_inventory=False,market_exhaustive=False,
                    sensor_binding=False,network_required=False,animation_default=False,page_size=12,
                    artwork='Original schematic reference illustrations; no manufacturer assets or CAD.',
                    hashes='Payload files below; SHA256SUMS.txt additionally covers this manifest.')
                write('manifest.json',(_json(manifest)+b'\n',))
                checksums=''.join(row['sha256']+'  '+row['path']+'\n' for row in sorted(summaries,key=lambda row:row['path']))
                write('SHA256SUMS.txt',(checksums.encode('ascii'),))
    except BaseException:
        if created:target.unlink(missing_ok=True)
        raise
    finally:clear_cache()
    digest=hashlib.sha256()
    with target.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return dict(version=VERSION,file=name,bytes=target.stat().st_size,sha256=digest.hexdigest(),
                counts=counts,models=sum(counts.values()),styles=len(styles),combinations=sum(counts.values())*len(styles),
                data_shards=len(KINDS)*len(styles),files=len(summaries),network_required=False,animation_default=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    print(json.dumps(export(parser.parse_args().output),ensure_ascii=False,sort_keys=True))


if __name__=='__main__':main()
