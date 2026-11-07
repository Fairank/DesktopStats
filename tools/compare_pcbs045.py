"""Compare public publisher part-list metadata, never game assets or meshes.

Explicit authoring command only. Reads saved official article HTML; report
counts reference entries, including variant groups, not a complete game SKU DB.
Full names remain private; the public summary contains counts and sources.
"""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
_CATEGORIES={'cases':'case','cpus':'cpu','gpus':'gpu','motherboards':'board','power supplies':'psu','psu':'psu','psus':'psu',
 'storage':'storage','ssd':'storage','ram':'memory','memory':'memory','case fans':'fan','cpu coolers':'cooler','air coolers':'cooler','coolers':'cooler','liquid coolers':'cooler','cooling':'cooling','custom water cooling':'water','cpu blocks':'cpu_block','gpu blocks':'gpu_block','other':'expansion','peripherals':'peripheral'}


class Lines(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.lines=[];self.skip=0
    def flush(self):
        text=' '.join(''.join(self.parts).split()).strip(' ●•\t:');self.parts=[]
        if text:self.lines.append(text)
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if not self.skip and tag in ('br','p','div','h1','h2','h3','h4','li'):self.flush()
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        elif not self.skip and tag in ('p','div','h1','h2','h3','h4','li'):self.flush()
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)


def part_kind(category,name):
    if category not in ('cooling','water'):return category
    low=name.casefold()
    if any(s in low for s in ('gpublock','gpu block','vector2')):return 'gpu_block'
    if any(s in low for s in ('cpublock','cpu block','cpu water block','monoblock','velocity2')):return 'cpu_block'
    if any(s in low for s in ('fitting','compression','connector')):return 'fitting'
    if any(s in low for s in ('radiator','pacific sr')):return 'radiator'
    if any(s in low for s in ('reservoir','pump')):return 'pump_reservoir'
    if any(s in low for s in ('case fan','sickleflow',' p12',' p14',' ct120',' ct140')):return 'fan'
    return 'water_other' if category=='water' else 'cooler'


def parse_article(text):
    parser=Lines();parser.feed(text);parser.flush();active=False;category='';rows=[]
    for line in parser.lines:
        low=line.casefold().strip(': ')
        if low in ('full parts list','parts list'):active=True;category='';continue
        if active and low in ('bug list','bug fixes','quality of life improvements','general fixes'):active=False;category='';continue
        if not active:continue
        if low in _CATEGORIES:category=_CATEGORIES[low];continue
        if category:
            # Only bounded component metadata lines from the part-list block.
            if len(line)>300 or '<' in line or '>' in line:continue
            rows.append(dict(kind=part_kind(category,line),name=line,variant_group='|' in line or 'includes ' in low))
    return rows


def canonical(name):
    name=name.casefold().split(' · ')[0]
    name=re.sub(r'\((?:r|tm)\)|[®™]','',name)
    name=re.sub(r'\b(?:geforce|nvidia)\b','',name)
    return re.sub('[^a-z0-9]','',name)


def compare(catalog,source_rows,private_directory):
    ours={}
    products=catalog['products']+catalog.get('optional_products',[])
    for row in products:
        for title in (row['label'],row['model_id']):ours.setdefault((row['kind'],canonical(title)),set()).add(row['model_id'])
    sources=[];details=[]
    for source in source_rows:
        raw=(private_directory/(source['id']+'.html')).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==source['sha256'],source['id']
        parsed=parse_article(raw.decode('utf8'));assert parsed,source['id']
        count=Counter();matched=0;groups=0
        for row in parsed:
            matches=sorted(ours.get((row['kind'],canonical(row['name'])),set()))
            # A grouped listing is not silently promoted to many verified SKUs.
            hit=len(matches)==1 and not row['variant_group'];matched+=hit;groups+=row['variant_group'];count[row['kind']]+=1
            details.append(dict(row,source_id=source['id'],candidate_ids=matches,name_exact_match=hit))
        sources.append(dict(id=source['id'],url=source['url'],snapshot_sha256=source['sha256'],reference_entries=len(parsed),
            grouped_variant_entries=groups,name_exact_matches=matched,unmatched_or_review=len(parsed)-matched,by_kind=dict(count)))
    return dict(reviewed='2026-11-08',source_policy='Publisher articles only; no game files, screenshots or models copied.',
        whole_game_inventory=False,scope='Published-update part-list entries only; grouped variants are not expanded; exact normalized name matches are not visual/model acceptance.',
        reference_entries=len(details),grouped_variants=sum(r['variant_group'] for r in details),
        name_exact_matches=sum(r['name_exact_match'] for r in details),unmatched_or_review=sum(not r['name_exact_match'] for r in details),
        by_kind=dict(Counter(r['kind'] for r in details)),sources=sources),details


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--references',type=Path,required=True);parser.add_argument('--catalog',type=Path,default=ROOT/'docs/ASSEMBLY_CATALOG.json');parser.add_argument('--output',type=Path,default=ROOT/'docs/PCBS_COMPARISON.json');parser.add_argument('--private-details',type=Path,required=True);args=parser.parse_args()
    sources=json.loads(args.references.read_text(encoding='utf8'));catalog=json.loads(args.catalog.read_text(encoding='utf8'))
    report,details=compare(catalog,sources,args.references.parent)
    assert args.private_details.resolve().is_relative_to((ROOT/'qa-private').resolve())
    args.private_details.write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'},ensure_ascii=False))


if __name__=='__main__':main()
