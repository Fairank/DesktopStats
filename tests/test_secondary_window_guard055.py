"""V2 pre-apply/lifecycle controls, synthetic own windows and native buffers only."""
import ast
import ctypes as c
from ctypes import wintypes as w
import importlib.util
import os
from pathlib import Path
import sys
import threading
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

import secondary_window_guard055 as guard

AREA=(2560,-509,4000,1971)


class Signal:
    def __init__(self):self.callbacks=[]
    def connect(self,fn):self.callbacks.append(fn)
    def disconnect(self,fn):self.callbacks.remove(fn)
    def emit(self,*args):
        for callback in tuple(self.callbacks):callback(*args)


class Window:
    def __init__(self,hwnd=55,parent=None,top_level=True):
        self.hwnd=hwnd;self._parent=parent;self.visible=False;self.hides=0;self.filters=[]
        self.top_level=top_level
        for name in('screenChanged','xChanged','yChanged','widthChanged','heightChanged','destroyed'):
            setattr(self,name,Signal())
    def parent(self):return self._parent
    def isTopLevel(self):return self.top_level
    def isVisible(self):return self.visible
    def hide(self):self.visible=False;self.hides+=1
    def winId(self):return self.hwnd
    def installEventFilter(self,value):self.filters.append(value)
    def removeEventFilter(self,value):self.filters.remove(value)


class Api:
    def __init__(self,pid=123,tid=456):
        self.pid,self.tid=pid,tid;self.cookies={};self.writes=[];self.child=False;self.noactivate=True
        self.owner=True;self.release_error=False;self.fail_state=False
        self.rect=(2700,-400,3500,200);self.native_id=r'\\.\DISPLAY37'
    def attach(self,hwnd,generation,pid,thread):
        if not self.owner or(pid,thread)!=(self.pid,self.tid):raise ValueError('Foreign owner')
        if self.child:return None
        if not self.noactivate:raise ValueError('No precreated NOACTIVATE policy')
        if hwnd in self.cookies:raise ValueError('Occupied generation')
        self.cookies[hwnd]=generation;self.writes.append(('attach',hwnd,generation))
        return guard.Token(hwnd,pid,thread,'OwnClass',generation)
    def valid(self,token):return self.owner and self.cookies.get(token.hwnd)==token.generation
    def state(self,token):
        if not self.valid(token):return None
        if self.child:return dict(child=True)
        if self.fail_state or not self.noactivate:raise ValueError('Unknown state')
        return dict(rect=self.rect,native_id=self.native_id,minimized=False)
    def release(self,token):
        if not self.valid(token):return
        if self.release_error:raise OSError('Fake release failure')
        self.writes.append(('release',token.hwnd,token.generation));del self.cookies[token.hwnd]
    def message(self,address):return w.MSG.from_address(address)
    def pending(self,address):return guard.WINDOWPOS.from_address(address)


class Bridge:
    def __init__(self):self.started=0;self.stopped=0;self.watched=[];self.fail_stop=False
    def start(self,core):self.started+=1;self.core=core
    def watch(self,window,core):self.watched.append(window)
    def unwatch(self,window):self.watched.remove(window)
    def stop(self):
        if self.fail_stop:raise RuntimeError('Fake filter removal failure')
        self.stopped+=1


class Function:
    def __init__(self,fn):self.fn=fn
    def __call__(self,*args):return self.fn(*args)


class NativeUser:
    """Synthetic Win32 table for the actual ownership/property API body."""
    class Monitor(c.Structure):
        _fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD),('device',w.WCHAR*32)]
    def __init__(self):
        self.pid,self.tid,self.klass=123,456,'OwnQtClass'
        self.cookie=0;self.writes=[];self.reads=[];self.style=0;self.extended=0x08000000
        self.VirtualQuery=Function(lambda *args:0)  # No real own-memory query in fakes.
        def owner(hwnd,pid):
            self.reads.append('owner');c.cast(pid,c.POINTER(w.DWORD)).contents.value=self.pid;return self.tid
        def klass(hwnd,buffer,size):self.reads.append('class');buffer.value=self.klass;return len(self.klass)
        def long(hwnd,index):self.reads.append('style');return self.extended if index==-20 else self.style
        def get(hwnd,name):self.reads.append('get_property');return self.cookie
        def put(hwnd,name,value):self.writes.append(('set',hwnd));self.cookie=value.value;return True
        def remove(hwnd,name):self.writes.append(('remove',hwnd));value=self.cookie;self.cookie=0;return value
        def bounds(hwnd,buffer):
            row=c.cast(buffer,c.POINTER(w.RECT)).contents
            row.left,row.top,row.right,row.bottom=2700,-400,3500,200;return True
        def monitor(handle,buffer):
            row=c.cast(buffer,c.POINTER(self.Monitor)).contents;row.device=r'\\.\DISPLAY37';return True
        for name,fn in dict(GetWindowThreadProcessId=owner,GetClassNameW=klass,GetWindowLongPtrW=long,
            GetPropW=get,SetPropW=put,RemovePropW=remove,GetWindowRect=bounds,
            MonitorFromWindow=lambda *a:1,GetMonitorInfoW=monitor,IsIconic=lambda *a:False,IsWindow=lambda *a:True).items():
            setattr(self,name,Function(fn))


def position(hwnd=55,x=0,y=0,cx=800,cy=600,flags=guard.SHOW|guard.NOACTIVATE):
    return guard.WINDOWPOS(hwnd,None,x,y,cx,cy,flags)


def fake_qt():
    package=ModuleType('PySide6');package.__path__=[]
    core=ModuleType('PySide6.QtCore');gui=ModuleType('PySide6.QtGui')
    class Base:
        def __init__(self,*a):pass
    core.QObject=Base;core.QAbstractNativeEventFilter=Base
    core.QEvent=SimpleNamespace(PlatformSurface=1,Show=2,Move=3,Resize=4,WindowStateChange=5)
    gui.QPlatformSurfaceEvent=SimpleNamespace(SurfaceCreated=10,SurfaceAboutToBeDestroyed=11)
    return {'PySide6':package,'PySide6.QtCore':core,'PySide6.QtGui':gui}


class SecondaryWindowGuard055Tests(unittest.TestCase):
    def make(self):
        api,bridge=Api(),Bridge();context=[dict(admitted=True,native_id=r'\\.\DISPLAY37',work=AREA)]
        owner=Window();model=guard.SecondaryWindowGuard(api,bridge,lambda window:context[0],pid=123,native_thread=456)
        self.assertTrue(model.watch(owner));self.assertTrue(model.bind(owner,55))
        return model,api,bridge,context,owner

    def test_cold_import_has_no_Qt_native_profile_or_window_work(self):
        path=Path(guard.__file__);code=compile(path.read_text('utf-8'),str(path),'exec')
        module=ModuleType('_cold_secondary_bounds');before=set(sys.modules)
        with patch.dict(sys.modules,{'_cold_secondary_bounds':module}),patch('ctypes.WinDLL',side_effect=AssertionError('No native call')):
            exec(code,module.__dict__)
        self.assertFalse(any(n.startswith(('PySide6','stats_config','profile_paths'))for n in set(sys.modules)-before))

    def test_pending_move_is_clamped_whole_frame_before_apply_negative_origin(self):
        model,api,bridge,context,owner=self.make();pending=position(x=0,y=-2000)
        self.assertEqual(model.native_message(55,guard.WM_WINDOWPOSCHANGING,pending),(True,0))
        self.assertEqual((pending.x,pending.y,pending.cx,pending.cy),(2560,-509,800,600))
        self.assertEqual(api.rect,(2700,-400,3500,200))  # No immediate/native window move API.
        self.assertEqual(owner.hides,0)

    def test_nomove_nosize_zorder_only_keeps_flags_avoids_redundant_resize(self):
        model,api,bridge,context,owner=self.make()
        pending=position(flags=guard.NOMOVE|guard.NOSIZE|guard.NOACTIVATE)
        model.native_message(55,guard.WM_WINDOWPOSCHANGING,pending)
        self.assertEqual(pending.flags,guard.NOMOVE|guard.NOSIZE|guard.NOACTIVATE)
        self.assertEqual((pending.x,pending.y,pending.cx,pending.cy),(2700,-400,800,600))

    def test_unknown_target_desktop_or_oversize_cancels_show_and_hides_own_pending(self):
        for value in(None,dict(admitted=None),dict(admitted=False)):
            model,api,bridge,context,owner=self.make();context[0]=value
            pending=position();model.native_message(55,guard.WM_WINDOWPOSCHANGING,pending)
            self.assertFalse(pending.flags&guard.SHOW);self.assertTrue(pending.flags&guard.HIDE)
            self.assertEqual(pending.flags&(guard.NOMOVE|guard.NOSIZE),guard.NOMOVE|guard.NOSIZE)
        model,api,bridge,context,owner=self.make();pending=position(cx=2000)
        model.native_message(55,guard.WM_WINDOWPOSCHANGING,pending)
        self.assertTrue(pending.flags&guard.HIDE)

    def test_foreign_wrong_generation_or_wrong_struct_never_changes_buffer(self):
        model,api,bridge,context,owner=self.make()
        for mode in('foreign','generation','struct'):
            api.owner=True;api.cookies[55]=model.tokens[id(owner)].generation
            pending=position();original=bytes(pending)
            if mode=='foreign':api.owner=False
            elif mode=='generation':api.cookies[55]+=1
            else:pending.hwnd=99;original=bytes(pending)
            self.assertEqual(model.native_message(55,guard.WM_WINDOWPOSCHANGING,pending),(False,0))
            self.assertEqual(bytes(pending),original)

    def test_mouse_nonactivation_uses_real_message_not_ignored_WINDOWPOS_flag_edit(self):
        model,api,bridge,context,owner=self.make()
        self.assertEqual(model.native_message(55,guard.WM_MOUSEACTIVATE),(True,guard.MA_NOACTIVATE))
        self.assertEqual(model.native_message(99,guard.WM_MOUSEACTIVATE),(False,0))
        # A synthetic WINDOWPOS without the caller's flag is not magically
        # certified nonactivating. Win32 ignores a late edit of this flag.
        pending=position(flags=guard.SHOW)
        model.native_message(55,guard.WM_WINDOWPOSCHANGING,pending)
        self.assertFalse(pending.flags&guard.NOACTIVATE)
        bad=Api();bad.noactivate=False
        other=guard.SecondaryWindowGuard(bad,Bridge(),lambda w:None,pid=123,native_thread=456)
        window=Window();self.assertTrue(other.watch(window));self.assertFalse(other.bind(window,55))

    def test_embedded_Quick_parent_and_native_WS_CHILD_are_not_desktop_clamped(self):
        api,bridge=Api(),Bridge();model=guard.SecondaryWindowGuard(api,bridge,lambda w:None,pid=123,native_thread=456)
        child=Window(parent=object(),top_level=False);self.assertTrue(model.watch(child));self.assertEqual(bridge.watched,[])
        top=Window();api.child=True;self.assertTrue(model.watch(top));self.assertTrue(model.bind(top,55))
        pending=position(x=0,y=0);before=bytes(pending)
        self.assertEqual(model.native_message(55,guard.WM_WINDOWPOSCHANGING,pending),(False,0))
        self.assertEqual(bytes(pending),before);self.assertEqual(api.cookies,{})

    def test_actual_window_monitor_or_frame_mismatch_hides_immediately(self):
        model,api,bridge,context,owner=self.make()
        self.assertTrue(model.allowed(owner));owner.visible=True;api.native_id=r'\\.\DISPLAY36'
        model.recheck(owner);self.assertFalse(owner.visible);self.assertEqual(owner.hides,1)
        api.native_id=r'\\.\DISPLAY37';api.rect=(2500,-400,3500,200);owner.visible=True
        model.recheck(owner);self.assertFalse(owner.visible);self.assertEqual(owner.hides,2)

    def test_surface_recreation_removes_old_generation_and_ignores_old_HWND(self):
        model,api,bridge,context,owner=self.make();old=model.tokens[id(owner)]
        model.surface_destroyed(owner);self.assertNotIn(55,api.cookies)
        owner.hwnd=56;self.assertTrue(model.bind(owner,56));new=model.tokens[id(owner)]
        self.assertNotEqual(old.generation,new.generation)
        self.assertEqual(model.native_message(55,guard.WM_MOUSEACTIVATE),(False,0))
        model.unwatch(owner);self.assertEqual(api.cookies,{});self.assertEqual(bridge.watched,[])

    def test_cleanup_failure_retains_filter_and_generation_until_explicit_close(self):
        model,api,bridge,context,owner=self.make();api.release_error=True
        result=model.close();self.assertFalse(result['complete']);self.assertFalse(model.closed)
        self.assertEqual(bridge.stopped,0);self.assertIn(55,api.cookies)
        api.release_error=False;self.assertTrue(model.close()['complete']);self.assertTrue(model.closed)
        self.assertEqual(bridge.stopped,1);self.assertEqual(api.cookies,{})
        self.assertTrue(model.close()['complete']);self.assertEqual(bridge.stopped,1)

    def test_real_Qt_bridge_install_surface_screen_change_destroy_and_uninstall_with_fakes(self):
        class App:
            def __init__(self):self.filters=[]
            def installNativeEventFilter(self,fn):self.filters.append(fn)
            def removeNativeEventFilter(self,fn):self.filters.remove(fn)
        app=App();api=Api(os.getpid(),threading.get_native_id())
        context=dict(admitted=True,native_id=r'\\.\DISPLAY37',work=AREA)
        with patch.dict(sys.modules,fake_qt()),patch.object(guard,'_NativeApi',return_value=api):
            model=guard.create_secondary_window_guard(app,lambda window:context)
            owner=Window();self.assertTrue(model.watch(owner));self.assertEqual(len(app.filters),1)
            watcher=owner.filters[0]
            event=SimpleNamespace(type=lambda:1,surfaceEventType=lambda:10)
            self.assertFalse(watcher.eventFilter(owner,event));self.assertIn(55,api.cookies)
            pending=position(x=0);message=w.MSG();message.hWnd=55;message.message=guard.WM_WINDOWPOSCHANGING
            message.lParam=c.addressof(pending)
            self.assertEqual(app.filters[0].nativeEventFilter(b'windows_generic_MSG',c.addressof(message)),(True,0))
            self.assertEqual(pending.x,AREA[0])
            owner.visible=True;api.native_id=r'\\.\DISPLAY36';owner.screenChanged.emit(object())
            self.assertFalse(owner.visible)
            event.surfaceEventType=lambda:11;watcher.eventFilter(owner,event)
            self.assertEqual(api.cookies,{})
            owner.hwnd=56;event.surfaceEventType=lambda:10;watcher.eventFilter(owner,event)
            self.assertIn(56,api.cookies)
            owner.destroyed.emit();self.assertEqual(model.windows,{});self.assertEqual(api.cookies,{})
            self.assertTrue(model.close()['complete']);self.assertEqual(app.filters,[])

    def test_chrome_legacy_defaults_true_and_only_V2_Settings_binds_capabilities_off(self):
        root=Path(__file__).resolve().parents[1]
        chrome=(root/'native/WindowChrome.qml').read_text('utf-8')
        settings=(root/'native/Settings.qml').read_text('utf-8')
        for name in('allowSystemMove','allowSystemResize','allowMaximize'):
            self.assertIn('property bool '+name+': true',chrome)
            self.assertIn(name+':!stats.secondaryMode',settings)
        self.assertIn('enabled: root.allowSystemMove',chrome)
        self.assertIn('visible: !root.maximized && root.allowSystemResize',chrome)

    def test_actual_native_API_checks_PID_thread_before_property_or_geometry_calls(self):
        for change in('pid','tid'):
            user=NativeUser();setattr(user,change,999)
            with patch('ctypes.WinDLL',return_value=user):api=guard._NativeApi()
            with self.assertRaises(ValueError):api.attach(55,1,123,456)
            self.assertEqual(user.reads,['owner']);self.assertEqual(user.writes,[])

    def test_actual_native_generation_release_never_removes_foreign_or_reused_property(self):
        user=NativeUser()
        with patch('ctypes.WinDLL',return_value=user):api=guard._NativeApi()
        token=api.attach(55,1,123,456);self.assertEqual(api.state(token)['native_id'],r'\\.\DISPLAY37')
        self.assertEqual(user.writes,[('set',55)])
        user.pid=999;api.release(token);self.assertEqual(user.writes,[('set',55)])
        user.pid=123;user.cookie=2;api.release(token);self.assertEqual(user.cookie,2)
        self.assertEqual(user.writes,[('set',55)])
        user.cookie=1;api.release(token);self.assertEqual(user.writes,[('set',55),('remove',55)])

    def test_primary_runtime_registration_returns_before_any_guard_or_window_action(self):
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/'native_runtime.py').read_text('utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='Runtime')
        function=next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name=='register_secondary_window')
        function.decorator_list=[]
        scope=dict(secondary_active=lambda:False)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'<actual primary early return>','exec'),scope)
        self.assertTrue(scope['register_secondary_window'](object(),object()))

    def test_parented_tool_top_level_still_receives_global_frame_guard(self):
        api,bridge=Api(),Bridge()
        model=guard.SecondaryWindowGuard(api,bridge,lambda w:dict(admitted=True,native_id=r'\\.\DISPLAY37',work=AREA),
            pid=123,native_thread=456)
        tool=Window(parent=object(),top_level=True)
        self.assertTrue(model.watch(tool));self.assertTrue(model.bind(tool,55))
        pending=position(x=0)
        self.assertEqual(model.native_message(55,guard.WM_WINDOWPOSCHANGING,pending),(True,0))
        self.assertEqual(pending.x,2560)

    def test_actual_memory_range_validation_rejects_null_guard_readonly_or_short_pending(self):
        user=NativeUser();protection=[4];committed=[0x1000];region=[4096]
        def query(address,buffer,length):
            info=c.cast(buffer,c.POINTER(guard.MEMORYINFO)).contents
            info.base=address.value;info.size=region[0];info.state=committed[0];info.protection=protection[0]
            return c.sizeof(info)
        user.VirtualQuery=Function(query)
        with patch('ctypes.WinDLL',return_value=user):api=guard._NativeApi()
        pending=position();address=c.addressof(pending)
        self.assertEqual(api.pending(address).hwnd,55)
        for value in(0,1):
            with self.assertRaises(ValueError):api.pending(value)
        for value in(1,2,0x104):
            protection[0]=value
            with self.assertRaises(ValueError):api.pending(address)
        protection[0]=4;region[0]=c.sizeof(guard.WINDOWPOS)-1
        with self.assertRaises(ValueError):api.pending(address)
        region[0]=4096;committed[0]=0x2000
        with self.assertRaises(ValueError):api.pending(address)

    def test_real_native_callback_owns_token_before_pending_and_contains_bad_pointer_exception(self):
        class App:
            def installNativeEventFilter(self,value):self.filter=value
            def removeNativeEventFilter(self,value):pass
        api=Api(os.getpid(),threading.get_native_id());app=App()
        with patch.dict(sys.modules,fake_qt()),patch.object(guard,'_NativeApi',return_value=api):
            model=guard.create_secondary_window_guard(app,lambda w:None)
            window=Window();model.watch(window);model.bind(window,55)
            reads=[]
            def pending(address):reads.append(address);raise ValueError('Invalid writable pending range')
            api.pending=pending
            message=w.MSG();message.message=guard.WM_WINDOWPOSCHANGING;message.hWnd=99;message.lParam=1
            self.assertEqual(app.filter.nativeEventFilter(b'windows_generic_MSG',c.addressof(message)),(False,0))
            self.assertEqual(reads,[])
            message.hWnd=55;api.cookies[55]+=1
            self.assertEqual(app.filter.nativeEventFilter(b'windows_generic_MSG',c.addressof(message)),(False,0))
            self.assertEqual(reads,[])
            api.cookies[55]-=1;message.lParam=0
            self.assertEqual(app.filter.nativeEventFilter(b'windows_generic_MSG',c.addressof(message)),(True,0))
            self.assertEqual(reads,[])
            message.lParam=1
            self.assertEqual(app.filter.nativeEventFilter(b'windows_generic_MSG',c.addressof(message)),(True,0))
            self.assertEqual(reads,[1])
            api.message=lambda address:(_ for _ in()).throw(ValueError('Invalid MSG range'))
            self.assertEqual(app.filter.nativeEventFilter(b'windows_generic_MSG',0),(False,0))
            self.assertTrue(model.close()['complete'])

    def test_partial_Qt_watch_failure_disconnects_prior_signals_and_event_filter(self):
        class App:
            def installNativeEventFilter(self,value):self.filter=value
            def removeNativeEventFilter(self,value):self.filter=None
        app=App();api=Api(os.getpid(),threading.get_native_id())
        with patch.dict(sys.modules,fake_qt()),patch.object(guard,'_NativeApi',return_value=api):
            model=guard.create_secondary_window_guard(app,lambda w:None);window=Window()
            window.yChanged.connect=lambda callback:(_ for _ in()).throw(RuntimeError('Fake connect failed'))
            with self.assertRaises(RuntimeError):model.watch(window)
            self.assertEqual(window.filters,[])
            self.assertEqual(window.screenChanged.callbacks,[]);self.assertEqual(window.xChanged.callbacks,[])
            self.assertEqual(model.windows,{})
            self.assertTrue(model.close()['complete']);self.assertIsNone(app.filter)


if __name__=='__main__':unittest.main()
