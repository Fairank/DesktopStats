"""Optional renderer ownership and fan clocks, without a graphics context or probes."""
import copy
import os
import sys
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent,QObject,Signal,QRect
from PySide6.QtQml import QQmlEngine
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QApplication,QWidget

from assembly_spec import build_spec
from assembly_config import target_screen
from assembly_window import AssemblyWindow
from stats_config import DEFAULT


class Controller(QObject):
    assemblyChanged=Signal();dataChanged=Signal();motionChanged=Signal()

    def __init__(self,spec):
        super().__init__();self.spec=spec;self.theme='light';self.motionEnabled=True;self.active=False
        self.fan=dict(available=True,rpm=1200,timestamp=time.time())
    def tr(self,text):return text
    def assembly_specification(self):return copy.deepcopy(self.spec)
    def set_assembly_viewer_active(self,value):self.active=value
    def assembly_fan_state(self):return copy.deepcopy(self.fan)
    def changeAssembly(self,key,value):
        self.spec['options'][key]=value;self.assemblyChanged.emit()


class Viewport(QWidget):
    rendererError=Signal(str);animationActiveChanged=Signal(bool)
    def __init__(self,parent):
        super().__init__(parent);self.scenes=[];self.frames=[];self.fan=None;self.enabled=False;self.released=False
    def set_dark(self,value):pass
    def set_scene(self,spec):self.scenes.append(spec)
    def set_exploded(self,value):self.exploded=value
    def set_fan_animation_enabled(self,value):self.enabled=value
    def set_fan_state(self,rpm,available,timestamp=None):self.fan=(rpm,available,timestamp)
    def advance_fans(self,elapsed):self.frames.append(elapsed)
    def focus_component(self,name):self.focus=name
    def reset_camera(self):pass
    def closeEvent(self,event):self.released=True;event.accept()


class AssemblyWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native query')))
        self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No process')))
        spec=build_spec(dict(cpu_name='Intel Core i7-13700KF',gpus={'0':dict(gpu_name='RTX 5090')}),
                        copy.deepcopy(DEFAULT),dict(state='unavailable'),[])
        self.controller=Controller(spec);self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.window=AssemblyWindow(self.controller,self.engine,spec,viewport_factory=Viewport)

    def tearDown(self):
        if self.window is not None:self.window.close()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(self.warnings,[])

    def test_numeric_readings_and_options_do_not_rebuild_geometry(self):
        self.assertNotIn('assembly_viewer',sys.modules)
        self.assertEqual(len(self.window.viewport.scenes),1)
        for rpm in (1200,1300,1400):
            self.controller.fan.update(rpm=rpm,timestamp=time.time());self.controller.dataChanged.emit()
        self.controller.changeAssembly('exploded',True)
        self.controller.changeAssembly('fan_animation',True)
        self.assertEqual(len(self.window.viewport.scenes),1)
        self.assertTrue(self.window.viewport.exploded)
        self.assertTrue(self.window.viewport.enabled)
        self.assertEqual(self.window.viewport.fan[0],1400)
        self.assertIn('1400 RPM',self.window.status.text())

    def test_stored_native_screen_identity_is_used_instead_of_friendly_qt_label(self):
        first,second=object(),object();native={first:r'\\.\DISPLAY1',second:r'\\.\DISPLAY37'}
        bar=dict(monitor_mode='selected',screens=[r'\\.\DISPLAY37'])
        self.assertIs(target_screen([first,second],bar,first,native.__getitem__),second)
        self.assertIsNone(target_screen([first],bar,first,native.__getitem__))
        self.assertIsNone(target_screen([second,second],bar,first,native.__getitem__))
        self.assertIsNone(target_screen([first,second],dict(monitor_mode='selected'),first,native.__getitem__))

    def test_failed_profile_conversion_releases_partially_created_window_and_optional_work(self):
        controller=Controller(copy.deepcopy(self.controller.spec))
        before=set(self.app.topLevelWidgets())
        with patch('assembly_window.bake_profiles',side_effect=RuntimeError('injected profile failure')):
            with self.assertRaisesRegex(RuntimeError,'injected profile failure'):
                AssemblyWindow(controller,self.engine,controller.spec,viewport_factory=Viewport)
        self.assertFalse(controller.active)
        self.assertEqual(controller.receivers('2dataChanged()'),0)
        self.assertEqual(controller.receivers('2assemblyChanged()'),0)
        self.assertEqual(controller.receivers('2motionChanged()'),0)
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(set(self.app.topLevelWidgets()),before)

    def test_reopening_existing_view_moves_it_to_the_current_selected_screen(self):
        from unittest.mock import Mock
        from native_runtime import Runtime
        first,second=Mock(),Mock()
        second.availableGeometry.return_value=QRect(2560,-541,1440,2560)
        current=Mock();current.windowHandle.return_value=Mock()
        controller=SimpleNamespace(saved=dict(top_bar=dict(monitor_mode='selected',screens=['second'])),set_status=Mock())
        runtime=SimpleNamespace(headless=False,shutting_down=False,controller=controller,_assembly_window=current,
            app=SimpleNamespace(screens=lambda:[first,second],primaryScreen=lambda:first),
            top_bar=SimpleNamespace(adapter=SimpleNamespace(screen_identity=lambda s:SimpleNamespace(native_id='second' if s is second else 'first'))))
        Runtime.open_assembly_view(runtime,dict(example=True))
        current.windowHandle.return_value.setScreen.assert_called_once_with(second)
        current.move.assert_called_once();current.synchronize.assert_called_once_with(dict(example=True))
        current.showNormal.assert_called_once();controller.set_status.assert_not_called()

    def test_stale_reading_and_render_failure_stop_animation(self):
        self.controller.changeAssembly('fan_animation',True)
        self.window._last_fan['timestamp']=time.time()-4
        self.window.advanceFrame(16)
        self.assertEqual(self.window.viewport.fan,(None,False,None))
        self.assertEqual(self.window.viewport.frames,[])
        self.assertEqual(self.window.status.text(),'风扇转速不可用，保持静止')
        self.window.viewport.rendererError.emit('test')
        self.controller.dataChanged.emit()
        self.window.viewport.animationActiveChanged.emit(True)
        self.assertFalse(self.window.viewport.enabled)
        self.assertFalse(self.window._clock.property('active'))
        self.assertEqual(self.window.status.text(),'当前环境无法显示三维视图')

    def test_close_releases_renderer_disconnects_signals_and_retires_clock(self):
        self.assertTrue(self.controller.active)
        window=self.window;viewport=window.viewport;spy=QSignalSpy(window.closed)
        viewport.animationActiveChanged.emit(True);QTest.qWait(55)
        self.assertGreater(len(viewport.frames),0)
        self.assertTrue(window.close());self.window=None
        self.assertTrue(viewport.released);self.assertFalse(self.controller.active)
        self.assertEqual(spy.count(),1);self.assertIsNone(window._clock)
        self.assertEqual(self.controller.receivers('2dataChanged()'),0)
        self.controller.dataChanged.emit()


if __name__=='__main__':unittest.main()
