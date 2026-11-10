"""Assembly-only persistence through current real commit/rebase AST; fake IO."""
import ast
import copy
import logging
from pathlib import Path
from types import MethodType, SimpleNamespace
import unittest

from assembly_config import DEFAULT_ASSEMBLY, validate_assembly
from configuration_scopes import SCOPE_FIELDS, merge_scope, scope_dirty

ROOT=Path(__file__).resolve().parents[1]


def method(path,owner,name,namespace):
    tree=ast.parse((ROOT/path).read_text('utf8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name==owner)
    node=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name==name))
    node.decorator_list=[]
    exec(compile(ast.Module([node],[]),str(ROOT/path),'exec'),namespace)
    return namespace[name]


class Signal:
    def __init__(self):self.calls=[];self.callbacks=[]
    def connect(self,callback):self.callbacks.append(callback)
    def emit(self,*args):
        self.calls.append(args)
        for callback in self.callbacks:callback(*args)


def state():
    return dict(version=6,assembly=copy.deepcopy(DEFAULT_ASSEMBLY),
        widgets={'cpu':dict(title='saved CPU',size=240,form='card',enabled=True,grouped=False)},
        widget_order=['cpu'],skin='glass',opacity=95,glass_transparency=50.,glass_curvature=12.,
        mode='individual',layout='vertical',size=240,group_columns=2,visible=True,locked=False,
        magnet_enabled=True,magnet_gap=8,magnet_bounce=False,reflow_on_resize=True,
        top_bar=dict(enabled=False,height=32),language='zh',theme='dark',autostart=False,
        refresh=1,history_enabled=False,cpu_temperature_prompt_on_start=False)


def controller(secondary=False):
    ui=SimpleNamespace(_saved=state(),_replacement_backup=None,_undo_drafts=[],_redo_drafts=[],
        _last_edit_key=('assembly','case_model'),_last_edit_time=10.,saved_attempts=[],statuses=[],applied=[],
        autostart_calls=[],capacity_calls=[],save_error=False)
    ui._draft=copy.deepcopy(ui._saved)
    for signal in ('savedChanged','draftChanged','dataChanged','languageChanged','assemblySaveChanged',
                   'assemblyCasesChanged','hardwarePacksChanged','draftHistoryChanged','applyRequested'):
        setattr(ui,signal,Signal())
    ui.set_status=lambda text,error=False:ui.statuses.append((text,error))
    ui._applied_status=ui.applied.append
    ui._refresh_assembly=lambda:None
    def validate(value):
        value=copy.deepcopy(value);value['assembly']=validate_assembly(value['assembly']);return value
    def save(value):
        ui.saved_attempts.append(copy.deepcopy(value))
        if ui.save_error:raise OSError('fake read-only settings file')
    def set_autostart(value):
        ui.autostart_calls.append(value);raise AssertionError('Assembly save must never change autostart')
    def layout_error(value,rearrange):
        ui.capacity_calls.append((copy.deepcopy(value),rearrange));return ''
    ui.layout_error=layout_error
    ns=dict(copy=copy,validate=validate,merge_scope=merge_scope,secondary_active=lambda:secondary,
        save=save,set_autostart=set_autostart,logging=logging)
    for name in ('_commit','_rebase_scope_history','undoDraft','redoDraft'):
        setattr(ui,name,MethodType(method('native_controller.py','Controller',name,ns),ui))
    ui.saveAssembly=MethodType(method('assembly_tools.py','AssemblyTools','saveAssembly',{}),ui)
    def edit(value,*,record_history=False):
        ui._draft=validate(value);ui.draftChanged.emit();return True
    ui.edit=edit
    return ui


def dirty_all(ui):
    ui._draft['assembly'].update(case_model='case-a',appearance_style='notebook_line',desktop_frame=False)
    ui._draft['theme']='light';ui._draft['autostart']=True;ui._draft['refresh']=.25
    ui._draft['language']='en';ui._draft['history_enabled']=True
    ui._draft['cpu_temperature_prompt_on_start']=True
    ui._draft['widgets']['cpu']['title']='pending CPU'
    ui._draft['top_bar']['height']=48


class AssemblySaveTests(unittest.TestCase):
    def test_leaf_projection_is_detached_and_ui_scope_partition_is_unchanged(self):
        self.assertEqual(set(SCOPE_FIELDS),{'desktop','preferences','topbar'})
        base=state();source=copy.deepcopy(base);source['assembly']['desktop_frame']=False
        source['theme']='light';source['widgets']['cpu']['title']='pending'
        result=merge_scope(base,source,'assembly')
        self.assertEqual(result['assembly'],source['assembly'])
        self.assertEqual({k:v for k,v in result.items()if k!='assembly'}, {k:v for k,v in base.items()if k!='assembly'})
        result['assembly']['part_styles']['gpu']='papercut'
        self.assertEqual(source['assembly']['part_styles'],{})
        self.assertEqual(base['assembly']['part_styles'],{})
        with self.assertRaises(KeyError):merge_scope(base,source,'invalid')

    def test_success_uses_real_commit_and_preserves_every_unapplied_other_branch(self):
        for secondary in (False,True):
            with self.subTest(secondary=secondary):
                ui=controller(secondary);dirty_all(ui)
                saved,draft=copy.deepcopy(ui._saved),copy.deepcopy(ui._draft)
                self.assertTrue(ui.saveAssembly())
                expected=merge_scope(saved,draft,'assembly')
                self.assertEqual(ui.saved_attempts,[expected])
                self.assertEqual(ui._saved,expected);self.assertEqual(ui._draft,draft)
                self.assertEqual(ui.autostart_calls,[])
                self.assertEqual(ui.applyRequested.calls,[(False,)])
                self.assertEqual(ui.applied[-1],'主机方案已保存')
                self.assertFalse(ui._saved['autostart']);self.assertTrue(ui._draft['autostart'])
                self.assertEqual({s:scope_dirty(ui._saved,ui._draft,s)for s in SCOPE_FIELDS},
                    dict(desktop=True,preferences=True,topbar=True))

    def test_save_failure_leaves_saved_draft_and_history_exact(self):
        ui=controller();dirty_all(ui);ui.save_error=True
        ui._undo_drafts=[state(),copy.deepcopy(ui._draft)];ui._redo_drafts=[state()]
        before=copy.deepcopy((ui._saved,ui._draft,ui._undo_drafts,ui._redo_drafts,ui._last_edit_key,ui._last_edit_time))
        with self.assertLogs(level='ERROR'):
            self.assertFalse(ui.saveAssembly())
        self.assertEqual((ui._saved,ui._draft,ui._undo_drafts,ui._redo_drafts,ui._last_edit_key,ui._last_edit_time),before)
        self.assertEqual(ui.autostart_calls,[]);self.assertEqual(ui.applyRequested.calls,[])
        self.assertEqual(ui.savedChanged.calls,[]);self.assertEqual(ui.applied,[])
        self.assertTrue(ui.statuses[-1][1])

    def test_replacement_preview_blocks_before_any_save_or_rebase(self):
        ui=controller();dirty_all(ui);ui._replacement_backup={'preview':'all settings'}
        before=copy.deepcopy((ui._saved,ui._draft,ui._replacement_backup))
        self.assertFalse(ui.saveAssembly())
        self.assertEqual((ui._saved,ui._draft,ui._replacement_backup),before)
        self.assertEqual(ui.saved_attempts,[]);self.assertEqual(ui.capacity_calls,[])
        self.assertEqual(ui.applied,[]);self.assertIn('全部设置预览',ui.statuses[-1][0])

    def test_real_undo_redo_rebase_keeps_saved_assembly_and_unrelated_history(self):
        ui=controller();original=state();assembly_edit=copy.deepcopy(original)
        assembly_edit['assembly']['case_model']='case-a'
        widget_edit=copy.deepcopy(assembly_edit);widget_edit['widgets']['cpu']['title']='pending CPU'
        ui._draft=copy.deepcopy(widget_edit);ui._draft['theme']='light';ui._draft['top_bar']['height']=48
        ui._undo_drafts=[original,assembly_edit,widget_edit]
        later=copy.deepcopy(ui._draft);later['refresh']=.25;ui._redo_drafts=[later]
        self.assertTrue(ui.saveAssembly())
        saved_assembly=copy.deepcopy(ui._saved['assembly'])
        self.assertTrue(ui.redoDraft());self.assertEqual(ui._draft['refresh'],.25)
        count=0
        while ui.undoDraft():
            count+=1;self.assertEqual(ui._draft['assembly'],saved_assembly)
        self.assertGreaterEqual(count,2);self.assertEqual(ui._draft['widgets']['cpu']['title'],'saved CPU')
        while ui.redoDraft():self.assertEqual(ui._draft['assembly'],saved_assembly)
        self.assertEqual(ui._draft['widgets']['cpu']['title'],'pending CPU')
        self.assertEqual(ui._draft['theme'],'light');self.assertEqual(ui._draft['top_bar']['height'],48)
        self.assertEqual(ui._draft['refresh'],.25)

    def test_dirty_notification_and_noop_save_do_not_touch_other_preferences(self):
        ui=controller()
        initialize=method('assembly_tools.py','AssemblyTools','initialize_assembly_signals',{})
        initialize(ui)
        # Read the exact new production getter, without importing Qt/controller.
        tree=ast.parse((ROOT/'assembly_tools.py').read_text('utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='AssemblyTools')
        assignment=next(n for n in cls.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='assemblyDirty'for t in n.targets))
        getter=eval(compile(ast.Expression(assignment.value.args[1]),'<production assemblyDirty getter>','eval'))
        self.assertFalse(getter(ui))
        ui._draft['assembly']['desktop_frame']=False;ui.draftChanged.emit()
        self.assertTrue(getter(ui));self.assertEqual(len(ui.assemblySaveChanged.calls),1)
        self.assertTrue(ui.saveAssembly());self.assertFalse(getter(ui))
        self.assertEqual(len(ui.assemblySaveChanged.calls),3)  # draft edit plus saved/draft notifications.
        ui._draft['theme']='light';ui._draft['autostart']=True
        attempts=len(ui.saved_attempts);self.assertTrue(ui.saveAssembly())
        self.assertEqual(len(ui.saved_attempts),attempts)
        self.assertEqual(ui._saved['theme'],'dark');self.assertEqual(ui._draft['theme'],'light')
        self.assertEqual(ui.autostart_calls,[])


if __name__=='__main__':unittest.main()
