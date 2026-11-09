"""Real case constraints and pierced tray geometry; no UI/GL or device IO."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine
import hardware_packs
from hardware_packs import PackStore
from assembly_case_layout051 import HELIOS,SPEC,add_helios_tray,radiator_stack_check
from assembly_auxiliary import _segment_triangle,segment_hits_box
from assembly_cooling import add_cooling,_aio_route_issues,_lfiii_front_reference_paths
from assembly_geometry import build_scene
from assembly_parts import reference_preset,fit_messages
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
from case_fan_clearance047 import _bounds,conflicts
from chassis_catalog import CASES,get_case
from cooling_catalog import get_cooler,get_fan
from stats_config import DEFAULT

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


class CaseLayout051Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software-only layout construction')

    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No hardware/network/process/worker')))
        temporary=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(hardware_packs,'_store',PackStore(temporary/'packs')))
        self.case=get_case(HELIOS)

    def tearDown(self):
        self.assertEqual(self.app.topLevelWindows(),[])
        self.assertIsNone(QOpenGLContext.currentContext())

    def test_official_helios_limits_check_each_fan_bank_without_resizing(self):
        cooler=get_cooler('arctic-liquid-freezer-iii-360');fan=get_fan(cooler['fan_model'])
        before=copy.deepcopy((self.case,cooler,fan))
        top=radiator_stack_check(self.case,cooler,'top',fan)
        self.assertEqual(top['limit_mm'],60.)
        self.assertEqual(top['required_mm'],63.8)
        self.assertFalse(top['within_limit']);self.assertEqual(top['source'],SPEC)
        self.assertTrue(radiator_stack_check(self.case,cooler,'front',fan)['within_limit'])
        both=radiator_stack_check(self.case,dict(cooler,_radiator_fan_layout='push_pull'),'top',fan)
        self.assertEqual(both['required_mm'],89.6)
        bare=radiator_stack_check(self.case,dict(cooler,_radiator_fan_layout='none'),'top',fan)
        self.assertEqual(bare['required_mm'],38.);self.assertTrue(bare['within_limit'])
        self.assertFalse(top['placement_verified']);self.assertFalse(top['cad_fit_verified'])
        self.assertEqual((self.case,cooler,fan),before)

    def test_thinner_actual_27mm_radiator_is_allowed_and_unknown_cases_have_no_invented_limit(self):
        cooler=get_cooler('corsair-h150i-elite-capellix-xt');fan=get_fan(cooler['fan_model'])
        result=radiator_stack_check(self.case,cooler,'top',fan)
        self.assertEqual(result['required_mm'],52.8);self.assertTrue(result['within_limit'])
        self.assertIsNone(radiator_stack_check(get_case('fractal-north-xl-mesh'),cooler,'top',fan))
        self.assertIsNone(radiator_stack_check(self.case,cooler,'side',fan))

    def test_over_thick_top_selection_is_explicitly_rejected_not_moved_or_replaced_with_a_tower(self):
        selection=dict(cpu_cooler='arctic-liquid-freezer-iii-360',radiator_mount='top',case_fans=[])
        spec=dict(case=self.case,cooling=selection)
        anchors=dict(case_dimensions=(250.,591.,565.),cpu=dict(position=(84.,60.,-150.),normal=(-1.,0.,0.),up=(0.,1.,0.)))
        before=copy.deepcopy((spec,anchors))
        meshes,meta=add_cooling((),spec,'eco',anchors)
        self.assertEqual(meshes,())
        self.assertEqual(meta['parts'],[])
        self.assertEqual(meta['rejected'][0]['reason'],'radiator_fan_stack_exceeds_case_clearance')
        self.assertEqual(meta['rejected'][0]['mount'],'top')
        self.assertEqual(meta['rejected'][0]['required_mm'],63.8)
        self.assertEqual(meta['rejected'][0]['limit_mm'],60.)
        self.assertTrue(any('官方上限' in value for value in fit_messages(spec,dict(cooling=meta))))
        self.assertEqual((spec,anchors),before)

    def test_helios_tray_has_real_octagonal_and_three_cable_openings(self):
        meshes,meta=add_helios_tray((),self.case,(250.,591.,565.))
        self.assertEqual(len(meshes),1);mesh=meshes[0]
        self.assertLessEqual(mesh.vertex_count//3,1200)
        self.assertLessEqual(len(meta['solid_bounds']),64)
        self.assertEqual(len(meta['openings']),4)
        self.assertEqual(len(meta['openings'][0]['polygon']),8)
        self.assertEqual(meta['documented_cable_space_mm'],33.)
        self.assertFalse(meta['factory_hole_positions_verified']);self.assertFalse(meta['cad_verified'])
        x=meta['plane_x_mm']
        for opening in meta['openings']:
            polygon=opening['polygon'];z=sum(p[0] for p in polygon)/len(polygon);y=sum(p[1] for p in polygon)/len(polygon)
            a,b=(x-5.,y,z),(x+5.,y,z)
            self.assertFalse(any(_segment_triangle(a,b,tuple(tuple(mesh.vertices[n+k:n+k+3][j]+mesh.position[j] for j in range(3)) for k in (0,6,12))) for n in range(0,len(mesh.vertices),18)),opening)
            self.assertFalse(any(segment_hits_box(a,b,(row['min'],row['max'])) for row in meta['solid_bounds']),opening)
        # Every cap triangle's centroid is represented by solid collision cells;
        # chamfer corners are conservatively covered rather than omitted.
        for n in range(0,len(mesh.vertices),18):
            if abs(mesh.vertices[n+3])<.99:continue
            p=tuple(sum(mesh.vertices[n+k+j] for k in (0,6,12))/3+mesh.position[j] for j in range(3))
            self.assertTrue(any(all(row['min'][j]-1e-6<=p[j]<=row['max'][j]+1e-6 for j in range(3)) for row in meta['solid_bounds']))

    def test_tray_line_art_has_only_real_perimeters_not_cap_partition_ribs(self):
        from assembly_style import crease_edges
        meshes,meta=add_helios_tray((),self.case,(250.,591.,565.));mesh=meshes[0]
        contours=[meta['outer_polygon'],*[row['polygon'] for row in meta['openings']]]
        def on_segment(p,a,b):
            cross=(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
            return abs(cross)<1e-5 and all(min(a[k],b[k])-1e-6<=p[k]<=max(a[k],b[k])+1e-6 for k in (0,1))
        edges=crease_edges(mesh.vertices)
        for edge in edges:
            a,b=edge[:2]
            if abs(a[0]-b[0])<1e-6:
                p,q=(a[2],a[1]),(b[2],b[1])
                self.assertTrue(any(on_segment(p,first,last) and on_segment(q,first,last)
                    for poly in contours for first,last in zip(poly,(*poly[1:],poly[0]))),(p,q))

    def test_helios_tray_is_case_fixed_and_other95_cases_are_untouched(self):
        sentinel=object()
        for case in CASES:
            if case['id']==HELIOS:continue
            value,meta=add_helios_tray(sentinel,case,(250.,591.,565.))
            self.assertIs(value,sentinel);self.assertEqual(meta,{})
        raw,_=add_helios_tray((),self.case,(250.,591.,565.))
        for height,width in ((170.,170.),(244.,244.),(305.,244.)):
            scene=build_scene(dict(case=self.case,board=dict(dimensions_mm=dict(height=height,width=width)),memory=dict(count=0)))
            actual=next(m for m in scene.meshes if m.name=='case-motherboard-tray-reference')
            self.assertEqual(actual.vertices,raw[0].vertices)
            self.assertEqual(actual.position,raw[0].position)
            cells=[row for row in scene.metadata['attachment_anchors']['obstacles'] if row.get('name')==actual.name]
            self.assertEqual(len(cells),len(scene.metadata['case_tray']['solid_bounds']))

    def test_fresh_helios_air_preserves_core_parts_collision_checked_wires_and_all_six_styles(self):
        engine=QQmlEngine();warnings=[];engine.warnings.connect(lambda rows:warnings.extend(r.toString() for r in rows))
        try:
            cfg=copy.deepcopy(DEFAULT);cfg['assembly']=dict(reference_preset({},'air'),case_model=HELIOS)
            spec=bake_profiles(build_spec({},cfg,{},[]),engine);cache=SceneCache()
            try:
                scene=cache.build(spec);meta=scene.metadata
                self.assertEqual(meta['memory_rendered_count'],2)
                self.assertEqual(sum(p['kind']=='psu' for p in meta['auxiliary']['parts']),1)
                self.assertEqual(len(meta['lighting_preview']['zones']),2)
                self.assertEqual(meta['cooling']['cooler']['kind'],'single_tower')
                self.assertEqual(meta['cooling']['rejected'],[])
                self.assertTrue(any(m.name=='case-motherboard-tray-reference' for m in scene.meshes))
                self.assertFalse(any('radiator' in m.name or m.name=='cooler-liquid-tubes' for m in scene.meshes))
                # Existing incompletefront-I/O capacities remain an explicit
                # review, never invented headers or an all-wires-complete claim.
                self.assertTrue(all(row['kind']=='front_io' and row['reason']=='header_capacity_unverified' for row in meta['auxiliary']['omitted_routes']))
                self.assertEqual(len(meta['auxiliary']['cables']),14)
                tray=next(m for m in scene.meshes if m.name=='case-motherboard-tray-reference')
                for cable in meta['auxiliary']['cables']:
                    points=cable.get('points') or cable.get('path')
                    self.assertTrue(points)
                    for a,b in zip(points,points[1:]):
                        self.assertFalse(any(_segment_triangle(a,b,tuple(tuple(tray.vertices[n+k+j]+tray.position[j] for j in range(3)) for k in (0,6,12))) for n in range(0,len(tray.vertices),18)),cable['kind'])
                gpu=[(m.part_id,m.name,_bounds(m.vertices,m.position)) for m in scene.meshes if m.component=='gpu']
                for mesh in scene.meshes:
                    if mesh.component=='fans' and not any(word in mesh.name for word in ('wire','lead','connector')):
                        self.assertEqual(conflicts(_bounds(mesh.vertices,mesh.position),gpu),[])
                physical=[m for m in scene.meshes if not m.name.startswith('style-')]
                for style in SIX:
                    changed=cache.build(dict(spec,visual_style=style))
                    actual=[m for m in changed.meshes if not m.name.startswith('style-')]
                    self.assertEqual(len(actual),len(physical))
                    self.assertTrue(all(a.vertices is b.vertices and a.position==b.position and a.axis==b.axis and a.rotor==b.rotor for a,b in zip(physical,actual)))
            finally:cache.clear()
        finally:
            engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(warnings,[])

    def test_front_aio_uses_unmoved_mouths_full_length_and_checked_actual_solids_all_lods(self):
        from case_fan_clearance047 import blockers
        engine=QQmlEngine();warnings=[];engine.warnings.connect(lambda rows:warnings.extend(r.toString() for r in rows))
        endpoints=None
        try:
            for level in ('eco','balanced','close'):
                cfg=copy.deepcopy(DEFAULT);cfg['assembly']=dict(reference_preset({},'aio'),case_model=HELIOS,
                    detail_level=level,cooler_mount='front',case_fans=[
                        dict(model='arctic-p12-pwm',mount='top',count=2,direction='exhaust'),
                        dict(model='arctic-p12-pwm',mount='rear',count=1,direction='exhaust')])
                spec=bake_profiles(build_spec({},cfg,{},[]),engine);scene=build_scene(spec);meta=scene.metadata
                hoses=meta['cooling']['aio_hoses']
                self.assertEqual(len(hoses),2);self.assertEqual(meta['cooling']['connection_issues'],[])
                self.assertEqual(meta['cooling']['rejected'],[])
                self.assertEqual(meta['cooling']['cooler']['kind'],'aio')
                self.assertFalse(any(row['role']=='cpu_main' for row in meta['cooling']['fans']))
                self.assertEqual(meta['cooling']['radiator_fan_count'],3)
                self.assertEqual(len(meta['auxiliary']['cables']),12)
                control=[row for row in meta['auxiliary']['cables'] if row.get('role')=='aio_control_reference']
                self.assertEqual(len(control),1);self.assertEqual(control[0]['target_header_label'],'CPU_FAN')
                self.assertFalse(control[0]['telemetry_bound'])
                self.assertTrue(all(row['reason']=='header_capacity_unverified' for row in meta['auxiliary']['omitted_routes']))
                current=[(row['points'][0],row['points'][-1]) for row in hoses]
                if endpoints is None:endpoints=current
                else:self.assertEqual(current,endpoints)
                for row in hoses:
                    self.assertEqual(row['nominal_length_mm'],450.)
                    self.assertAlmostEqual(row['centerline_length_mm'],450.,delta=.02)
                    self.assertTrue(row['nominal_length_preserved'])
                    guide=row['guide_reference']
                    self.assertLessEqual(guide['candidates_checked'],20)
                    self.assertFalse(guide['route_verified_as_factory'])
                static={};rotors=[]
                for mesh in scene.meshes:
                    if mesh.component not in ('cooler','fans'):continue
                    if mesh.rotor:rotors.append(mesh);continue
                    vertices=tuple(value+mesh.position[i%6] if i%6<3 else value for i,value in enumerate(mesh.vertices))
                    static[(mesh.name,mesh.color,mesh.component,mesh.part_id)]=vertices
                obstacles=blockers(scene.meshes,static,rotors)
                self.assertEqual(_aio_route_issues([row['points'] for row in hoses],scene.dimensions,obstacles),[])
        finally:
            engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(warnings,[])

    def test_compensated_reference_still_rejects_an_enclosed_route(self):
        starts=((15.5,24.115,-121.056),(15.5,24.115,-147.056))
        ends=((-13.,187.,225.5),(13.,187.,225.5))
        paths,meta=_lfiii_front_reference_paths(starts,ends,(-1.,0.,0.),(0.,0.,-1.),(-1.,0.,0.),'eco',
            (250.,591.,565.),[('blocker','solid-enclosing-volume',((-125.,-295.,-282.),(125.,295.,282.)))])
        self.assertIsNone(paths);self.assertIsNone(meta)


if __name__=='__main__':unittest.main()
