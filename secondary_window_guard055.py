"""V2-only, event-driven bounds for explicitly retained own top-level windows.

Cold import has no Qt/native work. Pending WINDOWPOS coordinates are clamped
before Windows applies them. NOACTIVATE must already come from the Qt window
policy/caller: Win32 ignores changes to that flag in WM_WINDOWPOSCHANGING.
WM_MOUSEACTIVATE is separately handled with MA_NOACTIVATE, without eating clicks.

https://learn.microsoft.com/windows/win32/winmsg/wm-windowposchanging
https://learn.microsoft.com/windows/win32/api/winuser/ns-winuser-windowpos
"""
import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
import os
import threading

PROPERTY='DesktopStats.SecondaryBounds055.Generation'
WM_WINDOWPOSCHANGING=0x46
WM_MOUSEACTIVATE=0x21
MA_NOACTIVATE=3
NOMOVE,NOSIZE,NOZORDER,NOACTIVATE,SHOW,HIDE=2,1,4,16,64,128


class WINDOWPOS(c.Structure):
    _fields_=[('hwnd',w.HWND),('after',w.HWND),('x',c.c_int),('y',c.c_int),
              ('cx',c.c_int),('cy',c.c_int),('flags',w.UINT)]

class MEMORYINFO(c.Structure):
    _fields_=([('base',c.c_void_p),('allocation',c.c_void_p),('allocation_protection',w.DWORD)]
        +([('_alignment',w.DWORD)]if c.sizeof(c.c_void_p)==8 else[])
        +[('size',c.c_size_t),('state',w.DWORD),('protection',w.DWORD),('type',w.DWORD)])


@dataclass(frozen=True)
class Token:
    hwnd:int
    pid:int
    thread:int
    class_name:str
    generation:int


def _rect(value):
    if not isinstance(value,(tuple,list))or len(value)!=4:
        raise ValueError('Physical bounds unavailable')
    if any(type(n)is not int for n in value)or value[2]<=value[0]or value[3]<=value[1]:
        raise ValueError('Physical bounds invalid')
    return tuple(value)


def contained(bounds,area):
    bounds,area=_rect(bounds),_rect(area)
    return area[0]<=bounds[0]<bounds[2]<=area[2]and area[1]<=bounds[1]<bounds[3]<=area[3]


def constrain(current,position,area):
    """Pure pending-frame calculation; no tolerance or primary-screen fallback."""
    flags=int(position.flags)
    if flags&HIDE:return dict(x=position.x,y=position.y,cx=position.cx,cy=position.cy,flags=flags)
    try:
        current=_rect(current)
        area=_rect(area)
        width=current[2]-current[0]if flags&NOSIZE else position.cx
        height=current[3]-current[1]if flags&NOSIZE else position.cy
        if type(width)is not int or type(height)is not int or not 0<width<=area[2]-area[0]or not 0<height<=area[3]-area[1]:
            raise ValueError('Own window cannot fit the selected work area')
        x=current[0]if flags&NOMOVE else position.x
        y=current[1]if flags&NOMOVE else position.y
        x=max(area[0],min(x,area[2]-width));y=max(area[1],min(y,area[3]-height))
        changed=flags
        if (x,y)!=(current[0],current[1]):changed&=~NOMOVE
        return dict(x=x,y=y,cx=width,cy=height,flags=changed)
    except(ValueError,TypeError):
        # These bits may be changed in WINDOWPOS. Do not pretend that adding
        # NOACTIVATE here can replace the already-created no-focus policy.
        return dict(x=position.x,y=position.y,cx=position.cx,cy=position.cy,
                    flags=(flags|NOMOVE|NOSIZE|NOZORDER|HIDE)&~SHOW)


class SecondaryWindowGuard:
    """Small injectable core: no window enumeration, polling or foreign writes."""
    def __init__(self,api,bridge,context,*,pid=None,native_thread=None):
        self.api,self.bridge,self.context=api,bridge,context
        self.pid=os.getpid()if pid is None else pid
        self.native_thread=threading.get_native_id()if native_thread is None else native_thread
        self.thread=threading.get_ident()
        self.windows={};self.tokens={};self.handles={};self.serial=0
        self.closed=False;self.errors=[];self.busy=False
        bridge.start(self)

    def _thread_ok(self):
        return not self.closed and threading.get_ident()==self.thread

    def watch(self,window):
        if not self._thread_ok():return False
        top=getattr(window,'isTopLevel',None)or getattr(window,'isWindow',None)
        if callable(top)and top()is False:return True
        key=id(window)
        if key in self.windows:return self.windows[key]is window
        if len(self.windows)>=64:return False
        self.windows[key]=window
        try:self.bridge.watch(window,self)
        except Exception:
            self.windows.pop(key,None);raise
        return True

    def bind(self,window,hwnd):
        if not self._thread_ok()or self.windows.get(id(window))is not window:return False
        old=self.tokens.get(id(window))
        if old is not None:
            if old.hwnd==hwnd and self.api.state(old)is not None:return True
            self.surface_destroyed(window)
        self.serial+=1
        try:
            token=self.api.attach(hwnd,self.serial,self.pid,self.native_thread)
            if token is None:
                self.unwatch(window);return True  # Native WS_CHILD: no desktop coordinates.
            self.tokens[id(window)]=token;self.handles[token.hwnd]=id(window)
            if self.api.state(token)is None:
                self.surface_destroyed(window);return False
            return True
        except(OSError,ValueError,RuntimeError)as error:
            self.errors=(self.errors+[type(error).__name__])[-16:];return False

    def surface_destroyed(self,window):
        token=self.tokens.get(id(window))
        if token is not None:
            self.api.release(token)
            self.tokens.pop(id(window),None);self.handles.pop(token.hwnd,None)

    def unwatch(self,window):
        if self.windows.get(id(window))is not window:return
        self.surface_destroyed(window)
        self.bridge.unwatch(window)
        self.windows.pop(id(window),None)

    def _state(self,window):
        token=self.tokens.get(id(window))
        return self.api.state(token)if token is not None else None

    def proven(self,hwnd):
        if not self._thread_ok():return False
        key=self.handles.get(hwnd);token=self.tokens.get(key)
        try:return bool(token and self.api.valid(token))
        except(OSError,ValueError,RuntimeError,TypeError):return False

    def allowed(self,window):
        if not self._thread_ok()or self.windows.get(id(window))is not window:return False
        try:
            state=self._state(window);context=self.context(window)
            return bool(state and not state.get('child')and context and context.get('admitted')is True
                and state['native_id'].casefold()==context['native_id'].casefold()
                and (state.get('minimized')or contained(state['rect'],context['work'])))
        except(OSError,ValueError,TypeError,KeyError,RuntimeError,AttributeError):return False

    def recheck(self,window):
        if not self._thread_ok()or self.busy:return
        try:
            if not window.isVisible():return
            state=self._state(window)
            if state is not None and not state.get('child')and not state.get('minimized')and not self.allowed(window):
                self.busy=True
                window.hide()  # Only the same current Qt object/token can reach this.
        except(OSError,ValueError,RuntimeError,AttributeError):
            token=self.tokens.get(id(window))
            if token is not None and self.api.valid(token):
                self.busy=True;window.hide()
        finally:self.busy=False

    def native_message(self,hwnd,message,position=None):
        if not self._thread_ok():return False,0
        key=self.handles.get(hwnd);window=self.windows.get(key)
        if window is None:return False,0
        try:state=self._state(window)
        except(OSError,ValueError,RuntimeError):
            token=self.tokens.get(id(window))
            if token is None or not self.api.valid(token):return False,0
            state=dict(rect=None,invalid=True)
        if state is None:return False,0  # A stale/reused foreign HWND is untouched.
        if state.get('child'):return False,0
        if message==WM_MOUSEACTIVATE:return True,MA_NOACTIVATE
        if message!=WM_WINDOWPOSCHANGING or position is None or int(position.hwnd or 0)!=hwnd:return False,0
        if state.get('minimized')and not position.flags&SHOW:return False,0
        try:
            context=self.context(window)
            area=context['work']if not state.get('invalid')and context and context.get('admitted')is True else None
        except(OSError,ValueError,TypeError,KeyError,RuntimeError,AttributeError):area=None
        result=constrain(state['rect'],position,area)
        for name,value in result.items():setattr(position,name,value)
        # Handling this message also avoids DefWindowProc min/max adjustment
        # moving our constrained frame outside the selected monitor afterwards.
        return True,0

    def close(self):
        if self.closed:return dict(complete=True,errors=[])
        if threading.get_ident()!=self.thread:raise RuntimeError('Close own guard on its GUI thread')
        errors=[]
        for window in tuple(self.windows.values()):
            try:
                state=self._state(window)
                if window.isVisible()and state is not None and not state.get('child'):window.hide()
                self.unwatch(window)
            except Exception as error:errors.append(type(error).__name__)
        if not errors:
            try:self.bridge.stop()
            except Exception as error:errors.append(type(error).__name__)
        if not errors:self.closed=True
        return dict(complete=not errors,errors=errors)


class _NativeApi:
    def __init__(self):
        self.user=c.WinDLL('user32',use_last_error=True)
        self.kernel=c.WinDLL('kernel32',use_last_error=True)
        self.kernel.VirtualQuery.argtypes=[c.c_void_p,c.POINTER(MEMORYINFO),c.c_size_t]
        self.kernel.VirtualQuery.restype=c.c_size_t
        for name,args,result in(
            ('GetWindowThreadProcessId',[w.HWND,c.POINTER(w.DWORD)],w.DWORD),
            ('IsWindow',[w.HWND],w.BOOL),('GetClassNameW',[w.HWND,w.LPWSTR,c.c_int],c.c_int),
            ('GetWindowLongPtrW',[w.HWND,c.c_int],c.c_ssize_t),
            ('GetPropW',[w.HWND,w.LPCWSTR],w.HANDLE),('SetPropW',[w.HWND,w.LPCWSTR,w.HANDLE],w.BOOL),
            ('RemovePropW',[w.HWND,w.LPCWSTR],w.HANDLE),('GetWindowRect',[w.HWND,c.POINTER(w.RECT)],w.BOOL),
            ('MonitorFromWindow',[w.HWND,w.DWORD],w.HANDLE),('GetMonitorInfoW',[w.HANDLE,c.c_void_p],w.BOOL),
            ('IsIconic',[w.HWND],w.BOOL)):
            fn=getattr(self.user,name);fn.argtypes=args;fn.restype=result

    def _memory(self,address,size,writable=False):
        # Query only this callback's MSG/WINDOWPOS range in our own process.
        # No ReadProcessMemory/foreign-process memory or enumeration is used.
        if type(address)is not int or address<65536:return False
        info=MEMORYINFO()
        if self.kernel.VirtualQuery(c.c_void_p(address),c.byref(info),c.sizeof(info))!=c.sizeof(info):return False
        protection=info.protection&255
        permitted=(4,8,64,128)if writable else(2,4,8,32,64,128)
        return bool(info.state==0x1000 and not info.protection&0x100 and protection in permitted
            and int(info.base or 0)<=address and address+size<=int(info.base or 0)+info.size)

    def message(self,address):
        if not self._memory(address,c.sizeof(w.MSG)):raise ValueError('Native message range unavailable')
        return w.MSG.from_buffer_copy(c.string_at(address,c.sizeof(w.MSG)))

    def pending(self,address):
        if address%c.alignment(WINDOWPOS)or not self._memory(address,c.sizeof(WINDOWPOS),True):
            raise ValueError('Own pending position range unavailable')
        return WINDOWPOS.from_address(address)

    def _identity(self,hwnd,pid,thread):
        owner=w.DWORD();tid=int(self.user.GetWindowThreadProcessId(hwnd,c.byref(owner)))
        if not tid or owner.value!=pid or tid!=thread:return None
        name=c.create_unicode_buffer(256)
        if not self.user.GetClassNameW(hwnd,name,len(name)):raise c.WinError(c.get_last_error())
        return name.value

    def attach(self,hwnd,generation,pid,thread):
        klass=self._identity(hwnd,pid,thread)
        if not klass:raise ValueError('Only the current GUI-thread owner may be retained')
        if self.user.GetWindowLongPtrW(hwnd,-16)&0x40000000:return None
        if not self.user.GetWindowLongPtrW(hwnd,-20)&0x08000000:
            raise ValueError('V2 owner lacks its pre-created no-activate window policy')
        if self.user.GetPropW(hwnd,PROPERTY):raise ValueError('Own generation property already occupied')
        if not self.user.SetPropW(hwnd,PROPERTY,c.c_void_p(generation)):raise c.WinError(c.get_last_error())
        token=Token(hwnd,pid,thread,klass,generation)
        return token

    def _current(self,token):
        return (self._identity(token.hwnd,token.pid,token.thread)==token.class_name
            and int(self.user.GetPropW(token.hwnd,PROPERTY)or 0)==token.generation)

    def valid(self,token):
        return self._current(token)and not self.user.GetWindowLongPtrW(token.hwnd,-16)&0x40000000

    def state(self,token):
        if not self._current(token):return None
        if self.user.GetWindowLongPtrW(token.hwnd,-16)&0x40000000:return dict(child=True)
        if not self.user.GetWindowLongPtrW(token.hwnd,-20)&0x08000000:
            raise ValueError('Own no-activate policy changed')
        bounds=w.RECT()
        if not self.user.GetWindowRect(token.hwnd,c.byref(bounds)):raise c.WinError(c.get_last_error())
        class Monitor(c.Structure):
            _fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD),('device',w.WCHAR*32)]
        info=Monitor();info.size=c.sizeof(info)
        handle=self.user.MonitorFromWindow(token.hwnd,0)  # No nearest/primary fallback.
        if not handle or not self.user.GetMonitorInfoW(handle,c.byref(info)):raise c.WinError(c.get_last_error())
        return dict(rect=(bounds.left,bounds.top,bounds.right,bounds.bottom),
            native_id=info.device,minimized=bool(self.user.IsIconic(token.hwnd)))

    def release(self,token):
        if not self._current(token):return  # Destroyed/reused generation: no foreign write.
        removed=int(self.user.RemovePropW(token.hwnd,PROPERTY)or 0)
        if removed!=token.generation:raise RuntimeError('Own generation release was not confirmed')


def create_secondary_window_guard(application,context):
    """Qt lifecycle bridge is loaded only for an actual admitted V2 runtime."""
    from PySide6.QtCore import QObject,QAbstractNativeEventFilter,QEvent
    from PySide6.QtGui import QPlatformSurfaceEvent
    class NativeFilter(QAbstractNativeEventFilter):
        def __init__(self,bridge):super().__init__();self.bridge=bridge
        def nativeEventFilter(self,event_type,message):
            owned=False
            try:
                if bytes(event_type)not in(b'windows_generic_MSG',b'windows_dispatcher_MSG'):return False,0
                native=self.bridge.core.api.message(int(message))
                if native.message not in(WM_WINDOWPOSCHANGING,WM_MOUSEACTIVATE):return False,0
                hwnd=int(native.hWnd or 0)
                owned=self.bridge.core.proven(hwnd)
                if not owned:return False,0
                if native.message==WM_WINDOWPOSCHANGING:
                    if not native.lParam:return True,0
                    position=self.bridge.core.api.pending(int(native.lParam))
                else:position=None
                return self.bridge.core.native_message(hwnd,int(native.message),position)
            except(OSError,ValueError,TypeError,RuntimeError,OverflowError,AttributeError):
                # Consume an invalid own message instead of forwarding a bad
                # lParam to Qt/DefWindowProc. Never dereference a foreign one.
                return owned,0
    class Watcher(QObject):
        def __init__(self,bridge):super().__init__();self.bridge=bridge
        def eventFilter(self,window,event):
            if id(window)not in self.bridge.core.windows:return False
            try:
                if event.type()==QEvent.PlatformSurface:
                    if event.surfaceEventType()==QPlatformSurfaceEvent.SurfaceCreated:
                        hwnd=int(window.winId())
                        if not self.bridge.core.bind(window,hwnd)and self.bridge.core.proven(hwnd):window.hide()
                    else:self.bridge.core.surface_destroyed(window)
                elif event.type()in(QEvent.Show,QEvent.Move,QEvent.Resize,QEvent.WindowStateChange):
                    self.bridge.core.recheck(window)
            except(OSError,ValueError,TypeError,RuntimeError,OverflowError,AttributeError)as error:
                self.bridge.core.errors=(self.bridge.core.errors+[type(error).__name__])[-16:]
            return False
    class Bridge:
        def __init__(self):self.connections={};self.native=NativeFilter(self);self.watcher=Watcher(self)
        def start(self,core):self.core=core;application.installNativeEventFilter(self.native)
        def watch(self,window,core):
            window.installEventFilter(self.watcher);callbacks=[]
            self.connections[id(window)]=callbacks
            try:
                for name in('screenChanged','xChanged','yChanged','widthChanged','heightChanged'):
                    signal=getattr(window,name,None)
                    if signal is not None:
                        callback=lambda *args,owner=window:core.recheck(owner)
                        signal.connect(callback);callbacks.append((signal,callback))
                callback=lambda *args,owner=window:core.unwatch(owner)
                window.destroyed.connect(callback);callbacks.append((window.destroyed,callback))
            except Exception:
                self.unwatch(window);raise
        def unwatch(self,window):
            for signal,callback in self.connections.pop(id(window),()):
                try:signal.disconnect(callback)
                except (RuntimeError,TypeError):pass  # Qt already destroyed this exact signal.
            try:window.removeEventFilter(self.watcher)
            except RuntimeError:pass
        def stop(self):application.removeNativeEventFilter(self.native)
    return SecondaryWindowGuard(_NativeApi(),Bridge(),context)
