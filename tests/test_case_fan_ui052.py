"""Actual offscreen inspector and desktop actions for a reference fan mount."""
from unittest.mock import patch
import unittest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu
from assembly_desktop_widget import AssemblyWidgetWindow
import test_part_motion_ui052 as fixture


class FanViewport(fixture.PartViewport):
    def set_scene(self,spec):
        super().set_scene(spec);self.mount_released=False;self.mount_calls=[]
        self.scene.metadata['cooling']['parts'].append(dict(id='case-fan:0',kind='case_fan',
            label='Rear reference P12',model_id='arctic-p12-pwm',mount='rear'))

    def part_motion_state(self):
        if self.selected!='case-fan:0':return super().part_motion_state()
        released=getattr(self,'mount_released',False)
        return dict(target=self.selected,kind='case_fan',available=released and self.motion,
            reason='case_fan_mount_disengagement_reference' if released else 'case_fan_release_required',
            allowed_mount_release_part_ids=('case-fan:0',),released_mounts=('case-fan:0',) if released else (),
            mount_released=released,active=self.part_motion.active,progress=self.part_motion.progress,
            motion_target=self.part_motion.target,hidden_parts=tuple(self.hidden_parts),
            allowed_opened_mesh_names=(),retention_hidden=False,distance_mm=33.)

    def set_mount_released(self,value):
        if type(value) is not bool or self.selected!='case-fan:0' or not self.motion:return False
        self._reset_part();self.mount_released=value;self.mount_calls.append(value)
        self.partAssemblyChanged.emit();return True


class CaseFanUiTests(unittest.TestCase):
    setUpClass=classmethod(fixture.PartMotionUiTests.setUpClass.__func__)
    tearDown=fixture.PartMotionUiTests.tearDown
    control=fixture.PartMotionUiTests.control
    click=fixture.PartMotionUiTests.click
    select=fixture.PartMotionUiTests.select
    finish=fixture.PartMotionUiTests.finish

    def setUp(self):
        with patch.object(fixture,'PartViewport',FanViewport):fixture.PartMotionUiTests.setUp(self)

    def test_actual_release_checkbox_controls_the_same_finite_clock_and_guard(self):
        self.select('case-fan:0');window=self.window;view=window.viewport
        self.assertFalse(window.part_mount_release.isHidden());self.assertTrue(window.part_retention.isHidden())
        self.assertFalse(window.part_remove.isEnabled());self.assertTrue(window.part_mount_release.isEnabled())
        clock=window._clock;scenes=len(view.scenes)
        self.click('assemblyPartMountReleased');self.assertEqual(view.mount_calls,[True])
        self.assertTrue(window.part_remove.isEnabled())
        self.click('assemblyPartRemove');self.assertTrue(clock.property('active'))
        self.assertFalse(window.part_mount_release.isEnabled());self.finish()
        self.assertTrue(window.part_insert.isEnabled());self.click('assemblyPartInsert');self.finish()
        self.assertEqual(view.part_motion.progress,0.);self.assertIs(window._clock,clock)
        self.assertEqual(len(view.scenes),scenes)
        window.setProperty('modelMotionAllowed',False)
        self.assertFalse(window._toggle_mount_release(False));self.assertEqual(view.mount_calls,[True])

    def test_desktop_reference_release_action_keeps_individual_selection(self):
        widget=AssemblyWidgetWindow(self.controller,self.engine,self.controller.spec,viewport_factory=FanViewport)
        try:
            widget.show();self.app.processEvents();widget._select_part('case-fan:0')
            self.assertEqual(widget.selected_component,'case-fan:0')
            with patch.object(QMenu,'popup',lambda *args:None):widget._show_menu(QPoint(20,20))
            menu=widget._context_menu
            release=next(a for a in menu.actions() if a.objectName()=='assemblyPartMountReleaseAction')
            remove=next(a for a in menu.actions() if a.objectName()=='assemblyPartRemoveAction')
            self.assertTrue(release.isEnabled());self.assertFalse(remove.isEnabled())
            release.trigger();self.app.processEvents()
            self.assertEqual(widget.viewport.mount_calls,[True]);self.assertFalse(widget._clock.property('active'))
        finally:widget.close();self.app.processEvents()


if __name__=='__main__':unittest.main()
