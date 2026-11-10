"""Explicit independent second-version session; no native work on import.

Bootstrap runs before stats_config/native_ipc imports. It owns a separate data
directory and existing environment-profile IPC namespace. CPU-owner selection
is an explicit transient launch argument, never a saved/default PID.
"""
from dataclasses import dataclass
import copy
import json
import math
import os
from pathlib import Path

MODE_ENV='DESKTOP_STATS_SECONDARY055'
SCREEN_ENV='DESKTOP_STATS_SECONDARY_SCREEN055'
OWNER_ENV='DESKTOP_STATS_SECONDARY_CPU_OWNER055'
MARKER='secondary-session055.json'
LABEL='DesktopStats 第二版'
APPLICATION_ID='Fairank.DesktopStats.Secondary'
_screen_identity_adapter=None


def active(environ=None):return (os.environ if environ is None else environ).get(MODE_ENV)=='1'
def target_native_id(environ=None):return (os.environ if environ is None else environ).get(SCREEN_ENV,'')
def display_name(environ=None):
    if not active(environ):return'Desktop Stats'
    from product_version import VERSION
    return LABEL+' · '+VERSION


def screen_native_id(screen,*,adapter=None):
    """Resolve the QScreen's real HMONITOR, never its friendly display label."""
    global _screen_identity_adapter
    if adapter is None:
        if _screen_identity_adapter is None:
            from top_bar_runtime import WindowsTopBarAdapter
            _screen_identity_adapter=WindowsTopBarAdapter()
        adapter=_screen_identity_adapter
    value=adapter.screen_identity(screen).native_id
    if type(value)is not str or not value:raise ValueError('Native screen identity unavailable')
    return value


def apply_process_identity(*,environ=None,setter=None):
    """Give only the opt-in current process its own Windows taskbar identity."""
    if not active(environ):return False
    if setter is None:
        import ctypes as c
        shell=c.WinDLL('shell32',use_last_error=True)
        setter=shell.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes=[c.c_wchar_p];setter.restype=c.c_long
    if setter(APPLICATION_ID)!=0:raise OSError('Cannot select second-version process identity')
    return True


def parse_owner(value):
    if not isinstance(value,str)or len(value)>96:raise ValueError('CPU cache owner requires PID:creation-time')
    pieces=value.split(':')
    if len(pieces)!=2 or not pieces[0].isascii()or not pieces[0].isdigit():raise ValueError('CPU cache owner requires PID:creation-time')
    pid=int(pieces[0]);created=float(pieces[1])
    if not 0<pid<2**32 or not math.isfinite(created)or created<=0:raise ValueError('Invalid CPU cache owner identity')
    return dict(pid=pid,created=created)


def _same(a,b):return os.path.normcase(os.path.abspath(a))==os.path.normcase(os.path.abspath(b))
def _no_links(path):
    for part in(path,*path.parents):
        try:info=part.lstat()
        except FileNotFoundError:continue
        if part.is_symlink()or getattr(info,'st_file_attributes',0)&0x400:raise ValueError('Secondary profile cannot use a link or junction')


def primary_profile(environ):
    """Read installed profile selection only; no profile mkdir/migration."""
    from profile_paths import resolve_profile_paths
    from cpu_temperature_owner055 import installed_executable
    clean=dict(environ);clean.pop('DESKTOP_STATS_DATA',None)
    executable=installed_executable(clean)
    if not executable.parent.exists():return Path(clean['LOCALAPPDATA'])/'DesktopStats'
    return resolve_profile_paths(environ=clean,frozen=True,executable=executable).directory


def validate_directory(directory,primary):
    directory=Path(directory)
    if not directory.is_absolute():raise ValueError('Secondary profile must be absolute')
    _no_links(directory);selected=directory.resolve();original=Path(primary).resolve()
    if _same(selected,original)or selected.is_relative_to(original)or original.is_relative_to(selected):
        raise ValueError('Secondary profile collides with the original profile')
    marker=directory/MARKER
    if directory.exists():
        if not directory.is_dir():raise ValueError('Secondary profile is not a directory')
        if marker.exists():
            _no_links(marker);raw=marker.read_bytes()
            if len(raw)>512 or json.loads(raw)!={'schema':1,'role':'secondary'}:raise ValueError('Secondary profile marker does not match')
        elif any(directory.iterdir()):raise ValueError('Refusing to adopt an existing unmarked profile')
    return directory


@dataclass
class SecondarySession:
    directory:Path
    requested_screen:str|None
    cache_requested:bool
    target_screen:str=''
    fresh:bool=True

    def select_screen(self,application,environ=None,*,identity_reader=None):
        env=os.environ if environ is None else environ
        screens=list(application.screens());primary=application.primaryScreen()
        native=identity_reader or screen_native_id
        identities=[(screen,native(screen))for screen in screens]
        if self.requested_screen:
            requested=self.requested_screen.casefold()
            candidates=[(screen,value)for screen,value in identities if value.casefold()==requested]
        else:candidates=[(screen,value)for screen,value in identities if screen is not primary]
        if not candidates or self.requested_screen and len(candidates)!=1:raise ValueError('Second-version target screen is unavailable; primary fallback is disabled')
        target,native_id=candidates[0]
        if target is primary:raise ValueError('A nonprimary second screen is required')
        if sum(value.casefold()==native_id.casefold()for _,value in identities)!=1:
            raise ValueError('Second-version native screen identity is not unique')
        self.target_screen=native_id;env[SCREEN_ENV]=self.target_screen
        return target

    def profile_value(self,value):
        if not self.target_screen:raise ValueError('Secondary target screen is not validated')
        result=copy.deepcopy(value)
        result['autostart']=False;result['cpu_temperature_prompt_on_start']=False
        if self.fresh:
            # First session is topbar-only. Subsequent V2 widget preferences
            # stay independent and retain the user's own selection.
            result['visible']=False
            items=result['top_bar'].get('items',[])
            for item in items:
                if item.get('metric')in('cpu_usage','gpu_usage'):
                    metrics=['cpu_usage','cpu_temp','cpu_power']if item['metric']=='cpu_usage'else['gpu_usage','gpu_temp','gpu_power']
                    item.setdefault('prefs',{}).update(style='icon_value',metrics=metrics)
            if any(item.get('metric')=='cpu_usage'for item in items):
                result['top_bar']['items']=[item for item in items if item.get('metric')!='cpu_temp']
        result['top_bar']['enabled']=True;result['top_bar']['monitor_mode']='selected';result['top_bar']['screens']=[self.target_screen]
        return result


def configure(args,*,environ=None,primary=None):
    """Own-profile setup only; never imports UI, installer or native IPC."""
    env=os.environ if environ is None else environ
    if not getattr(args,'secondary',False):return None
    if getattr(args,'install',False)or getattr(args,'uninstall',False):raise ValueError('第二版不安装或卸载原版。')
    owner=getattr(args,'share_installed_cpu_cache',None)
    descriptor=parse_owner(owner)if owner is not None else None
    local=env.get('LOCALAPPDATA')
    if not local or not Path(local).is_absolute():raise ValueError('Secondary data location is unavailable')
    requested=getattr(args,'secondary_profile',None)
    directory=validate_directory(Path(requested)if requested else Path(local)/'DesktopStats-Secondary',primary or primary_profile(env))
    # The normal instance's IPC key remains its legacy path even when its
    # installed profile pointer selects a different storage directory.
    user=Path(env.get('USERPROFILE',Path.home()))
    reserved=user/'AppData/Local/DesktopStats'
    if _same(directory,reserved):raise ValueError('Secondary profile collides with the original IPC namespace')
    fresh=not(directory/'preferences.json').exists()
    directory.mkdir(parents=True,exist_ok=True)
    marker=directory/MARKER
    if not marker.exists():marker.write_text('{"schema":1,"role":"secondary"}\n',encoding='utf-8')
    env['DESKTOP_STATS_DATA']=str(directory);env[MODE_ENV]='1';env.pop(SCREEN_ENV,None);env.pop(OWNER_ENV,None)
    if descriptor is not None:env[OWNER_ENV]=json.dumps(descriptor,separators=(',',':'))
    return SecondarySession(directory,getattr(args,'secondary_screen',None),descriptor is not None,fresh=fresh)


def status(environ=None):
    env=os.environ if environ is None else environ
    return dict(mode='secondary'if active(env)else'primary',label=display_name(env),
        target_screen=target_native_id(env),independent_profile=active(env),
        cpu_cache_requested=bool(active(env)and env.get(OWNER_ENV)),temperature_bridge_launch_allowed=not active(env),
        autostart_allowed=not active(env),installation_allowed=not active(env))


def temperature_reader(*,environ=None,reader_factory=None,lease_factory=None):
    """Lazy constructor; disabled/self-check paths never construct an owner API."""
    env=os.environ if environ is None else environ
    if reader_factory is None:
        from cpu_temperature import AsusCpuTemperature
        reader_factory=AsusCpuTemperature
    if not active(env):return reader_factory()
    if env.get('DESKTOP_STATS_CPU_BRIDGE_DISABLED')=='1'or not env.get(OWNER_ENV):return reader_factory(enabled=False)
    try:
        descriptor=json.loads(env[OWNER_ENV])
        if set(descriptor)!={'pid','created'}:raise ValueError('Unexpected shared CPU owner fields')
        if lease_factory is None:
            from cpu_temperature_owner055 import InstalledOwnerLease
            lease_factory=InstalledOwnerLease
        lease=lease_factory(descriptor['pid'],descriptor['created'],environ=env)
        return reader_factory(owner_lease=lease)
    except(ValueError,TypeError,KeyError):return reader_factory(enabled=False)
