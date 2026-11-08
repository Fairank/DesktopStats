"""Independent PSU-cover display: real render/pick flow, no native GL/device."""
import copy
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')

from PySide6.QtCore import QCoreApplication,QEvent,QPoint,Qt
from PySide6.QtQml import QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMenu

from assembly_config import DEFAULT_ASSEMBLY,validate_assembly
from assembly_geometry import Mesh,Scene,box,vertex_bytes
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
from assembly_style import apply_model_styles
from assembly_visibility048 import mesh_visible
from assembly_viewer import AssemblyRenderer,AssemblyViewport,GL_LINES,GL_TRIANGLES
from stats_config import DEFAULT
from top_bar_config import HARDWARE_ICON_STYLES
from test_assembly_visibility048 import Backend
import test_assembly_window as window_helpers


def objects():
    return (Mesh('psu-shroud',box(30.,30.,1.),(.2,.3,.4,1.),(0.,0.,10.),'case'),
            Mesh('psu-shell',box(8.,8.,8.),(.3,.4,.5,1.),component='psu',part_id='psu:0'),
            Mesh('case-depth-rail',box(2.,2.,30.),(.3,.4,.5,1.),(20.,15.,0.),'case'),
            Mesh('cable-0-atx24-rounded-loom',box(1.,1.,1.),(.1,.1,.1,1.),(20.,20.,0.),'cables'))


class PsuDisplay049Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        assert cls.app.platformName()=='offscreen'

    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(name,side_effect=AssertionError('No native GL, process, devices or sampling')))

    def renderer(self,style='miniature'):
        meshes,meta=apply_model_styles(objects(),style,{},(40.,40.,40.),{'front':'open'})
        node=AssemblyRenderer();node.program=Backend();node.buffer=Backend();node.vao=Backend();node.functions=Backend()
        node._uniforms={'backgroundMode':1,'shadeMix':2};node.upload(Scene(meshes,(40.,40.,40.),meta))
        self.addCleanup(node.close);return node

    def test_strict_persisted_default_and_controller_spec_routing(self):
        from assembly_tools import AssemblyTools
        self.assertIs(DEFAULT_ASSEMBLY['show_psu'],False)
        self.assertIs(validate_assembly({})['show_psu'],False)
        for value in (None,0,1,'true',[],{}):
            with self.assertRaises(ValueError):validate_assembly(dict(show_psu=value))
        edited=[];controller=SimpleNamespace(_draft={'assembly':validate_assembly()},edit=lambda value,**kw:edited.append((value,kw)))
        AssemblyTools.changeAssembly(controller,'show_psu',True)
        self.assertIs(edited[0][0]['assembly']['show_psu'],True)
        self.assertEqual(edited[0][1]['merge_key'],('assembly','show_psu'))
        for value in (False,True):
            spec=build_spec({},dict(assembly=dict(show_psu=value)),{},[],identify_case=lambda *a,**kw:{})
            self.assertIs(spec['show_psu'],value);self.assertIs(spec['options']['show_psu'],value)

    def test_defaults_keep_actual_cover_and_open_frame_never_loses_psu(self):
        for name in ('psu-shroud','top-psu-shroud','rear-chamber-shroud'):
            cover=SimpleNamespace(name=name,component='case')
            for cutaway in (False,True):
                self.assertTrue(mesh_visible(cover,cutaway))
                self.assertFalse(mesh_visible(cover,cutaway,True))
        psu=objects()[1]
        for cutaway in (False,True):
            for show in (False,True):self.assertTrue(mesh_visible(psu,cutaway,show))
        self.assertTrue(mesh_visible(SimpleNamespace(name='unknown-case-cover',component='case'),True,True))

    def test_all_styles_share_triangle_and_ink_gate_without_geometry_or_upload_changes(self):
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                node=self.renderer(style);before=vertex_bytes(node.scene);rows=node.ranges;edges=node.edge_ranges;calls=[]
                ink_names={row[0].name for row in edges}
                node._draw_part=lambda row,*a,**kw:calls.append((row[0].name,kw.get('mode',GL_TRIANGLES)))
                for cutaway in (False,True):
                    for show in (False,True,False):
                        calls.clear();node.draw(640,480,yaw=0.,pitch=0.,inspection_cutaway=cutaway,show_psu=show)
                        self.assertEqual(('psu-shroud',GL_TRIANGLES) in calls,not show)
                        self.assertIn(('psu-shell',GL_TRIANGLES),calls)
                        self.assertIn(('cable-0-atx24-rounded-loom',GL_TRIANGLES),calls)
                        if node.edge_ranges:
                            self.assertEqual(('psu-shroud',GL_LINES) in calls,not show and 'psu-shroud' in ink_names)
                            if 'psu-shell' in ink_names:self.assertIn(('psu-shell',GL_LINES),calls)
                if style=='notebook_line':self.assertIn('psu-shroud',ink_names);self.assertIn('psu-shell',ink_names)
                self.assertEqual(vertex_bytes(node.scene),before);self.assertIs(node.ranges,rows);self.assertIs(node.edge_ranges,edges)
                self.assertEqual(node.upload_count,1);self.assertEqual(sum(name=='allocate' for name,args in node.buffer.calls),1)
                node.close();self.assertEqual(node._psu_cover_ids,frozenset())

    def test_real_triangle_pick_restores_cover_occlusion_and_psu_focus_still_displays(self):
        node=self.renderer('notebook_line');node._draw_part=lambda *a,**kw:None
        for cutaway in (False,True):
            for show,expected in ((False,'case'),(True,'psu:0'),(False,'case')):
                node.draw(640,480,yaw=0.,pitch=0.,inspection_cutaway=cutaway,show_psu=show)
                point=node.project_point((0.,0.,0.));self.assertEqual(node.pick(*point[:2]),expected)
        node.draw(640,480,yaw=0.,pitch=0.,focus='psu',inspection_cutaway=True,show_psu=False)
        point=node.project_point((0.,0.,0.));self.assertEqual(node.pick(*point[:2]),'psu:0')
        self.assertEqual(node.upload_count,1)

    def test_show_flag_is_not_a_physical_cache_field_or_profile_rebake_trigger(self):
        base=Scene(objects(),(40.,40.,40.),{'visual_style':'miniature'});built=[];cache=SceneCache()
        def build(value):built.append(value);return base
        with patch('assembly_scene_cache.build_scene',side_effect=build):
            for value in (False,True,False):self.assertIs(cache.build(dict(visual_style='miniature',show_psu=value)),base)
        self.assertEqual(len(built),1);self.assertNotIn('show_psu',built[0])
        updates=[];draws=[]
        renderer=SimpleNamespace(_pick_state={'old':True},draw=lambda *a,**kw:draws.append(kw))
        view=SimpleNamespace(_renderer=renderer,_show_psu=False,_error='',_pending=False,
            _yaw=0.,_pitch=0.,_zoom=1.,_exploded=False,_phase=0.,_dark=False,_focus='all',
            _transparent_background=False,update=lambda:updates.append(True),devicePixelRatioF=lambda:1.,width=lambda:320,height=lambda:240)
        AssemblyViewport.set_show_psu(view,True);self.assertIsNone(renderer._pick_state);self.assertFalse(view._pending)
        AssemblyViewport.set_show_psu(view,True);self.assertEqual(updates,[True])
        AssemblyViewport.paintGL(view);self.assertIs(draws[-1]['show_psu'],True)
        AssemblyViewport.set_show_psu(view,False);AssemblyViewport.paintGL(view);self.assertNotIn('show_psu',draws[-1])

    def test_actual_power_stays_unknown_and_oled_never_borrows_cpu_gpu_or_rated_watts(self):
        from assembly_inspection import snapshot
        from component_catalog import get_component
        data=dict(time=100.,cpu_power=120.,gpus={'0':dict(gpu_power=400.)})
        identity='asus-rog-thor-1000p2';model=get_component(identity)
        result=snapshot(data,dict(auxiliary=dict(psu=dict(model_id=identity))),{},'psu',now=100.)
        rows={row['label']:row for row in result['rows']}
        self.assertEqual(rows['额定功率']['value'],'1000 W');self.assertTrue(rows['额定功率']['available'])
        self.assertFalse(rows['实际功率']['available']);self.assertNotIn('520',rows['实际功率']['value'])
        self.assertTrue(model['oled_display']);self.assertFalse(model['oled_live_telemetry'])
        self.assertIn('OLED 仅示意外观，尚未绑定功率读数。',result['notes'])

    def test_real_inspector_checkbox_and_desktop_action_share_only_display_state(self):
        from assembly_window import AssemblyWindow
        from assembly_desktop_widget import AssemblyWidgetWindow
        class Viewport(window_helpers.Viewport):
            def set_show_psu(self,value):self.show_psu=value
        spec=build_spec({},copy.deepcopy(DEFAULT),{},[])
        controller=window_helpers.Controller(spec);controller.fan=dict(available=False);controller.openAssemblyInspect=lambda:None
        engine=QQmlEngine();warnings=[];engine.warnings.connect(lambda rows:warnings.extend(row.toString() for row in rows))
        window=AssemblyWindow(controller,engine,spec,viewport_factory=Viewport);widget=None
        try:
            window.show();self.app.processEvents();before=len(window.viewport.scenes)
            self.assertFalse(window.show_psu.isChecked());self.assertFalse(window.viewport.show_psu)
            with patch('assembly_window.bake_profiles',side_effect=AssertionError('Display only; no profile rebake')):
                QTest.mouseClick(window.show_psu,Qt.LeftButton);self.assertTrue(controller.spec['options']['show_psu'])
                self.assertTrue(window.viewport.show_psu);self.assertEqual(len(window.viewport.scenes),before)
                QTest.mouseClick(window.show_psu,Qt.LeftButton);self.assertFalse(window.viewport.show_psu)
            widget=AssemblyWidgetWindow(controller,engine,controller.spec,viewport_factory=Viewport);widget.show();self.app.processEvents()
            before=len(widget.viewport.scenes)
            with patch.object(QMenu,'popup'),patch('assembly_window.bake_profiles',side_effect=AssertionError('Desktop action must not rebake')):
                widget._show_menu(QPoint());actions={a.text():a for a in widget._context_menu.actions()}
                self.assertTrue(actions['展示电源'].isCheckable());self.assertFalse(actions['展示电源'].isChecked())
                actions['展示电源'].trigger();self.assertTrue(widget.viewport.show_psu)
                self.assertTrue(window.show_psu.isChecked());self.assertEqual(len(widget.viewport.scenes),before)
            self.assertFalse(widget._clock.property('active'))
        finally:
            if widget is not None:widget.close()
            window.close();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
            engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(warnings,[])

    def test_actual_qml_toggle_changes_the_saved_assembly_preference(self):
        import test_assembly_page as page
        helper=page.AssemblyPageTests();helper.setUpClass();helper.setUp()
        try:
            helper.show_assembly();toggle=helper.find('assemblyShowPsuToggle')
            self.assertFalse(toggle.property('checked'))
            page_root=helper.find('assemblyPageLoader').property('item');scroll=page_root.property('contentItem')
            scroll.setProperty('contentY',max(0.,scroll.property('contentHeight')-scroll.property('height')));QTest.qWait(30)
            helper.click(toggle);self.app.processEvents()
            self.assertIs(helper.controller._draft['assembly']['show_psu'],True)
            self.assertTrue(toggle.property('checked'))
            self.assertEqual(helper.controller.scopeDirty,dict(desktop=False,preferences=True,topbar=False))
            helper.click(toggle);self.app.processEvents()
            self.assertIs(helper.controller._draft['assembly']['show_psu'],False)
            self.assertEqual(helper.controller.scopeDirty,dict(desktop=False,preferences=False,topbar=False))
        finally:helper.tearDown();helper.doCleanups()


if __name__=='__main__':unittest.main()
