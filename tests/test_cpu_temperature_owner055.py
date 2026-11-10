"""Retained-owner identity and cache invalidation controls, no native APIs."""
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from cpu_temperature import AsusCpuTemperature,MAGIC,SENSOR_ID
from cpu_temperature_owner055 import InstalledOwnerLease


class Api:
    def __init__(self):
        self.opens=0;self.closes=0;self.running=True
        self.facts=dict(pid=123,created=100.,path=str(Path('C:/Local/Programs/DesktopStats/DesktopStats.exe')),same_user=True,same_session=True)
    def open(self,pid):self.opens+=1;return object()
    def identity(self,handle):return dict(self.facts)
    def alive(self,handle):return self.running
    def close(self,handle):self.closes+=1


class Cache:
    def __init__(self,owner=123):self.owner=owner;self.reads=0;self.closes=0
    def read(self):
        self.reads+=1
        return struct.pack('<7IiqI',MAGIC,1,2,1,456,SENSOR_ID,450,0,1000000,self.owner)+bytes(20)
    def close(self):self.closes+=1


class CpuTemperatureOwner055Tests(unittest.TestCase):
    def setUp(self):
        # All owner/mapping objects in this suite are fakes. The real user's
        # disable flag is separately tested and never reaches a native API.
        guard=patch.dict(os.environ,{'DESKTOP_STATS_CPU_BRIDGE_DISABLED':'0'})
        guard.start();self.addCleanup(guard.stop)

    def lease(self,api):
        return InstalledOwnerLease(123,100.,api_factory=lambda:api,environ={'LOCALAPPDATA':'C:/Local'})

    def test_construction_does_no_native_work_and_handle_is_retained(self):
        api=Api();lease=self.lease(api);self.assertEqual(api.opens,0)
        self.assertTrue(lease.alive());self.assertTrue(lease.alive());self.assertEqual(api.opens,1)
        lease.close();lease.close();self.assertEqual(api.closes,1)

    def test_wrong_path_creation_user_session_or_pid_is_rejected_without_rebind(self):
        for key,value in(('pid',124),('created',101.),('path','C:/Other/DesktopStats.exe'),('same_user',False),('same_session',False)):
            with self.subTest(key=key):
                api=Api();api.facts[key]=value;lease=self.lease(api)
                self.assertFalse(lease.alive());self.assertEqual(api.closes,1)
                api.facts=Api().facts;self.assertFalse(lease.alive());self.assertEqual(api.opens,1)

    def test_owner_exit_never_follows_pid_reuse(self):
        api=Api();lease=self.lease(api);self.assertTrue(lease.alive())
        api.running=False;self.assertFalse(lease.alive());self.assertEqual(lease.state,'owner_exited')
        api.running=True;api.facts['created']=200.
        self.assertFalse(lease.alive());self.assertEqual(api.opens,1);self.assertEqual(api.closes,1)

    def test_owner_exit_clears_reading_before_interval_cache_return(self):
        api=Api();lease=self.lease(api);cache=Cache();clock=[0.]
        reader=AsusCpuTemperature(api=cache,owner_lease=lease,clock=lambda:clock[0],wall_clock=lambda:1000.,enabled=True)
        self.assertEqual(reader.read()['cpu_temp'],45.);self.assertEqual(cache.reads,1)
        api.running=False;clock[0]=.1
        self.assertEqual(reader.read(),{});self.assertIsNone(reader.sample_time)
        self.assertEqual(reader.state,'owner_exited');self.assertEqual(cache.reads,1)
        reader.close();self.assertEqual(api.closes,1)

    def test_explicit_disable_wins_even_over_enabled_and_does_not_validate_owner(self):
        api=Api();cache=Cache();lease=self.lease(api)
        with patch.dict(os.environ,{'DESKTOP_STATS_CPU_BRIDGE_DISABLED':'1'}):
            reader=AsusCpuTemperature(api=cache,owner_lease=lease,enabled=True)
            self.assertEqual(reader.read(),{})
        self.assertEqual(api.opens,0);self.assertEqual(cache.reads,0)

    def test_existing_mapping_owner_identity_checks_are_not_weakened(self):
        api=Api();cache=Cache(owner=999)
        reader=AsusCpuTemperature(api=cache,owner_lease=self.lease(api),clock=lambda:0.,wall_clock=lambda:1000.,enabled=True)
        self.assertEqual(reader.read(),{});self.assertEqual(reader.state,'invalid_value')
        reader.close()

if __name__=='__main__':unittest.main()
