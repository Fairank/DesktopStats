"""Real dispatch and monitor gates, with no Qt/window/driver initialization."""
import ast
from copy import deepcopy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def method(file,owner,name,scope):
    tree=ast.parse((ROOT/file).read_text('utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==owner)
    node=deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name))
    node.decorator_list=[]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(file),'exec'),scope)
    return scope[name]


class Signal:
    def __init__(self):self.callbacks=[];self.emitted=0
    def connect(self,callback):self.callbacks.append(callback)
    def emit(self,*args):
        self.emitted+=1
        for callback in self.callbacks:callback(*args)


class Window:
    window_mode='reference'
    def __init__(self):
        self.closed=Signal();self.visible=False;self.shown=0;self.closed_count=0
        self.props={};self.attributes=[];self.lowered=0;self.activations=0;self.motion=[]
        self.viewport=SimpleNamespace(set_motion_enabled=self.motion.append)
        self.handle=SimpleNamespace(setScreen=lambda value:setattr(self,'target',value),screenChanged=Signal())
        self.clocks=[]
    def isMinimized(self):return False
    def isVisible(self):return self.visible
    def property(self,key):return self.props.get(key)
    def setProperty(self,key,value):self.props[key]=value
    def setAttribute(self,*value):self.attributes.append(value)
    def hide(self):self.visible=False
    def lower(self):self.lowered+=1
    def showNormal(self):self.visible=True;self.shown+=1
    def raise_(self):self.activations+=1
    def activateWindow(self):self.activations+=1
    def _clock_active(self,value):self.clocks.append(value)
    def update_readings(self):raise AssertionError('Reference must not read hardware')
    def setMinimumSize(self,*_):pass
    def resize(self,*_):pass
    def winId(self):return 1
    def windowHandle(self):return self.handle
    def move(self,*_):pass
    def installEventFilter(self,*_):pass
    def close(self):self.closed_count+=1;self.visible=False;self.closed.emit()


class OpenReferenceRuntime054Tests(unittest.TestCase):
    def test_chooser_monitor_participates_in_the_actual_common_event_guard(self):
        api=method('native_runtime.py','_DesktopAwareTopBarManager','_model_monitors',{})
        runtime=SimpleNamespace(_model_guard_monitors={'widget':(1,)},
            _assembly_guard_monitors={'assembly':(2,)},_reference_import_monitors={'chooser':(3,)})
        self.assertEqual(api(SimpleNamespace(runtime=runtime)),
                         {'widget':(1,),'assembly':(2,),'chooser':(3,)})

    def test_closed_gallery_cannot_request_native_import(self):
        api=method('assembly_tools.py','AssemblyTools','openReferenceModel',{})
        target=SimpleNamespace(_accessory_gallery_active=False,referenceModelImportRequested=Signal())
        api(target);self.assertEqual(target.referenceModelImportRequested.emitted,0)
        target._accessory_gallery_active=True;api(target)
        self.assertEqual(target.referenceModelImportRequested.emitted,1)

    def test_reference_dispatch_has_no_identity_or_sensor_lookup(self):
        calls=[]
        runtime=SimpleNamespace(open_assembly_view=lambda owner,value:calls.append(value))
        api=method('native_runtime.py','Runtime','open_reference_view',{'Runtime':runtime})
        owner=object()
        for bad in (None,True,[], '', 'x'*32768):api(owner,bad)
        self.assertEqual(calls,[])
        api(owner,'D:/models/cooler.zip')
        self.assertEqual(calls,[dict(reference_package='D:/models/cooler.zip',options={'window_mode':'reference'})])

    def test_chooser_rejects_only_when_its_own_monitor_or_session_is_unsafe(self):
        rejected=[]
        owner=SimpleNamespace(_reference_file_dialog=SimpleNamespace(reject=lambda:rejected.append(True)),
                              _reference_import_monitors={'monitor2':(0,0,1920,1080)})
        api=method('native_runtime.py','Runtime','_update_reference_import_guard',{})
        api(owner,True,True,SimpleNamespace(_foreground_hidden_screens={'monitor1'}))
        self.assertEqual(rejected,[])
        api(owner,True,True,SimpleNamespace(_foreground_hidden_screens={'monitor2'}))
        api(owner,False,True,SimpleNamespace(_foreground_hidden_screens=set()))
        api(owner,True,False,SimpleNamespace(_foreground_hidden_screens=set()))
        self.assertEqual(len(rejected),3)

    def test_reference_hides_and_restores_without_activation_or_readings(self):
        window=Window();window.visible=True
        owner=SimpleNamespace(_assembly_window=window,_assembly_guard_monitors={'monitor2':()},shutting_down=False)
        api=method('native_runtime.py','Runtime','_update_assembly_motion',
                   {'Qt':SimpleNamespace(WA_ShowWithoutActivating='no-activate')})
        api(owner,True,True,SimpleNamespace(_foreground_hidden_screens={'monitor2'}))
        self.assertFalse(window.visible);self.assertTrue(owner._assembly_guard_hidden)
        self.assertEqual(window.motion,[False]);self.assertEqual(window.clocks,[False])
        api(owner,True,True,SimpleNamespace(_foreground_hidden_screens={'monitor1'}))
        self.assertTrue(window.visible);self.assertEqual(window.lowered,1)
        self.assertEqual(window.activations,0)
        self.assertEqual(window.attributes,[('no-activate',True)])

    def test_file_choice_is_parsed_only_once_after_accept_and_hide(self):
        dialogs=[];loads=[]
        class Chooser(Window):
            Option=SimpleNamespace(DontUseNativeDialog=1)
            FileMode=SimpleNamespace(ExistingFile=1)
            AcceptMode=SimpleNamespace(AcceptOpen=1)
            def __init__(self,*args):
                super().__init__();self.fileSelected=Signal();self.finished=Signal();dialogs.append(self)
            def setOption(self,*_):pass
            def setFileMode(self,*_):pass
            def setNameFilter(self,*_):pass
            def setAcceptMode(self,*_):pass
            def open(self):self.visible=True
            def reject(self):self.visible=False;self.finished.emit(0)
        area=SimpleNamespace(width=lambda:1920,height=lambda:1080,x=lambda:1920,y=lambda:0)
        screen=SimpleNamespace(availableGeometry=lambda:area)
        runtime=SimpleNamespace(_assembly_target_allowed=lambda *args:True,
            _model_screen_fact=lambda *args:('monitor2',(1920,0,3840,1080)),
            refresh_model_motion=lambda *args,**kwargs:None)
        owner=SimpleNamespace(headless=False,shutting_down=False,_assembly_guard_monitors={},
            controller=SimpleNamespace(saved={'top_bar':{}},tr=lambda text:text,
                                       set_status=lambda *args,**kwargs:None),
            app=SimpleNamespace(screens=lambda:[screen],primaryScreen=lambda:screen),
            top_bar=SimpleNamespace(adapter=SimpleNamespace(screen_identity=lambda _:None)))
        runtime.open_reference_view=lambda target,path:loads.append(
            (path,target._reference_file_dialog,dict(target._reference_import_monitors),dialogs[-1].visible))
        api=method('native_runtime.py','Runtime','import_reference_model',dict(Runtime=runtime,
            Qt=SimpleNamespace(WA_DeleteOnClose=1,WA_ShowWithoutActivating=2),
            foreground_fullscreen=lambda:True,_desktop_session_ready=lambda:True,
            logging=SimpleNamespace(exception=lambda *_:self.fail('Unexpected chooser failure'))))
        config=ModuleType('assembly_config');config.target_screen=lambda *args:screen
        qt=ModuleType('PySide6');qt.__path__=[]
        widgets=ModuleType('PySide6.QtWidgets');widgets.QFileDialog=Chooser
        widgets.QDialog=SimpleNamespace(DialogCode=SimpleNamespace(Accepted=1))
        qt.QtWidgets=widgets
        with patch.dict(sys.modules,{'assembly_config':config,'PySide6':qt,'PySide6.QtWidgets':widgets}):
            api(owner);first=dialogs[-1]
            first.fileSelected.emit('D:/models/aio.zip')
            self.assertTrue(first.visible);self.assertIs(owner._reference_file_dialog,first)
            self.assertEqual(loads,[])
            first.visible=False;first.finished.emit(1)
            self.assertEqual(loads,[('D:/models/aio.zip',None,{},False)])
            first.finished.emit(1);self.assertEqual(len(loads),1)
            api(owner);second=dialogs[-1]
            first.finished.emit(1)
            self.assertIs(owner._reference_file_dialog,second)
            self.assertIn('monitor2',owner._reference_import_monitors)
            second.fileSelected.emit('D:/models/wind.zip');second.reject()
            self.assertIsNone(owner._reference_file_dialog);self.assertEqual(len(loads),1)

    def _open(self,gates,game_starts_during_load=False):
        events=[];window=Window()
        area=SimpleNamespace(width=lambda:1920,height=lambda:1080,x=lambda:1920,y=lambda:0)
        screen=SimpleNamespace(availableGeometry=lambda:area)
        controller=SimpleNamespace(saved={'top_bar':{}},set_status=lambda *a,**k:events.append(('status',a,k)))
        owner=SimpleNamespace(headless=False,shutting_down=False,_assembly_window=None,
            _assembly_guard_monitors={},controller=controller,engine=None,
            app=SimpleNamespace(screens=lambda:[screen],primaryScreen=lambda:screen),
            top_bar=SimpleNamespace(adapter=SimpleNamespace(screen_identity=lambda _:None)))
        remaining=list(gates)
        runtime=SimpleNamespace(_assembly_target_allowed=lambda *a:remaining.pop(0),
                                refresh_model_motion=lambda *a,**k:None)
        state={'fullscreen':not game_starts_during_load}
        scope=dict(Runtime=runtime,Path=Path,Qt=SimpleNamespace(WA_ShowWithoutActivating='no-activate'),
            foreground_fullscreen=lambda:state['fullscreen'],_desktop_session_ready=lambda:True,
            logging=SimpleNamespace(exception=lambda *a:events.append(('error',))))
        api=method('native_runtime.py','Runtime','open_assembly_view',scope)
        config=ModuleType('assembly_config');config.target_screen=lambda *args:screen
        loader=ModuleType('open_reference_models054')
        def load_reference(path):
            events.append(('load',path));state['fullscreen']=True
            return object()
        loader.load_reference=load_reference
        view=ModuleType('open_reference_window054')
        view.OpenReferenceWindow=lambda model,parent:events.append(('construct',)) or window
        with patch.dict(sys.modules,assembly_config=config,open_reference_models054=loader,open_reference_window054=view):
            api(owner,dict(reference_package='D:/models/aio.zip',options={'window_mode':'reference'}))
        self.assertFalse(any(row[0]=='error' for row in events),events)
        return owner,window,events

    def test_native_loader_is_after_first_screen_guard_and_before_second(self):
        _,window,events=self._open([False])
        self.assertFalse(any(row[0]=='load' for row in events));self.assertEqual(window.shown,0)
        owner,window,events=self._open([True,False])
        self.assertEqual([row[0] for row in events],['load','construct'])
        self.assertEqual(window.shown,0);self.assertEqual(window.closed_count,1)
        self.assertIsNone(owner._assembly_window)

    def test_other_monitor_fullscreen_keeps_reference_on_target_without_activation(self):
        owner,window,events=self._open([True,True])
        self.assertIs(owner._assembly_window,window)
        self.assertEqual([row[0] for row in events],['load','construct'])
        self.assertEqual(window.shown,1);self.assertEqual(window.activations,0)
        self.assertEqual(window.attributes,[('no-activate',True)])
        self.assertIs(window.target,owner.app.primaryScreen())

    def test_returning_to_game_during_load_does_not_use_old_focus_permission(self):
        _,window,events=self._open([True,True],game_starts_during_load=True)
        self.assertEqual(window.shown,1);self.assertEqual(window.activations,0)
        self.assertEqual(window.attributes,[('no-activate',True)])


if __name__=='__main__':unittest.main()
