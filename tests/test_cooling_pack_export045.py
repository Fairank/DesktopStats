"""Real optional exports, immutable bytes, source-archive boundaries and cold runtime."""
import ast
import builtins
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import hardware_packs as packs
from tools import export_cooling_packs045 as cooling_export
from tools import export_source as source_export


PROJECT=Path(__file__).resolve().parents[1]
SCRATCH=PROJECT/'qa-private'/'cooling-export045'


class CoolingPackExport045Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guards=ExitStack();cls.addClassCleanup(cls.guards.close)
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            cls.guards.enter_context(patch(name,side_effect=AssertionError('Export tests do not launch UI, network or hardware work')))
        SCRATCH.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='fixture-',dir=SCRATCH)
        cls.root=Path(cls.temporary.name)
        if not cls.root.resolve().is_relative_to(SCRATCH.resolve()):
            raise AssertionError('Temporary export fixture escaped its workspace scratch')
        cls.addClassCleanup(cls.cleanup_scratch)
        # Export the current authoring source, never the pregenerated public
        # model-packs tree; that tree can legitimately be awaiting regeneration.
        cls.library=cooling_export.pack_models()
        cls.first=cls.root/'first';cls.index=cooling_export.export(cls.first)
        cls.raw={row['id']:(cls.first/Path(row['file']).name).read_bytes() for row in cls.index['packs']}

    @classmethod
    def cleanup_scratch(cls):
        if not cls.root.resolve().is_relative_to(SCRATCH.resolve()):
            raise AssertionError('Refusing cleanup outside the named export-test directory')
        cls.temporary.cleanup()

    def source_fixture(self,name,payload):
        root=self.root/self._testMethodName
        root.mkdir(parents=True,exist_ok=True)
        (root/'product_version.py').write_text('VERSION = "0.45.0-preview.1"\n',encoding='utf8')
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
        return root,root/'out/source.zip',['product_version.py',name]

    def source_run(self,name,payload):
        root,output,inventory=self.source_fixture(name,payload)
        # The fixture supplies an already reviewed inventory. Reading, path
        # confinement, archive validation, privacy scans, capture and output
        # serialization all remain the real exporter; collector build inputs
        # are exercised separately by test_source_export.
        with patch.object(source_export,'collect_paths',return_value=inventory):
            report=source_export.export_source(output,root=root)
        return root,output,report

    def one_fan(self):
        return deepcopy(self.library['fan'][0])

    def valid_small_pack(self,row=None):
        return packs.make_pack('export-fixture','Export fixture',[row or self.one_fan()],kind='fan')

    def test_all_32_current_source_packs_are_byte_deterministic_and_exactly_indexed(self):
        second=self.root/'second';report=cooling_export.export(second)
        self.assertEqual(len(report['packs']),32)
        self.assertEqual(report['by_kind'],{'fan':40,'cooler':23,'radiator':104})
        self.assertEqual(report['unique_products'],167)
        self.assertFalse(report['installed_by_default']);self.assertFalse(report['market_exhaustive'])
        self.assertEqual(len({r['id'] for r in report['packs']}),32)
        self.assertEqual({r['group'] for r in report['packs']},{'collection','brand'})
        expected={kind:{r['id'] for r in rows} for kind,rows in self.library.items()}
        for row in report['packs']:
            raw=(second/Path(row['file']).name).read_bytes()
            self.assertEqual(raw,self.raw[row['id']])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            self.assertEqual(len(raw),row['bytes']);manifest,models=packs._archive(raw)
            self.assertEqual([m['id'] for m in models],row['model_ids'])
            self.assertEqual(manifest['kind'],row['kind']);self.assertEqual(len(models),row['products'])
            self.assertEqual({m['id'] for m in models},expected[row['kind']] if row['group']=='collection' else {m['id'] for m in self.library[row['kind']] if m['vendor']==models[0]['vendor']})
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                self.assertEqual(archive.namelist(),['manifest.json','models.json'])
                self.assertTrue(all(r.date_time==(2026,1,1,0,0,0) for r in archive.infolist()))
            self.assertFalse(row['code']);self.assertFalse(row['source_photos'])
            self.assertEqual(row['persistent_meshes'],0);self.assertEqual(row['background_workers'],0)
        for kind,models in self.library.items():
            all_brand_ids=[identity for r in report['packs'] if r['kind']==kind and r['group']=='brand' for identity in r['model_ids']]
            self.assertEqual(set(all_brand_ids),expected[kind]);self.assertEqual(len(all_brand_ids),len(models))

    def test_reexport_identical_bytes_does_not_rewrite_existing_files(self):
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.first.glob('*.dspack')}
        self.assertEqual(cooling_export.export(self.first),self.index)
        after={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.first.glob('*.dspack')}
        self.assertEqual(after,before)

    def test_different_valid_existing_archive_is_never_overwritten(self):
        target=self.root/'already-published';target.mkdir()
        leaf='DesktopStats-fan-collection-045-1.0.0.dspack';path=target/leaf
        prior=packs.make_pack('fan-collection-045','Prior reviewed inventory',[self.one_fan()],kind='fan')
        path.write_bytes(prior);stamp=path.stat().st_mtime_ns
        with self.assertRaisesRegex(FileExistsError,'immutable'):
            cooling_export.export(target)
        self.assertEqual(path.read_bytes(),prior);self.assertEqual(path.stat().st_mtime_ns,stamp)
        self.assertEqual({p.name for p in target.iterdir()},{leaf})

    def test_valid_data_pack_inside_reviewed_folder_round_trips_into_source_zip(self):
        raw=self.valid_small_pack();name='model-packs/v045/fixture.dspack'
        root,output,report=self.source_run(name,raw)
        self.assertTrue(report['ok'])
        with zipfile.ZipFile(output) as archive:
            prefix='DesktopStats-0.45.0-preview.1-source/'
            self.assertEqual(archive.read(prefix+name),raw)
            manifest=json.loads(archive.read(prefix+'SOURCE_MANIFEST.json'))
            item=next(r for r in manifest['files'] if r['path']==name)
            self.assertEqual(item['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(item['bytes'],len(raw))
            self.assertEqual(set(archive.namelist()),{prefix+name,prefix+'product_version.py',prefix+'SOURCE_MANIFEST.json'})

    def test_pack_outside_model_folder_and_private_or_traversal_paths_fail_before_output(self):
        raw=self.valid_small_pack()
        for i,name in enumerate(('fixture.dspack','assets/fixture.dspack','docs/fixture.dspack','qa-private/fixture.dspack','model-packs/v045/preferences.json')):
            with self.subTest(path=name):
                root,output,inventory=self.source_fixture(name,raw)
                with patch.object(source_export,'collect_paths',return_value=inventory),self.assertRaises(source_export.ExportError):
                    source_export.export_source(output,root=root)
                self.assertFalse(output.exists())
        root=self.root/self._testMethodName
        for name in ('model-packs/../fixture.dspack','model-packs//fixture.dspack','model-packs/./fixture.dspack','model-packs\\fixture.dspack','C:/fixture.dspack','/fixture.dspack'):
            with self.subTest(path=name),self.assertRaises(source_export.ExportError):
                source_export._read(root,name)

    def test_malformed_archives_and_embedded_private_json_never_enter_source_zip(self):
        good=self.valid_small_pack()
        with zipfile.ZipFile(io.BytesIO(good)) as archive:
            manifest=archive.read('manifest.json');models=archive.read('models.json')
        bad=[]
        for extra in ('../outside.json','telemetry.json','code.py'):
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w') as archive:
                archive.writestr('manifest.json',manifest);archive.writestr('models.json',models);archive.writestr(extra,b'{}')
            bad.append(buffer.getvalue())
        bad.extend((b'not an archive',good[:-32],b'{"preferences":{}}'))
        for i,payload in enumerate(bad):
            with self.subTest(case=i):
                root,output,inventory=self.source_fixture('model-packs/v045/bad-'+str(i)+'.dspack',payload)
                with patch.object(source_export,'collect_paths',return_value=inventory),self.assertRaises(source_export.ExportError):
                    source_export.export_source(output,root=root)
                self.assertFalse(output.exists())
        private_values=('C:/'+'Users/'+'PrivatePackOwner/'+'personal/model.json','sk-'+'proj-'+'q'*28,'-----BEGIN '+'PRIVATE KEY-----')
        for i,text in enumerate(private_values):
            row=self.one_fan();row['reference']['notes']=text;payload=self.valid_small_pack(row)
            # Runtime schema validity alone must not bypass source privacy.
            self.assertTrue(packs._archive(payload)[1])
            root,output,inventory=self.source_fixture('model-packs/v045/private-'+str(i)+'.dspack',payload)
            with patch.object(source_export,'collect_paths',return_value=inventory),self.assertRaises(source_export.ExportError) as caught:
                source_export.export_source(output,root=root)
            self.assertNotIn(text,str(caught.exception));self.assertFalse(output.exists())

    def test_cold_runtime_and_real_picker_calls_never_import_authoring_catalogs(self):
        forbidden={'cooling_expansion045','liquid_radiator_expansion045'};actual_import=builtins.__import__;seen=[]
        def guarded(name,*args,**kwargs):
            if name.split('.')[0] in forbidden:raise AssertionError('Runtime attempted to import optional authoring catalog: '+name)
            seen.append(name);return actual_import(name,*args,**kwargs)
        store=packs.PackStore(self.root/'empty-installed')
        with patch.object(builtins,'__import__',side_effect=guarded),patch.object(packs,'_store',store):
            runtime=runpy.run_path(str(PROJECT/'cooling_pack_runtime045.py'))
            fans=runpy.run_path(str(PROJECT/'cooling_catalog.py'))
            radiators=runpy.run_path(str(PROJECT/'liquid_cooling_catalog044.py'))
            schema=runpy.run_path(str(PROJECT/'cooling_pack_schema045.py'))
            parts=runpy.run_path(str(PROJECT/'assembly_parts.py'))
            self.assertEqual(runtime['radiator_choices'](),[])
            self.assertTrue(fans['choices_fans']());self.assertTrue(fans['choices_coolers']())
            self.assertEqual(len(radiators['records']()),24)
            self.assertIsNone(radiators['get_radiator']('uninstalled-radiator'))
            self.assertTrue(parts['choices']()['fans']);self.assertEqual(schema['KINDS'],('fan','cooler','radiator'))
        self.assertFalse(forbidden.intersection(name.split('.')[0] for name in seen))
        self.assertEqual(store.memory_status()['selected_records'],0)
        self.assertFalse(store.directory.exists())


if __name__=='__main__':unittest.main()
