"""Actual independent loop QML with synthetic data, no windows or collectors."""
import copy
import ctypes
import os
import subprocess
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')

from PySide6.QtCore import QObject,Property,Signal,Slot,QCoreApplication,QEvent,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent,QQmlEngine
from PySide6.QtQuick import QQuickItem

ROOT=Path(__file__).resolve().parents[1]


class FakeStats(QObject):
    changed=Signal()
    portsChanged=Signal()
    def __init__(self):
        super().__init__();self.calls=[];self.port_reads=0
        self.value=dict(loop_components_mode='reference',loop_tubes_visible=True,loop_fittings={})
        self.ports=[dict(key='cpu_block_model:in',label='CPU block · in',role='inlet',thread='G1/4'),
                    dict(key='pump_reservoir_model:fill',label='Combo · fill',role='fill',thread='G1/4')]
        self.rows={key:[dict(id='',label='None'),dict(id=identity,label=label,brand='Example',form=form)]
                   for key,identity,label,form in (
                       ('cpu_blocks','block-a','CPU Block A','cpu_block'),
                       ('loop_pumps','pump-a','Pump A','pump_body'),
                       ('loop_pump_tops','top-a','Top A','pump_top'),
                       ('loop_reservoirs','tank-a','Tank A','reservoir_tube'),
                       ('loop_combos','combo-a','Combo A','pump_reservoir_combo'),
                       ('loop_fittings','fitting-a','Fitting A','soft_compression'),
                       ('loop_tubing','tube-a','Tube A','soft_tube'))}
    theme=Property(str,lambda self:'light',constant=True)
    language=Property(str,lambda self:'en',constant=True)
    motionEnabled=Property(bool,lambda self:False,constant=True)
    material=Property('QVariantMap',lambda self:{},constant=True)
    texts=Property('QVariantMap',lambda self:{},constant=True)
    config=Property('QVariantMap',lambda self:copy.deepcopy(self.value),notify=changed)
    catalog=Property('QVariantMap',lambda self:copy.deepcopy(self.rows),notify=changed)
    @Property('QVariantList',notify=portsChanged)
    def assemblyLoopPorts(self):
        self.port_reads+=1
        return copy.deepcopy(self.ports)
    @Slot(str,'QVariant')
    def changeAssembly(self,field,value):
        self.calls.append((field,value));self.value[field]=value;self.changed.emit()
    @Slot(str,str)
    def changeAssemblyLoopFitting(self,key,value):
        self.calls.append(('port',key,value))
        if value:self.value['loop_fittings'][key]=value
        else:self.value['loop_fittings'].pop(key,None)
        self.changed.emit()


class LoopControls046Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen','Never open a native test window'
    def setUp(self):
        self.enterContext(patch.object(ctypes,'WinDLL',side_effect=AssertionError('No native API'),create=True))
        self.enterContext(patch.object(subprocess,'Popen',side_effect=AssertionError('No worker process')))
        self.enterContext(patch.object(threading.Thread,'start',side_effect=AssertionError('No sampler thread')))
        self.thread_ids={t.ident for t in threading.enumerate()}
        self.stats=FakeStats();self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.engine.rootContext().setContextProperty('stats',self.stats)
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'import QtQuick\nimport "."\nLoopParts046 { width:640; config:stats.config; catalog:stats.catalog }',
                               QUrl.fromLocalFile(str(ROOT/'native/_loop_controls046_fixture.qml')))
        self.item=self.component.create()
        self.assertIsNotNone(self.item,[r.toString() for r in self.component.errors()]);self.app.processEvents()
    def tearDown(self):
        self.item.setProperty('visible',False);self.item.deleteLater();self.component.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.engine.deleteLater();self.stats.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[])
        self.assertEqual({t.ident for t in threading.enumerate()},self.thread_ids)
        self.assertEqual(self.app.topLevelWindows(),[])
    def find(self,name):
        result=next((obj for obj in self.walk() if obj.objectName()==name),None)
        self.assertIsNotNone(result,name)
        return result
    def walk(self):
        todo=[self.item];seen={}
        while todo:
            obj=todo.pop()
            if id(obj) in seen:continue
            seen[id(obj)]=obj;yield obj
            todo.extend(obj.children())
            if hasattr(obj,'childItems'):todo.extend(obj.childItems())
    def toggle(self,name,checked):
        item=self.find(name);item.setProperty('checked',checked);item.toggled.emit();self.app.processEvents()
    def selected(self):
        self.toggle('loopComponentsToggle',True)
        self.assertEqual(self.stats.value['loop_components_mode'],'selected')
    def value(self,obj,key):
        value=obj.property(key)
        return value.toVariant() if hasattr(value,'toVariant') else value
    def test_mode_and_reference_tubes_only_dispatch_their_own_preferences(self):
        self.assertFalse(self.find('loopSelectedComponents').property('visible'))
        self.assertEqual(self.stats.port_reads,0)
        self.selected();self.assertTrue(self.find('loopSelectedComponents').property('visible'))
        self.toggle('loopReferenceTubesToggle',False)
        self.assertFalse(self.stats.value['loop_tubes_visible'])
        self.toggle('loopComponentsToggle',False)
        self.assertEqual(self.stats.calls,[('loop_components_mode','selected'),('loop_tubes_visible',False),('loop_components_mode','reference')])
        self.assertEqual(self.stats.port_reads,0)
    def test_all_seven_part_selectors_keep_separate_ids_and_callbacks(self):
        self.selected()
        expected={'cpu_block_model':'block-a','pump_model':'pump-a','pump_top_model':'top-a',
                  'reservoir_model':'tank-a','pump_reservoir_model':'combo-a',
                  'fitting_model':'fitting-a','tubing_model':'tube-a'}
        for field,identity in expected.items():
            self.find('loopPart_'+field).picked.emit(identity);self.app.processEvents()
            self.assertEqual(self.stats.value[field],identity)
            self.assertEqual(self.stats.calls[-1],(field,identity))
        self.assertEqual(self.stats.port_reads,0)
    def test_foldout_is_lazy_and_empty_inherits_only_flow_port_default(self):
        self.selected();self.assertFalse(self.item.property('interfacesExpanded'))
        self.assertEqual(self.stats.port_reads,0)
        self.find('loopInterfacesButton').clicked.emit();self.app.processEvents()
        self.assertTrue(self.item.property('interfacesExpanded'));self.assertGreater(self.stats.port_reads,0)
        inlet=self.find('loopPort_cpu_block_model:in');fill=self.find('loopPort_pump_reservoir_model:fill')
        self.assertEqual(self.value(inlet,'model')[0]['label'],'沿用默认接头')
        self.assertEqual(self.value(fill,'model')[0]['label'],'不放置接头')
        inlet.picked.emit('fitting-a');self.app.processEvents()
        self.assertEqual(self.stats.value['loop_fittings'],{'cpu_block_model:in':'fitting-a'})
        self.assertEqual(self.stats.calls[-1],('port','cpu_block_model:in','fitting-a'))
        fill.picked.emit('fitting-a');self.app.processEvents()
        self.assertEqual(self.stats.value['loop_fittings']['pump_reservoir_model:fill'],'fitting-a')
        inlet.picked.emit('');self.app.processEvents()
        self.assertNotIn('cpu_block_model:in',self.stats.value['loop_fittings'])
        self.find('loopInterfacesButton').clicked.emit();self.app.processEvents()
        reads=self.stats.port_reads;self.stats.portsChanged.emit();self.app.processEvents()
        self.assertEqual(self.stats.port_reads,reads)
        self.assertEqual(len(self.value(self.item,'interfaceRows')),0)
    def test_unknown_current_id_is_visible_and_conflicting_choices_are_not_erased(self):
        self.stats.value.update(loop_components_mode='selected',pump_reservoir_model='unknown-combo',
                                pump_top_model='old-top',reservoir_model='old-tank')
        self.stats.changed.emit();self.app.processEvents()
        self.assertEqual(self.find('loopPart_pump_reservoir_model').property('displayText'),'unknown-combo')
        self.assertEqual(self.find('loopPart_pump_top_model').property('displayText'),'old-top')
        self.assertTrue(self.find('loopPart_pump_top_model').property('visible'))
        self.assertTrue(self.find('loopPart_reservoir_model').property('visible'))
        self.assertEqual(self.stats.calls,[])
    def test_hiding_releases_foldout_delegates_without_querying_or_writing(self):
        self.selected();self.find('loopInterfacesButton').clicked.emit();self.app.processEvents()
        self.assertTrue(self.item.property('interfacesExpanded'))
        calls=copy.deepcopy(self.stats.calls);self.item.setProperty('visible',False);self.app.processEvents()
        self.assertFalse(self.item.property('interfacesExpanded'))
        self.assertEqual(len(self.value(self.item,'interfaceRows')),0)
        reads=self.stats.port_reads;self.stats.portsChanged.emit();self.app.processEvents()
        self.assertEqual(self.stats.port_reads,reads);self.assertEqual(self.stats.calls,calls)
        source=(ROOT/'native/LoopParts046.qml').read_text(encoding='utf8')
        for forbidden in ('Timer {','FrameAnimation {','WorkerScript','Qt.createQmlObject','onCompleted:stats'):
            self.assertNotIn(forbidden,source)
    def test_reopening_uses_the_current_ports_and_never_keeps_old_delegates(self):
        self.selected();self.find('loopInterfacesButton').clicked.emit();self.app.processEvents()
        self.assertIsNotNone(self.find('loopPort_cpu_block_model:in'))
        self.find('loopInterfacesButton').clicked.emit();self.app.processEvents()
        self.assertFalse(any(o.objectName().startswith('loopPort_') for o in self.walk()))
        reads=self.stats.port_reads
        self.stats.ports=[dict(key='reservoir_model:out',label='New tank · out',role='outlet',thread='G1/4')]
        self.stats.portsChanged.emit();self.app.processEvents()
        self.assertEqual(self.stats.port_reads,reads)
        self.find('loopInterfacesButton').clicked.emit();self.app.processEvents()
        self.assertIsNotNone(self.find('loopPort_reservoir_model:out'))
        self.assertFalse(any(o.objectName()=='loopPort_cpu_block_model:in' for o in self.walk()))
        self.assertFalse(any(row[0]=='port' for row in self.stats.calls))
    def test_controls_fit_narrow_and_wide_groups_with_actual_layout_polish(self):
        from PySide6.QtCore import QPointF
        self.selected();self.find('loopInterfacesButton').clicked.emit();self.app.processEvents()
        for width in (360.,640.):
            self.item.setWidth(width)
            for _ in range(3):
                for obj in self.walk():
                    if isinstance(obj,QQuickItem):obj.ensurePolished()
                self.app.processEvents()
            for obj in self.walk():
                if not obj.objectName().startswith(('loopPart_','loopPort_')) or not obj.isVisible():continue
                position=obj.mapToItem(self.item,QPointF(0.,0.))
                self.assertGreater(obj.width(),0.)
                self.assertGreaterEqual(position.x(),-0.1)
                self.assertLessEqual(position.x()+obj.width(),width+0.1)


if __name__=='__main__':unittest.main()
