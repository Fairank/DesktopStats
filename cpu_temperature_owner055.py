"""Opt-in retained lease on the existing installed Stats process.

No native work on import/construction. This never starts, signals or terminates
the owner/helper, opens COM, or queries a hardware sensor. A live retained
process handle prevents PID reuse from silently selecting a different owner.
"""
import ctypes as c
from ctypes import wintypes as w
import math
import os
from pathlib import Path


def installed_executable(environ=None):
    env=os.environ if environ is None else environ
    local=env.get('LOCALAPPDATA')
    if not local or not Path(local).is_absolute():raise ValueError('Installed Stats path is unavailable')
    return Path(local)/'Programs/DesktopStats/DesktopStats.exe'


def _same_path(a,b):return os.path.normcase(os.path.abspath(a))==os.path.normcase(os.path.abspath(b))


class InstalledOwnerLease:
    def __init__(self,pid,created,*,api_factory=None,environ=None):
        if type(pid)is not int or not 0<pid<2**32:raise ValueError('Invalid installed owner PID')
        if type(created)not in(int,float)or not math.isfinite(created)or created<=0:raise ValueError('Invalid installed owner creation time')
        self.pid,self.created=pid,float(created)
        self.expected_path=installed_executable(environ)
        self._factory=api_factory or _NativeOwnerApi
        self._api=self._handle=None
        self._terminal=False
        self.state='unopened'
        self.error=''

    def alive(self):
        if self._terminal:return False
        try:
            if self._handle is None:
                self._api=self._factory();self._handle=self._api.open(self.pid)
                facts=self._api.identity(self._handle)
                if (facts['pid']!=self.pid or not _same_path(facts['path'],self.expected_path)
                        or abs(facts['created']-self.created)>1e-4
                        or facts['same_user']is not True or facts['same_session']is not True):
                    raise ValueError('Installed CPU-cache owner identity mismatch')
            if not self._api.alive(self._handle):
                self.state='owner_exited';self._terminal=True;self._release();return False
            self.state='ready';return True
        except(OSError,ValueError,KeyError,TypeError)as error:
            self.state='owner_unavailable';self.error=type(error).__name__;self._terminal=True
            self._release();return False

    def _release(self):
        if self._handle is not None:
            handle=self._handle;self._handle=None
            try:self._api.close(handle)
            except OSError:self.error='CloseHandle'

    def close(self):
        self._terminal=True;self._release()
        if self.state!='owner_exited':self.state='closed'

    def status(self):
        return dict(state=self.state,owner_pid=self.pid,owner_creation_unix=self.created,
                    retained_handle=self._handle is not None,read_only=True,error=self.error)


class _NativeOwnerApi:
    """Only owner metadata, token equality and retained-handle liveness."""
    def __init__(self):
        if os.name!='nt':raise OSError('Windows installed-owner lease only')
        self.k=c.WinDLL('kernel32',use_last_error=True);self.a=c.WinDLL('advapi32',use_last_error=True)
        for name,args,result in(
            ('OpenProcess',[w.DWORD,w.BOOL,w.DWORD],w.HANDLE),('GetProcessId',[w.HANDLE],w.DWORD),
            ('QueryFullProcessImageNameW',[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)],w.BOOL),
            ('GetProcessTimes',[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)],w.BOOL),
            ('WaitForSingleObject',[w.HANDLE,w.DWORD],w.DWORD),('CloseHandle',[w.HANDLE],w.BOOL),
            ('GetCurrentProcess',[],w.HANDLE),('GetCurrentProcessId',[],w.DWORD),
            ('ProcessIdToSessionId',[w.DWORD,c.POINTER(w.DWORD)],w.BOOL)):
            fn=getattr(self.k,name);fn.argtypes=args;fn.restype=result
        for name,args,result in(
            ('OpenProcessToken',[w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)],w.BOOL),
            ('GetTokenInformation',[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)],w.BOOL),
            ('EqualSid',[c.c_void_p,c.c_void_p],w.BOOL)):
            fn=getattr(self.a,name);fn.argtypes=args;fn.restype=result

    def open(self,pid):
        handle=self.k.OpenProcess(0x1000|0x100000,False,pid) # QUERY_LIMITED_INFORMATION | SYNCHRONIZE
        if not handle:raise c.WinError(c.get_last_error())
        return handle

    def _token_user(self,process):
        token=w.HANDLE()
        if not self.a.OpenProcessToken(process,8,c.byref(token)):raise c.WinError(c.get_last_error())
        try:
            size=w.DWORD();self.a.GetTokenInformation(token,1,None,0,c.byref(size))
            if not 0<size.value<=4096:raise OSError('Invalid owner token information')
            data=c.create_string_buffer(size.value)
            if not self.a.GetTokenInformation(token,1,data,size,c.byref(size)):raise c.WinError(c.get_last_error())
            return data,c.cast(data,c.POINTER(c.c_void_p)).contents.value
        finally:self.k.CloseHandle(token)

    def identity(self,handle):
        pid=int(self.k.GetProcessId(handle));path=c.create_unicode_buffer(32768);length=w.DWORD(len(path))
        if not pid or not self.k.QueryFullProcessImageNameW(handle,0,path,c.byref(length)):raise c.WinError(c.get_last_error())
        times=[w.FILETIME()for _ in range(4)]
        if not self.k.GetProcessTimes(handle,*(c.byref(t)for t in times)):raise c.WinError(c.get_last_error())
        ticks=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
        owner_buf,owner_sid=self._token_user(handle);self_buf,self_sid=self._token_user(self.k.GetCurrentProcess())
        own_session,current_session=w.DWORD(),w.DWORD()
        if not(self.k.ProcessIdToSessionId(pid,c.byref(own_session))and self.k.ProcessIdToSessionId(self.k.GetCurrentProcessId(),c.byref(current_session))):raise c.WinError(c.get_last_error())
        return dict(pid=pid,path=path.value,created=(ticks-116444736000000000)/10000000,
                    same_user=bool(self.a.EqualSid(owner_sid,self_sid)),same_session=own_session.value==current_session.value)

    def alive(self,handle):
        state=self.k.WaitForSingleObject(handle,0)
        if state==0x102:return True
        if state==0:return False
        raise c.WinError(c.get_last_error())

    def close(self,handle):
        if not self.k.CloseHandle(handle):raise c.WinError(c.get_last_error())
