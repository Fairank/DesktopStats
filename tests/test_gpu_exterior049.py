"""Exact Astral exterior: real holes, unchanged fans/envelope, bounded static LODs."""
import copy
import math
import os
import unittest
from unittest.mock import patch

from assembly_geometry import build_scene
from assembly_gpu_exterior049 import EXACT_ID,refine
from assembly_style import apply_model_styles

def ray_triangle(origin,direction,a,b,c):
    """Independent two-sided ray/triangle test, no renderer import."""
    sub=lambda x,y:tuple(i-j for i,j in zip(x,y))
    dot=lambda x,y:sum(i*j for i,j in zip(x,y))
    cross=lambda x,y:(x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])
    e1,e2=sub(b,a),sub(c,a);p=cross(direction,e2);det=dot(e1,p)
    if abs(det)<1e-10:return None
    t=sub(origin,a);u=dot(t,p)/det
    if not -1e-8<=u<=1+1e-8:return None
    q=cross(t,e1);v=dot(direction,q)/det
    if v< -1e-8 or u+v>1+1e-8:return None
    distance=dot(e2,q)/det
    return distance if distance>=0 else None


def hits(mesh,origin,direction,maximum=None):
    for n in range(0,len(mesh.vertices),18):
        tri=[tuple(mesh.vertices[n+off+a]+mesh.position[a] for a in range(3)) for off in (0,6,12)]
        distance=ray_triangle(origin,direction,*tri)
        if distance is not None and (maximum is None or distance<=maximum):return True
    return False


def mesh_signature(mesh):
    return mesh.name,mesh.vertices,mesh.color,mesh.position,mesh.rotor,mesh.axis,mesh.direction,mesh.part_id


class GpuExterior049Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtQml import QQmlEngine
        from assembly_profiles import bake_profiles
        from hardware_appearance import appearance_for
        cls.app=QCoreApplication.instance() or QCoreApplication([]);cls.engine=QQmlEngine()
        appearance=appearance_for('gpu','ROG-ASTRAL-RTX5090-32G-GAMING')
        cls.spec=bake_profiles(dict(case={'layout':'tower'},cpu={'appearance':appearance_for('cpu','Intel Core i7-13700KF')},memory={'count':0,'modules':[]},
            gpu=dict(appearance=appearance,length_mm=357.6,width_mm=149.3,thickness_mm=76.,dimensions_verified=True)),cls.engine)
    @classmethod
    def tearDownClass(cls):
        from PySide6.QtCore import QCoreApplication,QEvent
        cls.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    def setUp(self):
        for name in ('socket.socket','ctypes.WinDLL','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(name,side_effect=AssertionError('Static CPU geometry only')))
    def scene(self,level='balanced'):
        value=copy.deepcopy(self.spec);value['detail_level']=level;return build_scene(value)

    def test_exact_envelope_and_all_lods_have_finite_unit_normals_with_bounded_growth(self):
        stats=[]
        for level in ('eco','balanced','close'):
            scene=self.scene(level);shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
            old=lambda meshes,*args,**kwargs:(meshes,{})
            with patch('assembly_gpu_exterior049.refine',side_effect=old),patch(
                    'assembly_gpu_exterior049.prepare_front_fans',side_effect=lambda meshes,*a:(meshes,{})):before=self.scene(level)
            for axis,expected in enumerate((149.3,76.,357.6)):
                self.assertAlmostEqual(max(shell.vertices[axis::6])-min(shell.vertices[axis::6]),expected,places=6)
            old_gpu=sum(len(m.vertices)//18 for m in before.meshes if m.component=='gpu')
            gpu=[m for m in scene.meshes if m.component=='gpu'];new_gpu=sum(len(m.vertices)//18 for m in gpu)
            self.assertLessEqual(new_gpu-old_gpu,3000 if level=='close' else 2600)
            self.assertLessEqual(len(gpu)-sum(m.component=='gpu' for m in before.meshes),6)
            for mesh in gpu:
                for n in range(0,len(mesh.vertices),6):
                    self.assertTrue(all(math.isfinite(v) for v in mesh.vertices[n:n+6]))
                    self.assertAlmostEqual(sum(v*v for v in mesh.vertices[n+3:n+6]),1.,places=6)
                if mesh.name.startswith('detail-gpu-observed-'):
                    for axis,size in enumerate((149.3,76.,357.6)):
                        values=[mesh.vertices[n]+mesh.position[axis]-shell.position[axis] for n in range(axis,len(mesh.vertices),6)]
                        self.assertGreaterEqual(min(values),-size/2-1e-6,(level,mesh.name,axis))
                        self.assertLessEqual(max(values),size/2+1e-6,(level,mesh.name,axis))
            stats.append((level,old_gpu,new_gpu))
        self.assertTrue(stats)

    def test_rear_socket_opening_and_four_ear_frame_are_real_and_do_not_invent_chips(self):
        scene=self.scene();shell=next(m for m in scene.meshes if m.name=='gpu-shroud');gx,gy,gz=shell.position
        x=gx+((355.5-238.)/256.-.5)*149.3;z=gz+((246.5-45.)/659.-.5)*357.6
        back=next(m for m in scene.meshes if m.name=='gpu-backplate')
        frame=next(m for m in scene.meshes if m.name=='detail-gpu-observed-retention-frame')
        self.assertFalse(hits(back,(x,gy+100,z),(0,-1,0)))
        self.assertFalse(hits(frame,(x,gy+100,z),(0,-1,0)))
        pcb=next(m for m in scene.meshes if m.name=='gpu-pcb')
        self.assertTrue(hits(pcb,(x,gy+100,z),(0,-1,0)))
        meta=scene.metadata['detail']['gpu'];self.assertTrue(meta['retention_frame']);self.assertTrue(meta['rear_socket_window'])
        self.assertFalse(meta['retention_frame_is_support_stand']);self.assertFalse(meta['pcb_internal_layout_verified'])
        self.assertEqual(meta['source_retention_fasteners_observed'],4)

    def test_dark_rear_side_and_fins_are_separate_from_silver_front(self):
        scene=self.scene();rows={m.name:m for m in scene.meshes}
        light=lambda m:sum(a*b for a,b in zip(m.color[:3],(.2126,.7152,.0722)))
        self.assertLess(light(rows['gpu-backplate']),.30);self.assertLess(light(rows['gpu-shroud']),.35)
        self.assertLess(light(rows['detail-gpu-heatsink-fins']),.40)
        covers=[m for m in scene.meshes if m.name=='gpu-cover-panel']
        self.assertTrue(covers);self.assertGreater(max(light(m) for m in covers),.60)
        self.assertFalse(any('expression' in m.name for m in scene.meshes if m.component=='gpu'))

    def test_reference_power_casing_is_not_buried_in_side_wall_or_backplate(self):
        scene=self.scene();shell=next(m for m in scene.meshes if m.name=='gpu-shroud');gx,gy,gz=shell.position
        # Actual casing3mm deep,13mm tall,21mm wide, same referenced layer
        # and unchanged longitudinal0.08L position as the final-anchor source.
        for dy,dz in ((0,0),(-5.,-8.),(5.,8.)):
            origin=(gx-149.3/2-1.,gy+76.*.4+dy,gz+357.6*.08+dz)
            for mesh in scene.meshes:
                if mesh.name in ('gpu-shroud','gpu-backplate'):
                    self.assertFalse(hits(mesh,origin,(1,0,0),maximum=4.1),(mesh.name,dy,dz))

    def test_front_radius_photo_resize_keeps_leaf_profile_centers_direction_and_unknown_rear_rpm(self):
        current=self.scene()
        with patch('assembly_gpu_exterior049.refine',side_effect=lambda meshes,*a,**k:(meshes,{})),patch(
                'assembly_gpu_exterior049.prepare_front_fans',side_effect=lambda meshes,*a:(meshes,{})):before=self.scene()
        front=lambda s:[m for m in s.meshes if m.name.startswith('gpu-fan-')]
        self.assertEqual(len(front(current)),12)
        for new,old in zip(front(current),front(before)):
            self.assertEqual((new.name,new.color,new.position[0],new.position[2],new.rotor,new.axis,new.direction),
                             (old.name,old.color,old.position[0],old.position[2],old.rotor,old.axis,old.direction))
            if new.name=='gpu-fan-recess':
                shell=next(m for m in current.meshes if m.name=='gpu-shroud')
                self.assertAlmostEqual(new.position[1],shell.position[1]-76./2+11.)
            else:self.assertEqual(new.position[1],old.position[1])
            if new.rotor:continue
            self.assertEqual(len(new.vertices),len(old.vertices))
            radius=55.428/45.46824857142857
            # Fixed recess is rebuilt by legacy detail from its resized radius.
            for n in range(0,len(new.vertices),6):
                self.assertAlmostEqual(new.vertices[n],old.vertices[n]*radius,places=6)
                self.assertAlmostEqual(new.vertices[n+2],old.vertices[n+2]*radius,places=6)
                self.assertAlmostEqual(new.vertices[n+1],old.vertices[n+1],places=6)
        rear=lambda s:[mesh_signature(m) for m in s.meshes if m.name.startswith('detail-gpu-rear-observed')]
        self.assertEqual(rear(current),rear(before))
        self.assertEqual(sum(m.rotor for m in current.meshes if m.component=='gpu'),3)
        self.assertTrue(all(not m.rotor for m in current.meshes if m.name.startswith('detail-gpu-rear-observed')))
        self.assertFalse(current.metadata['detail']['gpu']['rear_rpm_verified'])
        observation=current.metadata['detail']['gpu']['front_radius_observation']
        self.assertEqual(observation['geometry'],'photo_reference_not_measured_diameter')
        self.assertFalse(observation['generic_147_radius_mapping_changed'])
        self.assertTrue(all(abs(v-55.428)<1e-6 for v in observation['reference_radius_mm']))

    def test_exact_front_painter_panels_have_no_coplanar_overlap(self):
        scene=self.scene();shell=next(m for m in scene.meshes if m.name=='gpu-shroud');gx,gy,gz=shell.position
        panels=[m for m in scene.meshes if m.name=='gpu-cover-panel']
        occupied=0
        for xi in range(1,20):
            for zi in range(1,41):
                origin=(gx+(xi/20.-.5)*149.3,gy-100.,gz+(zi/41.-.5)*357.6)
                count=sum(hits(m,origin,(0,1,0)) for m in panels)
                self.assertLessEqual(count,1,(xi,zi,count))
                occupied+=count
        self.assertGreater(occupied,40)
        self.assertTrue(scene.metadata['detail']['gpu']['front_panels_partitioned'])

    def test_real_fin_gaps_are_not_backed_by_an_invented_opposite_solid_wall(self):
        for level in ('eco','balanced','close'):
            scene=self.scene(level);shell=next(m for m in scene.meshes if m.name=='gpu-shroud');gx,gy,gz=shell.position
            fins=[m for m in scene.meshes if m.name in ('detail-gpu-heatsink-fins','detail-gpu-heatsink-cut-edges')]
            count=scene.metadata['detail']['gpu']['heatsink_fins'];step=357.6*.82/(count-1)
            for sample in (.2,.4,.6,.8):
                index=int((count-2)*sample)
                gap=gz-357.6*.41+(index+.5)*step
                fin=gz-357.6*.41+index*step
                for direction,side in (((1,0,0),-1),((-1,0,0),1)):
                    origin=(gx+side*200.,gy+2.,gap)
                    self.assertFalse(hits(shell,origin,direction,maximum=300.))
                    self.assertFalse(any(hits(m,origin,direction,maximum=300.) for m in fins))
                    self.assertTrue(any(hits(m,(origin[0],origin[1],fin),direction,maximum=300.) for m in fins))
            self.assertTrue(scene.metadata['detail']['gpu']['pcb_edge_open'])
            self.assertFalse(scene.metadata['detail']['gpu']['fin_gaps_have_opaque_far_wall'])

    def test_fin_tone_partition_preserves_each_original_closed_sheet_without_overlay(self):
        from collections import Counter
        from assembly_detail import _boxes
        for level in ('eco','balanced','close'):
            scene=self.scene(level);shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
            count=scene.metadata['detail']['gpu']['heatsink_fins']
            all_sheets=_boxes([((149.3*.84,76.*.60,.25),(0.,1.,-357.6*.41+n*357.6*.82/(count-1))) for n in range(count)])
            triangle_key=lambda values:Counter(tuple(round(v,8) for v in values[n:n+18]) for n in range(0,len(values),18))
            actual=Counter()
            rows=[m for m in scene.meshes if m.name in ('detail-gpu-heatsink-fins','detail-gpu-heatsink-cut-edges')]
            self.assertEqual(len(rows),2)
            for m in rows:
                self.assertEqual(m.position,shell.position);actual.update(triangle_key(m.vertices))
            self.assertEqual(actual,triangle_key(all_sheets))
            self.assertEqual(sum(actual.values()),count*12)

    def test_actual_curved_leaf_depth_normals_and_cavity_do_not_cross_fixed_hardware(self):
        for level in ('eco','balanced','close'):
            scene=self.scene(level)
            rotors=[m for m in scene.meshes if m.name=='gpu-fan-rotor']
            recess=[m for m in scene.meshes if m.name=='gpu-fan-recess']
            fins=[m for m in scene.meshes if m.name in ('detail-gpu-heatsink-fins','detail-gpu-heatsink-cut-edges')]
            self.assertEqual(len(rotors),3)
            for rotor in rotors:
                self.assertGreater(max(rotor.vertices[1::6])-min(rotor.vertices[1::6]),4.0)
                self.assertLessEqual(max(rotor.vertices[1::6]),5.951)
                self.assertGreaterEqual(min(rotor.vertices[1::6]),-.551)
                self.assertTrue(any(abs(rotor.vertices[n+4])<.98 and abs(rotor.vertices[n+4])>.5 for n in range(0,len(rotor.vertices),6)))
                cavity=min(recess,key=lambda m:abs(m.position[2]-rotor.position[2]))
                rear=max(rotor.vertices[1::6])+rotor.position[1]
                self.assertLess(rear+1.,min(cavity.vertices[1::6])+cavity.position[1])
                self.assertTrue(all(rear+2.<min(fin.vertices[1::6])+fin.position[1] for fin in fins))
            meta=scene.metadata['detail']['gpu'];self.assertFalse(meta['front_manufacturer_blade_pitch_verified'])
            self.assertGreater(meta['front_rotor_triangles_after_curving'],meta['front_rotor_triangles_before_curving'])

    def test_curved_projected_leaf_outline_and_closed_shared_midpoints_are_preserved(self):
        from collections import Counter
        with patch('assembly_gpu_exterior049.curve_front_rotor',side_effect=lambda vertices,*a:vertices):before=self.scene()
        after=self.scene();old=[m for m in before.meshes if m.name=='gpu-fan-rotor'];new=[m for m in after.meshes if m.name=='gpu-fan-rotor']
        def projected_triangles(mesh):
            return [tuple((mesh.vertices[n+i],mesh.vertices[n+i+2]) for i in (0,6,12)) for n in range(0,len(mesh.vertices),18)]
        def covered(triangles,x,z):
            for points in triangles:
                a,b,c=points;area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                if abs(area)<1e-8:continue
                values=[(q[0]-p[0])*(z-p[1])-(q[1]-p[1])*(x-p[0]) for p,q in zip(points,points[1:]+points[:1])]
                if min(values)>=-1e-8 or max(values)<=1e-8:return True
            return False
        for previous,current in zip(old,new):
            for axis in (0,2):
                self.assertAlmostEqual(min(previous.vertices[axis::6]),min(current.vertices[axis::6]))
                self.assertAlmostEqual(max(previous.vertices[axis::6]),max(current.vertices[axis::6]))
            a,b=projected_triangles(previous),projected_triangles(current)
            for index in range(12):
                angle=(index+.231)*math.tau/12
                for radius in (.30,.48,.66,.86):
                    x,z=55.428*radius*math.cos(angle),55.428*radius*math.sin(angle)
                    self.assertEqual(covered(a,x,z),covered(b,x,z))
            edges=Counter()
            for n in range(0,len(current.vertices),18):
                points=[tuple(round(v,6) for v in current.vertices[n+i:n+i+3]) for i in (0,6,12)]
                for p,q in zip(points,points[1:]+points[:1]):edges[tuple(sorted((p,q)))]+=1
            self.assertFalse([edge for edge,count in edges.items() if count%2], 'Adaptive caps must not leave T-junction cracks')

    def test_exact_astral_distal_end_is_open_between_real_posts_and_rails(self):
        for level in ('eco','balanced','close'):
            scene=self.scene(level);shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
            gx,gy,gz=shell.position
            # Exact galleryD6BE479C shows an open distal cage. Probe only a
            # bounded segment through that end, never the opposite I/O end.
            origin=(gx,gy,gz+357.6/2+8.)
            self.assertFalse(hits(shell,origin,(0,0,-1),maximum=12.))
            # An open center must retain the actual corner posts/top/bottom
            # rails; deleting the whole end would fail these independent rays.
            for x,y in ((-149.3*.40,0),(149.3*.40,0),(0,76.*.42),(0,-76.*.42)):
                self.assertTrue(hits(shell,(gx+x,gy+y,origin[2]),(0,0,-1),maximum=12.))
            for axis,size in enumerate((149.3,76.,357.6)):
                self.assertAlmostEqual(max(shell.vertices[axis::6])-min(shell.vertices[axis::6]),size)
            meta=scene.metadata['detail']['gpu'];self.assertTrue(meta['end_cage_open'])
            self.assertEqual(meta['exterior_model_id'],EXACT_ID)
            self.assertIn('https://dlcdnwebimgs.asus.com/gain/D6BE479C-B386-4FAB-AC40-4582B7C6F499/w1000/h732',meta['exterior_sources'])

    def test_silver_panels_have_real_depth_and_sloping_edges_inside_card_envelope(self):
        scene=self.scene();shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
        panels=[m for m in scene.meshes if m.name=='gpu-cover-panel'];self.assertTrue(panels)
        self.assertTrue(any(.02<abs(m.vertices[n+4])<.98 for m in panels for n in range(0,len(m.vertices),6)))
        for mesh in panels:
            self.assertAlmostEqual(max(mesh.vertices[1::6])-min(mesh.vertices[1::6]),1.1)
            self.assertGreaterEqual(min(mesh.vertices[1::6])+mesh.position[1],shell.position[1]-38.)

    def test_all_styles_share_physical_arrays_and_other_models_are_exact_noop(self):
        from top_bar_config import HARDWARE_ICON_STYLES
        scene=self.scene();gpu=tuple(m for m in scene.meshes if m.component=='gpu')
        for style in HARDWARE_ICON_STYLES:
            styled,_=apply_model_styles(gpu,style,{},scene.dimensions,{'front':'open'})
            self.assertEqual([(m.name,m.vertices,m.position,m.rotor,m.axis) for m in styled],
                             [(m.name,m.vertices,m.position,m.rotor,m.axis) for m in gpu],style)
        for identity in ('asus-astral-5090-oc','asus-astral-5080','unknown'):
            spec=copy.deepcopy(self.spec);spec['gpu']['appearance']['id']=identity
            result,meta=refine(gpu,spec,'balanced',outer=None,front_holes=None,rear_hole=None,edge_windows=None,
                               edge_recesses=None,front_cutouts=None,port_holes=None)
            self.assertIs(result,gpu);self.assertEqual(meta,{})
            with patch('assembly_gpu_exterior049.refine',side_effect=lambda rows,*a,**k:(rows,{})):before=build_scene(spec)
            after=build_scene(spec)
            self.assertEqual([mesh_signature(m) for m in before.meshes],[mesh_signature(m) for m in after.meshes])


if __name__=='__main__':unittest.main()
