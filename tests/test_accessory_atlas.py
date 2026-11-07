"""Real deterministic offline atlas exports, using only the standard library."""
import ast
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path,PurePosixPath
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
COUNTS={'case':96,'cooler':66,'psu':21,'fan':70}
PREFIX='window.DesktopStatsAtlas.receive('


class Page(HTMLParser):
    def __init__(self,source):
        super().__init__();self.tags=[];self.feed(source)
    def handle_starttag(self,tag,attrs):self.tags.append((tag,dict(attrs)))


class AccessoryAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='desktopstats-model-atlas-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output=Path(cls.temporary.name)
        script='''import builtins,importlib.abc,json,pathlib,sys
denied={'PySide6','PyQt6','PyQt5','assembly_geometry','assembly_cooling','assembly_auxiliary','assembly_viewer',
 'top_bar_config','ctypes','psutil','wmi','winreg','win32api','win32gui','win32com','pythoncom',
 'sensors','activity_sensors','gpu_fan_sensor','chassis_identity','memory_identity','native_controller',
 'hardware_monitor','sensor_diagnostics','subprocess','socket','ssl','urllib','http','requests','aiohttp','webbrowser'}
already=set(sys.modules)&denied
original=builtins.__import__
def guarded(name,globals=None,locals=None,fromlist=(),level=0):
 if name.split('.')[0] in denied:raise AssertionError('Forbidden atlas dependency: '+name)
 return original(name,globals,locals,fromlist,level)
builtins.__import__=guarded
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in denied:raise AssertionError('Forbidden atlas dependency: '+fullname)
sys.meta_path.insert(0,Guard())
from tools.export_accessory_atlas import export
import accessory_art
base=pathlib.Path(sys.argv[1]);reports=[export(base/'one'),export(base/'two')]
target=base/'one'/reports[0]['file'];saved=target.read_bytes()
try:export(base/'one')
except FileExistsError:refused=True
else:raise AssertionError('The existing atlas was overwritten')
assert saved==target.read_bytes()
loaded=sorted((set(sys.modules)&denied)-already)
assert not loaded,loaded
print(json.dumps(dict(reports=reports,refused=refused,denied_modules_loaded=loaded,cache=accessory_art.cache_info())))
'''
        result=subprocess.run([sys.executable,'-c',script,str(cls.output)],cwd=ROOT,capture_output=True,text=True,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0),timeout=60)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.export_run=json.loads(result.stdout)
        cls.report=cls.export_run['reports'][0]
        cls.archive=zipfile.ZipFile(cls.output/'one'/cls.report['file'])
        cls.addClassCleanup(cls.archive.close)
        cls.manifest=json.loads(cls.archive.read('manifest.json'))
        cls.html=cls.archive.read('index.html').decode('utf8')
        match=re.search(r'<script type="application/json" id="catalog">(.*?)</script>',cls.html,re.S)
        if not match:raise AssertionError('Inline model metadata is missing')
        cls.catalog=json.loads(match.group(1))

    def payloads(self):
        for path in sorted(self.archive.namelist()):
            if path.endswith('.js'):
                source=self.archive.read(path).decode('utf8')
                self.assertTrue(source.startswith(PREFIX) and source.endswith(');\n'))
                yield path,json.loads(source[len(PREFIX):-3])

    def test_byte_identical_archives_and_refusal_to_overwrite(self):
        self.assertEqual(self.export_run['reports'][0],self.export_run['reports'][1])
        name=self.report['file']
        self.assertEqual((self.output/'one'/name).read_bytes(),(self.output/'two'/name).read_bytes())
        raw=(self.output/'one'/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.report['sha256'])
        self.assertEqual(len(raw),self.report['bytes'])
        self.assertRegex(name,r'^DesktopStats-[0-9A-Za-z._-]+-Model-Atlas\.zip$')
        self.assertTrue(self.export_run['refused'])
        self.assertEqual(self.export_run['denied_modules_loaded'],[])
        self.assertEqual(self.export_run['cache']['entries'],0)

    def test_all_models_have_light_metadata_and_exactly_52_independent_classic_shards(self):
        self.assertEqual(self.manifest['counts'],COUNTS)
        self.assertEqual(self.manifest['models'],253)
        self.assertEqual(self.manifest['combinations'],3289)
        self.assertEqual(self.manifest['data_shards'],52)
        self.assertEqual(len(self.manifest['styles']),13)
        seen=set()
        for kind,rows in self.catalog['models'].items():
            self.assertEqual(len(rows),COUNTS[kind])
            for row in rows:
                self.assertEqual(set(row),{'id','label','brand'})
                self.assertTrue(row['label'] and row['brand'])
                self.assertRegex(row['id'],r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
        for path,payload in self.payloads():
            kind,style=payload['kind'],payload['style']
            self.assertEqual(path,'data/'+kind+'/'+style+'.js')
            self.assertEqual(len(payload['models']),COUNTS[kind])
            self.assertEqual([row['id'] for row in payload['models']],[row['id'] for row in self.catalog['models'][kind]])
            self.assertNotIn((kind,style),seen);seen.add((kind,style))
        self.assertEqual(seen,{(kind,style) for kind in COUNTS for style in self.manifest['styles']})

    def test_style_names_match_the_native_app_without_importing_its_settings_graph(self):
        tree=ast.parse((ROOT/'assembly_config.py').read_text(encoding='utf8'))
        labels=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
                    and any(isinstance(target,ast.Name) and target.id=='STYLE_LABELS' for target in node.targets))
        self.assertEqual({row['id']:row['label'] for row in self.catalog['styles']},labels)

    def test_failed_generation_removes_only_its_partial_archive_and_releases_artwork(self):
        import accessory_art
        from tools.export_accessory_atlas import export
        destination=self.output/'failed-generation'
        with patch.object(accessory_art,'art',side_effect=ValueError('Expected test failure')):
            with self.assertRaisesRegex(ValueError,'Expected test failure'):export(destination)
        self.assertEqual(list(destination.iterdir()),[])
        self.assertEqual(accessory_art.cache_info()['entries'],0)

    def test_shards_use_the_actual_artwork_and_keep_every_original_layer(self):
        import accessory_art
        try:
            for _path,payload in self.payloads():
                for record in payload['models']:
                    actual=accessory_art.art(payload['kind'],record['id'],payload['style'])
                    for key in ('svg','body_svg','foreground_svg','rotors','art_details','reference_details',
                                'motion_source','rotation_direction_verified','original_face'):
                        self.assertEqual(record[key],actual[key],(record['id'],payload['style'],key))
                    if payload['kind']=='case' or record['art_details'].get('fan_count')==0:
                        self.assertEqual(record['rotors'],[])
                    if payload['style']=='miniature':self.assertEqual(record['original_face'],'none')
                    self.assertFalse(record['rotation_direction_verified'])
                    self.assertEqual(record['motion_source'],'reference_demo')
        finally:accessory_art.clear_cache()

    def test_complete_unmodified_license_notices_and_public_source_statuses_are_included(self):
        for name in ('LICENSE','NOTICE','LICENSING.md','THIRD_PARTY_NOTICES.md'):
            self.assertEqual(self.archive.read(name),(ROOT/name).read_bytes())
        sources=json.loads(self.archive.read('SOURCES.json'))['models']
        self.assertEqual(len(sources),253)
        self.assertEqual(sum(row['record_type']=='product' for row in sources),252)
        self.assertEqual([row['id'] for row in sources if row['record_type']=='reference_combination'],['custom-loop-360-reference'])
        self.assertTrue(all(row['sources'] and row['reference_details'] for row in sources))
        self.assertTrue(all(url.startswith('https://') for row in sources for url in row['sources']))
        for key in ('machine_inventory','market_exhaustive','sensor_binding','network_required','animation_default'):
            self.assertFalse(self.manifest[key])
        self.assertIn('OLED 读数未知',self.html)
        self.assertIn('不得商用盈利',self.html)

    def test_every_payload_and_manifest_has_a_matching_file_hash(self):
        names=set(self.archive.namelist())
        self.assertEqual(len(names),self.report['files'])
        records={row['path']:row for row in self.manifest['files']}
        self.assertEqual(set(records),names-{'manifest.json','SHA256SUMS.txt'})
        for path,row in records.items():
            raw=self.archive.read(path)
            self.assertEqual(len(raw),row['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        checks={line.split('  ',1)[1]:line.split('  ',1)[0] for line in self.archive.read('SHA256SUMS.txt').decode('ascii').splitlines()}
        self.assertEqual(set(checks),names-{'SHA256SUMS.txt'})
        for path,digest in checks.items():self.assertEqual(hashlib.sha256(self.archive.read(path)).hexdigest(),digest)

    def test_file_protocol_page_has_no_external_resources_or_initial_svg_dump(self):
        page=Page(self.html)
        policy=next(attrs['content'] for tag,attrs in page.tags if tag=='meta' and attrs.get('http-equiv')=='Content-Security-Policy')
        self.assertIn("connect-src 'none'",policy)
        self.assertIn("script-src 'unsafe-inline' file:",policy)
        self.assertFalse(any('src' in attrs for tag,attrs in page.tags if tag in ('script','img','iframe')))
        self.assertFalse(any(tag in ('iframe','object','embed','svg') for tag,_attrs in page.tags))
        for tag,attrs in page.tags:
            if tag=='a':self.assertFalse(re.match(r'(?:https?:)?//',attrs.get('href','')))
        inputs={attrs.get('id'):attrs for tag,attrs in page.tags if tag in ('input','select')}
        self.assertTrue({'search','brand','style','demo'}<=set(inputs))
        self.assertNotIn('checked',inputs['demo'])
        self.assertEqual(self.manifest['page_size'],12)
        self.assertNotIn('body_svg',json.dumps(self.catalog))

    def test_archive_contains_no_vendor_assets_executables_private_paths_or_symlinks(self):
        allowed={'index.html','LICENSE','NOTICE','LICENSING.md','THIRD_PARTY_NOTICES.md',
                 'README.txt','SOURCES.json','manifest.json','SHA256SUMS.txt'}
        for info in self.archive.infolist():
            path=PurePosixPath(info.filename)
            self.assertFalse(path.is_absolute())
            self.assertNotIn('..',path.parts)
            self.assertNotIn('\\',info.filename)
            self.assertTrue(info.filename in allowed or (len(path.parts)==3 and path.parts[0]=='data' and path.suffix=='.js'))
            self.assertEqual(info.date_time,(2026,1,1,0,0,0))
            self.assertEqual((info.external_attr>>16)&0o170000,0o100000)
            source=self.archive.read(info).decode('utf8')
            self.assertNotIn('qa-private',source)
            self.assertNotRegex(source,r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]')


if __name__=='__main__':unittest.main()
