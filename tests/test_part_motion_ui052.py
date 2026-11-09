"""Actual inspector/menu input; fake QWidget viewport, finite pure motion only.

These tests verify host wiring, not real 3-D clearance or a removal procedure.
The planner/renderer have separate physical tests. No OpenGL widget is made.
"""
import copy
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt, Signal
from PySide6.QtQml import QQmlEngine
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication, QCheckBox, QMenu, QScrollArea, QWidget
from shiboken6 import isValid

from assembly_part_motion052 import PartMotion
from assembly_gpu_insertion049 import GpuInsertion
from assembly_spec import build_spec
from assembly_window import AssemblyWindow
from assembly_desktop_widget import AssemblyWidgetWindow
from stats_config import DEFAULT
import test_assembly_window as foundation


class PartViewport(foundation.Viewport):
    """A finite-state viewport double, without a planner, meshes or GL calls."""
    partAssemblyChanged = Signal()
    gpuAssemblyChanged = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.part_motion = PartMotion(); self.gpu_motion = GpuInsertion()
        self.part_calls = []; self.hidden_calls = []; self.retention_calls = []
        self.gpu_calls = []; self.hidden_parts = set(); self.retention = False
        self.blocked_reason = ''; self.scene = None

    def set_scene(self, spec):
        super().set_scene(spec)
        self.scene = SimpleNamespace(metadata={'hardware': {'parts': [
            dict(id='cpu:0', component='cpu', label='Reference CPU'),
            dict(id='memory:0', component='memory', label='Reference DIMM A2'),
            dict(id='memory:1', component='memory', label='Reference DIMM B2')
        ]}, 'cooling': {'parts': [dict(id='cooler:0', component='cooler', label='Reference cooler')]}})
        self.part_motion.reset(); self.gpu_motion.reset()
        self.hidden_parts.clear(); self.retention = False

    def set_transparent_background(self, value): self.transparent = value

    def part_motion_state(self):
        target = self.selected
        supported = target in ('cpu', 'cpu:0', 'memory:0', 'memory:1')
        reason = self.blocked_reason
        if not supported: reason = 'choose_cpu_or_memory'
        elif not self.motion: reason = 'motion_disabled'
        elif target in self.hidden_parts: reason = 'target_hidden'
        allowed = ('detail-board-retention-lever',) if target.startswith('cpu') else (
            ('board-dimm-end-latches',) if target.startswith('memory:') else ())
        return dict(target=target, available=supported and not reason,
                    reason=reason, active=self.part_motion.active,
                    progress=self.part_motion.progress, motion_target=self.part_motion.target,
                    hidden_parts=tuple(sorted(self.hidden_parts)), retention_hidden=self.retention,
                    allowed_opened_mesh_names=allowed, blocked_by=('cooler:0',) if reason else (),
                    scope='visible_reference_clearance', full_case_extraction=False,
                    mechanical_installation_complete=False)

    def preview_part_motion(self, removed=True):
        if not self.motion or not self.part_motion_state()['available']: return False
        result = self.part_motion.start(removed)
        if result:
            self.part_calls.append((self.selected, removed))
            self.animationActiveChanged.emit(True); self.partAssemblyChanged.emit()
        return result

    def _reset_part(self):
        if self.part_motion.reset():
            self.animationActiveChanged.emit(False); self.partAssemblyChanged.emit()

    def set_part_hidden(self, target, enabled):
        self.hidden_calls.append((target, enabled)); self._reset_part()
        if enabled: self.hidden_parts.add(target)
        else: self.hidden_parts.discard(target)
        self.retention = False; self.partAssemblyChanged.emit(); return True

    def restore_hidden_parts(self):
        changed = bool(self.hidden_parts or self.retention)
        self._reset_part(); self.hidden_parts.clear(); self.retention = False
        self.partAssemblyChanged.emit(); return changed

    def set_retention_hidden(self, enabled):
        if enabled and not self.part_motion_state()['allowed_opened_mesh_names']: return False
        self.retention_calls.append(enabled); self._reset_part(); self.retention = enabled
        self.partAssemblyChanged.emit(); return True

    def select_component(self, name):
        if name != self.selected:
            self._reset_part(); self.retention = False
        super().select_component(name); self.partAssemblyChanged.emit(); return True

    def set_motion_enabled(self, value):
        super().set_motion_enabled(value)
        if not value:
            self._reset_part()
            if self.gpu_motion.reset(): self.gpuAssemblyChanged.emit()

    def gpu_insertion_state(self):
        return dict(available=self.motion, active=self.gpu_motion.active,
                    progress=self.gpu_motion.progress, target=self.gpu_motion.target, reason='')

    def preview_gpu_insertion(self, removed=True):
        if not self.motion: return False
        result = self.gpu_motion.start(removed)
        if result:
            self.gpu_calls.append(removed)
            self.animationActiveChanged.emit(True); self.gpuAssemblyChanged.emit()
        return result

    def advance_animations(self, elapsed):
        self.animation_ticks += 1
        was_part, was_gpu = self.part_motion.active, self.gpu_motion.active
        self.part_motion.advance(elapsed); self.gpu_motion.advance(elapsed)
        if was_part and not self.part_motion.active: self.partAssemblyChanged.emit()
        if was_gpu and not self.gpu_motion.active: self.gpuAssemblyChanged.emit()
        self.animationActiveChanged.emit(self.part_motion.active or self.gpu_motion.active)

    def refresh_visibility(self):
        if not self.isVisible() or self.window().isMinimized(): self._reset_part()

    def hideEvent(self, event):
        self._reset_part(); super().hideEvent(event)

    def closeEvent(self, event):
        self._reset_part(); self.hidden_parts.clear(); self.retention = False
        super().closeEvent(event)


class PartMotionUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != 'offscreen': raise unittest.SkipTest('Offscreen only')

    def setUp(self):
        for name in ('ctypes.WinDLL', 'subprocess.Popen', 'threading.Thread.start', 'socket.socket'):
            self.enterContext(patch(name, side_effect=AssertionError('No native window, GL, devices or workers')))
        spec = build_spec(dict(cpu_name='Intel Core i7-13700KF', gpus={'0': dict(gpu_name='RTX 5090')}),
                          copy.deepcopy(DEFAULT), dict(state='unavailable'), [])
        self.controller = foundation.Controller(spec)
        self.controller.fan = dict(available=False)
        self.controller.openAssemblyInspect = lambda: None
        self.engine = QQmlEngine(); self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(r.toString() for r in rows))
        self.window = AssemblyWindow(self.controller, self.engine, spec, viewport_factory=PartViewport)
        self.window.show(); self.app.processEvents()

    def tearDown(self):
        if self.window is not None: self.window.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); self.app.processEvents()
        self.engine.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertEqual(self.warnings, [])

    def control(self, name):
        result = self.window.findChild(QWidget, name)
        self.assertIsNotNone(result, name)
        return result

    def click(self, name):
        value = self.control(name)
        scroll = self.window.findChild(QScrollArea, 'assemblyInspectorScroll')
        if scroll is not None: scroll.ensureWidgetVisible(value)
        self.app.processEvents()
        point = QPoint(8, value.height()//2) if isinstance(value, QCheckBox) else value.rect().center()
        QTest.mouseClick(value, Qt.LeftButton, pos=point); self.app.processEvents()

    def select(self, target):
        choice = self.window.component_choice
        index = choice.findData(target); self.assertGreaterEqual(index, 0, target)
        choice.setFocus(); QTest.keyClick(choice, Qt.Key_Home)
        # Keyboard navigation skips the nonselectable separator row.
        for _ in range(choice.count()):
            if choice.currentIndex() >= index: break
            QTest.keyClick(choice, Qt.Key_Down)
        self.app.processEvents(); self.assertEqual(choice.currentData(), target)
        self.assertEqual(self.window.selected_component, target)

    def finish(self, window=None):
        window = window or self.window
        for _ in range(8): window.advanceFrame(136.)
        self.assertFalse(window._clock.property('active'))

    def test_actual_cpu_buttons_finish_hold_and_insert_without_rebake_or_sampling(self):
        self.select('cpu:0'); view = self.window.viewport; scenes = len(view.scenes)
        clock = self.window._clock
        original = copy.deepcopy((self.controller.readings, self.controller.draft, self.controller.spec))
        changed = QSignalSpy(self.controller.assemblyChanged); samples = QSignalSpy(self.controller.dataChanged)
        self.assertTrue(self.control('assemblyPartRemove').isEnabled())
        self.assertFalse(self.control('assemblyPartInsert').isEnabled())
        with patch('assembly_window.bake_profiles', side_effect=AssertionError('Motion cannot rebake')):
            self.click('assemblyPartRemove')
            self.assertTrue(self.window._clock.property('active'))
            self.assertFalse(self.control('assemblyPartRemove').isEnabled())
            self.assertFalse(self.control('assemblyPartInsert').isEnabled())
            self.finish(); self.assertEqual(view.part_motion.progress, 1.)
            self.assertTrue(self.control('assemblyPartInsert').isEnabled())
            for _ in range(4): self.window.advanceFrame(136.)
            self.assertEqual(view.part_motion.progress, 1.)  # No automatic return.
            self.click('assemblyPartInsert'); self.finish()
        self.assertEqual(view.part_calls, [('cpu:0', True), ('cpu:0', False)])
        self.assertEqual(view.part_motion.progress, 0.); self.assertEqual(len(view.scenes), scenes)
        self.assertIs(self.window._clock, clock)
        self.assertEqual((changed.count(), samples.count()), (0, 0))
        self.assertEqual((self.controller.readings, self.controller.draft, self.controller.spec), original)

    def test_each_dimm_selector_targets_only_its_own_finite_action_and_old_gpu_stays_available(self):
        for target in ('memory:0', 'memory:1'):
            self.select(target)
            self.assertEqual(self.window._part_assembly_state()['target'], target)
            self.assertIn('A2' if target.endswith('0') else 'B2', self.window.components.text())
            self.click('assemblyPartRemove'); self.finish()
            self.click('assemblyPartInsert'); self.finish()
        self.assertEqual(self.window.viewport.part_calls, [('memory:0', True), ('memory:0', False),
                                                          ('memory:1', True), ('memory:1', False)])
        self.select('gpu')
        self.assertFalse(self.control('assemblyPartRemove').isVisible())
        QTest.mouseClick(self.window.gpu_remove, Qt.LeftButton); self.finish()
        self.assertEqual(self.window.viewport.gpu_calls, [True])
        self.assertEqual(len(self.window.viewport.scenes), 1)

    def test_temporary_hide_and_restore_are_model_masks_without_persisting_or_rebuilding(self):
        self.select('cooler:0'); view = self.window.viewport
        before = copy.deepcopy((self.controller.draft, self.controller.spec))
        with patch('assembly_window.bake_profiles', side_effect=AssertionError('Mask cannot rebake')):
            self.click('assemblyPartHidden')
            self.assertEqual(view.hidden_parts, {'cooler:0'})
            self.assertTrue(self.control('assemblyPartHidden').isChecked())
            self.assertTrue(self.control('assemblyRestoreHidden').isEnabled())
            self.assertGreaterEqual(self.window.component_choice.findData('cooler:0'), 0)
            self.click('assemblyRestoreHidden')
        self.assertEqual(view.hidden_parts, set())
        self.assertFalse(self.control('assemblyPartHidden').isChecked())
        self.assertFalse(self.control('assemblyRestoreHidden').isEnabled())
        self.assertEqual((self.controller.draft, self.controller.spec), before)
        self.assertEqual(len(view.scenes), 1); self.assertFalse(self.window._clock.property('active'))

    def test_retention_toggle_obeys_state_capability_and_clears_with_restore(self):
        self.select('cpu:0'); view = self.window.viewport
        self.assertEqual(self.window._part_assembly_state()['allowed_opened_mesh_names'],
                         ('detail-board-retention-lever',))
        self.assertTrue(self.control('assemblyPartRetentionHidden').isEnabled())
        self.click('assemblyPartRetentionHidden')
        self.assertTrue(view.retention); self.assertEqual(view.retention_calls, [True])
        self.assertTrue(self.window._part_assembly_state()['retention_hidden'])
        self.click('assemblyRestoreHidden')
        self.assertFalse(view.retention)
        self.assertFalse(self.control('assemblyPartRetentionHidden').isChecked())
        self.assertFalse(self.window._clock.property('active')); self.assertEqual(len(view.scenes), 1)

    def test_game_guard_rejects_actions_before_stale_viewport_motion_is_refreshed(self):
        self.select('memory:0')
        self.window.setProperty('modelMotionAllowed', False)
        self.window.viewport.motion = True
        self.assertFalse(self.window._preview_part_motion(True))
        self.assertEqual(self.window.viewport.part_calls, [])
        self.assertFalse(self.window._toggle_part_hidden(True))
        self.assertFalse(self.window._toggle_retention(True))
        self.assertFalse(self.window._restore_hidden())
        self.assertEqual(self.window.viewport.hidden_calls, [])
        self.assertEqual(self.window.viewport.retention_calls, [])
        self.assertFalse(self.window._clock.property('active'))
        self.controller.motionEnabled = False; self.controller.motionChanged.emit()
        self.assertFalse(self.control('assemblyPartRemove').isEnabled())

    def test_hide_minimize_and_close_stop_shared_clock_and_disconnect_ownership(self):
        self.select('cpu:0'); self.click('assemblyPartRemove'); self.window.advanceFrame(136.)
        self.window.hide(); self.app.processEvents()
        self.assertFalse(self.window._clock.property('active'))
        self.window.show(); self.app.processEvents()
        self.click('assemblyPartRemove'); self.window.advanceFrame(136.)
        self.window.showMinimized(); self.app.processEvents()
        self.assertFalse(self.window._clock.property('active'))
        self.window.showNormal(); self.app.processEvents()
        self.click('assemblyPartRemove')
        clock = self.window._clock; view = self.window.viewport
        self.assertTrue(clock.property('active'))
        self.window.close()
        self.assertFalse(clock.property('active')); self.assertIsNone(self.window._clock)
        self.assertTrue(view.released); self.assertFalse(self.controller.active)
        self.assertEqual(self.window._connections, [])
        for signal in ('2dataChanged()', '2assemblyChanged()', '2motionChanged()'):
            self.assertEqual(self.controller.receivers(signal), 0)

    def test_desktop_menu_actions_share_part_state_and_restore_without_popup_or_geometry(self):
        widget = AssemblyWidgetWindow(self.controller, self.engine, self.controller.spec, viewport_factory=PartViewport)
        try:
            widget.show(); self.app.processEvents(); widget._select_part('memory:1')
            with patch.object(QMenu, 'popup'): widget._show_menu(QPoint())
            actions = {action.objectName(): action for action in widget._context_menu.actions() if action.objectName()}
            self.assertIn('assemblyPartRemoveAction', actions)
            actions['assemblyPartRemoveAction'].trigger(); self.finish(widget)
            self.assertEqual(widget.viewport.part_calls, [('memory:1', True)])
            with patch.object(QMenu, 'popup'): widget._show_menu(QPoint())
            actions = {action.objectName(): action for action in widget._context_menu.actions() if action.objectName()}
            self.assertTrue(actions['assemblyPartInsertAction'].isEnabled())
            actions['assemblyPartInsertAction'].trigger(); self.finish(widget)
            actions['assemblyPartHiddenAction'].trigger()
            self.assertEqual(widget.viewport.hidden_parts, {'memory:1'})
            with patch.object(QMenu, 'popup'): widget._show_menu(QPoint())
            actions = {action.objectName(): action for action in widget._context_menu.actions() if action.objectName()}
            actions['assemblyRestoreHiddenAction'].trigger()
            self.assertEqual(widget.viewport.hidden_parts, set()); self.assertEqual(len(widget.viewport.scenes), 1)
        finally: widget.close()

    def test_unknown_and_blocked_reasons_use_readable_explanations(self):
        self.select('cpu:0'); self.window.viewport.blocked_reason = 'future_internal_clearance_reason'
        self.window.viewport.partAssemblyChanged.emit(); self.app.processEvents()
        self.assertFalse(self.control('assemblyPartRemove').isEnabled())
        text = self.window._part_assembly_reason(self.window._part_assembly_state())
        self.assertTrue(text); self.assertNotIn('_', text)
        self.assertNotIn('future_internal_clearance_reason', text)

    def test_actual_popup_closes_when_owner_is_hidden_or_minimized(self):
        # An actual offscreen QMenu is required: mocking popup() cannot reveal
        # its independent top-level visibility when a game hides its owner.
        widget = AssemblyWidgetWindow(self.controller, self.engine, self.controller.spec,
                                      viewport_factory=PartViewport)
        try:
            widget.show(); self.app.processEvents(); widget._select_part('memory:1')
            for mode in ('hide', 'minimize'):
                with self.subTest(mode=mode):
                    widget.showNormal(); self.app.processEvents()
                    widget._show_menu(QPoint()); self.app.processEvents()
                    menu = widget._context_menu; spy = QSignalSpy(menu.aboutToHide)
                    self.assertTrue(menu.isVisible())
                    if mode == 'hide': widget.hide()
                    else: widget.showMinimized()
                    self.app.processEvents()
                    self.assertFalse(isValid(menu) and menu.isVisible())
                    self.assertGreaterEqual(spy.count(), 1)
                    self.assertFalse(widget._clock.property('active'))
                    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                    self.assertIsNone(widget._context_menu)
                    # An action already queued before the game/visibility
                    # change must not reopen a top-level popup afterwards.
                    widget._show_menu(QPoint()); self.app.processEvents()
                    self.assertIsNone(widget._context_menu)
            widget.showNormal(); self.app.processEvents()
            widget.setProperty('modelMotionAllowed', False)
            widget._show_menu(QPoint()); self.app.processEvents()
            self.assertIsNone(widget._context_menu)
            self.assertEqual(len(widget.viewport.scenes), 1)
        finally: widget.close()


if __name__ == '__main__': unittest.main()
