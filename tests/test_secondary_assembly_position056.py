"""Real opening route bodies plus the real guard; no Qt or live native calls."""
import ast
import copy
from functools import lru_cache
import logging
import traceback
from pathlib import Path
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

from secondary_window_guard055 import (
    SecondaryWindowGuard,Token,WINDOWPOS,NOACTIVATE,NOZORDER,NOMOVE,NOSIZE,HIDE,
)

ROOT=Path(__file__).resolve().parents[1]
TARGET=r'\\.\DISPLAY37'
PRIMARY=r'\\.\DISPLAY36'
WORK=(2560,-509,4000,1971)
CAPTURED_LOGS=[]


class Rect:
    def __init__(self,x,y,width,height):self.value=(x,y,width,height)
    def x(self):return self.value[0]
    def y(self):return self.value[1]
    def width(self):return self.value[2]
    def height(self):return self.value[3]


class Signal:
    def __init__(self):self.slots=[]
    def connect(self,slot):self.slots.append(slot)
    def emit(self,*args):
        for slot in tuple(self.slots):slot(*args)


class NativeOwner:
    def __init__(self,case):
        self.case=case;self.rect=(1070,456,1490,936);self.screenChanged=Signal()
        self.hwnd=100;self.qt_screen=None
    def isTopLevel(self):return True
    def setScreen(self,screen):self.qt_screen=screen
    def isVisible(self):return self.case.window.visible
    def hide(self):self.case.window.visible=False
    def setGeometry(self,rect):
        self.case.events.append('native-sync')
        self.case.sync_rect=rect.value
        assert self.case.registered and self.case.guard.tokens[id(self)].hwnd==self.hwnd
        assert not self.case.window.visible,'Synchronize an existing hidden owner before Show'
        if self.case.failure=='raise':raise RuntimeError('native setter failed')
        if self.case.failure=='ignore':return
        if self.case.failure=='lost-target':self.case.safe=False
        position=WINDOWPOS(hwnd=self.hwnd,x=rect.x(),y=rect.y(),cx=rect.width(),cy=rect.height(),
                           flags=NOACTIVATE|NOZORDER)
        self.case.guard.native_message(self.hwnd,0x46,position)
        self.case.pending_flags=position.flags
        if not position.flags&(NOMOVE|NOSIZE|HIDE):
            self.rect=(position.x,position.y,position.x+position.cx,position.y+position.cy)


class Window:
    window_mode='desktop'
    def __init__(self,case):
        self.case=case;self.visible=False;self.closed_count=0;self.closed=Signal()
        self.finished=Signal();self.fileSelected=Signal();self.cached=Rect(1070,456,420,480)
        self.native=NativeOwner(case)
    def setMinimumSize(self,*args):pass
    def resize(self,w,h):self.cached=Rect(self.cached.x(),self.cached.y(),w,h)
    def setWindowFlag(self,*args):pass
    def setWindowTitle(self,*args):pass
    def setAttribute(self,*args):pass
    def winId(self):return self.native.hwnd
    def windowHandle(self):return None if self.case.failure=='missing-owner'and self.case.registered else self.native
    def move(self,x,y):
        self.case.events.append('widget-cache-move')
        self.cached=Rect(x,y,self.cached.width(),self.cached.height())
        # This reproduces the observed hidden QWidget/actual QWindow mismatch.
        # Show would apply this cache later, after the strict pre-Show gate.
    def geometry(self):return self.cached
    def installEventFilter(self,*args):pass
    def synchronize(self,*args):pass
    def showNormal(self):self.case.events.append('show');self.visible=True
    def lower(self):pass
    def hide(self):self.visible=False
    def raise_(self):self.case.events.append('raise')
    def activateWindow(self):self.case.events.append('activate')
    def close(self):
        self.closed_count+=1;self.visible=False;self.closed.emit();self.finished.emit(0)
    def reject(self):self.close()
    def open(self):self.showNormal()
    def setOption(self,*args):pass
    def setFileMode(self,*args):pass
    def setNameFilter(self,*args):pass
    def setAcceptMode(self,*args):pass


class Api:
    def __init__(self,case):self.case=case
    def attach(self,hwnd,generation,pid,thread):return Token(hwnd,pid,thread,'OwnStatsFake',generation)
    def state(self,token):
        assert token.hwnd==self.case.window.native.hwnd
        rect=self.case.window.native.rect
        return dict(rect=rect,native_id=TARGET if rect[0]>=WORK[0]else PRIMARY,minimized=False)
    def valid(self,token):return token.hwnd==self.case.window.native.hwnd
    def release(self,token):pass


class Bridge:
    def start(self,core):pass
    def watch(self,window,core):pass
    def unwatch(self,window):pass
    def stop(self):pass


@lru_cache(maxsize=1)
def route_nodes():
    tree=ast.parse((ROOT/'native_runtime.py').read_text('utf8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='Runtime')
    return {n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)and
            n.name in('open_assembly_view','import_reference_model','_secondary_window_admitted')}


def route_body(name,scope,*,old=False):
    node=copy.deepcopy(route_nodes()[name])
    if old:
        class RemoveOnlyNativeSync(ast.NodeTransformer):
            count=0
            def visit_If(self,item):
                if (len(item.body)==1 and isinstance(item.body[0],ast.Expr)
                        and isinstance(item.body[0].value,ast.Call)
                        and isinstance(item.body[0].value.func,ast.Attribute)
                        and item.body[0].value.func.attr=='setGeometry'):
                    self.count+=1;return None
                return self.generic_visit(item)
        remover=RemoveOnlyNativeSync();node=remover.visit(node);assert remover.count==1
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                 'native_runtime.py::<actual opening route>','exec'),scope)
    return scope[name]


class Case:
    def __init__(self,*,secondary=True,failure='',safe=True,desktop=True,missing_target=False,old=False):
        self.secondary=secondary;self.failure=failure;self.safe=safe;self.desktop=desktop
        self.events=[];self.window=None;self.registered=False;self.sync_rect=None;self.pending_flags=None
        self.target=SimpleNamespace(availableGeometry=lambda:Rect(WORK[0],WORK[1],WORK[2]-WORK[0],WORK[3]-WORK[1]))
        runtime=type('Runtime',(),{})
        runtime._allowed_screens=lambda _:[]if missing_target else[self.target]
        runtime._placement_screen=lambda _:None if missing_target else self.target
        runtime._assembly_target_allowed=lambda _,target:self.safe
        runtime._model_screen_fact=lambda _,target:(TARGET,WORK)
        runtime.refresh_model_motion=lambda *args,**kwargs:None
        runtime.open_reference_view=lambda *args:None
        def register(instance,window):
            self.events.append('register');self.registered=True
            if failure=='register':return False
            assert self.guard.watch(window.native)and self.guard.bind(window.native,window.native.hwnd)
            return True
        runtime.register_secondary_window=register
        qt=SimpleNamespace(WindowDoesNotAcceptFocus=1,WA_ShowWithoutActivating=2,WA_DeleteOnClose=3)
        scope=dict(Runtime=runtime,secondary_active=lambda:secondary,_desktop_session_ready=lambda:self.desktop,
            session_display_name=lambda:'DesktopStats V2',foreground_fullscreen=lambda:False,Qt=qt,logging=logging)
        runtime._secondary_window_admitted=route_body('_secondary_window_admitted',scope)
        runtime.open_assembly_view=route_body('open_assembly_view',scope,old=old)
        runtime.import_reference_model=route_body('import_reference_model',scope,old=old)
        self.runtime=runtime();self.runtime.headless=False;self.runtime.shutting_down=False
        self.runtime.engine=object()
        self.runtime._assembly_window=None;self.runtime._assembly_guard_monitors={}
        self.runtime._reference_file_dialog=None;self.runtime._reference_import_monitors={}
        self.status=[]
        self.runtime.controller=SimpleNamespace(saved={'top_bar':{'monitor_mode':'selected','screens':[TARGET]}},
            set_status=lambda *args,**kwargs:self.status.append((args,kwargs)),tr=lambda text:text)
        self.runtime.top_bar=SimpleNamespace(adapter=SimpleNamespace(screen_identity=lambda screen:SimpleNamespace(native_id=TARGET)))
        self.guard=SecondaryWindowGuard(Api(self),Bridge(),lambda owner:
            dict(admitted=True,native_id=TARGET,work=WORK)if self.safe else None,pid=1,native_thread=2)
        self.runtime._secondary_window_guard=self.guard
    def make(self,*args,**kwargs):
        assert self.window is None,'Exactly one candidate, no hidden replacement'
        self.events.append('construct');self.window=Window(self);return self.window
    def call(self,route):
        module=ModuleType('assembly_window');module.create_assembly_window=self.make
        qt_package=ModuleType('PySide6');qt_package.__path__=[]
        widgets=ModuleType('PySide6.QtWidgets')
        widgets.QDialog=SimpleNamespace(DialogCode=SimpleNamespace(Accepted=1))
        class Dialog:
            Option=SimpleNamespace(DontUseNativeDialog=1)
            FileMode=SimpleNamespace(ExistingFile=1)
            AcceptMode=SimpleNamespace(AcceptOpen=1)
            def __new__(cls,*args):return self.make()
        widgets.QFileDialog=Dialog
        qt_package.QtWidgets=widgets
        def capture_log(message,*args,**kwargs):
            CAPTURED_LOGS.append(dict(route=route,failure=self.failure,message=str(message),traceback=traceback.format_exc()))
        with patch.dict('sys.modules',{'assembly_window':module,'PySide6':qt_package,'PySide6.QtWidgets':widgets}),patch.object(logging,'exception',side_effect=capture_log):
            if route=='assembly':self.runtime.open_assembly_view({'options':{'window_mode':'desktop'}})
            else:self.runtime.import_reference_model()
    def retained(self,route):
        return self.runtime._assembly_window if route=='assembly'else self.runtime._reference_file_dialog
    def close(self):
        if self.window is not None:self.window.close()
        self.guard.close()


class SecondaryAssemblyPosition056Tests(unittest.TestCase):
    def test_both_hidden_widget_routes_sync_actual_native_before_show_with_old_negative(self):
        for route in('assembly','chooser'):
            for old in(True,False):
                with self.subTest(route=route,old=old):
                    case=Case(old=old)
                    try:
                        case.call(route)
                        if old:
                            self.assertNotIn('native-sync',case.events);self.assertNotIn('show',case.events)
                            self.assertIsNone(case.retained(route));self.assertEqual(case.window.native.rect,(1070,456,1490,936))
                            self.assertGreaterEqual(case.window.closed_count,1)
                        else:
                            self.assertEqual(case.events[:3],['construct','register','widget-cache-move'])
                            self.assertEqual(case.events[3:5],['native-sync','show'])
                            self.assertIs(case.retained(route),case.window)
                            self.assertTrue(case.runtime._secondary_window_admitted(case.window))
                            self.assertEqual(case.window.native.rect,
                                (case.sync_rect[0],case.sync_rect[1],case.sync_rect[0]+case.sync_rect[2],case.sync_rect[1]+case.sync_rect[3]))
                            self.assertTrue(case.pending_flags&NOACTIVATE)
                            self.assertNotIn('activate',case.events);self.assertNotIn('raise',case.events)
                    finally:case.close()

    def test_native_setter_errors_missing_owner_or_unchanged_native_never_show(self):
        for route in('assembly','chooser'):
            for failure in('raise','ignore','missing-owner'):
                with self.subTest(route=route,failure=failure):
                    case=Case(failure=failure)
                    try:
                        case.call(route)
                        self.assertIsNone(case.retained(route));self.assertNotIn('show',case.events)
                        self.assertGreaterEqual(case.window.closed_count,1)
                        self.assertEqual(case.window.native.rect,(1070,456,1490,936))
                    finally:case.close()

    def test_unknown_desktop_target_registration_or_target_loss_fail_closed(self):
        for route in('assembly','chooser'):
            for params in(dict(safe=False),dict(desktop=False),dict(missing_target=True),
                          dict(failure='register'),dict(failure='lost-target')):
                with self.subTest(route=route,params=params):
                    case=Case(**params)
                    try:
                        case.call(route)
                        self.assertIsNone(case.retained(route));self.assertNotIn('show',case.events)
                        if case.window is not None:self.assertGreaterEqual(case.window.closed_count,1)
                        if params.get('failure')=='lost-target':
                            self.assertTrue(case.pending_flags&HIDE)
                            self.assertEqual(case.window.native.rect,(1070,456,1490,936))
                    finally:case.close()

    def test_legacy_routes_keep_original_placement_without_new_native_sync(self):
        for route in('assembly','chooser'):
            with self.subTest(route=route):
                case=Case(secondary=False,failure='raise')
                try:
                    case.call(route)
                    self.assertIs(case.retained(route),case.window)
                    self.assertNotIn('register',case.events);self.assertNotIn('native-sync',case.events)
                    self.assertIn('show',case.events)
                finally:case.close()


if __name__=='__main__':unittest.main()
