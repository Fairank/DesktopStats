"""Actual controller projection and a windowless software-QML I/O card fixture."""
import copy
import os
from pathlib import Path
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QCoreApplication,QEvent,QObject,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent,QQmlEngine

import native_controller as controls
from stats_config import DEFAULT

ROOT=Path(__file__).resolve().parents[1]


def raw_report():
    return dict(kind='io',state='ready',reason_code='',unit='bytes/s',timestamp=time.time(),denied_count=0,
        attribution_scope='all_processes',physical_disk_attribution=False,
        rows=[dict(name='Editor.exe',value=3072.,read_bytes_per_second=1024.,write_bytes_per_second=2048.,
                   fraction=1.,process_count=2)])


class IoControllerProjectionTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','psutil.pids','psutil.Process','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No device/process/worker activity')))
        self.target=dict(kind='io',metric='disk_read',hardware_name='Secret physical disk label')
        self.state=SimpleNamespace(stop=threading.Event(),_process_requests={'io':self.target},
            _process_results={'io':raw_report()},_saved=dict(language='zh-CN'),tr=lambda value:value)

    def project(self):return controls.Controller.processUsage(self.state,'io')

    def test_total_and_read_write_rates_have_byte_units_not_percent_or_disk_identity(self):
        report=self.project()
        self.assertEqual(report['title'],'软件读写 I/O Top 5')
        self.assertEqual(report['caption'],'进程读写 I/O')
        self.assertIn('非当前磁盘',report['note'])
        self.assertEqual(report['rows'][0]['value_text'],'3 KiB/s')
        self.assertEqual(report['rows'][0]['read_text'],'1 KiB/s')
        self.assertEqual(report['rows'][0]['write_text'],'2 KiB/s')
        self.assertNotIn('%',report['rows'][0]['value_text'])
        self.assertNotIn(self.target['hardware_name'],str(report))
        self.target['hardware_name']='Another physical disk'
        self.assertEqual(self.project(),report)

    def test_missing_parts_baseline_stale_and_missing_permissions_never_render_fake_zero(self):
        source=self.state._process_results['io']
        source['rows'][0].pop('read_bytes_per_second')
        self.assertEqual(self.project()['rows'][0]['read_text'],'—')
        for state,reason in (('warming_up','rate_baseline'),('unavailable','io_counters_unavailable')):
            source.update(state=state,reason_code=reason,rows=[],timestamp=None)
            report=self.project();self.assertEqual(report['state'],state);self.assertEqual(report['rows'],[])
        source.update(state='ready',reason_code='',rows=raw_report()['rows'],timestamp=time.time()-9)
        report=self.project();self.assertEqual(report['state'],'stale');self.assertEqual(report['rows'],[])

    def test_bytes_to_mib_rates_are_not_clamped_to_machine_percent(self):
        for value,expected in ((8.,'8 B/s'),(2**20,'1 MiB/s')):
            self.state._process_results['io']['rows'][0]['value']=value
            self.assertEqual(self.project()['rows'][0]['value_text'],expected)


class IoQmlCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'

    def find_visual(self,parent,name):
        pending=[parent]
        while pending:
            item=pending.pop()
            if item.objectName()==name:return item
            if hasattr(item,'childItems'):pending.extend(item.childItems())
        return None

    def test_scope_is_always_visible_bars_compare_rates_and_hidden_card_releases_lease(self):
        with (patch('ctypes.WinDLL',side_effect=AssertionError('No native API')),
              patch('threading.Thread.start',side_effect=AssertionError('No worker'))):
            engine=QQmlEngine();warnings=[]
            engine.warnings.connect(lambda messages:warnings.extend(value.toString() for value in messages))
            component=QQmlComponent(engine)
            component.setData(b'''import QtQuick
import "../native" as Native
Item {
 id:fixture;width:360;height:500
 property bool running:true
 property int released:0
 QtObject {
  id:provider
  property int processUsageRevision:0
  function beginProcessUsage(metric,name) {return "fixture"}
  function updateProcessUsage(token,metric,name) {}
  function endProcessUsage(token) {fixture.released++}
  function tr(text) {return text}
  function processUsage(token) {return {kind:"io",state:"ready",rows:[
   {name:"Large.exe",value:4096,value_text:"4 KiB/s",fraction:.01,process_count:1},
   {name:"Small.exe",value:1024,value_text:"1 KiB/s",fraction:.99,process_count:1}]}}
 }
 Native.ProcessUsageCard {objectName:"card";width:360;provider:provider;metric:"disk_read";active:fixture.running;motionEnabled:false}
}''',QUrl.fromLocalFile(str(ROOT/'tests/ProcessIoFixture.qml')))
            fixture=component.create()
            try:
                self.assertIsNotNone(fixture,[error.toString() for error in component.errors()])
                self.app.processEvents()
                card=fixture.findChild(QObject,'card');self.assertIsNotNone(card)
                scope=fixture.findChild(QObject,'processIoScope');self.assertIsNotNone(scope)
                self.assertTrue(scope.property('visible'));self.assertIn('非当前磁盘',scope.property('text'))
                self.assertFalse(card.property('showLimitations'))
                self.assertEqual(card.property('displayedCount'),2)
                first=self.find_visual(fixture,'processSoftwareRow0');second=self.find_visual(fixture,'processSoftwareRow1')
                self.assertIsNotNone(first);self.assertIsNotNone(second)
                self.assertEqual(first.property('softwareFraction'),1.)
                self.assertEqual(second.property('softwareFraction'),.25)
                fixture.setProperty('running',False);self.app.processEvents()
                self.assertEqual(card.property('lease'),'');self.assertEqual(fixture.property('released'),1)
            finally:
                if fixture:fixture.deleteLater()
                component.deleteLater();engine.deleteLater()
                QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
            self.assertEqual(warnings,[])


if __name__=='__main__':unittest.main()
