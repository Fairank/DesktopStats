"""Exact-part masks, actual lazy cache and real draft/save AST; fake IO only."""
import ast
import copy
import json
from pathlib import Path
from types import MethodType, ModuleType
import unittest
from unittest.mock import patch

from assembly_config import DEFAULT_ASSEMBLY, validate_assembly, visual_style
from assembly_visibility056 import selection_signature, selected_hidden, validate_visibility
from test_assembly_save055 import controller, method
from metrics import metric_info

ROOT = Path(__file__).resolve().parents[1]


def spec():
    options = copy.deepcopy(DEFAULT_ASSEMBLY)
    options.update(case_model='case-a', cpu_model='cpu-a', gpu_model='gpu-a',
        board_model='board-a', memory_models=['ram-a', 'ram-b'],
        case_fans=[dict(model='fan-a', mount='front', count=2, direction='intake')])
    return dict(options=options, case=dict(id='case-a'),
        cpu=dict(appearance=dict(id='cpu-a'),label='CPU A',telemetry_bound=False),
        gpu=dict(appearance=dict(id='gpu-a'),label='GPU A',present=True,target='0',telemetry_bound=False),
        memory=dict(count=2,modules=[dict(appearance=dict(id='ram-a'),label='RAM A'),
                                    dict(appearance=dict(id='ram-b'),label='RAM B')]),
        board=dict(model_id='board-a',label='Board A',manufacturer='Maker',form_factor='atx'),
        model_library_generation=0,visual_style='miniature')


def fingerprint_functions():
    tree = ast.parse((ROOT/'assembly_spec.py').read_text('utf8'))
    nodes = [copy.deepcopy(n) for n in tree.body if isinstance(n,ast.FunctionDef)
             and n.name in ('gpu_preferences','component_fingerprint')]
    # Real external globals for both extracted functions; gpu_preferences is
    # defined by its real AST below. Only library_generation is a pure fixture.
    namespace = dict(metric_info=metric_info, visual_style=visual_style)
    exec(compile(ast.Module(nodes,[]),str(ROOT/'assembly_spec.py'),'exec'),namespace)
    return namespace['component_fingerprint']


def visibility_controller():
    ui = controller()
    ui._assembly_spec = spec()
    ui._saved['assembly'] = copy.deepcopy(ui._assembly_spec['options'])
    ui._draft = copy.deepcopy(ui._saved)
    ui._data = dict(cpu_name='CPU host',gpus={'0':dict(gpu_name='GPU host')})
    ui._assembly_firmware = dict(state='cached')
    ui._assembly_modules = []
    ui.edits = []
    fingerprint = fingerprint_functions()
    ui._assembly_fingerprint = fingerprint(ui._data,ui._draft,ui._assembly_firmware,ui._assembly_modules)
    ui.changeAssemblyVisibility = MethodType(method('assembly_tools.py','AssemblyTools',
        'changeAssemblyVisibility',dict(copy=copy,component_fingerprint=fingerprint)),ui)
    def edit(value,*,merge_key):
        result=copy.deepcopy(value);result['assembly']=validate_assembly(value['assembly'])
        ui._draft=result;ui.edits.append((copy.deepcopy(result),merge_key));ui.draftChanged.emit();return True
    ui.edit=edit
    def no_probe(*args,**kwargs):raise AssertionError('Visibility cannot refresh or probe identity')
    ui._ensure_assembly_identity=no_probe
    ui.assembly_specification=no_probe
    return ui


class AssemblyVisibilityTests(unittest.TestCase):
    def setUp(self):
        package=ModuleType('hardware_packs');package.library_generation=lambda:0
        self.enterContext(patch.dict('sys.modules',hardware_packs=package))

    def test_config_roundtrip_is_detached_exact_and_has_no_pose_channel(self):
        self.assertEqual(validate_assembly({})['part_visibility'],dict(signature='',hidden_parts=[]))
        signature=selection_signature(spec());self.assertEqual(len(signature),64)
        raw=dict(signature=signature,hidden_parts=['memory:1','gpu:0'])
        normalized=validate_assembly(dict(part_visibility=raw))
        self.assertEqual(normalized['part_visibility']['hidden_parts'],['gpu:0','memory:1'])
        normalized['part_visibility']['hidden_parts'].append('cpu:0')
        self.assertEqual(raw['hidden_parts'],['memory:1','gpu:0'])
        for invalid in ({'signature':'','hidden_parts':['gpu:0']},
                {'signature':signature,'hidden_parts':['gpu']},
                {'signature':signature,'hidden_parts':['all']},
                {'signature':signature,'hidden_parts':['gpu:0','gpu:0']},
                {'signature':signature,'hidden_parts':['reference:source']},
                {'signature':signature,'hidden_parts':['memory:'+str(i) for i in range(65)]},
                {'signature':signature,'hidden_parts':[],'xyz':[1,2,3]}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):validate_assembly(dict(part_visibility=invalid))
        self.assertNotIn('part_positions',validate_assembly(dict(part_positions={'gpu:0':[1,2,3]})))

    def test_physical_selection_signature_changes_with_models_mount_counts_and_unknown_identity(self):
        original=spec();baseline=selection_signature(original)
        mutations=(lambda s:s['options'].update(gpu_model='gpu-b'),
            lambda s:s['options']['case_fans'][0].update(count=3),
            lambda s:s['options']['case_fans'][0].update(mount='rear'),
            lambda s:s['gpu'].update(target='1'),
            lambda s:s['memory']['modules'].reverse(),
            lambda s:s['board'].update(model_id='board-b'),
            lambda s:s.update(model_library_generation=1))
        for mutate in mutations:
            changed=copy.deepcopy(original);mutate(changed)
            self.assertNotEqual(selection_signature(changed),baseline)
        automatic=copy.deepcopy(original);automatic['gpu'].update(telemetry_bound=True,detected_label='unknown model A')
        changed=copy.deepcopy(automatic);changed['gpu']['detected_label']='unknown model B'
        self.assertNotEqual(selection_signature(automatic),selection_signature(changed))
        # build_spec can override a generic matched part's physical drawing
        # using the cached DIMM/SO-DIMM form, without changing its ID or label.
        dimm=copy.deepcopy(original)
        dimm['memory']['modules'][0]=dict(appearance=dict(id='generic-memory',style='dimm'),label='same unknown part')
        sodimm=copy.deepcopy(dimm);sodimm['memory']['modules'][0]['appearance']['style']='sodimm'
        self.assertNotEqual(selection_signature(dimm),selection_signature(sodimm))
        # A manual reference does not bind its identity to the host card.
        a=copy.deepcopy(original);b=copy.deepcopy(original)
        a['gpu']['detected_label']='host A';b['gpu']['detected_label']='host B'
        self.assertEqual(selection_signature(a),selection_signature(b))
        self.assertEqual(selection_signature(None),'')

    def test_all_six_art_styles_and_temporary_view_states_preserve_physical_signature(self):
        original=spec();baseline=selection_signature(original)
        for style in ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
            changed=copy.deepcopy(original);changed['visual_style']=style
            changed['options'].update(appearance_style=style,part_styles={'gpu:0':'papercut'},
                lighting_preview='mint',desktop_frame=False,window_mode='desktop',detail_level='close',
                fan_animation=True,fan_motion='demo',inspection_cutaway=True,show_psu=True,
                exploded=True,part_visibility=dict(signature=baseline,hidden_parts=['gpu:0']))
            changed.update(hidden_parts=['cpu:0'],released_mounts=['gpu:0'],part_offsets={'gpu:0':[2,3,4]})
            changed['gpu'].update(temperature=85,rpm=1200)
            for row in (changed['cpu'],changed['gpu'],*changed['memory']['modules']):
                row['appearance']['icon_set']=style
            self.assertEqual(selection_signature(changed),baseline)

    def test_saved_mask_requires_original_selection_and_all_live_exact_ids(self):
        current=spec();signature=selection_signature(current)
        current['options']['part_visibility']=dict(signature=signature,hidden_parts=['memory:1','gpu:0'])
        self.assertEqual(selected_hidden(current['options'],current,('gpu:0','memory:1')),('gpu:0','memory:1'))
        # Never partially reinterpret a missing instance or broaden to GPU.
        self.assertEqual(selected_hidden(current['options'],current,('gpu','gpu:0')),())
        replacement=copy.deepcopy(current);replacement['options']['gpu_model']='gpu-b'
        self.assertEqual(selected_hidden(current['options'],replacement,('gpu:0','memory:1')),())
        self.assertEqual(current['options']['part_visibility']['hidden_parts'],['memory:1','gpu:0'])

    def test_actual_scene_cache_reuses_same_physical_owner_for_visibility_only_edit(self):
        tree=ast.parse((ROOT/'assembly_scene_cache.py').read_text('utf8'))
        nodes=[copy.deepcopy(n) for n in tree.body if isinstance(n,(ast.Assign,ast.ClassDef))]
        calls=[];owner=object()
        def build(value):calls.append(copy.deepcopy(value));return owner
        namespace=dict(json=json,build_scene=build,resolve_style=lambda value:value)
        exec(compile(ast.Module(nodes,[]),str(ROOT/'assembly_scene_cache.py'),'exec'),namespace)
        cache=namespace['SceneCache']();current=spec()
        self.assertIs(cache.build(current),owner);key=cache.key
        changed=copy.deepcopy(current)
        changed['options']['part_visibility']=dict(signature=selection_signature(current),hidden_parts=['gpu:0'])
        self.assertIs(cache.build(changed),owner)
        self.assertEqual(len(calls),1);self.assertEqual(cache.key,key)
        self.assertNotIn('options',calls[0]);self.assertNotIn('part_visibility',calls[0])

    def test_real_action_requires_current_cached_identity_and_changes_only_assembly_draft(self):
        ui=visibility_controller();signature=selection_signature(ui._assembly_spec)
        ui._draft['theme']='light';ui._draft['widgets']['cpu']['title']='pending CPU'
        before=copy.deepcopy(ui._draft)
        self.assertTrue(ui.changeAssemblyVisibility(signature,['gpu:0','memory:1']))
        self.assertEqual(ui._draft['assembly']['part_visibility'],dict(signature=signature,hidden_parts=['gpu:0','memory:1']))
        self.assertEqual({k:v for k,v in ui._draft.items()if k!='assembly'},{k:v for k,v in before.items()if k!='assembly'})
        self.assertEqual(ui._saved['assembly']['part_visibility'],dict(signature='',hidden_parts=[]))
        self.assertEqual(ui.edits[-1][1],('assembly','part_visibility'));self.assertEqual(ui.saved_attempts,[])
        for stale in ('options','data','signature','not_initialized'):
            rejected=visibility_controller();expected=selection_signature(rejected._assembly_spec)
            if stale=='options':rejected._draft['assembly']['case_model']='case-b'
            elif stale=='data':rejected._data['gpus']['0']['gpu_name']='other card'
            elif stale=='signature':expected='0'*64
            else:rejected._assembly_modules=None
            unchanged=copy.deepcopy(rejected._draft)
            self.assertFalse(rejected.changeAssemblyVisibility(expected,['gpu:0']))
            self.assertEqual(rejected._draft,unchanged);self.assertEqual(rejected.edits,[])

    def test_new_visibility_record_uses_real_assembly_only_save_and_failure_preserves_draft(self):
        for fail in (False,True):
            ui=visibility_controller();signature=selection_signature(ui._assembly_spec)
            ui._draft['theme']='light';ui._draft['autostart']=True;ui._draft['refresh']=.25
            ui._draft['widgets']['cpu']['title']='pending CPU';ui._draft['top_bar']['height']=48
            self.assertTrue(ui.changeAssemblyVisibility(signature,['gpu:0']))
            saved,draft=copy.deepcopy(ui._saved),copy.deepcopy(ui._draft);ui.save_error=fail
            if fail:
                with self.assertLogs(level='ERROR'):self.assertFalse(ui.saveAssembly())
                self.assertEqual(ui._saved,saved);self.assertEqual(ui._draft,draft)
            else:
                self.assertTrue(ui.saveAssembly())
                self.assertEqual(ui._saved['assembly'],draft['assembly'])
                self.assertEqual({k:v for k,v in ui._saved.items()if k!='assembly'},{k:v for k,v in saved.items()if k!='assembly'})
                self.assertEqual(ui._draft,draft)
            self.assertEqual(ui.autostart_calls,[])


if __name__ == '__main__':unittest.main()
