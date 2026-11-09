"""Real GPU cap-and-wall apertures, including crossed thin decoration walls."""
import copy
import hashlib
import math
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from assembly_detail import (TRIANGLE_BUDGETS,_area,_point_inside,_material_wall_segments,
                             perforated_plate,chamfer_rect,circle)
from assembly_geometry import build_scene,vertex_bytes


def front_caps_at(mesh,x,z):
    """Independent point-in-triangle ray test through a front-facing plane."""
    hits=[]
    for n in range(0,len(mesh.vertices),18):
        if abs(mesh.vertices[n+4])<.999:continue
        points=[(mesh.vertices[n+k]+mesh.position[0],mesh.vertices[n+k+2]+mesh.position[2]) for k in (0,6,12)]
        crosses=[(b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(x-a[0]) for a,b in zip(points,points[1:]+points[:1])]
        if min(crosses)>=-1e-7 or max(crosses)<=1e-7:hits.append(n//18)
    return hits


def enters_hole(a,b,hole):
    """Independent convex line/half-plane intersection with strict interior."""
    low,high=0.,1.;dx,dy=b[0]-a[0],b[1]-a[1]
    for p,q in zip(hole,(*hole[1:],hole[0])):
        start=(q[0]-p[0])*(a[1]-p[1])-(q[1]-p[1])*(a[0]-p[0])
        slope=(q[0]-p[0])*dy-(q[1]-p[1])*dx
        if abs(slope)<1e-12:
            if start<=1e-7:return False
        elif slope>0:low=max(low,(1e-7-start)/slope)
        else:high=min(high,(1e-7-start)/slope)
        if high<=low:return False
    return high-low>1e-7


def wall_crossings(vertices,holes,axes=(0,1),normal_axis=2,position=(0.,0.,0.)):
    result=[]
    for n in range(0,len(vertices),18):
        if abs(vertices[n+3+normal_axis])>.999:continue
        points=[tuple(vertices[n+off+k]+position[k] for k in axes) for off in (0,6,12)]
        if any(enters_hole(a,b,hole) for a,b in zip(points,points[1:]+points[:1]) for hole in holes):result.append(n//18)
    return result


class GpuPlateWall046Tests(unittest.TestCase):
    def test_slanted_perimeter_wall_is_removed_only_inside_hole(self):
        poly=((-20.,-20.),(20.,20.),(-20.,20.));hole=circle(0.,0.,8.,24)
        old=perforated_plate(poly,[hole],.3)
        new=perforated_plate(poly,[hole],.3,clip_walls=True)
        self.assertTrue(wall_crossings(old,[hole]))
        self.assertEqual(wall_crossings(new,[hole]),[])
        self.assertTrue(new)
        spans=_material_wall_segments(poly[0],poly[1],poly,[hole],True)
        self.assertEqual(len(spans),2)
        self.assertEqual(spans[0][0],poly[0]);self.assertEqual(spans[-1][1],poly[1])
        self.assertTrue(all(math.hypot(*p)>=7.9 for span in spans for p in span))

    def test_partial_hole_walls_remain_within_plate_and_union_material(self):
        poly=chamfer_rect(30.,20.,1.);holes=[circle(13.,0.,7.,20),circle(5.,0.,5.,20)]
        vertices=perforated_plate(poly,holes,2.,clip_walls=True)
        self.assertEqual(wall_crossings(vertices,holes),[])
        self.assertTrue(all(-15.000001<=vertices[n]<=15.000001 and -10.000001<=vertices[n+1]<=10.000001
                            for n in range(0,len(vertices),6)))
        for a,b in _material_wall_segments(holes[0][0],holes[0][1],poly,holes,False):
            self.assertTrue(_point_inside(tuple((x+y)/2 for x,y in zip(a,b)),poly))

    def test_default_legacy_plate_and_non_gpu_scene_bytes_stay_exact(self):
        cases=[('e44344a194c8f3fa0bd57f7460076997862dd856649fbc79524c208170c17ac3',chamfer_rect(40.,30.,2.),[(0.,0.,6.)],2.),
               ('45c78c98eb640f9453f7342b787c3e27185bafb255a100417865a9fb22b7c329',((-20.,-20.),(20.,20.),(-20.,20.)),[(0.,0.,8.)],.3),
               ('82eb9da972e0181c451a373fb0ccc61d740eb82433408065d4faaf0fa0c1f261',chamfer_rect(80.,32.,1.),[(-15.,0.,9.),(15.,0.,9.)],1.2)]
        for expected,poly,holes,depth in cases:
            vertices=perforated_plate(poly,holes,depth)
            self.assertEqual(hashlib.sha256(struct.pack('<'+str(len(vertices))+'d',*vertices)).hexdigest(),expected)
        scene=build_scene({'case':{'dimensions_mm':dict(width=240,height=500,depth=500)},'gpu':{'present':False},'memory':{'count':2}})
        self.assertEqual(hashlib.sha256(vertex_bytes(scene)).hexdigest(),'cd6272e24526f644bbf7ce30fa2648afbb7ad1667b8387dbb43707ea24f47c6b')

    def test_fully_masked_thin_panel_has_no_phantom_walls(self):
        self.assertEqual(perforated_plate(chamfer_rect(4.,4.,.1),[(0.,0.,8.)],.3,clip_walls=True),())

    def test_opt_in_synthetic_surface_has_closed_geometric_edge_coverage(self):
        vertices=perforated_plate(((-20.,-20.),(20.,20.),(-20.,20.)),[(0.,0.,8.)],.3,segments=12,clip_walls=True)
        edges=[]
        for n in range(0,len(vertices),18):
            p=[vertices[n+k:n+k+3] for k in (0,6,12)]
            edges.extend(zip(p,p[1:]+p[:1]))
        for index,(a,b) in enumerate(edges):
            delta=tuple(b[k]-a[k] for k in range(3));den=sum(v*v for v in delta)
            if den<1e-15:continue
            intervals=[]
            for j,(p,q) in enumerate(edges):
                if j==index:continue
                ts=[]
                for point in (p,q):
                    t=sum((point[k]-a[k])*delta[k] for k in range(3))/den
                    if math.dist(point,tuple(a[k]+delta[k]*t for k in range(3)))>1e-7:break
                    ts.append(t)
                if len(ts)==2:intervals.append((max(0.,min(ts)),min(1.,max(ts))))
            end=0.
            for low,high in sorted(intervals):
                if high<low or high<=end:continue
                if low>end+1e-6:break
                end=high
            self.assertGreaterEqual(end,1.-1e-6,(a,b))


class ProfiledGpuCover046Tests(unittest.TestCase):
    IDS=('asus-astral-5090','asus-rog-strix-4090-oc','nvidia-founders-rtx5090-32g',
         'amd-reference-rx7900xtx-24g','sapphire-pulse-rx7900xt-20g',
         'intel-limited-arc-a770-16g','acer-bifrost-a770-16g-oc')
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen');os.environ.setdefault('QT_QUICK_BACKEND','software')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        from PySide6.QtQml import QQmlEngine
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('Offline geometry only')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda values:self.warnings.extend(v.toString() for v in values))
    def tearDown(self):
        from PySide6.QtCore import QCoreApplication,QEvent
        from PySide6.QtGui import QOpenGLContext
        self.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(self.warnings,[]);self.assertIsNone(QOpenGLContext.currentContext());self.assertEqual(self.app.topLevelWindows(),[])
    def spec(self,identity,level):
        from assembly_profiles import bake_profiles
        from hardware_appearance import appearance_for
        from assembly_spec import build_spec
        from stats_config import DEFAULT
        config=copy.deepcopy(DEFAULT);config['assembly'].update(case_model='cooler-master-haf-700-evo',
            cpu_model='intel-13700kf',gpu_model=identity,detail_level=level,cables_enabled=False,case_fans=[])
        value=build_spec({},config,{},[]);self.assertEqual(value['gpu']['appearance']['id'],identity)
        return bake_profiles(value,self.engine)
    def assert_front_openings_fit(self,scene,spec):
        """Actual fixed rings within the known or explicit reference envelope."""
        shroud=next(m for m in scene.meshes if m.name=='gpu-shroud');gx,gy,gz=shroud.position
        anchor=scene.metadata['attachment_anchors']['gpu']
        width=anchor['width_mm'];length=anchor['length_mm'];circles=[]
        for mesh in scene.meshes:
            if mesh.name!='gpu-fan-opening' or mesh.position[1]>=gy:continue
            radius=max(math.hypot(mesh.vertices[n],mesh.vertices[n+2]) for n in range(0,len(mesh.vertices),6))
            self.assertLessEqual(abs(mesh.position[0]-gx)+radius,width/2+1e-5)
            self.assertLessEqual(abs(mesh.position[2]-gz)+radius,length/2+1e-5)
            circles.append((mesh.position[0],mesh.position[2],radius))
        for n,(x,z,radius) in enumerate(circles):
            for other_x,other_z,other_radius in circles[n+1:]:
                self.assertGreaterEqual(math.hypot(x-other_x,z-other_z)+1e-5,radius+other_radius)
    def test_real_baked_front_panels_do_not_leave_walls_across_fan_apertures(self):
        meaningful=False;meaningful_models=set()
        import assembly_detail,assembly_gpu_panels051
        real=assembly_detail.perforated_plate
        current_partition=assembly_gpu_panels051.partition
        def legacy_cover_walls(polygons,fan_holes,depth,*,segments=20):
            # Inject only at the generic cover boundary. Retain the actual
            # disjoint painter-order caps; deliberately restore prior uncut
            # cover walls using those same live source polygons/fan holes.
            # Exact Astral backplate/retention/port construction stays real.
            values,meta=current_partition(polygons,fan_holes,depth,segments=segments)
            prior=[]
            for polygon,current in zip(polygons,values):
                legacy=real(polygon,fan_holes,depth,segments=segments,clip_walls=False) if polygon else ()
                caps=tuple(v for n in range(0,len(current),18) if abs(current[n+5])>.999 for v in current[n:n+18])
                walls=tuple(v for n in range(0,len(legacy),18) if abs(legacy[n+5])<=.999 for v in legacy[n:n+18])
                prior.append(caps+walls)
            return tuple(prior),dict(meta,legacy_unclipped_cover_wall_control=True)
        for identity in self.IDS:
            for level in ('eco','balanced','close'):
                with self.subTest(model=identity,lod=level):
                    value=self.spec(identity,level);scene=build_scene(value)
                    self.assert_front_openings_fit(scene,value)
                    with patch('assembly_gpu_panels051.partition',side_effect=legacy_cover_walls) as prior:
                        before=build_scene(value)
                    self.assertEqual(prior.call_count,0 if identity=='asus-astral-5090' else 1)
                    def unchanged(s):return [(m.name,m.vertices,m.color,m.position,m.rotor,m.axis,m.direction,m.part_id)
                                             for m in s.meshes if m.name!='gpu-cover-panel']
                    self.assertEqual(unchanged(scene),unchanged(before))
                    shroud=next(m for m in scene.meshes if m.name=='gpu-shroud')
                    fans=[m for m in scene.meshes if m.name=='gpu-fan-opening' and m.position[1]<shroud.position[1]]
                    n=32 if level=='close' else 12 if level=='eco' else 20
                    holes=[circle(f.position[0],f.position[2],max(abs(v) for v in f.vertices[0::6])*1.005,n) for f in fans]
                    old=[m for m in before.meshes if m.name=='gpu-cover-panel'];new=[m for m in scene.meshes if m.name=='gpu-cover-panel']
                    crossed=any(wall_crossings(m.vertices,holes,(0,2),1,m.position) for m in old)
                    meaningful|=crossed
                    if crossed:meaningful_models.add(identity)
                    for panel in new:self.assertEqual(wall_crossings(panel.vertices,holes,(0,2),1,panel.position),[],(identity,panel.name))
                    self.assertLessEqual(scene.triangle_count,TRIANGLE_BUDGETS[level])
        self.assertTrue(meaningful,'Real crossing-wall regression fixture must actually exercise the bug')
        self.assertTrue({'intel-limited-arc-a770-16g','amd-reference-rx7900xtx-24g'}<=meaningful_models,
                        'Two actual source profiles must retain a meaningful uncut-wall negative control')

    def test_astral_shared_bevel_keeps_actual_apertures_caps_and_edge_coverage(self):
        # Every LOD uses its actual ProfileReader geometry. Keep the existing
        # through-hole wall assertion above; additionally cover bevelled caps
        # and near-identical clipping vertices at source T junctions.
        import collections,assembly_gpu_exterior049 as exterior
        from assembly_geometry import gpu_plane
        original=exterior._bevel_silver_panel
        def overlap_area(triangle,hole):
            points=tuple(triangle)
            for a,b in zip(hole,(*hole[1:],hole[0])):
                if not points:return 0.
                def side(p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
                out=[];previous=points[-1];old=side(previous)
                for point in points:
                    current=side(point)
                    if (current>=0)!=(old>=0):
                        t=old/(old-current)
                        out.append(tuple(previous[k]+t*(point[k]-previous[k]) for k in (0,1)))
                    if current>=0:out.append(point)
                    previous,old=point,current
                points=tuple(out)
            return abs(_area(points)) if len(points)>=3 else 0.
        for level in ('eco','balanced','close'):
            with self.subTest(lod=level):
                captured=[]
                def record(vertices,outer,holes,depth):
                    result=original(vertices,outer,holes,depth)
                    captured.append((vertices,result,holes))
                    return result
                with patch.object(exterior,'_bevel_silver_panel',side_effect=record):
                    scene=build_scene(self.spec(exterior.EXACT_ID,level))
                self.assertEqual(len(captured),1)
                raw,bevel,holes=captured[0];self.assertEqual(len(raw),len(bevel))
                panels=[m for m in scene.meshes if m.name=='gpu-cover-panel']
                self.assertEqual(len(panels),6)
                self.assertTrue(all(m.vertices for m in panels))
                self.assertNotIn('silver_panel_bevel_fallback',scene.metadata['detail']['gpu'])
                self.assertEqual(tuple(v for panel in panels for v in panel.vertices),gpu_plane(bevel),
                                 'The actual scene must use the guarded geometry, not discard it')
                segments={'eco':12,'balanced':20,'close':32}[level]
                hole_polys=[circle(*hole,segments) for hole in holes]
                shared={};moved=0
                for n in range(0,len(raw),6):
                    key=tuple(round(v,9) for v in raw[n:n+3]);point=tuple(bevel[n:n+3])
                    if key in shared:self.assertEqual(shared[key],point)
                    shared[key]=point
                    if math.dist(raw[n:n+3],point)>.01:moved+=1
                self.assertGreater(moved,0,'The guard must retain a real shallow bevel')
                for n in range(0,len(bevel),18):
                    a,b,c=(bevel[n+k:n+k+3] for k in (0,6,12))
                    ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
                    cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                    length=math.sqrt(sum(v*v for v in cross));self.assertGreater(length,1e-10)
                    for k in range(3):self.assertAlmostEqual(bevel[n+3+k],cross[k]/length,places=10)
                    if abs(raw[n+5])>.999:self.assertGreater(cross[2]*raw[n+5],0.)
                    projected=[p[:2] for p in (a,b,c)]
                    self.assertTrue(all(overlap_area(projected,hole)<1e-8 for hole in hole_polys))
                for panel in (m for m in scene.meshes if m.name=='gpu-cover-panel'):
                    edges=collections.Counter()
                    for n in range(0,len(panel.vertices),18):
                        points=[tuple(round(v,7) for v in panel.vertices[n+k:n+k+3]) for k in (0,6,12)]
                        edges.update(tuple(sorted((a,b))) for a,b in zip(points,(*points[1:],points[0])))
                    # Existing source paint can share an edge more than twice;
                    # every geometric edge must nevertheless have a mate.
                    self.assertTrue(edges)
                    self.assertTrue(all(count>=2 for count in edges.values()))

    def test_astral_refinement_budget_preserves_safe_unbeveled_source_plate(self):
        import assembly_gpu_exterior049 as exterior
        from assembly_geometry import gpu_plane
        value=self.spec(exterior.EXACT_ID,'eco');captured=[]
        def reject(panels):
            captured.append(panels)
            raise ValueError('Bounded test input')
        with patch.object(exterior,'_conforming_panel_edges',side_effect=reject):
            scene=build_scene(value)
        self.assertEqual(len(captured),1)
        panels=[m for m in scene.meshes if m.name=='gpu-cover-panel']
        self.assertEqual(len(panels),6);self.assertEqual(len(captured[0]),6)
        self.assertTrue(all(m.vertices for m in panels))
        self.assertEqual(tuple(m.vertices for m in panels),tuple(gpu_plane(v) for v in captured[0]),
                         'Fallback must retain every actual unmodified source cap and wall')
        details=scene.metadata['detail']['gpu']
        self.assertEqual(details['silver_panel_bevel_fallback'],'safe_unbeveled_source_plate_refinement_budget')
        self.assertEqual(details['silver_panel_bevel_reference_mm'],0.)
        shroud=next(m for m in scene.meshes if m.name=='gpu-shroud')
        fans=[m for m in scene.meshes if m.name=='gpu-fan-opening' and m.position[1]<shroud.position[1]]
        holes=[circle(f.position[0],f.position[2],max(abs(v) for v in f.vertices[0::6])*1.005,12) for f in fans]
        for panel in (m for m in scene.meshes if m.name=='gpu-cover-panel'):
            self.assertEqual(wall_crossings(panel.vertices,holes,(0,2),1,panel.position),[])

    def test_explicit_shell_window_only_opens_front_shroud_and_preserves_later_bridge(self):
        for level in ('eco','balanced','close'):
            with self.subTest(lod=level):
                value=self.spec('gigabyte-windforce-4060-oc',level)
                self.assertEqual(len(value['gpu'].get('shell_holes',[])),1)
                old_value=copy.deepcopy(value);old_value['gpu'].pop('shell_holes')
                current=build_scene(value);old=build_scene(old_value)
                self.assert_front_openings_fit(current,value)
                unaffected=lambda scene:[(m.name,m.vertices,m.color,m.position,m.rotor,m.axis,m.direction,m.part_id)
                    for m in scene.meshes if m.name!='gpu-shroud']
                self.assertEqual(unaffected(current),unaffected(old))
                shroud=next(m for m in current.meshes if m.name=='gpu-shroud')
                previous=next(m for m in old.meshes if m.name=='gpu-shroud')
                length=value['gpu']['length_mm'];width=value['gpu']['width_mm']
                self.assertTrue(value['gpu']['fans'])
                self.assertTrue(all(len(fan.get('radius_uv',()))==2 for fan in value['gpu']['fans']))
                point=lambda u,v:(shroud.position[0]+(v-.5)*width,shroud.position[2]+(u-.5)*length)
                # Explicit source evenodd window: this point is outside the
                # fan circles and every independent decoration polygon.
                x,z=point(.56,.5)
                self.assertTrue(front_caps_at(previous,x,z))
                self.assertFalse(front_caps_at(shroud,x,z))
                self.assertFalse(any(front_caps_at(m,x,z) for m in current.meshes if m.name=='gpu-cover-panel'))
                # Another point inside the same window is covered by a later
                # source slash bridge; never broadcast shell holes to it.
                x,z=point(.46,.5)
                self.assertFalse(front_caps_at(shroud,x,z))
                self.assertTrue(any(front_caps_at(m,x,z) for m in current.meshes if m.name=='gpu-cover-panel'))


if __name__=='__main__':unittest.main()
