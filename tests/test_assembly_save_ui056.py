"""Real save UI statements and real assembly-only commit, with fake IO/APIs."""
import ast
import copy
from pathlib import Path
from types import MethodType,SimpleNamespace
import unittest

import test_assembly_save055 as provider

ROOT=Path(__file__).resolve().parents[1]


def method(path,owner,name):
    tree=ast.parse((ROOT/path).read_text('utf8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name==owner)
    value=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name==name))
    value.decorator_list=[]
    return value


def bind(obj,name):
    fn=method('assembly_window.py','AssemblyWindow',name);scope={}
    exec(compile(ast.Module([fn],[]),str(ROOT/'assembly_window.py'),'exec'),scope)
    setattr(obj,name,MethodType(scope[name],obj))


class Button:
    def __init__(self,text=''):
        self.text=text;self.enabled=False;self.tooltip='';self.name='';self.clicked=provider.Signal()
    def setObjectName(self,value):self.name=value
    def setEnabled(self,value):self.enabled=value
    def setToolTip(self,value):self.tooltip=value


class Label:
    def __init__(self):self.value=''
    def text(self):return self.value
    def setText(self,value):self.value=value


class ControllerView:
    def __init__(self,ui):self.ui=ui
    def __getattr__(self,name):return getattr(self.ui,name)
    @property
    def assemblyDirty(self):return self.ui._saved['assembly']!=self.ui._draft['assembly']
    def tr(self,text):return text


def view():
    ui=provider.controller(secondary=True);controller=ControllerView(ui)
    provider.method('assembly_tools.py','AssemblyTools','initialize_assembly_signals',{})(ui)
    owner=SimpleNamespace(controller=controller,_assembly_save_feedback='',_connections=[],status=Label(),
        _renderer_error=False,_spec={'options':{'fan_animation':False}},admitted=True)
    owner._can_interact=lambda:owner.admitted
    owner._gpu_assembly_state=lambda:{};owner._part_assembly_state=lambda:{}
    for name in('_sync_assembly_save','_save_assembly','_update_status'):bind(owner,name)
    return owner,ui


def execute(fn,condition,scope):
    selected=[copy.deepcopy(n)for n in fn.body if condition(n)]
    if not selected:raise AssertionError('real product UI connection missing')
    exec(compile(ast.Module(selected,[]),'<actual save UI statements>','exec'),scope)


class AssemblySaveUiTests(unittest.TestCase):
    def test_real_toolbar_click_calls_real_assembly_commit_without_other_draft_saves(self):
        owner,ui=view();provider.dirty_all(ui)
        before_saved,before_draft=copy.deepcopy(ui._saved),copy.deepcopy(ui._draft)
        fn=method('assembly_window.py','AssemblyWindow','_build_inspector')
        execute(fn,lambda n:any(isinstance(x,ast.Attribute)and x.attr=='save_assembly_button'for x in ast.walk(n)),
            dict(self=owner,controller=owner.controller,QPushButton=Button,header=SimpleNamespace(addWidget=lambda *a:None)))
        owner._sync_assembly_save()
        self.assertEqual(owner.save_assembly_button.name,'assemblySavePlanButton')
        self.assertTrue(owner.save_assembly_button.enabled)
        owner.save_assembly_button.clicked.emit()
        self.assertEqual(len(ui.saved_attempts),1)
        self.assertEqual(ui._saved['assembly'],before_draft['assembly'])
        self.assertEqual({k:v for k,v in ui._saved.items()if k!='assembly'},
            {k:v for k,v in before_saved.items()if k!='assembly'})
        self.assertEqual(ui._draft,before_draft);self.assertEqual(ui.autostart_calls,[])
        self.assertFalse(owner.save_assembly_button.enabled)
        self.assertIn('主机方案已保存',owner.status.text())
        self.assertIn('临时检视状态不保存',owner.save_assembly_button.tooltip)

    def test_real_desktop_menu_reports_failure_and_allows_safe_retry(self):
        owner,ui=view();provider.dirty_all(ui)
        actions=[]
        def add(text,callback):
            action=Button(text);action.clicked.connect(callback);actions.append(action);return action
        fn=method('assembly_desktop_widget.py','AssemblyWidgetWindow','_show_menu')
        execute(fn,lambda n:any(isinstance(x,ast.Name)and x.id=='save_plan'for x in ast.walk(n)),
            dict(self=owner,menu=SimpleNamespace(addAction=add)))
        self.assertEqual(len(actions),1);self.assertEqual(actions[0].name,'assemblySavePlanAction')
        self.assertTrue(actions[0].enabled)
        before=copy.deepcopy((ui._saved,ui._draft));ui.save_error=True
        with self.assertLogs(level='ERROR'):actions[0].clicked.emit()
        self.assertEqual((ui._saved,ui._draft),before)
        self.assertEqual(owner._assembly_save_feedback,'failed');self.assertIn('保存失败',owner.status.text())
        self.assertEqual(ui.applyRequested.calls,[]);self.assertEqual(ui.autostart_calls,[])
        ui.save_error=False;actions[0].clicked.emit()
        self.assertEqual(owner._assembly_save_feedback,'saved')
        self.assertFalse(owner.controller.assemblyDirty);self.assertIn('主机方案已保存',owner.status.text())

    def test_actual_dirty_signal_connection_and_noactivate_guard_block_saves(self):
        owner,ui=view();owner.save_assembly_button=Button()
        fn=method('assembly_window.py','AssemblyWindow','_attach_session')
        def matching(n):
            if isinstance(n,ast.Assign):return any(isinstance(t,ast.Name)and t.id=='save_signal'for t in n.targets)
            return isinstance(n,ast.If)and any(isinstance(x,ast.Name)and x.id=='save_signal'for x in ast.walk(n.test))
        execute(fn,matching,dict(self=owner,controller=owner.controller))
        self.assertEqual(len(owner._connections),1)
        owner._sync_assembly_save();self.assertFalse(owner.save_assembly_button.enabled)
        ui._draft['assembly']['show_psu']=True;ui.draftChanged.emit()
        self.assertTrue(owner.save_assembly_button.enabled);self.assertIn('未保存',owner.status.text())
        owner.admitted=False;owner._sync_assembly_save();self.assertFalse(owner.save_assembly_button.enabled)
        self.assertFalse(owner._save_assembly());self.assertEqual(ui.saved_attempts,[])
        owner.admitted=True;ui._replacement_backup={'preview':'all'}
        self.assertFalse(owner._save_assembly());self.assertEqual(ui.saved_attempts,[])
        self.assertEqual(owner._assembly_save_feedback,'failed')
        self.assertIn('保存失败',owner.status.text())


if __name__=='__main__':unittest.main()
