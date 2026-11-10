"""Real UI/controller and temporary-visibility AST bodies, with fake APIs only."""
import ast
import copy
from pathlib import Path
from types import MethodType,ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
_PARSED={}


def function(path,owner,name):
    if path not in _PARSED:_PARSED[path]=ast.parse((ROOT/path).read_text('utf8'))
    tree=_PARSED[path]
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name==owner)
    value=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name==name))
    value.decorator_list=[]
    return value


def body(path,owner,name,namespace=None):
    fn=function(path,owner,name);ns={}if namespace is None else namespace
    exec(compile(ast.Module([fn],[]),str(ROOT/path),'exec'),ns)
    return ns[name]


class Signal:
    def __init__(self):self.callbacks=[]
    def connect(self,callback):self.callbacks.append(callback)
    def emit(self,value):
        for callback in self.callbacks:callback(value)


class Control:
    def __init__(self,text=''):
        self.text=text;self.checked=False;self.blocked=False
        self.toggled=Signal();self.triggered=self.toggled;self.name=''
    def setObjectName(self,value):self.name=value
    def setCheckable(self,value):self.checkable=value
    def setChecked(self,value):
        self.checked=value
        if not self.blocked:self.toggled.emit(value)
    def blockSignals(self,value):self.blocked=value


def controller():
    fields=next(n.value for n in ast.parse((ROOT/'assembly_config.py').read_text('utf8')).body
                if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PART_FIELDS'for t in n.targets))
    module=ModuleType('assembly_config');module.PART_FIELDS=ast.literal_eval(fields)
    node=SimpleNamespace(_draft={'assembly':{'inspection_cutaway':False,'show_psu':False,'desktop_frame':True}},edits=[],tr=lambda value:value)
    def edit(value,**kwargs):node._draft=value;node.edits.append((copy.deepcopy(value),kwargs));return True
    node.edit=edit
    actual=body('assembly_tools.py','AssemblyTools','changeAssembly',{'copy':copy})
    def change(field,value):
        with patch.dict('sys.modules',{'assembly_config':module}):return actual(node,field,value)
    node.changeAssembly=change
    return node


def select_statements(fn,match,namespace):
    selected=[copy.deepcopy(n)for n in fn.body if match(n)]
    if not selected:raise AssertionError('real UI wiring missing')
    exec(compile(ast.Module(selected,[]),'<actual public UI statements>','exec'),namespace)


def node(hidden=(),required=('cooler:0',)):
    # A vertices property must never be consulted by visibility action discovery.
    class Mesh:
        def __init__(self,identity,component='cooler'):self.part_id=identity;self.component=component
        @property
        def vertices(self):raise AssertionError('no vertex scan')
    state=SimpleNamespace(hidden=set(hidden),calls=[],deny=set(),raising=set(),admitted=True)
    viewport=SimpleNamespace(scene=SimpleNamespace(meshes=(Mesh('cooler:0'),Mesh('cooler:1'),
        Mesh('cpu:0','cpu'),Mesh('gpu:0','gpu'),Mesh('storage:0','storage'))))
    obj=SimpleNamespace(viewport=viewport,selected_component='cpu:0',_motion_hidden_parts=set(),_motion_blocker_key=None,
        _motion_blocker_cache=(),_part_family=lambda:'cpu',_can_interact=lambda:state.admitted)
    def status():return dict(reason='cooler_must_be_hidden_or_moved_first',required_first=required,
        hidden_parts=tuple(state.hidden),available=False,active=False)
    obj._part_assembly_state=status
    from test_assembly_visibility056 import spec
    from assembly_visibility056 import selection_signature
    obj._spec=spec();obj._visibility_signature=selection_signature(obj._spec)
    obj._visibility_user_parts=set(hidden);obj._visibility_families=set()
    obj._visibility_syncing=False;obj._visibility_mask_key=None;obj._visibility_notice=''
    for name in('_motion_blocker_ids','_sync_motion_visibility_actions','_hide_motion_blockers','_restore_motion_blockers',
                '_toggle_part_hidden','_restore_hidden','_visibility_exact_ids','_visibility_key',
                '_sync_saved_visibility','_visibility_targets','_visibility_selection_hidden','_edit_visibility','_set_user_part_hidden'):
        setattr(obj,name,MethodType(body('assembly_window.py','AssemblyWindow',name),obj))
    obj._sync_part_assembly=lambda:obj._sync_motion_visibility_actions(status())
    obj._sync_gpu_assembly=lambda:None
    def hide(part,value):
        state.calls.append((part,value))
        if(part,value)in state.raising:raise RuntimeError('API rejected')
        if(part,value)in state.deny:return False
        if value:state.hidden.add(part)
        else:state.hidden.discard(part)
        # Real set_part_hidden emits the synchronous status signal before return.
        obj._sync_part_assembly();return True
    viewport.set_part_hidden=hide
    def batch(parts,*,temporary_families=()):
        state.hidden=set(parts)|set(temporary_families);obj._sync_part_assembly();return True
    viewport.set_hidden_parts=batch
    def change(signature,parts):
        obj._spec['options']['part_visibility']=dict(signature=signature,hidden_parts=parts)
        obj._sync_saved_visibility(obj._spec);return True
    obj.controller=SimpleNamespace(changeAssemblyVisibility=change)
    return obj,state


class AssemblyInteractionTests(unittest.TestCase):
    def test_actual_inspector_checkbox_reaches_controller_and_sync_does_not_reedit(self):
        ui=controller();window=SimpleNamespace()
        tools=SimpleNamespace(addWidget=lambda value:None)
        fn=function('assembly_window.py','AssemblyWindow','_build_inspector')
        select_statements(fn,lambda n:any(isinstance(x,ast.Attribute)and x.attr=='cutaway'
            and isinstance(x.value,ast.Name)and x.value.id=='self'for x in ast.walk(n)),
            dict(self=window,controller=ui,tools=tools,QCheckBox=Control))
        self.assertEqual(window.cutaway.name,'assemblyInspectionCutawayCheck')
        window.cutaway.setChecked(True)
        self.assertTrue(ui._draft['assembly']['inspection_cutaway']);self.assertEqual(len(ui.edits),1)
        for name in('exploded','show_psu','animate'):setattr(window,name,Control())
        fn=function('assembly_window.py','AssemblyWindow','synchronize')
        loop=next(n for n in fn.body if isinstance(n,ast.For)and 'inspection_cutaway'in ast.unparse(n))
        exec(compile(ast.Module([loop],[]),'<actual synchronize control loop>','exec'),
            dict(self=window,options=dict(exploded=False,inspection_cutaway=False,show_psu=True,fan_animation=False)))
        self.assertFalse(window.cutaway.checked);self.assertTrue(window.show_psu.checked)
        self.assertEqual(len(ui.edits),1)

    def test_actual_desktop_cutaway_action_reaches_same_controller_field(self):
        ui=controller();window=SimpleNamespace(controller=ui,_spec={'options':{'inspection_cutaway':True}})
        actions=[]
        def add(text):value=Control(text);actions.append(value);return value
        menu=SimpleNamespace(addAction=add)
        fn=function('assembly_desktop_widget.py','AssemblyWidgetWindow','_show_menu')
        select_statements(fn,lambda n:any(isinstance(x,ast.Name)and x.id=='cutaway'for x in ast.walk(n)),dict(self=window,menu=menu))
        self.assertEqual(len(actions),1);self.assertTrue(actions[0].checked)
        self.assertEqual(actions[0].name,'assemblyInspectionCutawayAction')
        actions[0].triggered.emit(False)
        self.assertFalse(ui._draft['assembly']['inspection_cutaway']);self.assertEqual(len(ui.edits),1)
        self.assertEqual(ui._draft['assembly']['desktop_frame'],True)
        self.assertFalse(ui._draft['assembly']['show_psu'])

    def test_exact_blockers_hide_and_restore_preserve_user_masks_selection_and_mounts(self):
        obj,state=node(hidden=('gpu:0','cooler:1'),required=('cooler:0','cooler:1','unknown:0'))
        self.assertTrue(obj._hide_motion_blockers())
        self.assertEqual(state.calls,[('cooler:0',True)])
        self.assertEqual(obj.selected_component,'cpu:0');self.assertEqual(obj._motion_hidden_parts,{'cooler:0'})
        state.hidden.add('storage:0')  # A later, independent user mask stays.
        self.assertTrue(obj._restore_motion_blockers())
        self.assertEqual(state.hidden,{'gpu:0','cooler:1','storage:0'});self.assertFalse(obj._motion_hidden_parts)
        self.assertEqual(obj.selected_component,'cpu:0')
        state.calls.clear();obj._part_family=lambda:'memory'
        self.assertFalse(obj._hide_motion_blockers());self.assertEqual(state.calls,[])
        obj._part_family=lambda:'cpu';state.admitted=False
        self.assertFalse(obj._hide_motion_blockers());self.assertEqual(state.calls,[])
        state.admitted=True;obj._part_assembly_state=lambda:dict(reason='motion_path_blocked',required_first=('cooler',),hidden_parts=())
        self.assertFalse(obj._hide_motion_blockers());self.assertEqual(state.calls,[])

    def test_partial_failure_rolls_back_only_new_masks_and_keeps_failed_restore_recoverable(self):
        obj,state=node(hidden=('gpu:0',),required=('cooler:0','cooler:1'))
        state.deny.add(('cooler:1',True))
        self.assertFalse(obj._hide_motion_blockers())
        self.assertEqual(state.calls,[('cooler:0',True),('cooler:1',True),('cooler:0',False)])
        self.assertEqual(state.hidden,{'gpu:0'});self.assertFalse(obj._motion_hidden_parts)
        state.calls.clear();state.raising.add(('cooler:0',False))
        self.assertFalse(obj._hide_motion_blockers())
        self.assertEqual(state.hidden,{'gpu:0','cooler:0'});self.assertEqual(obj._motion_hidden_parts,{'cooler:0'})
        self.assertFalse(obj._restore_motion_blockers());self.assertEqual(obj._motion_hidden_parts,{'cooler:0'})
        state.raising.clear();self.assertTrue(obj._restore_motion_blockers());self.assertEqual(state.hidden,{'gpu:0'})
        state.deny.clear();self.assertTrue(obj._hide_motion_blockers())
        # An explicit user change takes ownership away from the temporary action.
        obj.selected_component='cooler:0';self.assertTrue(obj._toggle_part_hidden(True))
        self.assertNotIn('cooler:0',obj._motion_hidden_parts)
        self.assertTrue(obj._restore_motion_blockers());self.assertIn('cooler:0',state.hidden)


if __name__=='__main__':unittest.main()
