"""Actual GPU painter-order surfaces: physical fan holes and disjoint colour caps."""
import math
import os
import unittest
from assembly_gpu_panels051 import partition


def inside(point,triangle):
    x,y=point
    values=[(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]) for a,b in zip(triangle,(*triangle[1:],triangle[0]))]
    return min(values)>1e-8 or max(values)<-1e-8


def cap_rows(vertices):
    return [tuple(tuple(vertices[n+off:n+off+2]) for off in (0,6,12))
            for n in range(0,len(vertices),18) if vertices[n+5]>.999]


class GpuPaintPartition051Tests(unittest.TestCase):
    def test_source_painter_order_uses_real_concave_cutout_and_no_common_depth_overlap(self):
        lower=((-40,-20),(40,-20),(40,20),(-40,20))
        later=((-10,-18),(35,-18),(35,-4),(5,-4),(5,18),(-10,18))
        values,meta=partition((lower,later),((0.,0.,3.),),.3)
        self.assertFalse(meta['z_offset_used']);self.assertEqual(meta['omitted_source_paint'],())
        self.assertTrue(all(set(round(v,8) for v in result[2::6])=={-.15,.15} for result in values))
        for x in range(-39,40,3):
            for y in range(-19,20,3):
                point=(x+.127,y+.231)
                layers=[i for i,v in enumerate(values) if any(inside(point,t) for t in cap_rows(v))]
                if math.hypot(*point)<2.8:self.assertEqual(layers,[])
                elif point[0]>36:self.assertEqual(layers,[0])
                else:self.assertLessEqual(len(layers),1,(point,layers))
        # The upper polygon's concave corner remains lower paint, not a
        # convex-hull deletion or a fabricated hardware gap.
        self.assertTrue(any(inside((25,12),t) for t in cap_rows(values[0])))
        self.assertFalse(any(inside((25,12),t) for t in cap_rows(values[1])))
        self.assertTrue(any(inside((20,-12),t) for t in cap_rows(values[1])))
        self.assertFalse(any(inside((20,-12),t) for t in cap_rows(values[0])))

    def test_partition_preserves_actual_fan_mouth_and_does_not_add_diagonal_solid_walls(self):
        a=((-20,-20),(20,-20),(20,20),(-20,20));b=((-10,-10),(15,-10),(15,15),(-10,15))
        values,meta=partition((a,b),((0.,0.,6.),),.3,segments=24)
        self.assertFalse(meta['omitted_source_paint'])
        for result in values:
            self.assertTrue(all(math.isfinite(v) for v in result))
            for tri in cap_rows(result):
                center=tuple(sum(p[i] for p in tri)/3 for i in (0,1))
                self.assertGreaterEqual(math.hypot(*center),6*math.cos(math.pi/24)-1e-6)
        # The upper square perimeter consists only of horizontal/vertical
        # walls plus the real circular mouth. Ear-clipping diagonals must not
        # become physical braces through that face.
        for n in range(0,len(values[1]),18):
            if abs(values[1][n+5])>.999:continue
            center=tuple(sum(values[1][n+off+i] for off in (0,6,12))/3 for i in (0,1))
            at_square=any(abs(center[i]-edge)<1e-7 for i in (0,1) for edge in (-10,15))
            self.assertTrue(at_square or abs(math.hypot(*center)-6)<.1,center)

    def test_large_source_partition_fails_conservatively_with_explicit_metadata(self):
        polygons=[]
        for i in range(6):polygons.append(tuple((math.cos(n*math.tau/40)*(20+i),math.sin(n*math.tau/40)*(20+i)) for n in range(40)))
        values,meta=partition(tuple(polygons),(),.3)
        self.assertFalse(values[0]);self.assertTrue(values[-1]);self.assertTrue(meta['omitted_source_paint'])
        self.assertEqual(meta['omitted_source_paint'][0]['reason'],'source_partition_cutters_exceeded')
        with self.assertRaises(ValueError):partition(tuple(polygons+[polygons[-1]]),(),.3)


class ActualGpuPaint051Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtQml import QQmlEngine
        cls.app=QCoreApplication.instance() or QCoreApplication([]);cls.engine=QQmlEngine()

    @classmethod
    def tearDownClass(cls):
        from PySide6.QtCore import QCoreApplication,QEvent
        cls.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_actual_intel_amd_asus_three_lods_have_no_floating_common_depth_faces(self):
        from assembly_geometry import build_scene
        from assembly_profiles import bake_profiles
        from hardware_appearance import CATALOG,appearance_for
        from assembly_detail import _point_inside
        rows={r[0]:r for r in CATALOG if r[1]=='gpu'}
        for identity in ('intel-limited-arc-a770-16g','amd-reference-rx7900xtx-24g','asus-dual-4060-oc'):
            a=appearance_for('gpu',rows[identity][-1][0]);d=a['board_details']['dimensions_mm']
            spec=bake_profiles(dict(case={'layout':'tower'},cpu={'appearance':appearance_for('cpu','Intel Core i7-13700KF')},memory={'count':0,'modules':[]},
                gpu=dict(appearance=a,length_mm=d['length'],width_mm=d['height'],thickness_mm=d['thickness'])),self.engine)
            for level in ('eco','balanced','close'):
                scene=build_scene(dict(spec,detail_level=level));panels=[m for m in scene.meshes if m.name=='gpu-cover-panel']
                shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
                width=max(shell.vertices[0::6])-min(shell.vertices[0::6]);length=max(shell.vertices[2::6])-min(shell.vertices[2::6])
                meta=scene.metadata['detail']['gpu']['front_paint_partition']
                self.assertTrue(meta['source_painter_partition']);self.assertFalse(meta['omitted_source_paint'])
                projected=[]
                for m in panels:
                    projected.append([tuple((m.vertices[n+off],m.vertices[n+off+2]) for off in (0,6,12))
                        for n in range(0,len(m.vertices),18) if m.vertices[n+4]<-.999])
                occupied=0
                for xi in range(1,16):
                    for zi in range(1,29):
                        point=((xi/16-.5)*width+.0127,(zi/29-.5)*length+.0231)
                        hits=sum(any(inside(point,t) for t in triangles) for triangles in projected)
                        self.assertLessEqual(hits,1,(identity,level,point,hits));occupied+=hits
                self.assertGreater(occupied,5)
                self.assertLessEqual(scene.triangle_count,{'eco':80000,'balanced':160000,'close':300000}[level])


if __name__=='__main__':unittest.main()
