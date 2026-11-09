"""Assembly state stays lazy, preserves scoped edits and releases its shared clock."""
import copy
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent,QObject,Slot,QUrl
from PySide6.QtQml import QQmlEngine,QQmlComponent,QQmlExpression,qmlContext
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QApplication

import native_controller as controls
from assembly_config import DEFAULT_ASSEMBLY,HARDWARE_ICON_STYLES,STYLE_LABELS,validate_assembly,visual_style
from stats_config import DEFAULT,validate

ROOT=Path(__file__).resolve().parents[1]
FIRMWARE=dict(state='available',system=dict(manufacturer='ASUS'),enclosures=[],
              baseboards=[dict(manufacturer='ASUSTeK COMPUTER INC.',product='ROG STRIX Z790-A GAMING WIFI D4')])


class Backend(QObject):
    def __init__(self):super().__init__();self.frames=[]
    @Slot(float)
    def advanceFrame(self,elapsed):self.frames.append(elapsed)


class AssemblyToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.native=self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native API')))
        self.process=self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No process')))
        self.snapshot=self.enterContext(patch('chassis_identity.snapshot',return_value=copy.deepcopy(FIRMWARE)))
        self.modules=self.enterContext(patch('memory_identity.modules',return_value=[]))
        self.enterContext(patch.object(controls,'load',return_value=copy.deepcopy(DEFAULT)))
        self.ui=controls.Controller();self.addCleanup(self.ui.close)

    def test_constructor_and_ordinary_readings_never_initialize_optional_identity_or_renderer(self):
        self.assertFalse(self.ui.assemblySummary['initialized'])
        for _ in range(4):self.ui.dataChanged.emit()
        self.snapshot.assert_not_called();self.modules.assert_not_called()
        self.assertNotIn('assembly_viewer',sys.modules)

    def test_activation_reads_identity_once_and_dynamic_values_do_not_rebuild_spec(self):
        spy=QSignalSpy(self.ui.assemblyChanged)
        self.ui._data=dict(cpu_name='Intel Core i7-13700KF',gpus={'0':dict(gpu_name='NVIDIA GeForce RTX 5090',gpu_usage=42)})
        self.ui.setAssemblyActive(True)
        self.assertTrue(self.ui.assemblySummary['initialized']);self.assertEqual(spy.count(),1)
        self.assertEqual(self.ui.assemblySummary['identity_state'],'unidentified')
        for load in (51,64,78):
            self.ui._data['gpus']['0']['gpu_usage']=load;self.ui.dataChanged.emit()
        self.assertEqual(spy.count(),1)
        self.ui.setAssemblyActive(False);self.ui.setAssemblyActive(True)
        self.snapshot.assert_called_once();self.modules.assert_called_once()

    def test_case_change_uses_preferences_scope_and_keeps_topbar_and_desktop_drafts(self):
        self.ui.setAssemblyActive(True)
        self.ui.changeWidget('cpu','title','Draft')
        self.ui.changeTopBar('height',40)
        before=copy.deepcopy(self.ui.saved)
        self.ui.changeAssembly('case_model','hyte-y60')
        self.assertEqual(self.ui.assemblySummary['identity_state'],'manual')
        self.assertTrue(self.ui.scopeDirty['preferences'])
        with patch.object(controls,'save') as save:self.assertTrue(self.ui.applyPreferences())
        self.assertEqual(self.ui.saved['assembly']['case_model'],'hyte-y60')
        self.assertEqual(self.ui.saved['top_bar'],before['top_bar'])
        self.assertEqual(self.ui.saved['widgets'],before['widgets'])
        self.assertEqual(self.ui.draft['widgets']['cpu']['title'],'Draft')
        self.assertEqual(self.ui.draft['top_bar']['height'],40)
        save.assert_called_once()

    def test_old_preferences_default_to_static_automatic_assembly_and_invalid_types_fail(self):
        old=copy.deepcopy(DEFAULT);old.pop('assembly')
        self.assertEqual(validate(old)['assembly'],DEFAULT_ASSEMBLY)
        prior=dict(case_model='hyte-y60',exploded=True,fan_animation=False)
        expected=copy.deepcopy(DEFAULT_ASSEMBLY);expected.update(prior)
        self.assertEqual(validate_assembly(prior),expected)
        for value in ([],dict(case_model='../bad'),dict(fan_animation=1),dict(exploded='yes'),
                      dict(appearance_style='unknown'),dict(appearance_style=1),dict(appearance_style=None),
                      dict(detail_level='ultra'),dict(detail_level=None),dict(detail_level=True),
                      dict(selection_effects=1),dict(selection_effects='yes'),dict(selection_effects=None)):
            with self.assertRaises(ValueError):validate_assembly(value)

    def test_quality_and_effect_preferences_persist_without_touching_other_scopes(self):
        self.ui.setAssemblyActive(True)
        before=copy.deepcopy(self.ui.saved)
        for level in ('eco','balanced','close'):
            self.ui.changeAssembly('detail_level',level)
            self.assertEqual(self.ui.assembly_specification()['detail_level'],level)
        self.ui.changeAssembly('selection_effects',False)
        self.assertEqual(self.ui.scopeDirty,dict(desktop=False,preferences=True,topbar=False))
        with patch.object(controls,'save'):self.assertTrue(self.ui.applyPreferences())
        self.assertEqual(self.ui.saved['assembly']['detail_level'],'close')
        self.assertIs(self.ui.saved['assembly']['selection_effects'],False)
        self.assertEqual(self.ui.saved['widgets'],before['widgets'])
        self.assertEqual(self.ui.saved['top_bar'],before['top_bar'])

    def test_all_bar_styles_are_available_without_changing_any_bar_or_case_setting(self):
        self.assertEqual(set(STYLE_LABELS),set(HARDWARE_ICON_STYLES))
        self.assertEqual([row['id'] for row in self.ui.assemblyStyles],['follow',*HARDWARE_ICON_STYLES])
        self.ui.setAssemblyActive(True);self.ui.changeAssembly('case_model','hyte-y60')
        bar=copy.deepcopy(self.ui.draft['top_bar'])
        for style in HARDWARE_ICON_STYLES:
            self.ui.changeAssembly('appearance_style',style)
            self.assertEqual(self.ui.assemblySummary['visual_style'],style)
            self.assertEqual(self.ui.assemblySummary['visual_style_label'],STYLE_LABELS[style])
            self.assertEqual(self.ui.draft['assembly']['case_model'],'hyte-y60')
            self.assertEqual(self.ui.draft['top_bar'],bar)
        self.assertEqual(self.ui.scopeDirty,dict(desktop=False,preferences=True,topbar=False))
        with patch.object(controls,'save'):self.assertTrue(self.ui.applyPreferences())
        self.assertEqual(self.ui.saved['assembly']['appearance_style'],HARDWARE_ICON_STYLES[-1])
        self.assertEqual(self.ui.saved['assembly']['case_model'],'hyte-y60')
        self.assertEqual(self.ui.saved['top_bar'],bar)

    def test_complete_reference_edits_only_preferences_and_reuses_identity_cache(self):
        self.ui.setAssemblyActive(True)
        self.ui.changeWidget('cpu','title','Keep draft');self.ui.changeTopBar('height',40)
        bar=copy.deepcopy(self.ui.draft['top_bar']);widgets=copy.deepcopy(self.ui.draft['widgets'])
        self.ui.useAssemblyReference('aio')
        spec=self.ui.assembly_specification()
        self.assertEqual(spec['cooling']['cpu_cooler'],'arctic-liquid-freezer-iii-360')
        self.assertEqual(spec['auxiliary']['psu']['model_id'],'corsair-rm1000x-2024')
        self.assertEqual(self.ui.draft['top_bar'],bar);self.assertEqual(self.ui.draft['widgets'],widgets)
        self.snapshot.assert_called_once();self.modules.assert_called_once()
        with patch.object(controls,'save'):self.assertTrue(self.ui.applyPreferences())
        self.assertEqual(self.ui.saved['assembly']['fan_motion'],'demo')
        self.assertEqual(self.ui.draft['widgets']['cpu']['title'],'Keep draft')
        choices=self.ui.assemblyParts
        for group,baseline,example in (('boards',7,'asus-rog-strix-z790-a-wifi-d4'),
                ('coolers',27,'noctua-nh-u12a'),('fans',27,'arctic-p12-pwm'),
                ('psus',22,'corsair-rm1000x-2024')):
            self.assertGreaterEqual(len(choices[group]),baseline)
            self.assertIn(example,{row['id'] for row in choices[group]})

    def test_follow_reacts_to_bar_style_once_but_explicit_style_ignores_later_bar_changes(self):
        self.ui.setAssemblyActive(True)
        spy=QSignalSpy(self.ui.assemblyChanged)
        self.ui.changeTopBar('hardware_icon_style','notebook_color')
        self.assertEqual(self.ui.assemblySummary['visual_style'],'notebook_color')
        self.assertEqual(spy.count(),1)
        self.ui.changeAssembly('appearance_style','notebook_line')
        self.assertEqual(spy.count(),2)
        self.ui.changeTopBar('hardware_icon_style','cartoon')
        self.assertEqual(self.ui.assemblySummary['visual_style'],'notebook_line')
        self.assertEqual(spy.count(),2)
        self.ui.changeAssembly('appearance_style','follow')
        self.assertEqual(self.ui.assemblySummary['visual_style'],'cartoon')
        self.assertEqual(spy.count(),3)
        for bad in (None,[],False,'unknown'):
            self.assertEqual(visual_style(dict(top_bar=dict(hardware_icon_style=bad))),'miniature')

    def test_individual_style_changes_and_reset_stay_in_preferences(self):
        self.ui.setAssemblyActive(True)
        before=copy.deepcopy(self.ui.draft)
        self.ui.changeAssemblyPartStyle('fans:side:0','notebook_line')
        self.ui.changeAssemblyPartStyle('case-fan:0','papercut')
        self.ui.changeAssemblyPartStyle('gpu','miniature')
        self.assertEqual(self.ui.assembly_specification()['part_styles'],
                         {'fans:side:0':'notebook_line','case-fan:0':'papercut','gpu':'miniature'})
        self.ui.changeAssemblyPartStyle('gpu','follow')
        self.assertEqual(self.ui.draft['assembly']['part_styles'],{'fans:side:0':'notebook_line','case-fan:0':'papercut'})
        self.assertEqual(self.ui.draft['top_bar'],before['top_bar'])
        self.assertEqual(self.ui.draft['widgets'],before['widgets'])
        self.assertEqual(self.ui.scopeDirty,dict(desktop=False,preferences=True,topbar=False))
        self.ui.resetAssemblyPartStyles()
        self.assertEqual(self.ui.draft['assembly']['part_styles'],{})

    def test_reference_models_never_drive_another_devices_rotors(self):
        self.ui._data=dict(time=time.time(),cpu_name='Intel Core i7-13700KF',cpu_fan_rpm=1200,
            gpus={'0':dict(gpu_name='RTX 5090',gpu_fan_rpm=1500,gpu_fan_rpm_timestamp=time.time(),
                gpu_fan_rpm_scope='card',gpu_fan_rpm_semantics='driver_current_rpm',gpu_fan_rpm_source='synthetic')})
        self.ui.setAssemblyActive(True)
        self.assertTrue(self.ui.assembly_cpu_fan_state()['available'])
        self.ui.changeAssembly('cpu_model','amd-9950x')
        from hardware_appearance import CATALOG
        model=next(row[0] for row in CATALOG if row[1]=='gpu')
        self.ui.changeAssembly('gpu_model',model)
        self.assertFalse(self.ui.assembly_cpu_fan_state()['available'])
        self.assertFalse(self.ui.assembly_fan_state()['available'])
        self.snapshot.assert_called_once();self.modules.assert_called_once()

    def test_shared_clock_only_ticks_while_opted_in_then_retires(self):
        engine=QQmlEngine();warnings=[]
        engine.warnings.connect(lambda rows:warnings.extend(row.toString() for row in rows))
        backend=Backend();component=QQmlComponent(engine,QUrl.fromLocalFile(str(ROOT/'native/AssemblyClock.qml')))
        clock=component.createWithInitialProperties(dict(backend=backend,active=False))
        self.assertIsNotNone(clock,[e.toString() for e in component.errors()])
        self.assertIsNone(clock.property('subscription'))
        clock.setProperty('active',True);QTest.qWait(110)
        self.assertGreater(len(backend.frames),0)
        clock.setProperty('active',False);count=len(backend.frames);QTest.qWait(75)
        self.assertEqual(len(backend.frames),count)
        self.assertIsNone(clock.property('subscription'))
        clock.setProperty('backend',None);clock.deleteLater();component.deleteLater();engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(warnings,[])


if __name__=='__main__':unittest.main()
