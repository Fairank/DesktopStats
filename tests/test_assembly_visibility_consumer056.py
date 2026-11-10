"""Real window/viewport mask consumers; fake GUI/IO, no graphics import."""
import ast
import copy
from pathlib import Path
from types import MethodType,ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

from assembly_visibility056 import selection_signature
from test_assembly_visibility056 import spec,visibility_controller,fingerprint_functions

ROOT=Path(__file__).resolve().parents[1]
_PARSED={}


def method(path,owner,name,scope=None):
    if path not in _PARSED:_PARSED[path]=ast.parse((ROOT/path).read_text('utf8'))
    tree=_PARSED[path]
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name==owner)
    fn=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name==name));fn.decorator_list=[]
    ns={}if scope is None else scope
    exec(compile(ast.Module([fn],[]),str(ROOT/path),'exec'),ns);return ns[name]


def window():
    ui=visibility_controller();value=spec();rows=[SimpleNamespace(part_id=p,component=c)
        for p,c in(('gpu:0','gpu'),('cpu:0','cpu'),('memory:1','memory'),('cooler:0','cooler'),('','case'))]
    scene=SimpleNamespace(meshes=tuple(rows));state=SimpleNamespace(hidden=set(),batches=[],single=[],changes=0)
    view=SimpleNamespace(scene=scene,_reference_scene_mode=False)
    node=SimpleNamespace(viewport=view,controller=ui,_spec=copy.deepcopy(value),selected_component='gpu:0',
        _visibility_signature='',_visibility_user_parts=set(),_visibility_families=set(),_visibility_syncing=False,
        _visibility_mask_key=None,_visibility_notice='',_motion_hidden_parts=set(),_motion_blocker_key=None,
        _motion_blocker_cache=(),_can_interact=lambda:True)
    labels={'all':'all','gpu':'gpu','cpu':'cpu','memory':'memory','case':'case','cooler':'cooler'}
    names=('_visibility_exact_ids','_visibility_key','_sync_saved_visibility','_visibility_targets',
        '_visibility_selection_hidden','_edit_visibility','_set_user_part_hidden','_toggle_part_hidden',
        '_motion_blocker_ids','_sync_motion_visibility_actions','_hide_motion_blockers','_restore_motion_blockers')
    for name in names:setattr(node,name,MethodType(method('assembly_window.py','AssemblyWindow',name,
        dict(COMPONENT_LABELS=labels)),node))
    node._part_family=lambda:'cpu'if node.selected_component.startswith('cpu')else'gpu'
    node._part_assembly_state=lambda:dict(hidden_parts=tuple(state.hidden),required_first=('cooler:0',),
        reason='cooler_must_be_hidden_or_moved_first',available=False)
    node._sync_part_assembly=lambda:node._sync_motion_visibility_actions(node._part_assembly_state())
    node._sync_gpu_assembly=lambda:None
    def batch(parts,*,temporary_families=()):
        following=set(parts)|set(temporary_families)
        state.batches.append((set(parts),set(temporary_families)))
        if following!=state.hidden:state.changes+=1
        state.hidden=following;node._sync_part_assembly();return True
    view.set_hidden_parts=batch
    def single(part,enabled):
        state.single.append((part,enabled))
        if enabled:state.hidden.add(part)
        else:state.hidden.discard(part)
        node._sync_part_assembly();return True
    view.set_part_hidden=single
    def reenter():
        # Simulate the real synchronous draft->spec->window notification.
        fresh=copy.deepcopy(ui._assembly_spec);fresh['options']=copy.deepcopy(ui._draft['assembly'])
        ui._assembly_spec=fresh;node._spec=copy.deepcopy(fresh)
        ui._assembly_fingerprint=fingerprint_functions()(ui._data,ui._draft,ui._assembly_firmware,ui._assembly_modules)
        node._sync_saved_visibility(node._spec)
    ui.draftChanged.connect(reenter)
    return node,state,ui


class AssemblyVisibilityConsumerTests(unittest.TestCase):
    def setUp(self):
        package=ModuleType('hardware_packs');package.library_generation=lambda:0
        self.enterContext(patch.dict('sys.modules',hardware_packs=package))

    def test_load_is_one_batch_keeps_stale_record_and_never_hides_replacement_gpu_ordinal(self):
        node,state,ui=window();value=copy.deepcopy(node._spec)
        value['options']['part_visibility']=dict(signature=selection_signature(value),hidden_parts=['gpu:0','memory:1'])
        record=copy.deepcopy(value['options']['part_visibility'])
        node._sync_saved_visibility(value)
        self.assertEqual(state.hidden,{'gpu:0','memory:1'});self.assertEqual(len(state.batches),1)
        node._sync_saved_visibility(value);self.assertEqual(len(state.batches),1)
        styled=copy.deepcopy(value);styled['visual_style']='notebook_line';styled['lighting_preview']='mint'
        styled['options'].update(appearance_style='notebook_line',lighting_preview='mint')
        node._sync_saved_visibility(styled);self.assertEqual(len(state.batches),1)
        changed=copy.deepcopy(styled);changed['options']['gpu_model']='gpu-other'
        changed['gpu']['appearance']['id']='gpu-other'
        node._motion_hidden_parts={'cooler:0'};node._visibility_families={'case'}
        node._sync_saved_visibility(changed)
        self.assertEqual(state.hidden,set());self.assertEqual(node._motion_hidden_parts,set())
        self.assertEqual(changed['options']['part_visibility'],record);self.assertEqual(ui.edits,[])
        node.viewport.scene=SimpleNamespace(meshes=(SimpleNamespace(part_id='gpu:0',component='gpu'),))
        node._visibility_mask_key=None;node._sync_saved_visibility(value)
        self.assertEqual(state.hidden,set());self.assertEqual(value['options']['part_visibility'],record)

    def test_explicit_user_mask_uses_real_draft_action_reentry_and_temporary_masks_never_persist(self):
        node,state,ui=window();node._sync_saved_visibility(node._spec)
        self.assertTrue(node._toggle_part_hidden(True))
        self.assertEqual(ui._draft['assembly']['part_visibility']['hidden_parts'],['gpu:0'])
        self.assertEqual(len(state.batches),2)  # initial no-op plus one explicit action; reentry applies nothing.
        self.assertEqual(ui.saved_attempts,[]);self.assertEqual(ui._saved['assembly']['part_visibility']['hidden_parts'],[])
        # Even a backend that changes its local mask and then rejects must not
        # leak the window's proposed tracking or reach the real draft action.
        previous=copy.deepcopy((node._visibility_user_parts,node._motion_hidden_parts,node._visibility_families))
        real_batch=node.viewport.set_hidden_parts;count=len(ui.edits)
        def rejecting(parts,*,temporary_families=()):
            real_batch(parts,temporary_families=temporary_families)
            return 'memory:1'not in parts
        node.viewport.set_hidden_parts=rejecting
        self.assertFalse(node._set_user_part_hidden('memory:1',True))
        self.assertEqual(state.hidden,{'gpu:0'});self.assertEqual(len(ui.edits),count)
        self.assertEqual((node._visibility_user_parts,node._motion_hidden_parts,node._visibility_families),previous)
        node.viewport.set_hidden_parts=real_batch
        old=copy.deepcopy(ui._draft);ui._assembly_fingerprint='stale'
        self.assertFalse(node._set_user_part_hidden('memory:1',True))
        self.assertEqual(ui._draft,old);self.assertEqual(state.hidden,{'gpu:0'})
        self.assertEqual((node._visibility_user_parts,node._motion_hidden_parts,node._visibility_families),previous)
        ui._assembly_fingerprint=fingerprint_functions()(ui._data,ui._draft,ui._assembly_firmware,ui._assembly_modules)
        node.selected_component='cpu:0';count=len(ui.edits)
        self.assertTrue(node._hide_motion_blockers())
        self.assertEqual(len(ui.edits),count);self.assertEqual(ui._draft['assembly']['part_visibility']['hidden_parts'],['gpu:0'])
        self.assertEqual(node._motion_hidden_parts,{'cooler:0'})
        self.assertTrue(node._set_user_part_hidden('cooler:0',True))
        self.assertEqual(node._motion_hidden_parts,set())
        self.assertTrue(node._restore_motion_blockers());self.assertIn('cooler:0',state.hidden)
        count=len(ui.edits);self.assertTrue(node._set_user_part_hidden('case',True))
        self.assertEqual(len(ui.edits),count);self.assertIn('case',state.hidden)
        self.assertNotIn('case',ui._draft['assembly']['part_visibility']['hidden_parts'])
        self.assertIn('不',node._visibility_notice)
        node._motion_hidden_parts={'memory:'+str(i)for i in range(64)}
        count=len(ui.edits);self.assertFalse(node._edit_visibility({'gpu:0'},()))
        self.assertEqual(len(ui.edits),count)

    def test_actual_viewport_batch_rejects_unknown_reference_and_preserves_scene_pn_pending(self):
        a=SimpleNamespace(part_id='gpu:0',component='gpu',vertices=(1.,2.,3.))
        b=SimpleNamespace(part_id='',component='case',vertices=(4.,5.,6.))
        owner=SimpleNamespace(meshes=(a,b));calls=[]
        renderer=SimpleNamespace(_selected=lambda m,k:m.part_id==k or m.component==k)
        viewport=SimpleNamespace(_reset_part_motion=lambda obj:calls.append('reset'),
            _refresh_part_plan=lambda obj:calls.append('plan'))
        ns=dict(AssemblyViewport=viewport,AssemblyRenderer=renderer,ASSEMBLY_COMPONENTS=('all','gpu','case'),
            hidden_connections=lambda scene,parts:(calls.append('connections')or()))
        action=method('assembly_viewer.py','AssemblyViewport','set_hidden_parts',ns)
        node=SimpleNamespace(_reference_scene_mode=False,_scene=owner,_hidden_parts=frozenset(),_pending=False,
            _hidden_connection_names=frozenset(),_opened_retention_names=frozenset(),_released_mounts=frozenset(),
            _renderer=SimpleNamespace(_pick_state=object(),upload_count=1),_update_animation_state=lambda:None,
            partAssemblyChanged=SimpleNamespace(emit=lambda:None),update=lambda:None)
        pn=a.vertices
        self.assertTrue(action(node,['gpu:0']));self.assertEqual(calls,['connections','reset','plan'])
        self.assertIs(node._scene,owner);self.assertIs(a.vertices,pn);self.assertFalse(node._pending)
        self.assertEqual(node._renderer.upload_count,1);self.assertIsNone(node._renderer._pick_state)
        self.assertTrue(action(node,['gpu:0']));self.assertEqual(len(calls),3)
        for bad in(['gpu'],['gpu:missing'],['gpu:0','gpu:0']):
            self.assertFalse(action(node,bad));self.assertEqual(node._hidden_parts,frozenset({'gpu:0'}))
        self.assertTrue(action(node,['gpu:0'],temporary_families=['case']))
        self.assertEqual(node._hidden_parts,frozenset({'gpu:0','case'}))
        node._reference_scene_mode=True
        self.assertFalse(action(node,[]));self.assertIs(node._scene,owner)
        self.assertFalse(node._pending);self.assertEqual(node._renderer.upload_count,1)


if __name__=='__main__':unittest.main()
