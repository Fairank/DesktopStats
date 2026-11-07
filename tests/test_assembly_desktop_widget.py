"""Offscreen desktop layout/alpha/selection/lifecycle, never a real GL window."""
import copy
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent,QPoint,Qt
from PySide6.QtGui import QImage,QMouseEvent
from PySide6.QtQml import QQmlEngine
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QApplication,QCheckBox,QComboBox,QMenu,QScrollArea

from assembly_config import validate_assembly
from assembly_spec import build_spec
from assembly_window import AssemblyWindow,create_assembly_window
from assembly_desktop_widget import AssemblyWidgetWindow
from stats_config import DEFAULT,validate
from tests.test_assembly_window import Controller,Viewport

ROOT=Path(__file__).resolve().parents[1]


class DesktopController(Controller):
    def __init__(self,spec):
        super().__init__(spec);self.requests=[]
    def openAssemblyInspect(self):self.requests.append('inspect')


class DesktopViewport(Viewport):
    def set_transparent_background(self,value):self.transparent=value


class AssemblyDesktopPreferencesTests(unittest.TestCase):
    def test_legacy_defaults_stay_inspection_and_new_values_roundtrip(self):
        self.assertEqual(validate_assembly()['window_mode'],'inspect')
        self.assertTrue(validate_assembly()['desktop_frame'])
        config=copy.deepcopy(DEFAULT);config['assembly'].update(window_mode='desktop',desktop_frame=False)
        config=validate(config)
        self.assertEqual(config['assembly']['window_mode'],'desktop')
        spec=build_spec({},config,{'state':'unavailable'},[])
        self.assertEqual(spec['options']['window_mode'],'desktop')
        self.assertFalse(spec['options']['desktop_frame'])

    def test_malformed_modes_and_nonboolean_frame_are_rejected(self):
        for field,value in (('window_mode','always-on-top'),('window_mode',False),
                            ('desktop_frame',1),('desktop_frame','false')):
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                validate_assembly({field:value})

    def test_preferences_page_has_explicit_desktop_and_inspection_entries(self):
        text=(ROOT/'native/AssemblyPage.qml').read_text(encoding='utf-8')
        for value in ('assemblyWindowModeChoice','assemblyDesktopFrameToggle','openAssemblyDesktopButton',
                      'stats.openAssemblyDesktop()','stats.openAssemblyInspect()'):
            self.assertIn(value,text)


class AssemblyDesktopWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No hardware/native query')))
        self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No process')))
        config=copy.deepcopy(DEFAULT);config['assembly'].update(window_mode='desktop',fan_animation=True)
        spec=build_spec(dict(cpu_name='Intel Core i7-13700KF',gpus={'0':dict(gpu_name='RTX 5090')}),
                        config,dict(state='unavailable'),[])
        self.controller=DesktopController(spec);self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.window=create_assembly_window(self.controller,self.engine,spec,viewport_factory=DesktopViewport)
        self.window.show();self.app.processEvents()

    def tearDown(self):
        self.window.close();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.app.processEvents();self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(self.warnings,[])

    def _image(self):
        image=QImage(self.window.size(),QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
        self.window.render(image)
        return image

    def test_factory_creates_only_a_compact_nonactivating_bottom_window(self):
        self.assertIsInstance(self.window,AssemblyWidgetWindow)
        self.assertEqual(self.window.window_mode,'desktop')
        flags=self.window.windowFlags()
        for flag in (Qt.FramelessWindowHint,Qt.WindowStaysOnBottomHint,Qt.WindowDoesNotAcceptFocus):
            self.assertTrue(flags&flag)
        self.assertFalse(flags&Qt.WindowStaysOnTopHint)
        self.assertTrue(self.window.testAttribute(Qt.WA_ShowWithoutActivating))
        self.assertTrue(self.window.testAttribute(Qt.WA_TranslucentBackground))
        self.assertEqual(self.window.size().width(),420)
        self.assertTrue(self.window.viewport.transparent)
        for kind in (QComboBox,QCheckBox,QScrollArea):self.assertEqual(self.window.findChildren(kind),[])
        self.assertGreater(self.window.viewport.height(),self.window.height()*.55)

    def test_card_and_true_unframed_alpha_keep_clock_and_scene_identity(self):
        window=self.window;clock=window._clock;viewport=window.viewport;count=len(viewport.scenes)
        framed=self._image()
        self.assertEqual(framed.pixelColor(framed.width()//2,4).alpha(),255)
        self.controller.changeAssembly('desktop_frame',False);self.app.processEvents()
        clear=self._image()
        self.assertEqual(clear.pixelColor(0,0).alpha(),0)
        self.assertEqual(clear.pixelColor(clear.width()//2,5).alpha(),0)
        self.assertEqual(clear.pixelColor(12,clear.height()//2).alpha(),0)
        self.assertFalse(window._header.isVisible())
        self.assertIs(window._clock,clock);self.assertIs(window.viewport,viewport)
        self.assertEqual(len(viewport.scenes),count)
        self.assertEqual(window.components.text(),window._spec['case']['label'])
        self.assertTrue(window.reading_summary._contrast)
        self.controller.changeAssembly('desktop_frame',True)
        self.assertTrue(window._header.isVisible())
        self.assertEqual(window.components.text(),'整机概览')
        self.assertFalse(window.reading_summary._contrast)

    def test_selected_cpu_and_gpu_use_real_cached_readings_and_update_without_geometry(self):
        window=self.window;before=len(window.viewport.scenes)
        window.viewport.componentSelected.emit('cpu')
        self.assertIn('62 °C',window.reading_summary.text())
        self.assertIn('65.0 W',window.reading_summary.text())
        window.viewport.componentSelected.emit('gpu')
        self.assertIn('44 °C',window.reading_summary.text())
        self.assertNotIn('62 °C',window.reading_summary.text())
        self.controller.readings['gpus']['0']['gpu_temp']=51;self.controller.dataChanged.emit()
        self.assertIn('51 °C',window.reading_summary.text())
        self.assertEqual(len(window.viewport.scenes),before)

    def test_unknown_board_does_not_borrow_cpu_or_gpu_temperature(self):
        self.window.viewport.componentSelected.emit('board')
        text=self.window.reading_summary.text()
        self.assertNotIn('62',text);self.assertNotIn('44',text);self.assertIn('—',text)
        self.assertIn('独立传感器',self.window.reading_summary.toolTip())

    def test_stale_and_reference_cpu_values_remain_unavailable(self):
        self.window.viewport.componentSelected.emit('cpu')
        self.controller.readings['time']=time.time()-60;self.controller.dataChanged.emit()
        self.assertNotIn('62 °C',self.window.reading_summary.text())
        self.assertIn('—',self.window.reading_summary.text())
        spec=copy.deepcopy(self.controller.spec);spec['cpu']['telemetry_bound']=False
        self.controller.spec=spec;self.controller.readings['time']=time.time()
        self.window.synchronize(spec)
        self.assertNotIn('62 °C',self.window.reading_summary.text())

    def test_compact_minimum_has_visible_readings_and_no_editor_sized_empty_shell(self):
        self.window.resize(280,300);self.app.processEvents()
        self.assertEqual(self.window.width(),280);self.assertEqual(self.window.height(),300)
        for item in (self.window.viewport,self.window.reading_summary,self.window.components):
            self.assertGreaterEqual(item.x(),0);self.assertLessEqual(item.x()+item.width(),280)
            self.assertLessEqual(item.y()+item.height(),300)
        self.assertGreater(self.window.viewport.height(),100)

    def test_single_clock_stops_on_hide_and_close_releases_resources(self):
        window=self.window;viewport=window.viewport
        viewport.animationActiveChanged.emit(True)
        self.assertTrue(window._clock.property('active'))
        window.hide();self.assertFalse(window._clock.property('active'))
        window.show();viewport.animationActiveChanged.emit(True)
        QTest.qWait(110);self.assertGreater(viewport.animation_ticks,0)
        spy=QSignalSpy(window.closed);window.close()
        self.assertEqual(spy.count(),1);self.assertTrue(viewport.released)
        self.assertFalse(self.controller.active);self.assertIsNone(window._clock)
        self.assertEqual(window._connections,[])

    def test_alt_drag_moves_window_and_plain_model_press_is_not_intercepted(self):
        window=self.window;viewport=window.viewport
        old=window.pos();point=QPoint(18,20)
        press=QMouseEvent(QEvent.MouseButtonPress,point,viewport.mapToGlobal(point),
                          Qt.LeftButton,Qt.LeftButton,Qt.NoModifier)
        self.assertFalse(window.eventFilter(viewport,press))
        alt=QMouseEvent(QEvent.MouseButtonPress,point,viewport.mapToGlobal(point),
                        Qt.LeftButton,Qt.LeftButton,Qt.AltModifier)
        self.assertTrue(window.eventFilter(viewport,alt))
        delta=QPoint(24,17);new=point+delta
        move=QMouseEvent(QEvent.MouseMove,new,viewport.mapToGlobal(new),
                         Qt.NoButton,Qt.LeftButton,Qt.AltModifier)
        self.assertTrue(window.eventFilter(viewport,move));self.assertEqual(window.pos(),old+delta)
        release=QMouseEvent(QEvent.MouseButtonRelease,new,viewport.mapToGlobal(new),
                            Qt.LeftButton,Qt.NoButton,Qt.AltModifier)
        self.assertTrue(window.eventFilter(viewport,release));self.assertIsNone(window._move_offset)

    def test_host_gate_survives_data_and_frame_changes_without_reopening_clock(self):
        window=self.window;viewport=window.viewport;clock=window._clock;scenes=len(viewport.scenes)
        window.setProperty('modelMotionAllowed',False);window.update_readings()
        self.controller.changeAssembly('desktop_frame',False)
        self.controller.changeAssembly('fan_animation',True)
        self.controller.dataChanged.emit();viewport.animationActiveChanged.emit(True)
        self.assertFalse(viewport.motion);self.assertFalse(viewport.enabled)
        self.assertFalse(clock.property('active'));self.assertIs(window._clock,clock)
        self.assertEqual(len(viewport.scenes),scenes)
        window.setProperty('modelMotionAllowed',True);window.update_readings()
        self.assertTrue(viewport.motion);self.assertTrue(viewport.enabled)
        self.assertIs(window._clock,clock)

    def test_failed_desktop_profile_conversion_releases_clock_connections_and_viewport(self):
        controller=DesktopController(copy.deepcopy(self.controller.spec))
        created=[]
        def factory(parent):
            viewport=DesktopViewport(parent);created.append(viewport);return viewport
        with patch('assembly_window.bake_profiles',side_effect=RuntimeError('injected failure')):
            with self.assertRaisesRegex(RuntimeError,'injected failure'):
                create_assembly_window(controller,self.engine,controller.spec,viewport_factory=factory)
        self.assertFalse(controller.active);self.assertTrue(created[0].released)
        for name in ('2dataChanged()','2assemblyChanged()','2motionChanged()'):
            self.assertEqual(controller.receivers(name),0)
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_context_actions_change_frame_open_inspection_and_preserve_selection(self):
        with patch.object(QMenu,'popup'):
            self.window._show_menu(QPoint(0,0))
        menu=self.window._context_menu
        next(a for a in menu.actions() if a.text()=='显示小组件边框').trigger()
        self.assertFalse(self.window._desktop_frame)
        with patch.object(QMenu,'popup'):self.window._show_menu(QPoint(0,0))
        menu=self.window._context_menu
        next(a for a in menu.actions() if a.text()=='打开完整检视').trigger()
        self.assertEqual(self.controller.requests,['inspect'])
        with patch.object(QMenu,'popup'):self.window._show_menu(QPoint(0,0))
        menu=self.window._context_menu
        parts=next(a.menu() for a in menu.actions() if a.text()=='查看部件')
        next(a for a in parts.actions() if a.text()=='显卡').trigger()
        self.assertEqual(self.window.selected_component,'gpu')


class ZAssemblyDesktopRendererContractTests(unittest.TestCase):
    def test_renderer_clears_real_alpha_to_zero_and_requests_an_alpha_channel(self):
        # Record the actual clear call without creating a GL context or window.
        from assembly_viewer import AssemblyRenderer,surface_format
        self.assertGreaterEqual(surface_format().alphaBufferSize(),8)
        class StoppedAtClear(Exception):pass
        class Functions:
            def glViewport(self,*args):pass
            def glClearColor(self,*value):
                self.value=value
                raise StoppedAtClear
        renderer=AssemblyRenderer();renderer.functions=Functions();renderer.scene=object()
        with self.assertRaises(StoppedAtClear):renderer.draw(32,32,transparent_background=True)
        self.assertEqual(renderer.functions.value,(0.,0.,0.,0.))
        with self.assertRaises(StoppedAtClear):renderer.draw(32,32)
        self.assertEqual(renderer.functions.value[3],1.)


if __name__=='__main__':unittest.main()
