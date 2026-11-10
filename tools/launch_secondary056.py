"""Independent ordinary V2 source entry. Default is preparation, never launch.

No Runtime hook, installer, extra listener, helper bridge or process supervisor.
The source root is fixed relative to tools; there is no CLI override.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import stat
import sys
import time
from types import SimpleNamespace
import uuid

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]  # Fixed tools/ location; no CLI override.
MODE_ENV='DESKTOP_STATS_SECONDARY055'
SCREEN_ENV='DESKTOP_STATS_SECONDARY_SCREEN055'
OWNER_ENV='DESKTOP_STATS_SECONDARY_CPU_OWNER055'
PROFILE_NAME='DesktopStats-Secondary'
RECEIPT_NAME='launcher-request056.json'
MAX_RECEIPT=4096


class EntryError(ValueError):pass


def arguments(argv):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    action=parser.add_mutually_exclusive_group()
    for name in('prepare','run','status','quit'):action.add_argument('--quit-clean'if name=='quit'else'--'+name,dest=name,action='store_true')
    parser.add_argument('--screen',metavar='NATIVE_ID',help='Explicit nonprimary native monitor; no fallback')
    parser.add_argument('--no-shared-cache',action='store_true')
    value=parser.parse_args(argv)
    if (value.status or value.quit)and(value.screen is not None or value.no_shared_cache):
        parser.error('屏幕和温度来源选项只用于启动。')
    return value


def clean_environment(environ,*,require_guard=True):
    value=dict(environ)
    if require_guard and value.get('DESKTOP_STATS_FULLSCREEN_GUARD_DISABLED')=='1':
        raise EntryError('第二版不会在全屏保护被禁用时启动。')
    for name in('DESKTOP_STATS_DATA',MODE_ENV,SCREEN_ENV,OWNER_ENV,
                 'QT_QPA_PLATFORM','QT_QUICK_BACKEND','QSG_RHI_BACKEND','QT_OPENGL'):
        value.pop(name,None)
    # An explicit CPU-disabled setting is intentionally retained.
    return value


def select_target(monitors,requested=None,saved=None):
    if not isinstance(monitors,list)or not 1<=len(monitors)<=16:raise EntryError('无法确认显示器。')
    known={};primary=0
    for row in monitors:
        name=row.get('native_id');flag=row.get('primary')
        if type(name)is not str or not name or type(flag)is not bool:raise EntryError('显示器身份不明确。')
        key=name.casefold()
        if key in known:raise EntryError('显示器身份重复。')
        known[key]=row;primary+=int(flag)
    if primary!=1:raise EntryError('无法确认主显示器。')
    selected=requested if requested is not None else saved
    if selected is not None:
        if type(selected)is not str or not selected:raise EntryError('第二版目标屏幕无效。')
        row=known.get(selected.casefold())
        if row is None or row['primary']:raise EntryError('目标屏幕不可用或已是主屏；不会自动换屏。')
        return row['native_id']
    choices=[row for row in monitors if not row['primary']]
    if len(choices)!=1:raise EntryError('请明确选择一个非主显示器；不会取多屏中的第一个。')
    return choices[0]['native_id']


def ready_status(value):
    if not isinstance(value,dict)or value.get('ok')is not True:return False
    mode=value.get('application_mode',{})
    return bool(type(value.get('pid'))is int and value['pid']>0 and isinstance(mode,dict)
        and mode.get('mode')=='secondary'and mode.get('independent_profile')is True
        and mode.get('installation_allowed')is False and mode.get('temperature_bridge_launch_allowed')is False)


def source_decision(lease,disabled):
    if disabled:return 'disabled','已禁用共享温度；不会启动桥接。'
    if lease is None:return 'unavailable','原版未运行或无法验证，第二版无 CPU 温度来源；不会启动桥接。'
    return 'validated_owner_requested','已验证原版进程，已请求只读复用；实际温度以第二版读数为准。'


class StartupMutex:
    """One noninheritable local mutex, zero wait; no polling or UI work."""
    def __init__(self,name,kernel=None):
        self.name=name;self.handle=None;self.owned=False
        self.kernel=kernel
    def acquire(self):
        if self.kernel is None:
            self.kernel=c.WinDLL('kernel32',use_last_error=True)
            for name,args,result in(
                ('CreateMutexW',[c.c_void_p,w.BOOL,w.LPCWSTR],w.HANDLE),
                ('WaitForSingleObject',[w.HANDLE,w.DWORD],w.DWORD),
                ('ReleaseMutex',[w.HANDLE],w.BOOL),('CloseHandle',[w.HANDLE],w.BOOL)):
                fn=getattr(self.kernel,name);fn.argtypes=args;fn.restype=result
        self.handle=self.kernel.CreateMutexW(None,False,self.name)
        if not self.handle:raise EntryError('无法建立第二版启动互斥。')
        result=self.kernel.WaitForSingleObject(self.handle,0)
        if result in(0,0x80):self.owned=True;return True
        if result==0x102:return False
        self.close();raise EntryError('无法确认第二版启动互斥状态。')
    def close(self):
        if self.handle is None:return
        handle=self.handle;self.handle=None
        try:
            if self.owned and not self.kernel.ReleaseMutex(handle):raise OSError('ReleaseMutex')
        finally:
            self.owned=False
            if not self.kernel.CloseHandle(handle):raise OSError('CloseHandle')


class Services:
    """Startup-only I/O. Native/profile/Qt imports are all lazy."""
    def __init__(self):self.root=ROOT;self.environ=dict(os.environ);self._ipc_core=None
    def source_paths(self):
        paths=[str(self.root),str(self.root/'.venv/Lib/site-packages')]
        for value in reversed(paths):
            if value not in sys.path:sys.path.insert(0,value)
    def locations(self,env):
        self.source_paths()
        from secondary_mode055 import primary_profile,validate_directory
        local=env.get('LOCALAPPDATA')
        if not local or not Path(local).is_absolute():raise EntryError('无法确认第二版独立目录。')
        original=primary_profile(env)
        profile=validate_directory(Path(local)/PROFILE_NAME,original)
        # Validate the lexical path before resolving it; never hide a junction.
        return profile.resolve(),original
    def validate_source(self):
        pythonw=Path(sys.base_prefix)/'pythonw.exe'
        if (not pythonw.is_file()or not(self.root/'app.py').is_file()
                or not(self.root/'.venv/Lib/site-packages').is_dir()):
            raise EntryError('本地开发运行环境不完整；不会安装依赖或调用原安装版。')
        if os.path.normcase(str(Path(sys.executable).resolve()))!=os.path.normcase(str(pythonw.resolve())):
            raise EntryError('常用启动入口必须直接使用已确认的 base pythonw。')
    def exists(self,profile):return profile.is_dir()
    def _read(self,path,cap):
        from secondary_mode055 import _no_links
        _no_links(path);before=path.stat()
        if not stat.S_ISREG(before.st_mode)or before.st_size>cap:raise EntryError('文件类型或大小无效。')
        with path.open('rb')as stream:
            opened=os.fstat(stream.fileno());raw=stream.read(cap+1);after_read=os.fstat(stream.fileno())
        after=path.stat()
        signatures=[(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns)for x in(before,opened,after_read,after)]
        if len(raw)>cap or len(set(signatures))!=1:raise EntryError('读取时文件发生变化。')
        return raw
    def saved_target(self,profile):
        path=profile/'preferences.json'
        if not path.exists():return None
        def pairs(rows):
            result={}
            for key,value in rows:
                if key in result:raise EntryError('独立配置包含重复字段。')
                result[key]=value
            return result
        value=json.loads(self._read(path,1024*1024).decode('utf-8-sig'),object_pairs_hook=pairs)
        if not isinstance(value,dict):raise EntryError('独立配置格式无效。')
        bar=value.get('top_bar',{})
        if not isinstance(bar,dict):raise EntryError('独立顶部栏配置格式无效。')
        if bar.get('monitor_mode')!='selected':return None
        screens=bar.get('screens',[])
        if not isinstance(screens,list)or len(screens)>1:raise EntryError('保存的第二版目标屏幕不唯一。')
        return screens[0]if screens else None
    def monitors(self):
        class Info(c.Structure):
            _fields_=[('size',w.DWORD),('bounds',w.RECT),('work',w.RECT),('flags',w.DWORD),('device',w.WCHAR*32)]
        user=c.WinDLL('user32',use_last_error=True)
        callback_type=c.WINFUNCTYPE(w.BOOL,w.HANDLE,w.HDC,c.POINTER(w.RECT),w.LPARAM)
        user.GetMonitorInfoW.argtypes=[w.HANDLE,c.POINTER(Info)];user.GetMonitorInfoW.restype=w.BOOL
        user.EnumDisplayMonitors.argtypes=[w.HDC,c.POINTER(w.RECT),callback_type,w.LPARAM]
        user.EnumDisplayMonitors.restype=w.BOOL
        rows=[];errors=[]
        def collect(handle,dc,rect,param):
            try:
                if len(rows)>=16:raise EntryError('显示器数量超出入口上限。')
                info=Info();info.size=c.sizeof(info)
                if not user.GetMonitorInfoW(handle,c.byref(info)):raise OSError('GetMonitorInfoW')
                rows.append(dict(native_id=info.device,primary=bool(info.flags&1)));return True
            except Exception as error:errors.append(type(error).__name__);return False
        callback=callback_type(collect)
        if not user.EnumDisplayMonitors(None,None,callback,0)or errors:raise EntryError('无法确认本机显示器。')
        return rows
    def mutex(self,profile):
        digest=hashlib.sha256(str(profile).encode()).hexdigest()[:20]
        return StartupMutex('Local\\DesktopStats.SecondaryLaunch.'+digest)
    def owner(self,original,env):
        from cpu_temperature_owner055 import InstalledOwnerLease
        import psutil
        lease=None
        try:
            raw=self._read(original/'app.pid',32).strip()
            if not raw or not raw.isascii()or not raw.isdigit():return None
            pid=int(raw)
            if not 0<pid<2**32:return None
            created=psutil.Process(pid).create_time()
            lease=InstalledOwnerLease(pid,created,environ=env)
            if not lease.alive():lease.close();return None
            return lease
        except(OSError,ValueError,psutil.Error):
            if lease is not None:lease.close()
            return None
    def bootstrap(self,profile,original,screen,descriptor,env):
        from secondary_mode055 import configure
        args=SimpleNamespace(secondary=True,install=False,uninstall=False,secondary_profile=str(profile),
            secondary_screen=screen,share_installed_cpu_cache=descriptor)
        session=configure(args,environ=env,primary=original)
        if session.directory.resolve()!=profile:raise EntryError('独立目录校验改变。')
    def receipt(self,profile,value):
        from secondary_mode055 import _no_links
        raw=(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode('utf8')
        if len(raw)>MAX_RECEIPT:raise EntryError('启动请求记录超出上限。')
        target=profile/RECEIPT_NAME
        _no_links(target)
        if target.exists()and not target.is_file():raise EntryError('启动请求记录类型无效。')
        temporary=profile/('launcher-request056-'+uuid.uuid4().hex+'.pending')
        created=None
        try:
            with temporary.open('xb')as stream:
                created=os.fstat(stream.fileno());stream.write(raw);stream.flush()
            _no_links(profile);_no_links(target);temporary.replace(target)
        finally:
            if created is not None and temporary.exists():
                info=temporary.lstat()
                if (info.st_dev,info.st_ino)==(created.st_dev,created.st_ino):temporary.unlink()
    def clock(self):return time.time()
    def execute(self,arguments,env):
        self.source_paths()
        saved_env=dict(os.environ);saved_argv=sys.argv[:]
        os.environ.clear();os.environ.update(env)
        sys.argv=[str(self.root/'app.py'),*arguments]
        try:
            try:runpy.run_path(str(self.root/'app.py'),run_name='__main__');return 0
            except SystemExit as error:
                if error.code is None:return 0
                if type(error.code)is int:return error.code
                raise EntryError('第二版启动失败；详情见独立 app.log。')from error
        finally:sys.argv=saved_argv;os.environ.clear();os.environ.update(saved_env)
    def ipc(self,profile,command,env):
        # Only status/quit processes take this branch. Never create QCoreApp
        # in the run process before the product creates its QApplication.
        self.source_paths();os.environ.clear();os.environ.update(env)
        os.environ['DESKTOP_STATS_DATA']=str(profile);os.environ[MODE_ENV]='1'
        from PySide6.QtCore import QCoreApplication
        from native_ipc import send
        self._ipc_core=QCoreApplication.instance()or QCoreApplication([])
        return send({'command':command},timeout=300)


def main(argv=None,services=None):
    args=arguments(sys.argv[1:]if argv is None else argv)
    if not(args.run or args.status or args.quit):
        return dict(prepared_only=True,launched=False,mode='secondary',profile_name=PROFILE_NAME,
            explicit_run_required=True,no_install=True,no_UAC=True,source_entry='app.py --secondary',
            no_arbitrary_executable_or_profile=True,screen_policy='explicit/saved unique nonprimary or sole nonprimary',
            default_cache='fresh validated existing owner only; no bridge',persistent_run=True)
    service=services or Services();env=clean_environment(service.environ,require_guard=args.run)
    profile,original=service.locations(env)
    if args.status or args.quit:
        if not service.exists(profile):return dict(ok=True,running=False,profile_created=False)
        value=service.ipc(profile,'status',env)
        if not ready_status(value):return dict(ok=False,running=None,reason='instance_unknown',quit_requested=False)
        if not args.quit:
            return dict(ok=True,running=True,version=value.get('version'),mode='secondary',
                target_screen=value['application_mode'].get('target_screen'),dirty=value.get('dirty'),
                cpu_cache_requested=value['application_mode'].get('cpu_cache_requested'),
                temperature_health_verified=False)
        if value.get('dirty')is not False:return dict(ok=False,quit_requested=False,reason='dirty_or_unknown')
        reply=service.ipc(profile,'quit_if_clean',env)
        accepted=isinstance(reply,dict)and reply.get('ok')is True and reply.get('quitting')is True and reply.get('dirty')is False
        return dict(ok=accepted,quit_requested=accepted,force=False,termination_verified=False,
            reason=None if accepted else'clean_exit_refused')
    service.validate_source()
    saved=None if args.screen is not None else service.saved_target(profile)
    screen=select_target(service.monitors(),args.screen,saved)
    mutex=service.mutex(profile);lease=None
    try:
        if not mutex.acquire():return dict(ok=False,launched=False,reason='already_running_or_starting',running_verified=False)
        disabled=args.no_shared_cache or env.get('DESKTOP_STATS_CPU_BRIDGE_DISABLED')=='1'
        if not disabled:lease=service.owner(original,env)
        descriptor=None if lease is None else f'{lease.pid}:{lease.created:.7f}'
        state,detail=source_decision(lease,disabled)
        service.bootstrap(profile,original,screen,descriptor,env)
        service.receipt(profile,dict(schema=1,state='requested',running_verified=False,mode='secondary',
            requested_utc=datetime.fromtimestamp(service.clock(),timezone.utc).isoformat(),target_screen=screen,
            temperature_source_decision=state,detail=detail,original_owner_descriptor_saved=False,
            new_bridge=False,UAC=False,installed=False))
        # Product constructs its own retained, revalidated read-only lease. Do
        # not leave this validation handle as extra steady-state ownership.
        if lease is not None:lease.close();lease=None
        app_arguments=['--secondary','--secondary-profile',str(profile),'--secondary-screen',screen,'--background']
        if descriptor is not None:app_arguments+=['--share-installed-cpu-cache',descriptor]
        env.update(PYTHONPATH=str(service.root/'.venv/Lib/site-packages'),PYTHONUTF8='1',
            PYTHONDONTWRITEBYTECODE='1',QML_DISABLE_DISK_CACHE='1')
        code=service.execute(app_arguments,env)
        return dict(ok=code==0,request_completed=True,app_exit_code=code,running_verified=False)
    finally:
        if lease is not None:lease.close()
        mutex.close()


if __name__=='__main__':
    try:
        result=main()
        if sys.stdout is not None:print(json.dumps(result,ensure_ascii=False))
        raise SystemExit(0 if result.get('ok',True)else 1)
    except(Exception,)as error:
        if sys.stderr is not None:print('第二版入口：'+str(error),file=sys.stderr)
        raise SystemExit(1)
