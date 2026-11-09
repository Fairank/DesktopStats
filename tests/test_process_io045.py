"""Process-wide read/write I/O fixtures; never query real processes or devices."""
import ctypes as c
import struct
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

import process_snapshot as native
import process_usage as usage


def row(pid=1,name='Editor.exe',read=1000,write=2000,started=1.):
    return dict(pid=pid,name=name,started=started,io_read_bytes=read,io_write_bytes=write,cpu_seconds=1.,memory_bytes=1000)


class NativeIoSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native API')))
        self.enterContext(patch('psutil.Process',side_effect=AssertionError('No process handles')))
        self.calls=0;self.read=123456;self.write=789012

    def query(self,kind,buffer,capacity,returned):
        self.calls+=1;self.assertEqual(kind,5)
        name='Fixture.exe'.encode('utf-16-le');address=c.addressof(buffer)
        struct.pack_into('<qqq',buffer,32,native._EPOCH+native._TICKS,2*native._TICKS,3*native._TICKS)
        struct.pack_into('<HH',buffer,56,len(name),len(name)+2)
        struct.pack_into('<Q',buffer,64,address+256);struct.pack_into('<Q',buffer,80,42)
        struct.pack_into('<Q',buffer,144,4096)
        # Operation counts and OtherTransferCount are intentionally huge: only
        # the two byte transfer fields at their exact x64 offsets may be read.
        struct.pack_into('<qqqqqq',buffer,208,9000000,8000000,7000000,self.read,self.write,6000000)
        c.memmove(address+256,name+b'\0\0',len(name)+2)
        c.cast(returned,c.POINTER(c.c_uint32)).contents.value=256+len(name)+2
        return 0

    def test_one_bulk_query_reads_transfer_bytes_only_when_requested(self):
        source=native.WindowsProcessSnapshot(query=self.query)
        plain=source.read()['rows'][0]
        self.assertNotIn('io_read_bytes',plain);self.assertNotIn('io_write_bytes',plain)
        report=source.read(include_io=True)['rows'][0]
        self.assertEqual(self.calls,2)
        self.assertEqual((report['io_read_bytes'],report['io_write_bytes']),(123456,789012))
        self.assertEqual(report['cpu_seconds'],5.)
        self.assertEqual(report['memory_bytes'],4096)
        self.assertNotIn('path',report);self.assertNotIn('command_line',report)

    def test_bad_io_counter_does_not_erase_cpu_memory_or_become_zero_io(self):
        self.read=-1
        report=native.WindowsProcessSnapshot(query=self.query).read(include_io=True)['rows'][0]
        self.assertNotIn('io_read_bytes',report);self.assertNotIn('io_write_bytes',report)
        self.assertEqual(report['memory_bytes'],4096)


class IoSourceDispatchTests(unittest.TestCase):
    def test_windows_cpu_memory_and_io_share_one_bulk_query(self):
        source=usage.ProcessSource();source._native=Mock()
        source._native.read.return_value=dict(rows=[row()],skipped=0)
        with (patch.object(usage.sys,'platform','win32'),patch('psutil.Process',side_effect=AssertionError('No handles')),
              patch('psutil.pids',side_effect=AssertionError('No enumeration')),
              patch('psutil.cpu_count',return_value=8),patch('psutil.virtual_memory',return_value=SimpleNamespace(total=4096))):
            result=source.snapshot({'cpu','memory','io'})
            source._native.read.assert_called_once_with(include_io=True)
            self.assertEqual(result['rows'][0]['io_read_bytes'],1000)
            source._native.read.reset_mock();source.snapshot({'cpu'})
            source._native.read.assert_called_once_with()

    def test_non_windows_only_requests_io_counters_when_io_is_demanded(self):
        attrs=[]
        class Process:
            def __init__(self,pid):self.pid=pid
            def io_counters(self):raise AssertionError('Use the single as_dict observation')
            def as_dict(self,**options):
                attrs.append(options['attrs'])
                return dict(name='Example.exe',create_time=1.,cpu_times=SimpleNamespace(user=1.,system=2.),
                    io_counters=SimpleNamespace(read_bytes=111,write_bytes=222))
        with patch.object(usage.sys,'platform','linux'),patch('psutil.pids',return_value=[42]),patch('psutil.Process',Process),patch('psutil.cpu_count',return_value=4):
            source=usage.ProcessSource();first=source.snapshot({'cpu'});second=source.snapshot({'io'})
        self.assertNotIn('io_counters',attrs[0]);self.assertIn('io_counters',attrs[1])
        self.assertNotIn('io_read_bytes',first['rows'][0]);self.assertEqual(second['rows'][0]['io_write_bytes'],222)
        self.assertFalse(any(key in str(attrs) for key in ('cmdline','username','exe')))

    def test_non_windows_missing_io_method_keeps_other_resource_fields(self):
        class Process:
            def __init__(self,pid):pass
            def as_dict(self,**options):
                self.asserted='io_counters' not in options['attrs']
                return dict(name='Example.exe',create_time=1.,memory_info=SimpleNamespace(rss=123))
        with patch.object(usage.sys,'platform','linux'),patch('psutil.pids',return_value=[42]),patch('psutil.Process',Process),patch('psutil.virtual_memory',return_value=SimpleNamespace(total=1000)):
            result=usage.ProcessSource().snapshot({'memory','io'})
        self.assertEqual(result['rows'][0]['memory_bytes'],123);self.assertNotIn('io_read_bytes',result['rows'][0])


class IoRateTests(unittest.TestCase):
    def setUp(self):
        self.rows=[];self.now=10.;self.denied={};self.calls=[];self.failure=False
        owner=self
        class Source:
            def snapshot(self,kinds):
                owner.calls.append(set(kinds))
                if owner.failure:raise OSError('Synthetic snapshot failure')
                return dict(rows=[dict(r) for r in owner.rows],denied=dict(owner.denied),logical_cpus=4,total_memory=10000)
        self.sampler=usage.ProcessUsageSampler(source=Source(),clock=lambda:self.now,wall_clock=lambda:1700000000+self.now)
        self.addCleanup(self.sampler.close)
        for name in ('ctypes.WinDLL','psutil.pids','psutil.Process','subprocess.Popen'):
            self.enterContext(patch(name,side_effect=AssertionError('No real process/device access')))

    def sample(self,kinds=('io',),names=('',)):
        targets={str(index):dict(kind=kind,hardware_name=names[index%len(names)]) for index,kind in enumerate(kinds)}
        return self.sampler.read(targets)

    def test_merges_case_insensitive_software_then_sorts_top_five_with_byte_rates(self):
        names=('Chrome.exe','chrome.EXE','Editor.exe','A.exe','B.exe','C.exe','D.exe')
        self.rows=[row(index,name,read=10000,write=20000) for index,name in enumerate(names,1)]
        self.assertEqual(self.sample()['0']['state'],'warming_up')
        self.now+=2
        for item,reads,writes in zip(self.rows,(100,300,300,200,100,50,25),(100,100,100,0,0,0,0)):
            item['io_read_bytes']+=reads;item['io_write_bytes']+=writes
        result=self.sample()['0']
        self.assertEqual([r['name'].casefold() for r in result['rows']],['chrome.exe','editor.exe','a.exe','b.exe','c.exe'])
        self.assertEqual([r['value'] for r in result['rows']],[300,200,100,50,25])
        self.assertEqual(result['rows'][0]['read_bytes_per_second'],200)
        self.assertEqual(result['rows'][0]['write_bytes_per_second'],100)
        self.assertEqual(result['rows'][0]['process_count'],2)
        self.assertEqual(result['rows'][0]['fraction'],1.)
        self.assertEqual(result['unit'],'bytes/s');self.assertFalse(result['physical_disk_attribution'])
        self.assertEqual(result['attribution_scope'],'all_processes')

    def test_two_disk_detail_leases_receive_same_global_reference_from_one_snapshot(self):
        self.rows=[row()];self.sample(('cpu','memory','io','io'),('Disk A','Disk B'))
        self.now+=1;self.rows[0]['io_read_bytes']+=500;before=len(self.calls)
        result=self.sample(('cpu','memory','io','io'),('Disk A','Disk B'))
        self.assertEqual(len(self.calls),before+1)
        self.assertEqual(self.calls[-1],{'cpu','memory','io'})
        self.assertEqual(result['2'],result['3']);self.assertEqual(result['2']['rows'][0]['value'],500)
        self.assertNotIn('hardware_name',result['2']);self.assertNotIn('disk_id',result['2'])
        self.assertEqual(result['1']['state'],'ready')

    def test_pid_reuse_and_counter_rollback_rewarm_without_spikes(self):
        for mutation in ('reuse','read_reset','write_reset'):
            with self.subTest(mutation=mutation):
                self.sampler.previous={};self.sampler.previous_at=None;self.sampler.previous_kinds=frozenset()
                self.rows=[row()];self.sample();self.now+=1
                if mutation=='reuse':self.rows[0].update(started=2.,io_read_bytes=999999999)
                else:self.rows[0]['io_read_bytes' if mutation=='read_reset' else 'io_write_bytes']=1
                result=self.sample()['0'];self.assertEqual(result['state'],'warming_up');self.assertEqual(result['rows'],[])
                self.now+=1;self.rows[0]['io_read_bytes']+=40;self.rows[0]['io_write_bytes']+=60
                self.assertEqual(self.sample()['0']['rows'][0]['value'],100)

    def test_new_io_demand_never_reuses_old_cpu_only_interval(self):
        self.rows=[row()];self.sample(('cpu',));self.now+=1
        self.assertEqual(self.sample(('cpu','io'))['1']['state'],'warming_up')
        self.now+=1;self.rows[0]['io_read_bytes']+=100
        self.assertEqual(self.sample(('cpu','io'))['1']['rows'][0]['value'],100)
        self.now+=1;self.sample(('cpu',));self.now+=1
        self.assertEqual(self.sample(('io',))['0']['state'],'warming_up')

    def test_absent_permissions_unknown_identity_and_bad_values_are_not_zero(self):
        for bad in (None,-1,True,float('nan'),2**63):
            self.rows=[row(read=bad)]
            result=self.sample()['0']
            self.assertEqual(result['state'],'unavailable');self.assertEqual(result['rows'],[])
            self.assertEqual(result['reason_code'],'io_counters_unavailable')
        self.rows=[row(started=0.)]
        self.assertEqual(self.sample()['0']['state'],'unavailable')
        self.rows=[];self.denied={'io':3}
        result=self.sample()['0'];self.assertEqual(result['denied_count'],3)
        self.assertEqual(result['state'],'unavailable')

    def test_partial_unreadable_processes_do_not_hide_valid_software(self):
        self.rows=[row(),row(2,'Unreadable.exe',read=None)];self.denied={'io':1};self.sample()
        self.now+=1;self.rows[0]['io_write_bytes']+=200
        result=self.sample()['0'];self.assertEqual(result['state'],'partial')
        self.assertEqual(result['denied_count'],2);self.assertEqual(len(result['rows']),1)

    def test_zero_rate_is_idle_and_sleep_clock_reset_or_query_failure_rewarm(self):
        self.rows=[row()];self.sample();self.now+=1
        self.assertEqual(self.sample()['0']['state'],'idle')
        for offset in (31,-1):
            self.now+=offset;self.rows[0]['io_read_bytes']+=100
            self.assertEqual(self.sample()['0']['state'],'warming_up')
        self.failure=True;self.assertEqual(self.sample()['0']['state'],'unavailable')
        self.assertEqual(self.sampler.previous_kinds,frozenset());self.failure=False;self.now+=1
        self.assertEqual(self.sample()['0']['state'],'warming_up')
        self.sampler.close();calls=len(self.calls)
        self.assertEqual(self.sample()['0']['state'],'closed');self.assertEqual(len(self.calls),calls)
        self.assertEqual(self.sampler.previous,{})

    def test_only_throughput_metrics_map_to_io_and_network_stays_unsupported(self):
        for metric in ('disk_read','disk_write'):self.assertEqual(usage.resource_kind(metric),'io')
        for metric in ('disk_temperature','disk_temp','disk_capacity','disk_health','disk_usage','storage_read','net_download','net_upload',None,True):
            self.assertNotEqual(usage.resource_kind(metric),'io')
        self.assertEqual(usage.resource_kind('net_download'),'')


class IoDemandLifecycleTests(unittest.TestCase):
    def test_same_existing_worker_pauses_and_recreates_rate_baseline_after_last_lease(self):
        reads=[];samplers=[];received=threading.Event();retired=threading.Event()
        class Sampler:
            def __init__(self):samplers.append(self)
            def read(self,targets):
                reads.append(tuple(targets));return {k:usage.empty_report(v['kind']) for k,v in targets.items()}
            def close(self):retired.set()
        monitor=usage.ProcessUsageMonitor(lambda generation,result:received.set(),factory=Sampler)
        try:
            monitor.set_targets({'a':dict(kind='io'),'b':dict(kind='memory')})
            self.assertTrue(received.wait(1));thread=monitor.thread
            monitor.set_targets({});self.assertTrue(retired.wait(1));count=len(reads)
            time.sleep(.04);self.assertEqual(len(reads),count)
            received.clear();monitor.set_targets({'c':dict(kind='io')})
            self.assertTrue(received.wait(1));self.assertIs(monitor.thread,thread);self.assertEqual(len(samplers),2)
        finally:monitor.close()
        self.assertFalse(thread.is_alive())


if __name__=='__main__':unittest.main()
