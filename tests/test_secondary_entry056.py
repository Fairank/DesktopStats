"""Injected entry controls; only one private fixture uses own temporary files."""
import io
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

from tools import launch_secondary056 as entry

TARGET=r'\\.\DISPLAY37'
PRIMARY=r'\\.\DISPLAY36'
OTHER=r'\\.\DISPLAY38'
MONITORS=[dict(native_id=PRIMARY,primary=True),dict(native_id=TARGET,primary=False)]


class Mutex:
    def __init__(self,service):self.service=service;self.owned=False
    def acquire(self):
        self.service.calls.append('mutex-acquire');self.owned=not self.service.busy;return self.owned
    def close(self):self.service.calls.append('mutex-close');self.owned=False


class Lease:
    pid=12345;created=1234567890.125
    def __init__(self,service):self.service=service;self.closed=False
    def close(self):self.closed=True;self.service.calls.append('lease-close')


class Service:
    def __init__(self):
        self.root=Path('D:/Source/Stats');self.profile=Path('D:/User/Local/DesktopStats-Secondary')
        self.original=Path('D:/User/Local/DesktopStats');self.environ={
            'LOCALAPPDATA':'D:/User/Local','DESKTOP_STATS_DATA':'D:/wrong',entry.OWNER_ENV:'old',
            'QT_QPA_PLATFORM':'offscreen'}
        self.calls=[];self.busy=False;self.available_owner=True;self.profile_exists=True
        self.saved=None;self.rows=list(MONITORS);self.receipts=[];self.executions=[]
        self.lock=Mutex(self);self.lease=None;self.run_error=None;self.bootstrap_error=None
        self.replies=[dict(ok=True,pid=200,dirty=False,version='test',application_mode=dict(
            mode='secondary',independent_profile=True,installation_allowed=False,
            temperature_bridge_launch_allowed=False,target_screen=TARGET,cpu_cache_requested=True))]
    def locations(self,env):
        self.calls.append('locations');assert entry.OWNER_ENV not in env and'DESKTOP_STATS_DATA'not in env
        return self.profile,self.original
    def exists(self,profile):self.calls.append('exists');return self.profile_exists
    def validate_source(self):self.calls.append('source')
    def saved_target(self,profile):self.calls.append('saved');return self.saved
    def monitors(self):self.calls.append('monitors');return self.rows
    def mutex(self,profile):self.calls.append('mutex');return self.lock
    def owner(self,original,env):
        self.calls.append('owner')
        if not self.available_owner:return None
        self.lease=Lease(self);return self.lease
    def bootstrap(self,profile,original,screen,descriptor,env):
        self.calls.append('bootstrap')
        if self.bootstrap_error:raise self.bootstrap_error
        assert profile==self.profile and original==self.original and screen==TARGET
        env['DESKTOP_STATS_DATA']=str(profile);env[entry.MODE_ENV]='1'
        self.descriptor=descriptor
    def receipt(self,profile,value):self.calls.append('receipt');self.receipts.append((profile,dict(value)))
    def clock(self):return 1234567890
    def execute(self,args,env):
        self.calls.append('execute');assert self.lock.owned
        assert self.lease is None or self.lease.closed,'No extra owner handle during product event loop'
        self.executions.append((list(args),dict(env)))
        if self.run_error:raise self.run_error
        return 0
    def ipc(self,profile,command,env):
        self.calls.append('ipc:'+command);assert profile==self.profile
        return self.replies.pop(0)


class Kernel:
    def __init__(self,result):self.result=result;self.calls=[]
    def CreateMutexW(self,attributes,owner,name):
        self.calls.append(('create',attributes,owner,name));return 99
    def WaitForSingleObject(self,handle,timeout):self.calls.append(('wait',handle,timeout));return self.result
    def ReleaseMutex(self,handle):self.calls.append(('release',handle));return True
    def CloseHandle(self,handle):self.calls.append(('close',handle));return True


class SecondaryEntry056Tests(unittest.TestCase):
    def test_default_is_cold_prepare_and_cli_cannot_select_profile_or_executable(self):
        service=Service()
        with patch.object(entry,'Services',side_effect=AssertionError('Default constructed I/O')):
            result=entry.main([],service)
        self.assertTrue(result['prepared_only']);self.assertEqual(service.calls,[])
        for args in(['--exe','DesktopStats.exe'],['--profile','D:/User/Local/DesktopStats'],
                    ['--run','--quit-clean'],['--quit'],['--ru'],['--status','--screen',TARGET]):
            with self.subTest(args=args),patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):entry.arguments(args)

    def test_monitor_identity_saved_choice_and_ambiguity_never_fall_back_to_primary(self):
        self.assertEqual(entry.select_target(MONITORS),TARGET)
        self.assertEqual(entry.select_target(MONITORS,saved=TARGET.lower()),TARGET)
        three=MONITORS+[dict(native_id=OTHER,primary=False)]
        self.assertEqual(entry.select_target(three,requested=OTHER,saved=PRIMARY),OTHER)
        for rows,requested,saved in((three,None,None),(MONITORS,None,PRIMARY),
                (MONITORS,None,OTHER),(MONITORS,PRIMARY,None),
                (MONITORS+[dict(native_id=TARGET.lower(),primary=False)],TARGET,None),
                ([dict(native_id=TARGET,primary=False)],None,None)):
            with self.subTest(rows=rows,requested=requested,saved=saved),self.assertRaises(entry.EntryError):
                entry.select_target(rows,requested,saved)

    def test_real_dispatch_requests_only_independent_app_and_never_persists_owner_descriptor(self):
        for mode in('ready','missing','disabled','opt-out'):
            with self.subTest(mode=mode):
                service=Service();args=['--run','--screen',TARGET]
                if mode=='missing':service.available_owner=False
                if mode=='disabled':service.environ['DESKTOP_STATS_CPU_BRIDGE_DISABLED']='1'
                if mode=='opt-out':args+=['--no-shared-cache']
                result=entry.main(args,service)
                self.assertTrue(result['ok']);self.assertFalse(result['running_verified'])
                self.assertEqual(len(service.executions),1);self.assertEqual(len(service.receipts),1)
                arguments,env=service.executions[0];profile,receipt=service.receipts[0]
                self.assertEqual(arguments[:5],['--secondary','--secondary-profile',str(service.profile),'--secondary-screen',TARGET])
                self.assertIn('--background',arguments)
                self.assertEqual(profile,service.profile);self.assertEqual(env['DESKTOP_STATS_DATA'],str(service.profile))
                self.assertNotIn('QT_QPA_PLATFORM',env);self.assertEqual(env['PYTHONDONTWRITEBYTECODE'],'1')
                self.assertEqual(receipt['state'],'requested');self.assertFalse(receipt['running_verified'])
                text=json.dumps(receipt)
                self.assertNotIn('12345',text);self.assertNotIn('1234567890.125',text)
                self.assertFalse(receipt['new_bridge']);self.assertFalse(receipt['UAC'])
                self.assertFalse(service.lock.owned);self.assertNotIn('saved',service.calls)
                if mode=='ready':
                    self.assertEqual(arguments[-2:],['--share-installed-cpu-cache','12345:1234567890.1250000'])
                    self.assertLess(service.calls.index('lease-close'),service.calls.index('execute'))
                else:
                    self.assertNotIn('--share-installed-cpu-cache',arguments)
                    if mode in('disabled','opt-out'):self.assertNotIn('owner',service.calls)
                    self.assertIn(receipt['temperature_source_decision'],('disabled','unavailable'))
        service=Service();service.busy=True
        result=entry.main(['--run'],service)
        self.assertFalse(result['running_verified']);self.assertEqual(service.receipts,[])
        self.assertNotIn('owner',service.calls);self.assertNotIn('bootstrap',service.calls);self.assertNotIn('execute',service.calls)
        for point in('bootstrap','run'):
            service=Service();setattr(service,point+'_error',RuntimeError(point))
            with self.assertRaisesRegex(RuntimeError,point):entry.main(['--run'],service)
            self.assertTrue(service.lease.closed);self.assertFalse(service.lock.owned)
        service=Service();service.environ['DESKTOP_STATS_FULLSCREEN_GUARD_DISABLED']='1'
        with self.assertRaises(entry.EntryError):entry.main(['--run'],service)
        self.assertEqual(service.calls,[])

    def test_status_and_clean_quit_use_only_own_ipc_and_refuse_dirty_or_unknown(self):
        service=Service();service.profile_exists=False
        self.assertFalse(entry.main(['--status'],service)['running']);self.assertNotIn('bootstrap',service.calls)
        service=Service();value=entry.main(['--status'],service)
        self.assertTrue(value['running']);self.assertFalse(value['temperature_health_verified'])
        self.assertEqual(service.calls,['locations','exists','ipc:status'])
        for state in('dirty','unknown','primary','missing'):
            service=Service()
            if state=='dirty':service.replies[0]['dirty']=True
            if state=='unknown':service.replies[0].pop('dirty')
            if state=='primary':service.replies[0]['application_mode']['mode']='primary'
            if state=='missing':service.replies=[None]
            result=entry.main(['--quit-clean'],service)
            self.assertFalse(result['quit_requested']);self.assertNotIn('ipc:quit_if_clean',service.calls)
        service=Service();service.replies.append(dict(ok=True,quitting=True,dirty=False))
        result=entry.main(['--quit-clean'],service)
        self.assertTrue(result['quit_requested']);self.assertFalse(result['force']);self.assertFalse(result['termination_verified'])
        self.assertEqual(service.calls,['locations','exists','ipc:status','ipc:quit_if_clean'])

    def test_zero_wait_mutex_handles_abandoned_busy_unknown_and_never_releases_foreign_owner(self):
        for value in(0,0x80,0x102,0xffffffff,7):
            with self.subTest(value=value):
                api=Kernel(value);mutex=entry.StartupMutex('Local\\TestOnly',kernel=api)
                if value in(0,0x80,0x102):self.assertEqual(mutex.acquire(),value!=0x102)
                else:
                    with self.assertRaises(entry.EntryError):mutex.acquire()
                mutex.close();mutex.close()
                self.assertEqual(api.calls.count(('close',99)),1)
                self.assertEqual(api.calls.count(('release',99)),int(value in(0,0x80)))
                self.assertIn(('wait',99,0),api.calls)
                self.assertEqual(api.calls[0][1:3],(None,False))

    def test_owner_wrapper_reads_one_bounded_pid_then_delegates_fresh_identity_to_existing_lease(self):
        import cpu_temperature_owner055
        module=ModuleType('psutil');module.Error=OSError
        process_calls=[];leases=[]
        module.Process=lambda pid:process_calls.append(pid)or SimpleNamespace(create_time=lambda:987654321.25)
        class Owner:
            def __init__(self,pid,created,*,environ):
                self.pid=pid;self.created=created;self.environ=environ;self.closed=False;leases.append(self)
            def alive(self):return permitted
            def close(self):self.closed=True
        service=entry.Services();original=Path('D:/User/Local/DesktopStats');env={'LOCALAPPDATA':'D:/User/Local'}
        with patch.dict('sys.modules',{'psutil':module}),patch.object(cpu_temperature_owner055,'InstalledOwnerLease',Owner):
            for permitted in(True,False):
                with self.subTest(permitted=permitted),patch.object(service,'_read',return_value=b'12345\n')as read:
                    owner=service.owner(original,env)
                    read.assert_called_once_with(original/'app.pid',32)
                    self.assertEqual(leases[-1].created,987654321.25);self.assertIs(leases[-1].environ,env)
                    self.assertEqual(owner is leases[-1],permitted)
                    self.assertEqual(leases[-1].closed,not permitted)
                    if owner is not None:owner.close()
            count=len(process_calls)
            for value in(b'0',b'-12',b'not-a-pid',b'4294967296'):
                with patch.object(service,'_read',return_value=value):self.assertIsNone(service.owner(original,env))
            with patch.object(service,'_read',side_effect=OSError('missing')):
                self.assertIsNone(service.owner(original,env))
            self.assertEqual(len(process_calls),count)

    def test_existing_bootstrap_creates_only_own_marker_and_receipt_is_small_atomic_and_cleans_partial(self):
        requested=os.environ.get('DESKTOP_STATS_ENTRY_QA_OUT056')
        root=Path(requested).resolve()if requested else None
        if root is not None:self.assertTrue(root.is_relative_to(entry.ROOT/'qa-private'))
        with tempfile.TemporaryDirectory(dir=root)as folder:
            base=Path(folder);profile=base/'Local'/entry.PROFILE_NAME;original=base/'Local'/'DesktopStats'
            env={'LOCALAPPDATA':str(base/'Local'),'USERPROFILE':str(base/'User')}
            service=entry.Services()
            service.bootstrap(profile,original,TARGET,None,env)
            self.assertEqual(json.loads((profile/'secondary-session055.json').read_text('utf8')),{'schema':1,'role':'secondary'})
            self.assertFalse((profile/'preferences.json').exists());self.assertFalse(original.exists())
            record=dict(schema=1,state='requested',running_verified=False,temperature_source_decision='unavailable')
            service.receipt(profile,record);destination=profile/entry.RECEIPT_NAME
            first=destination.read_bytes();self.assertLessEqual(len(first),4096)
            self.assertEqual(json.loads(first),record)
            with self.assertRaises(entry.EntryError):service.receipt(profile,{'oversized':'x'*4096})
            self.assertEqual(destination.read_bytes(),first)
            with patch.object(Path,'replace',side_effect=OSError('atomic replacement failed')):
                with self.assertRaises(OSError):service.receipt(profile,record)
            self.assertEqual(destination.read_bytes(),first)
            self.assertEqual(list(profile.glob('*.pending')),[])
            self.assertFalse((profile/'preferences.json').exists())


if __name__=='__main__':unittest.main()
