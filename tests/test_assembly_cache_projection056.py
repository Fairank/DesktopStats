"""Real window/cache methods with fake baking and one-triangle factory only.

No Qt, window, sensor, QML engine or full assembly factory is constructed.
The original payload and resulting Scene/PN identities are tested separately
from the key, so a cache optimization cannot silently delete product metadata.
"""
import ast
import copy
import json
from pathlib import Path
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import patch

from assembly_cache_projection056 import cache_key_input, current_reference_metadata
from assembly_geometry import Mesh, Scene
from assembly_scene_cache import SceneCache
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]


def reference_spec():
    return dict(case=dict(id='reference-case',mounts=dict(front=[120,140])),
        cpu=dict(label='Reference CPU',telemetry_bound=False,detected_label='Host CPU before',
            appearance=dict(id='reference-cpu',style='lga1700'),width=45.,height=37.5),
        gpu=dict(label='Reference GPU',telemetry_bound=False,detected_label='Host GPU before',
            appearance=dict(id='reference-gpu',style='triple_fan',fans=3),length=350.,thickness=70.,
            source='reference',target='0'),
        memory=dict(count=2,modules=[dict(label='Reference RAM',appearance=dict(id='reference-ram',style='dimm'))]),
        board=dict(model_id='reference-board',form_factor='atx'),
        cooling=dict(cpu_cooler='reference-cooler',case_fans=[dict(model='fan-a',mount='front',count=2)]),
        auxiliary=dict(psu='reference-psu',wiring=False),visual_style='miniature',
        part_styles={},lighting_preview='artwork',detail_level='balanced',model_library_generation=0,
        options=dict(part_visibility=dict(signature='',hidden_parts=[])))


def apply_scene_method():
    tree=ast.parse((ROOT/'assembly_window.py').read_text('utf8'))
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef)and node.name=='AssemblyWindow')
    node=copy.deepcopy(next(node for node in cls.body if isinstance(node,ast.FunctionDef)and node.name=='_apply_scene'))
    node.decorator_list=[]
    namespace=dict(copy=copy,json=json,HARDWARE_ICON_STYLES=HARDWARE_ICON_STYLES)
    exec(compile(ast.Module([node],[]),str(ROOT/'assembly_window.py'),'exec'),namespace)
    return namespace


class Pipeline:
    """Use both actual consumers; replace only costly bake and factory I/O."""
    def __init__(self,test):
        self.payloads=[];self.bakes=[];self.syncs=[];self.scenes=[];self.set_calls=0
        self.cache=SceneCache()
        namespace=apply_scene_method()
        self.window=SimpleNamespace(_closing=False,_spec=None,_profile_key=None,_profile_shapes=None,
            _geometry_key=None,_visibility_mask_key=None,engine=object(),
            controller=SimpleNamespace(tr=lambda text:text),
            fit_notice=SimpleNamespace(setText=lambda text:None,setVisible=lambda value:None),
            _refresh_part_choices=lambda:None,_sync_saved_visibility=lambda spec:self.syncs.append(copy.deepcopy(spec)))
        self.window.viewport=SimpleNamespace(set_scene=self.set_scene,scene=None)
        self.window.apply=MethodType(namespace['_apply_scene'],self.window)
        namespace['bake_profiles']=self.bake
        test.enterContext(patch('assembly_scene_cache.build_scene',side_effect=self.factory))

    def bake(self,spec,engine):
        self.bakes.append(copy.deepcopy(spec));result=copy.deepcopy(spec)
        for family in ('cpu','gpu','memory'):
            result[family].setdefault('shapes',[dict(kind='fixture',points=[1.,2.,3.])])
        return result

    def factory(self,payload):
        self.payloads.append(copy.deepcopy(payload))
        # Fresh immutable PN for each factory invocation; no geometry helper or
        # actual factory call can hide a repeat build behind a reused fixture.
        pn=tuple([0.,0.,0.,0.,0.,1.,1.,0.,0.,0.,0.,1.,0.,1.,0.,0.,0.,1.])
        result=Scene((Mesh('fixture-gpu',pn,(.2,.3,.4,1.),component='gpu',part_id='gpu:0'),),
            (200.,400.,400.),dict(visual_style='miniature',cooling={},auxiliary={}))
        self.scenes.append(result);return result

    def set_scene(self,baked):
        self.set_calls+=1;self.window.viewport.scene=self.cache.build(baked)


class AssemblyCacheProjection056Controls(unittest.TestCase):
    def test_projection_is_exact_false_top_level_cpu_gpu_only_and_nonmutating(self):
        original=reference_spec();original['board']['detected_label']='Board host'
        original['memory']['detected_label']='RAM host';original['cpu']['appearance']['detected_label']='physical detail'
        before=copy.deepcopy(original);projected=cache_key_input(original)
        expected=copy.deepcopy(original)
        for family in ('cpu','gpu'):expected[family].pop('detected_label')
        self.assertEqual(projected,expected);self.assertEqual(original,before)
        self.assertIsNot(projected['cpu'],original['cpu'])
        self.assertIs(projected['cpu']['appearance'],original['cpu']['appearance'])
        self.assertIs(projected['board'],original['board'])
        self.assertEqual(cache_key_input(original,('cpu','gpu','memory')),dict((key,expected[key])for key in ('cpu','gpu','memory')))
        for flag in (True,None,0,'false','missing'):
            for family in ('cpu','gpu'):
                spec=reference_spec()
                if flag=='missing':spec[family].pop('telemetry_bound')
                else:spec[family]['telemetry_bound']=flag
                self.assertEqual(cache_key_input(spec)[family],spec[family])
        profiles={family:copy.deepcopy(original[family])for family in ('cpu','gpu','memory')}
        profiles['gpu']['shapes']=[dict(points=[1.,2.,3.])];saved=copy.deepcopy(profiles)
        current=copy.deepcopy(original);current['gpu']['detected_label']='Host GPU after';current['cpu'].pop('detected_label')
        refreshed=current_reference_metadata(profiles,current)
        self.assertEqual(refreshed['gpu']['detected_label'],'Host GPU after')
        self.assertNotIn('detected_label',refreshed['cpu'])
        self.assertEqual(profiles,saved);self.assertIs(refreshed['gpu']['shapes'],profiles['gpu']['shapes'])

    def test_manual_host_metadata_refresh_keeps_scene_pn_and_profile_without_rebuild(self):
        pipe=Pipeline(self);spec=reference_spec();original=copy.deepcopy(spec)
        self.assertIs(pipe.window.apply(spec),True)
        first=pipe.window.viewport.scene;pn=first.meshes[0].vertices;profiles=pipe.window._profile_shapes
        for index in range(3):
            latest=copy.deepcopy(spec)
            for family in ('cpu','gpu'):latest[family]['detected_label']=f'Host {family} {index}'
            self.assertIs(pipe.window.apply(latest),True)
            self.assertEqual(pipe.window._spec,latest);self.assertIsNot(pipe.window._spec,latest)
            self.assertEqual(pipe.syncs[-1],latest)
            self.assertIs(pipe.window.viewport.scene,first);self.assertIs(first.meshes[0].vertices,pn)
            self.assertIs(pipe.window._profile_shapes,profiles)
        self.assertEqual((len(pipe.bakes),pipe.set_calls,len(pipe.payloads)),(1,1,1))
        self.assertEqual(spec,original)
        # SceneCache independently receives raw latest metadata too; its own
        # projection must preserve Scene/PN even outside the Window fast path.
        raw=copy.deepcopy(pipe.payloads[0]);raw['gpu']['detected_label']='direct cache refresh'
        self.assertIs(pipe.cache.build(raw),first);self.assertEqual(len(pipe.payloads),1)

    def test_cached_profiles_forward_current_metadata_to_real_geometry_change(self):
        pipe=Pipeline(self);spec=reference_spec();self.assertTrue(pipe.window.apply(spec))
        saved_profiles=copy.deepcopy(pipe.window._profile_shapes)
        latest=copy.deepcopy(spec);latest['gpu']['detected_label']='Latest host GPU';latest['cpu'].pop('detected_label')
        self.assertTrue(pipe.window.apply(latest));self.assertEqual(len(pipe.bakes),1)
        changed=copy.deepcopy(latest);changed['case']['mounts']['front'].append(180)
        self.assertTrue(pipe.window.apply(changed))
        self.assertEqual((len(pipe.bakes),pipe.set_calls,len(pipe.payloads)),(1,2,2))
        actual=pipe.payloads[-1]
        self.assertEqual(actual['gpu']['detected_label'],'Latest host GPU')
        self.assertNotIn('detected_label',actual['cpu'])
        self.assertEqual(actual['case'],changed['case'])
        for family in ('cpu','gpu','memory'):
            expected=copy.deepcopy(changed[family]);expected['shapes']=saved_profiles[family]['shapes']
            self.assertEqual(actual[family],expected)
        self.assertEqual(pipe.window._profile_shapes,saved_profiles)
        self.assertEqual(pipe.window._spec,changed)
        self.assertIsNot(pipe.scenes[0],pipe.scenes[1])
        self.assertIsNot(pipe.scenes[0].meshes[0].vertices,pipe.scenes[1].meshes[0].vertices)

    def test_automatic_unknown_and_non_boolean_binding_still_invalidate(self):
        for flag in (True,None,0,'missing'):
            for family in ('cpu','gpu'):
                with self.subTest(flag=flag,family=family):
                    pipe=Pipeline(self);spec=reference_spec()
                    if flag=='missing':spec[family].pop('telemetry_bound')
                    else:spec[family]['telemetry_bound']=flag
                    self.assertTrue(pipe.window.apply(spec));first=pipe.window.viewport.scene
                    latest=copy.deepcopy(spec);latest[family]['detected_label']='Changed detected model'
                    self.assertTrue(pipe.window.apply(latest))
                    self.assertEqual((len(pipe.bakes),pipe.set_calls,len(pipe.payloads)),(2,2,2))
                    self.assertIsNot(pipe.window.viewport.scene,first)
                    self.assertEqual(pipe.payloads[-1][family]['detected_label'],'Changed detected model')

    def test_every_other_physical_field_keeps_window_and_cache_invalidation(self):
        changes=(
            ('gpu_model',lambda s:s['gpu']['appearance'].update(id='another-model'),True),
            ('cpu_package',lambda s:s['cpu']['appearance'].update(style='am5'),True),
            ('gpu_length',lambda s:s['gpu'].update(length=351.),True),
            ('gpu_thickness',lambda s:s['gpu'].update(thickness=71.),True),
            ('cpu_width',lambda s:s['cpu'].update(width=46.),True),
            ('source',lambda s:s['gpu'].update(source='another-reference'),True),
            ('fan_shape',lambda s:s['gpu']['appearance'].update(fans=2),True),
            ('target',lambda s:s['gpu'].update(target='1'),True),
            ('shape_data',lambda s:s['cpu'].update(shapes=[dict(kind='other')]),True),
            ('board',lambda s:s['board'].update(model_id='another-board'),False),
            ('memory',lambda s:s['memory']['modules'][0]['appearance'].update(style='sodimm'),True),
            ('mount',lambda s:s['cooling']['case_fans'][0].update(mount='top'),False),
            ('count',lambda s:s['cooling']['case_fans'][0].update(count=3),False),
            ('psu',lambda s:s['auxiliary'].update(psu='another-psu'),False),
            ('detail',lambda s:s.update(detail_level='close'),False),
            ('library',lambda s:s.update(model_library_generation=1),False))
        for label,change,rebake in changes:
            with self.subTest(field=label):
                pipe=Pipeline(self);spec=reference_spec();self.assertTrue(pipe.window.apply(spec))
                first=pipe.window.viewport.scene;modified=copy.deepcopy(spec);change(modified)
                self.assertTrue(pipe.window.apply(modified))
                self.assertEqual((len(pipe.bakes),pipe.set_calls,len(pipe.payloads)),(2 if rebake else 1,2,2))
                self.assertIsNot(pipe.window.viewport.scene,first);self.assertEqual(pipe.window._spec,modified)


if __name__=='__main__':unittest.main()
