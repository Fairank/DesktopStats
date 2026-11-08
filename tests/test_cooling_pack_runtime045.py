"""Real data packs drive pickers, shared models and removal without sensors."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import hardware_packs as packs
from cooling_catalog import get_fan,get_cooler
from liquid_cooling_catalog044 import get_radiator


def fixture(kind,identity):
    ref=({'fan':lambda:get_fan('noctua-nf-a12x25-pwm'),
          'cooler':lambda:get_cooler('noctua-nh-u12a'),
          'radiator':lambda:get_radiator('corsair-xr5-240')}[kind])()
    ref.update(id=identity,label='Test '+identity)
    if kind=='cooler':ref['fan_reference_mm']=120
    if kind=='fan':selector=dict(size_mm=ref['size_mm'],depth_mm=ref['depth_mm'],frame=ref['frame'],frameless=ref.get('frameless',False),mount_pitch_mm=ref.get('mount_pitch_mm'),mount_pitch_verified=ref.get('mount_pitch_verified',False))
    elif kind=='cooler':selector=dict(kind=ref['kind'],fan_size_mm=ref['fan_reference_mm'])
    else:selector={key:ref[key] for key in ('fan_size_mm','fan_count','fan_mount_pitch_mm','fan_mount_pitch_verified')}
    return dict(id=identity,label=ref['label'],vendor=ref['brand'],series=ref['series'],aliases=[identity],
                sources=list(ref['sources']),selector=selector,reference=ref)


class CoolingPackRuntimeTests(unittest.TestCase):
    def test_frozen_selfcheck_reads_the_distributed_license_next_to_the_executable(self):
        import sys
        license_data=(Path(__file__).resolve().parents[1]/'LICENSE').read_bytes()
        (self.root/'LICENSE').write_bytes(license_data)
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(self.root/'DesktopStats.exe')):
            raw=packs.make_pack('isolated-frozen-fan','Isolated fan',[fixture('fan','isolated-frozen-fan')],kind='fan')
        manifest,models=packs._archive(raw)
        self.assertEqual(manifest['license_text'].encode('utf8'),license_data)
        self.assertEqual(models[0]['id'],'isolated-frozen-fan')

    def test_pack_change_does_not_import_a_dormant_accessory_gallery(self):
        import builtins,sys
        from types import SimpleNamespace
        from assembly_tools import AssemblyTools
        actual_import=builtins.__import__
        previous=sys.modules.pop('accessory_art',None)
        def guarded(name,*args,**kwargs):
            if name=='accessory_art':raise AssertionError('Dormant gallery imported')
            return actual_import(name,*args,**kwargs)
        signal=SimpleNamespace(emit=lambda:None)
        controller=SimpleNamespace(_assembly_fingerprint='old',_refresh_assembly=lambda:None,
            _accessory_jobs=None,_accessory_art_revision=0,accessoryArtChanged=signal,
            hardwarePacksChanged=signal,assemblyCasesChanged=signal,dataChanged=signal)
        controller._accessory_art_ready=lambda:AssemblyTools._accessory_art_ready(controller)
        try:
            with patch('builtins.__import__',side_effect=guarded):AssemblyTools._hardware_packs_updated(controller)
            self.assertNotIn('accessory_art',sys.modules)
            self.assertIsNone(controller._assembly_fingerprint)
            self.assertIsNone(controller._accessory_jobs)
            self.assertEqual(controller._accessory_art_revision,1)
        finally:
            if previous is not None:sys.modules['accessory_art']=previous

    def test_separate_radiator_drops_inherited_factory_fans_and_keeps_140mm_reference(self):
        from liquid_selection044 import resolve_liquid_choices
        from assembly_cooling import _reference_fan
        from accessory_art import _cooler_fan
        from tools.export_cooling_packs045 import model_row
        cooler=get_cooler('custom-loop-360-reference')
        cooler.update(id='synthetic-loop',label='Explicit synthetic loop',fan_reference_mm=120,
            bundled_fan_reference=get_fan(cooler['fan_model']),
            fan_sizes=[120]*3,fan_models=[cooler['fan_model']]*3,fan_relative_directions=[1]*3)
        self.install('cooler',[model_row('cooler',cooler)])
        selected,_,issues=resolve_liquid_choices(get_cooler('synthetic-loop'),dict(
            radiator_model='alphacool-xt45-v2-280',radiator_fan_layout='single'))
        self.assertFalse(issues)
        self.assertEqual(selected['fan_reference_mm'],140)
        for field in ('bundled_fan_reference','fan_sizes','fan_models','fan_relative_directions'):
            self.assertNotIn(field,selected)
        for producer in (_reference_fan,_cooler_fan):
            self.assertEqual(producer(selected)['size_mm'],140)
            # A mismatched stale factory descriptor is never a last fallback.
            stale=dict(selected,bundled_fan_reference=cooler['bundled_fan_reference'])
            self.assertEqual(producer(stale)['size_mm'],140)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=packs.PackStore(self.root/'installed')
        self.enterContext(patch.object(packs,'_store',self.store))
        for name in ('ctypes.WinDLL','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(name,side_effect=AssertionError('No device/window/background process')))

    def install(self,kind,rows,pack_id=None):
        path=self.root/(kind+'.dspack');path.write_bytes(packs.make_pack(pack_id or kind+'-sample',kind,rows,kind=kind));self.store.install(path)

    def test_three_kinds_are_real_runtime_choices_and_never_enter_cpu_identity_matching(self):
        from assembly_parts import choices
        from accessory_art import art,clear_cache
        from assembly_cooling import add_cooling
        from tests.test_assembly_cooling import ANCHORS
        from top_bar_config import HARDWARE_ICON_STYLES
        before=choices();rows={kind:fixture(kind,'sample-'+kind) for kind in ('fan','cooler','radiator')}
        for kind,row in rows.items():self.install(kind,[row])
        self.assertEqual(self.store.choices(),[])
        self.assertIsNone(self.store.get_cpu('sample-fan'))
        after=choices()
        for key in ('fans','coolers','radiators'):self.assertEqual(len(after[key])-len(before[key]),1)
        selection=dict(cooling=dict(cpu_cooler='custom-loop-360-reference',radiator_model='sample-radiator',
            radiator_fan_model='sample-fan',radiator_fan_layout='push_pull',case_fans=[]))
        meshes,meta=add_cooling((),selection,'eco',ANCHORS)
        self.assertTrue(meshes);self.assertFalse(meta['rejected']);self.assertEqual(meta['radiator_fan_count'],4)
        self.assertEqual({p['model_id'] for p in meta['parts'] if p['kind']=='radiator_fan'},{'sample-fan'})
        self.assertEqual(get_radiator('sample-radiator')['dimensions_mm'],rows['radiator']['reference']['dimensions_mm'])
        for style in HARDWARE_ICON_STYLES:
            for kind in ('fan','cooler'):
                image=art(kind,'sample-'+kind,style);self.assertEqual(image['id'],'sample-'+kind)
                self.assertFalse(image['rotation_direction_verified']);self.assertTrue(image['rotors'])
        clear_cache()

    def test_removal_and_same_id_update_invalidate_svg_and_scene_geometry(self):
        from accessory_art import art,choices,clear_cache
        from assembly_scene_cache import SceneCache
        from assembly_geometry import Scene,Mesh,box
        row=fixture('fan','sample-fan');self.install('fan',[row]);first=art('fan','sample-fan')
        generation=packs.library_generation();cache=SceneCache()
        base=Scene((Mesh('frame',box(1,1,1),(1,1,1,1)),),(200,400,400),{})
        with patch('assembly_scene_cache.build_scene',return_value=base) as build:
            cache.build(dict(model_library_generation=generation))
            row=copy.deepcopy(row);row['reference']['blade_color']='#d65c31';self.install('fan',[row])
            cache.build(dict(model_library_generation=packs.library_generation()))
            self.assertEqual(build.call_count,2)
        self.assertNotEqual(first['svg'],art('fan','sample-fan')['svg'])
        self.assertTrue(any(r['id']=='sample-fan' for r in choices()['fans']))
        self.store.remove('fan-sample')
        self.assertEqual(art('fan','sample-fan'),{})
        self.assertFalse(any(r['id']=='sample-fan' for r in choices()['fans']))
        clear_cache()

    def test_selected_record_limit_is_shared_across_kinds_and_hot_reads_do_not_rescan(self):
        for kind in ('fan','cooler','radiator'):self.install(kind,[fixture(kind,'sample-'+kind+'-'+str(n)) for n in range(4)])
        for kind in ('fan','cooler','radiator'):
            for n in range(4):self.store.get_model(kind,'sample-'+kind+'-'+str(n))
        self.assertEqual(self.store.memory_status()['selected_records'],8)
        self.assertEqual(self.store.memory_status()['background_workers'],0)
        self.assertEqual(self.store.memory_status()['persistent_meshes'],0)
        with patch.object(Path,'iterdir',side_effect=AssertionError('Rescan')),patch.object(Path,'open',side_effect=AssertionError('Disk on cached path')):
            for _ in range(20):
                self.assertEqual(len(self.store.choices('fan')),4)
                row=self.store.get_model('radiator','sample-radiator-3');row['reference']['fan_count']=99
                self.assertEqual(self.store.get_model('radiator','sample-radiator-3')['reference']['fan_count'],2)

    def test_cooler_pack_contains_its_documented_fan_without_requiring_another_pack(self):
        from assembly_cooling import _reference_fan
        from accessory_art import _cooler_fan
        fan=fixture('fan','bundled-only-fan')['reference'];fan.update(foil_profile=dict(sweep_deg=25,leading=.21,trailing=.14,root=.2),foil_profile_accuracy='qualitative_reference')
        cooler=fixture('cooler','bundled-only-cooler');cooler['reference'].update(fan_model=fan['id'],bundled_fan_reference=fan)
        self.install('cooler',[cooler]);actual=get_cooler(cooler['id'])
        self.assertEqual(get_fan(fan['id']),{})
        with patch('assembly_cooling.get_fan',side_effect=AssertionError('No second optional pack read')),patch('cooling_catalog.get_fan',side_effect=AssertionError('No second optional pack read')):
            self.assertEqual(_reference_fan(actual)['foil_profile'],fan['foil_profile'])
            self.assertEqual(_cooler_fan(actual)['foil_profile'],fan['foil_profile'])
            from accessory_art import art,clear_cache
            clear_cache()
            result=art('cooler',cooler['id'],'papercut')
            self.assertTrue(result['rotors'])
            self.assertTrue(set(fan['sources']).issubset(result['sources']))
            clear_cache()

    def test_visible_viewer_passes_same_id_pack_changes_through_the_outer_scene_signature(self):
        from assembly_window import AssemblyWindow
        from types import SimpleNamespace
        scenes=[]
        window=SimpleNamespace(_closing=False,_spec=None,_geometry_key='',_profile_key='',_profile_shapes={},engine=None,
            viewport=SimpleNamespace(set_scene=lambda spec:scenes.append(copy.deepcopy(spec))),
            fit_notice=SimpleNamespace(setText=lambda text:None,setVisible=lambda visible:None),
            controller=SimpleNamespace(tr=lambda text:text),_refresh_part_choices=lambda:None)
        spec=dict(case={},gpu={},cpu={},memory={},board={},cooling=dict(cpu_cooler='same-model-id'))
        with patch('assembly_window.bake_profiles',side_effect=copy.deepcopy) as bake,patch('assembly_parts.fit_messages',return_value=[]):
            # Initial selection, same-ID upgrade and library removal all reach
            # the viewport. Unchanged CPU/GPU/RAM shapes are still profiled once.
            for generation in (1,2,3):
                self.assertTrue(AssemblyWindow._apply_scene(window,dict(spec,model_library_generation=generation)))
            self.assertTrue(AssemblyWindow._apply_scene(window,dict(spec,model_library_generation=3)))
            self.assertEqual([row['model_library_generation'] for row in scenes],[1,2,3])
            self.assertEqual(bake.call_count,1)


if __name__=='__main__':unittest.main()
