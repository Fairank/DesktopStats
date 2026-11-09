"""Actual inspector controls and desktop actions with an offscreen fake viewport."""
import copy
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication,QEvent,QPoint,Signal,Qt
from PySide6.QtQml import QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMenu
from assembly_gpu_insertion049 import GpuInsertion
from assembly_spec import build_spec
from assembly_window import AssemblyWindow
from stats_config import DEFAULT
from test_assembly_window import Controller,Viewport


class DemoViewport(Viewport):
    gpuAssemblyChanged=Signal()
    def __init__(self,parent):
        super().__init__(parent);self.gpu_motion=GpuInsertion();self.gpu_calls=[]
    def gpu_insertion_state(self):
        return dict(available=self.motion,reason='' if self.motion else '动效已关闭。',active=self.gpu_motion.active,
                    progress=self.gpu_motion.progress,target=self.gpu_motion.target)
    def preview_gpu_insertion(self,removed=True):
        self.gpu_calls.append(removed)
        result=self.motion and self.gpu_motion.start(removed)
        if result:self.animationActiveChanged.emit(True);self.gpuAssemblyChanged.emit()
        return result
    def advance_animations(self,elapsed):
        super().advance_animations(elapsed)
        active=self.gpu_motion.active;self.gpu_motion.advance(elapsed)
        if active and not self.gpu_motion.active:
            self.animationActiveChanged.emit(False);self.gpuAssemblyChanged.emit()
    def set_motion_enabled(self,value):
        super().set_motion_enabled(value)
        if not value and self.gpu_motion.reset():
            self.animationActiveChanged.emit(False);self.gpuAssemblyChanged.emit()


class GpuInsertionUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No device/process/native window')))
        spec=build_spec(dict(cpu_name='Intel Core i7-13700KF',gpus={'0':dict(gpu_name='RTX 5090')}),
                        copy.deepcopy(DEFAULT),dict(state='unavailable'),[])
        self.controller=Controller(spec);self.controller.fan=dict(available=False)
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.window=AssemblyWindow(self.controller,self.engine,spec,viewport_factory=DemoViewport)
        self.window.show();self.app.processEvents()

    def tearDown(self):
        self.window.close();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(self.warnings,[])

    def test_actual_buttons_remove_hold_insert_without_rebaking_or_setting_scene(self):
        view=self.window.viewport;before=len(view.scenes)
        self.assertTrue(self.window.gpu_remove.isEnabled());self.assertFalse(self.window.gpu_insert.isEnabled())
        with patch('assembly_window.bake_profiles',side_effect=AssertionError('Never rebake for insertion')):
            QTest.mouseClick(self.window.gpu_remove,Qt.LeftButton)
            self.assertTrue(self.window._clock.property('active'))
            self.assertFalse(self.window.gpu_remove.isEnabled());self.assertFalse(self.window.gpu_insert.isEnabled())
            for _ in range(8):self.window.advanceFrame(136.)
            self.assertFalse(self.window._clock.property('active'));self.assertEqual(view.gpu_motion.progress,1.)
            self.assertTrue(self.window.gpu_insert.isEnabled());self.assertIn('已脱离插槽',self.window.status.text())
            QTest.mouseClick(self.window.gpu_insert,Qt.LeftButton)
            for _ in range(8):self.window.advanceFrame(136.)
        self.assertEqual(view.gpu_calls,[True,False]);self.assertEqual(view.gpu_motion.progress,0.)
        self.assertEqual(len(view.scenes),before);self.assertFalse(self.window._clock.property('active'))

    def test_disabling_motion_resets_the_demo_and_disables_controls(self):
        QTest.mouseClick(self.window.gpu_remove,Qt.LeftButton);self.window.advanceFrame(136.)
        self.controller.motionEnabled=False;self.controller.motionChanged.emit()
        self.assertFalse(self.window._clock.property('active'));self.assertEqual(self.window.viewport.gpu_motion.progress,0.)
        self.assertFalse(self.window.gpu_remove.isEnabled());self.assertFalse(self.window.gpu_insert.isEnabled())
        self.assertIn('动效已关闭',self.window.gpu_assembly_hint.text())

    def test_close_releases_the_shared_clock_and_viewer_registration(self):
        QTest.mouseClick(self.window.gpu_remove,Qt.LeftButton)
        clock=self.window._clock;self.assertTrue(clock.property('active'))
        self.window.close()
        self.assertFalse(clock.property('active'));self.assertIsNone(self.window._clock)
        self.assertFalse(self.controller.active);self.assertTrue(self.window.viewport.released)

    def test_desktop_menu_reaches_the_same_finite_action_without_opening_a_popup(self):
        from assembly_desktop_widget import AssemblyWidgetWindow
        self.controller.openAssemblyInspect=lambda:None
        widget=AssemblyWidgetWindow(self.controller,self.engine,self.controller.spec,viewport_factory=DemoViewport)
        try:
            widget.show();self.app.processEvents()
            with patch.object(QMenu,'popup') as popup:widget._show_menu(QPoint())
            self.assertEqual(popup.call_count,1)
            actions={action.text():action for action in widget._context_menu.actions()}
            self.assertTrue(actions['拔出查看'].isEnabled());self.assertFalse(actions['插回插槽'].isEnabled())
            actions['拔出查看'].trigger()
            for _ in range(8):widget.advanceFrame(136.)
            self.assertEqual(widget.viewport.gpu_calls,[True]);self.assertEqual(widget.viewport.gpu_motion.progress,1.)
            self.assertFalse(widget._clock.property('active'))
        finally:widget.close()

    def test_unverified_or_unknown_internal_reason_uses_a_readable_explanation(self):
        for reason in ('cable_owner_unverified','future_internal_reason'):
            text=self.window._gpu_assembly_reason(dict(reason=reason))
            self.assertNotIn('_',text);self.assertNotIn(reason,text)

    def test_game_motion_guard_blocks_a_request_even_before_viewport_refresh(self):
        self.window.setProperty('modelMotionAllowed',False)
        self.window.viewport.motion=True
        self.assertFalse(self.window._preview_gpu_insertion(True))
        self.assertEqual(self.window.viewport.gpu_calls,[])
        self.assertFalse(self.window._clock.property('active'))


if __name__=='__main__':unittest.main()
