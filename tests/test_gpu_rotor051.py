"""Real static blade depth: shared planforms, bounds and opt-out identities."""
import math
import os
import unittest
from unittest.mock import patch

from assembly_geometry import fan_rotor,gpu_plane,build_scene
from assembly_gpu_rotor051 import curve_rotor,cup
from assembly_style import apply_model_styles


def projected_area(vertices):
    total=0.
    for n in range(0,len(vertices),18):
        a,b,c=(vertices[n+i:n+i+3] for i in (0,6,12))
        total+=abs((b[0]-a[0])*(c[2]-a[2])-(b[2]-a[2])*(c[0]-a[0]))*.5
    return total


class RotorGeometry051Tests(unittest.TestCase):
    def test_known_closed_rotor_keeps_outline_tip_ring_and_actual_normals(self):
        for shape,count,ring,group in (('swept',11,True,1),('paired',10,False,2),('claw',9,False,1),('wide',7,False,1)):
            p=dict(blades=count,shape=shape,hub_ratio=.30,outer_ring=ring,group_size=group)
            original=gpu_plane(fan_rotor(p,45.))
            for level in ('eco','balanced','close'):
                curved,meta=curve_rotor(original,45.,p,level,axial_room_mm=2.4)
                self.assertTrue(meta['applied']);self.assertNotEqual(curved,original)
                self.assertLessEqual(len(curved),len(original)*4)
                if level=='eco':self.assertEqual(len(curved),len(original))
                self.assertAlmostEqual(projected_area(original),projected_area(curved),places=6)
                for axis in (0,2):
                    self.assertAlmostEqual(min(curved[axis::6]),min(original[axis::6]),places=8)
                    self.assertAlmostEqual(max(curved[axis::6]),max(original[axis::6]),places=8)
                original_fixed={tuple(original[n:n+6]) for n in range(0,len(original),6)
                                if math.hypot(original[n],original[n+2])>=45*.79}
                curved_fixed={tuple(curved[n:n+6]) for n in range(0,len(curved),6)
                              if math.hypot(curved[n],curved[n+2])>=45*.79}
                for v in original_fixed:self.assertIn(v,curved_fixed)
                for n in range(0,len(curved),6):
                    self.assertTrue(all(math.isfinite(v) for v in curved[n:n+6]))
                    self.assertAlmostEqual(sum(v*v for v in curved[n+3:n+6]),1.,places=7)
                for n in range(0,len(curved),18):
                    a,b,c=(curved[n+off:n+off+3] for off in (0,6,12))
                    u=tuple(b[k]-a[k] for k in range(3));v=tuple(c[k]-a[k] for k in range(3))
                    cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                    self.assertGreater(sum(x*x for x in cross),1e-16)
                    average=tuple(sum(curved[n+off+3+k] for off in (0,6,12)) for k in range(3))
                    self.assertGreater(sum(x*y for x,y in zip(cross,average)),0.)
                # A shared source corner is moved by one field, never by a
                # per-triangle random displacement which would tear seams.
                if level=='eco':
                    seen={}
                    for n in range(0,len(original),6):
                        key=tuple(original[n:n+3]);point=tuple(curved[n:n+3])
                        self.assertEqual(seen.setdefault(key,point),point)
                self.assertLessEqual(max(curved[1::6])-max(original[1::6]),2.4+1e-8)

    def test_unknown_blower_and_insufficient_cavity_are_exact_identity(self):
        source=gpu_plane(fan_rotor(dict(blades=11,shape='swept'),35.))
        for p in (dict(blades=None,shape='neutral'),dict(blades=9,shape='neutral'),
                  dict(blades=53,shape='radial',kind='blower'),dict(blades=11,shape='swept',kind='blower')):
            result,meta=curve_rotor(source,35.,p,axial_room_mm=4.)
            self.assertIs(result,source);self.assertFalse(meta['applied'])
        result,meta=curve_rotor(source,35.,dict(blades=11,shape='swept'),axial_room_mm=.05)
        self.assertIs(result,source);self.assertFalse(meta['applied'])

    def test_reflection_keeps_cup_handedness_and_tip_link_plane(self):
        p=dict(blades=9,shape='claw',hub_ratio=.3,direction=1)
        for x,z in ((10.,15.),(-19.,8.),(25.,-11.)):
            a=cup(x,z,45.,p,2.4)
            b=cup(x,-z,45.,dict(p,direction=-1),2.4)
            self.assertAlmostEqual(a[0],b[0]);self.assertAlmostEqual(a[1],b[1]);self.assertAlmostEqual(a[2],-b[2])
        self.assertEqual(cup(45*.86,0,45.,p,2.4),(0.,0.,0.))


class RotorScene051Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtQml import QQmlEngine
        from assembly_profiles import bake_profiles
        from hardware_appearance import CATALOG,appearance_for
        cls.app=QCoreApplication.instance() or QCoreApplication([]);cls.engine=QQmlEngine()
        rows={r[0]:r for r in CATALOG if r[1]=='gpu'};cls.specs={}
        for identity in ('asus-dual-4060-oc','msi-ventus-4060-2x-oc','amd-reference-rx7900xtx-24g',
                         'nvidia-gtx1080-founders','nvidia-gtx780ti-reference','asus-astral-5090','gigabyte-gaming-5070oc'):
            a=appearance_for('gpu',rows[identity][-1][0]);dims=a['board_details'].get('dimensions_mm') or {}
            cls.specs[identity]=bake_profiles(dict(case={'layout':'tower'},cpu={'appearance':appearance_for('cpu','Intel Core i7-13700KF')},
                memory={'count':0,'modules':[]},gpu=dict(appearance=a,length_mm=dims.get('length') or 270.,
                    width_mm=dims.get('height') or 130.,thickness_mm=dims.get('thickness') or 45.)),cls.engine)
    @classmethod
    def tearDownClass(cls):
        from PySide6.QtCore import QCoreApplication,QEvent
        cls.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_real_baked_lods_keep_scene_budget_no_new_mesh_and_six_style_shared_geometry(self):
        for identity in ('asus-dual-4060-oc','msi-ventus-4060-2x-oc','amd-reference-rx7900xtx-24g'):
            for level in ('eco','balanced','close'):
                spec=dict(self.specs[identity],detail_level=level)
                with patch('assembly_gpu_rotor051.curve_rotor',side_effect=lambda vertices,*a,**k:(vertices,dict(applied=False))):before=build_scene(spec)
                after=build_scene(spec);old=[m for m in before.meshes if m.component=='gpu'];new=[m for m in after.meshes if m.component=='gpu']
                self.assertEqual(len(old),len(new));self.assertLessEqual(after.triangle_count,{'eco':80000,'balanced':160000,'close':300000}[level])
                self.assertTrue(after.metadata['detail']['gpu']['axial_blade_depth_reference'])
                shell=next(m for m in new if m.name=='gpu-shroud')
                ys=[v+shell.position[1] for v in shell.vertices[1::6]]
                for a,b in zip(old,new):
                    self.assertEqual((a.name,a.position,a.axis,a.direction,a.part_id),(b.name,b.position,b.axis,b.direction,b.part_id))
                    if a.name!='gpu-fan-rotor':self.assertEqual(a.vertices,b.vertices)
                    else:
                        self.assertNotEqual(a.vertices,b.vertices)
                        self.assertGreaterEqual(min(b.vertices[1::6])+b.position[1],min(ys)-1e-6)
                        self.assertLessEqual(max(b.vertices[1::6])+b.position[1],max(ys)+1e-6)
                from top_bar_config import HARDWARE_ICON_STYLES
                for style in HARDWARE_ICON_STYLES:
                    styled,_=apply_model_styles(after.meshes,style,{},after.dimensions,{'front':'open'})
                    physical=[m for m in styled if 'expression' not in m.name]
                    self.assertEqual(len(physical),len(after.meshes))
                    for a,b in zip(after.meshes,physical):self.assertIs(a.vertices,b.vertices)

    def test_real_exact_astral_blower_and_unknown_do_not_change_geometry(self):
        for identity in ('asus-astral-5090','nvidia-gtx1080-founders','nvidia-gtx780ti-reference'):
            spec=dict(self.specs[identity],detail_level='balanced');current=build_scene(spec)
            with patch('assembly_gpu_rotor051.curve_rotor',side_effect=lambda vertices,*a,**k:(vertices,dict(applied=False))):legacy=build_scene(spec)
            self.assertEqual(current.meshes,legacy.meshes,identity)
            self.assertEqual(current.metadata['detail']['gpu']['axial_blade_depth_reference'],())

    def test_partly_reviewed_rotor_keeps_its_actual_source_index_and_unknown_ends(self):
        spec=self.specs['gigabyte-gaming-5070oc'];scene=build_scene(spec)
        self.assertFalse(spec['gpu']['appearance']['fan_profile']['render_ready'])
        self.assertEqual([f['blades'] for f in spec['gpu']['fans']],[None,7,None])
        rotors=[m for m in scene.meshes if m.name=='gpu-fan-rotor']
        self.assertEqual(len(rotors),1)
        meta=scene.metadata['detail']['gpu']['axial_blade_depth_reference']
        self.assertEqual([r['index'] for r in meta],[1])
        self.assertEqual(rotors[0].direction,-1)


class FanSource051Tests(unittest.TestCase):
    def test_partial_hawk_evidence_does_not_claim_outer_counts_or_series_matching(self):
        from hardware_appearance import appearance_for
        from hardware_fan_profiles import PROFILES
        row=PROFILES['gigabyte_gaming_oc']
        self.assertEqual(row['model_ids'],('gigabyte-gaming-5070oc',))
        self.assertEqual([p.get('blades',row['blades']) for p in row['fans']],[None,7,None])
        exact=appearance_for('gpu','GV-N5070GAMING-OC-12GD')
        self.assertEqual(exact['id'],'gigabyte-gaming-5070oc')
        self.assertFalse(exact['fan_profile']['render_ready'])
        self.assertEqual(exact['fan_profile']['blade_counts'],[None,7,None])
        self.assertNotEqual(appearance_for('gpu','Gigabyte RTX 5070')['confidence'],'model')


if __name__=='__main__':unittest.main()
