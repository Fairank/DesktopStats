"""Fixed chassis openings and real cable/hose clearance, software fixtures only."""
import ast
import copy
import hashlib
import inspect
import json
import math
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

import assembly_auxiliary as auxiliary
import hardware_packs
from assembly_geometry import build_scene
from assembly_north_tray049 import add_tray,add_obstacles
from chassis_catalog import CASES,get_case
from assembly_parts import reference_preset
from assembly_profiles import bake_profiles
from assembly_spec import build_spec
from stats_config import DEFAULT


class NorthTrayGeometry049Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No devices/processes/windows/workers'),create=True))
        self.case=get_case('fractal-north-xl-mesh')
        self.meshes,self.meta=add_tray((),self.case,(240.,509.,503.))

    def test_all_other_95_cases_keep_the_original_mesh_object_and_no_tray(self):
        meshes=object();other=[case for case in CASES if case['id']!=self.case['id']]
        self.assertEqual(len(other),95)
        for case in other:
            result,meta=add_tray(meshes,case,(240.,509.,503.))
            self.assertIs(result,meshes);self.assertEqual(meta,{})

    def test_case_shape_does_not_change_with_itx_matx_atx_or_cpu_selection(self):
        expected=self.meshes[0].vertices;before=copy.deepcopy(self.case)
        for height,width in ((170.,170.),(244.,244.),(305.,244.)):
            scene=build_scene(dict(case=self.case,board=dict(dimensions_mm=dict(height=height,width=width)),memory=dict(count=0)))
            tray=next(mesh for mesh in scene.meshes if mesh.name=='case-motherboard-tray-reference')
            self.assertEqual(tray.vertices,expected)
            self.assertEqual(scene.metadata['case_tray'],self.meta)
        self.assertEqual(self.case,before)
        self.assertIs(self.meta['cad_verified'],False)
        self.assertIs(self.meta['dimensions_verified'],False)
        self.assertEqual(self.meta['documented_cable_space_mm'],29.)

    def test_openings_are_physical_and_collision_boxes_do_not_fill_the_holes(self):
        mesh=self.meshes[0];x=self.meta['plane_x_mm']
        def solid_hit(y,z):
            origin,end=(x-10.,y,z),(x+10.,y,z)
            return any(auxiliary._segment_triangle(origin,end,tuple(mesh.vertices[i+k:i+k+3] for k in (0,6,12)))
                       for i in range(0,len(mesh.vertices),18))
        for opening in self.meta['openings']:
            y=(opening['y0']+min(opening['y1'],self.meta['bounds']['max'][1]))/2
            z=(opening['z0']+opening['z1'])/2
            a,b=(x-10.,y,z),(x+10.,y,z)
            self.assertFalse(solid_hit(y,z),opening)
            self.assertTrue(auxiliary.segment_hits_box(a,b,tuple(self.meta['bounds'][k] for k in ('min','max'))))
            self.assertFalse(any(auxiliary.segment_hits_box(a,b,tuple(row[k] for k in ('min','max'))) for row in self.meta['solid_bounds']))
        for row in self.meta['solid_bounds']:
            y,z=(row['min'][1]+row['max'][1])/2,(row['min'][2]+row['max'][2])/2
            self.assertTrue(solid_hit(y,z))
        self.assertLessEqual(len(self.meta['solid_bounds']),64)
        self.assertEqual(len(self.meshes),1)
        for i in range(0,len(mesh.vertices),6):
            self.assertTrue(all(math.isfinite(v) for v in mesh.vertices[i:i+6]))
            self.assertAlmostEqual(sum(v*v for v in mesh.vertices[i+3:i+6]),1.)

    def test_existing_obstacles_remain_and_tray_cells_enter_both_attachment_stages(self):
        sentinel=dict(bounds=dict(min=(0,0,0),max=(1,1,1)),kind='board')
        for _stage in range(2):
            anchors=add_obstacles(dict(obstacles=[sentinel]),self.meta)
            self.assertIs(anchors['obstacles'][0],sentinel)
            self.assertEqual(len(anchors['obstacles']),len(self.meta['solid_bounds'])+1)
            self.assertTrue(all(row['name']=='case-motherboard-tray-reference' for row in anchors['obstacles'][1:]))

    def test_strict_route_algorithm_has_not_changed(self):
        node=ast.parse(inspect.getsource(auxiliary.route_cable)).body[0]
        self.assertEqual(hashlib.sha256(ast.dump(node).encode()).hexdigest(),
                         'ee90555f30df246286921c5d625c610ebf54a57c4ea8c2d304779d554cbcd323')

    def test_hose_clearance_checks_capsules_instead_of_filling_empty_aabb_corners(self):
        box=auxiliary._TubeObstacle((0.,0.,0.),(10.,10.,0.),1.)
        self.assertTrue(auxiliary._segment_box((0.,10.,-4.),(0.,10.,4.),box))
        self.assertFalse(auxiliary.segment_hits_box((0.,10.,-4.),(0.,10.,4.),box))
        self.assertTrue(auxiliary.segment_hits_box((5.,5.,-4.),(5.,5.,4.),box))
        self.assertTrue(auxiliary.segment_hits_box((5.,7.,-4.),(5.,7.,4.),box,.5))
        for value in ([None],dict(points=[]),[dict(points=[[0,0,0],[1,1,1]],outer_radius_mm=float('nan'))],list(range(9))):
            with self.assertRaises(ValueError):auxiliary._aio_tube_obstacles(dict(aio_hoses=value))


class NorthTrayActualReference049Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software only')

    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No devices/processes/windows/workers'),create=True))
        directory=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(hardware_packs,'_store',hardware_packs.PackStore(directory/'packs')))

    def tearDown(self):
        self.assertEqual(self.app.topLevelWindows(),[])
        self.assertIsNone(QOpenGLContext.currentContext())

    def test_actual_baked_north_keeps_known_connections_and_control_clear_of_tray_and_new_hoses(self):
        engine=QQmlEngine();calls=[];original=auxiliary.route_cable
        def observe(*args,**kwargs):
            path,state=original(*args,**kwargs)
            calls.append((path,args[4] if len(args)>4 else kwargs.get('obstacles',())))
            return path,state
        try:
            config=copy.deepcopy(DEFAULT);config['assembly']=reference_preset({},'aio')
            spec=bake_profiles(build_spec({},config,{},[]),engine)
            with patch.object(auxiliary,'route_cable',new=observe):scene=build_scene(spec)
            meta=scene.metadata;actual=meta['auxiliary'];cables=actual['cables']
            self.assertEqual(actual['omitted_routes'],[]);self.assertEqual(actual['rejected'],[])
            self.assertEqual(meta['cooling']['rejected'],[])
            self.assertEqual(len(cables),9)
            self.assertTrue(all((c['preferred_waypoints_used'] or c.get('role')=='aio_control_reference') and not c['external_route'] for c in cables))
            self.assertEqual(len(meta['cooling']['aio_hoses']),2)
            rows=[]
            def normalized(value):
                if isinstance(value,float):return round(value,6)
                return [normalized(v) for v in value] if isinstance(value,(tuple,list)) else value
            for cable in cables:
                self.assertTrue(any(mesh.name.startswith(cable['mesh_prefix']+'-') for mesh in scene.meshes))
                self.assertEqual(cable['mesh_prefix'].split('-')[-1],cable['kind'])
                row=[cable['kind'],cable['source_owner'],cable['target_owner'],normalized(cable['target_socket']),normalized(cable['end'])]
                if cable['kind']=='gpu16':
                    # One declared source correction: restore its old depth
                    # only for the historical all-other-ports digest bridge.
                    delta=meta['attachment_anchors']['gpu']['thickness_mm']*.40
                    row[3][1]=round(row[3][1]-delta,6);row[4][1]=round(row[4][1]-delta,6)
                if not cable['source_owner'].startswith('fans:rear:'):row.extend((normalized(cable['source_socket']),normalized(cable['start'])))
                rows.append(row)
                path,obstacles=next(call for call in calls if call[0]==cable['path'])
                self.assertTrue(any(isinstance(obstacle,auxiliary._TubeObstacle) for obstacle in obstacles))
                tray_boxes=[tuple(cell[k] for k in ('min','max')) for cell in meta['case_tray']['solid_bounds']]
                self.assertTrue(all(cell in obstacles for cell in tray_boxes))
                for a,b in zip(path,path[1:]):
                    self.assertFalse(any(auxiliary.segment_hits_box(a,b,obstacle,1.1) for obstacle in obstacles))
            # Header identities were corrected from generic indices in051;
            # preserve the historical digest for every other socket/source.
            from test_case_fan_cable_routing048 import port_digest
            for cable in (c for c in cables if c['kind']=='fan4'):
                if cable.get('role')=='aio_control_reference':self.assertEqual(cable['target_header_label'],'CPU_FAN')
                if cable.get('role')=='case':self.assertTrue(cable['target_header_label'].startswith('CHA_FAN'))
                self.assertTrue(cable['target_header_role_verified'])
                header=next(r for r in meta['attachment_anchors']['connectors']['fan'] if r['label']==cable['target_header_label'])
                self.assertEqual(cable['target_socket'],header['position'])
            self.assertEqual(port_digest(cables,gpu_depth_correction=meta['attachment_anchors']['gpu']['thickness_mm']*.40,fan_headers=meta['attachment_anchors']['connectors']['fan']),
                             'b9dd2aeed32c6ab5c46d5caba4e90f6e82d7235aade3a20f00f33329907ce600')
            # Long EPS lifts and fore/aft runs must stay behind the PCB/tray;
            # their short final approach still meets the real fixed header.
            for cable in (c for c in cables if c['kind']=='eps8'):
                for a,b in zip(cable['path'],cable['path'][1:]):
                    if abs(a[1]-b[1])>100 or abs(a[2]-b[2])>100:
                        self.assertGreater(min(a[0],b[0]),meta['case_tray']['plane_x_mm'])
            gpu=next(c for c in cables if c['kind']=='gpu16')
            gpu_anchor=meta['attachment_anchors']['gpu']
            self.assertAlmostEqual(gpu['target_socket'][1],gpu_anchor['center'][1]+gpu_anchor['thickness_mm']*.40)
            self.assertFalse(gpu_anchor['power'][0]['position_verified'])
            self.assertEqual(gpu_anchor['power'][0]['normal'],(-1.,0.,0.))
            self.assertAlmostEqual(gpu['target_socket'][2],-30.092)
            self.assertEqual(gpu_anchor['power'][0]['position_source'],'official_photo_observed_depth_reference')
            inlet=next(mesh for mesh in scene.meshes if mesh.name=='gpu-power-inlet-0')
            face=min(inlet.vertices[0::6])+inlet.position[0]
            # Unplugged socket frame is exposed at the side/PCB layer; no
            # backplate or heatsink face may sit in front of its four borders.
            cy,cz=gpu['target_socket'][1:]
            for y,z in ((cy-6.,cz),(cy+6.,cz),(cy,cz-10.),(cy,cz+10.)):
                a,b=(face-20.,y,z),(face+.1,y,z);hits=[]
                for mesh in (m for m in scene.meshes if m.component=='gpu'):
                    bounds=tuple(tuple(fn(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for fn in (min,max))
                    if not auxiliary._segment_box(a,b,bounds,.001):continue
                    if any(auxiliary._segment_triangle(a,b,tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12)))
                           for i in range(0,len(mesh.vertices),18)):hits.append(mesh.name)
                self.assertEqual(hits,['gpu-power-inlet-0'])
            floor=meta['attachment_anchors']['gpu']['bounds']['min'][1]
            self.assertTrue(any(p[1]<floor-10. for p in gpu['path']))
        finally:
            engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__=='__main__':unittest.main()
