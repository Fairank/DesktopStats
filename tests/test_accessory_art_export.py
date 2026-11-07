"""Real, isolated and reproducible exports of the four SVG artwork collections."""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


ROOT=Path(__file__).resolve().parents[1]
ID=re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z',re.ASCII)
COUNTS={'case':64,'cooler':42,'psu':6,'fan':38}
SVG='{http://www.w3.org/2000/svg}'


def _shared_styles():
    tree=ast.parse((ROOT/'top_bar_config.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HARDWARE_ICON_STYLES' for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise AssertionError('Shared hardware style IDs were not found')


class AccessoryArtExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='desktopstats-svg-export-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output=Path(cls.temporary.name)
        cls.first=cls.output/'first'
        cls.second=cls.output/'second'
        cls.styles=_shared_styles()
        # Run real exports in a fresh interpreter. A denied dependency fails the
        # export immediately; the parent only reads the produced ZIPs afterward.
        script='''import builtins,importlib.abc,json,pathlib,sys
denied={'PySide6','PyQt6','PyQt5','assembly_geometry','assembly_cooling','assembly_viewer',
        'ctypes','psutil','wmi','winreg','win32api','win32gui','win32com','pythoncom',
        'sensors','activity_sensors','gpu_fan_sensor','chassis_identity','memory_identity',
        'native_controller','hardware_monitor','sensor_diagnostics','subprocess',
        'socket','ssl','urllib','http','requests','aiohttp','webbrowser'}
baseline_denied=set(sys.modules)&denied
original_import=builtins.__import__
def guarded_import(name,globals=None,locals=None,fromlist=(),level=0):
    if name.split('.')[0] in denied:
        raise AssertionError('Export attempted forbidden dependency: '+name)
    return original_import(name,globals,locals,fromlist,level)
builtins.__import__=guarded_import
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in denied:
            raise AssertionError('Export attempted forbidden dependency: '+fullname)
sys.meta_path.insert(0,Guard())
from tools.export_accessory_art import export
import accessory_art
from product_version import VERSION
first,second,other=[pathlib.Path(value) for value in sys.argv[1:4]]
reports=[];cache_sizes=[]
for output in (first,second):
    reports.append(export(output))
    cache_sizes.append(accessory_art.cache_info()['entries'])
before={p.name:p.read_bytes() for p in first.iterdir()}
try:
    export(first)
except FileExistsError:
    refused_collection=True
else:
    raise AssertionError('An existing collection was overwritten')
assert before=={p.name:p.read_bytes() for p in first.iterdir()},'Existing export bytes changed'
cache_sizes.append(accessory_art.cache_info()['entries'])
other.mkdir()
index=other/('DesktopStats-'+VERSION+'-SVG-index.json')
index.write_bytes(b'preexisting-index-must-survive')
try:
    export(other)
except FileExistsError:
    refused_index=True
else:
    raise AssertionError('An existing export index was overwritten')
assert index.read_bytes()==b'preexisting-index-must-survive'
cache_sizes.append(accessory_art.cache_info()['entries'])
loaded_denied=sorted((set(sys.modules)&denied)-baseline_denied)
assert not loaded_denied,loaded_denied
print(json.dumps(dict(reports=reports,cache_sizes=cache_sizes,
    refused_collection=refused_collection,refused_index=refused_index,
    denied_modules_loaded=loaded_denied),sort_keys=True))
'''
        result=subprocess.run([sys.executable,'-c',script,str(cls.first),str(cls.second),str(cls.output/'existing-index')],
                              cwd=ROOT,capture_output=True,text=True,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=60)
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        cls.export_run=json.loads(result.stdout)
        cls.manifests={}
        for collection in cls.export_run['reports'][0]['collections']:
            with zipfile.ZipFile(cls.first/collection['file']) as archive:
                cls.manifests[collection['kind']]=json.loads(archive.read('manifest.json'))

    def test_four_collections_are_byte_identical_across_two_real_exports(self):
        names1={p.name for p in self.first.iterdir()}
        names2={p.name for p in self.second.iterdir()}
        self.assertEqual(names1,names2)
        self.assertEqual(len([name for name in names1 if name.endswith('.zip')]),4)
        self.assertEqual(len([name for name in names1 if name.endswith('-SVG-index.json')]),1)
        self.assertEqual(self.export_run['reports'][0],self.export_run['reports'][1])
        for name in names1:
            self.assertEqual((self.first/name).read_bytes(),(self.second/name).read_bytes(),name)
        report=self.export_run['reports'][0]
        index=self.first/('DesktopStats-'+report['version']+'-SVG-index.json')
        self.assertEqual(json.loads(index.read_text(encoding='utf-8')),report)
        for collection in report['collections']:
            raw=(self.first/collection['file']).read_bytes()
            self.assertEqual(collection['bytes'],len(raw))
            self.assertEqual(collection['sha256'],hashlib.sha256(raw).hexdigest())

    def test_150_records_are_149_products_and_one_reference_combination(self):
        report=self.export_run['reports'][0]
        self.assertEqual(report['models'],150)
        self.assertEqual(report['svg_files'],1950)
        self.assertEqual(report['styles'],13)
        self.assertFalse(report['market_exhaustive'])
        self.assertEqual({c['kind']:c['models'] for c in report['collections']},COUNTS)
        all_models=[]
        for kind,manifest in self.manifests.items():
            self.assertEqual(manifest['kind'],kind)
            self.assertEqual(manifest['styles'],self.styles)
            self.assertEqual(len(manifest['models']),COUNTS[kind])
            self.assertFalse(manifest['machine_inventory'])
            self.assertFalse(manifest['market_exhaustive'])
            self.assertFalse(manifest['sensor_binding'])
            for model in manifest['models']:
                self.assertTrue(ID.fullmatch(model['id']))
                self.assertTrue(model['label'])
                self.assertTrue(model['brand'])
                self.assertTrue(model['reference_details'])
                self.assertTrue(model['sources'])
                self.assertTrue(all(source.startswith('https://') for source in model['sources']))
                self.assertEqual(len(model['files']),13)
                all_models.append(model)
        products=[m for m in all_models if m['record_type']=='product']
        combinations=[m for m in all_models if m['record_type']=='reference_combination']
        self.assertEqual(len(products),149)
        self.assertEqual([m['id'] for m in combinations],['custom-loop-360-reference'])
        self.assertEqual(len({m['id'] for m in all_models}),150)

    def test_each_svg_matches_its_manifest_hash_size_and_safe_relative_path(self):
        svg_count=0
        for collection in self.export_run['reports'][0]['collections']:
            with zipfile.ZipFile(self.first/collection['file']) as archive:
                self.assertIsNone(archive.testzip())
                entries=archive.infolist()
                names=[info.filename for info in entries]
                self.assertEqual(len(names),len(set(names)))
                for info in entries:
                    path=PurePosixPath(info.filename)
                    self.assertFalse(path.is_absolute())
                    self.assertNotIn('\\',info.filename)
                    self.assertNotIn(':',info.filename)
                    self.assertNotIn('..',path.parts)
                    self.assertNotIn('.',path.parts)
                    self.assertNotIn('',path.parts)
                    self.assertFalse(info.is_dir())
                    self.assertEqual(stat.S_IFMT(info.external_attr>>16),stat.S_IFREG)
                manifest=self.manifests[collection['kind']]
                declared=set()
                for model in manifest['models']:
                    expected={model['id']+'/'+style+'.svg' for style in self.styles}
                    self.assertEqual({entry['path'] for entry in model['files']},expected)
                    for entry in model['files']:
                        self.assertNotIn(entry['path'],declared)
                        declared.add(entry['path'])
                        raw=archive.read(entry['path'])
                        self.assertEqual(entry['bytes'],len(raw))
                        self.assertEqual(entry['sha256'],hashlib.sha256(raw).hexdigest())
                        self.assertRegex(entry['sha256'],r'^[0-9a-f]{64}$')
                        svg_count+=1
                self.assertEqual(declared,{name for name in names if name.endswith('.svg')})
                self.assertEqual(len(declared),collection['svg_files'])
        self.assertEqual(svg_count,1950)

    def test_all_exported_xml_is_static_and_has_no_external_assets_or_scripts(self):
        forbidden={'script','foreignObject','image','iframe','object','embed','text','font','font-face','style'}
        for collection in self.export_run['reports'][0]['collections']:
            with zipfile.ZipFile(self.first/collection['file']) as archive:
                for name in archive.namelist():
                    if not name.endswith('.svg'):
                        continue
                    raw=archive.read(name)
                    self.assertNotIn(b'<!DOCTYPE',raw.upper())
                    self.assertNotIn(b'<!ENTITY',raw.upper())
                    xml=ET.fromstring(raw)
                    self.assertEqual(xml.tag,SVG+'svg')
                    self.assertEqual(xml.get('viewBox'),'0 0 120 100')
                    for element in xml.iter():
                        self.assertNotIn(element.tag.removeprefix(SVG),forbidden,name)
                        for attribute,value in element.attrib.items():
                            local=attribute.rsplit('}',1)[-1].lower()
                            self.assertFalse(local.startswith('on'),name)
                            self.assertNotIn(local,('href','src'),name)
                            self.assertNotIn('javascript:',value.lower(),name)
                            self.assertFalse('url(' in value.lower() and 'url(#' not in value.lower(),name)

    def test_every_collection_retains_complete_license_notice_and_noncommercial_scope(self):
        license_bytes=(ROOT/'LICENSE').read_bytes()
        notice_bytes=(ROOT/'NOTICE').read_bytes()
        required_notice=notice_bytes.splitlines()[0]
        self.assertTrue(required_notice.startswith(b'Required Notice: Copyright'))
        for collection in self.export_run['reports'][0]['collections']:
            with zipfile.ZipFile(self.first/collection['file']) as archive:
                names=set(archive.namelist())
                license_names=names&{'LICENSE','LICENSE.md','LICENSE.txt'}
                notice_names=names&{'NOTICE','NOTICE.md','NOTICE.txt'}
                self.assertTrue(license_names,'Full license must accompany every SVG collection')
                self.assertTrue(notice_names,'The provided copyright Required Notice must accompany every collection')
                self.assertTrue(any(archive.read(name)==license_bytes for name in license_names))
                self.assertTrue(any(archive.read(name)==notice_bytes for name in notice_names))
                self.assertTrue(any(required_notice in archive.read(name) for name in notice_names))
                readme=archive.read('README.txt').decode('utf-8').lower()
                self.assertIn('noncommercial',readme)
                self.assertIn('original',readme)
                self.assertIn('trademarks',readme)
                manifest=self.manifests[collection['kind']]
                self.assertEqual(manifest['license'],'PolyForm-Noncommercial-1.0.0')
                self.assertIn('original',manifest['artwork'].lower())

    def test_export_cleanup_refuses_overwrites_and_keeps_device_network_code_unloaded(self):
        self.assertEqual(self.export_run['cache_sizes'],[0,0,0,0])
        self.assertTrue(self.export_run['refused_collection'])
        self.assertTrue(self.export_run['refused_index'])
        self.assertEqual(self.export_run['denied_modules_loaded'],[])


if __name__=='__main__':
    unittest.main()
