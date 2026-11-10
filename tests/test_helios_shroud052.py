"""GX601 split cover/window and actual built-radiator assembly state."""
import copy
from collections import Counter
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,Scene,box,build_scene,vertex_bytes
from assembly_helios_shroud052 import CASE_ID,prepare,finish
from assembly_visibility048 import mesh_visible,psu_cover_mesh_ids
from assembly_style import apply_model_styles
from assembly_auxiliary import _segment_triangle
from chassis_catalog import CASES,get_case

DIMS=(250.,591.,565.)
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def triangles(mesh):
    return [tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12))
            for i in range(0,len(mesh.vertices),18)]


def hit(mesh,a,b):return any(_segment_triangle(a,b,t) for t in triangles(mesh))


def cover_fixture():return prepare(get_case(CASE_ID),DIMS,(.15,.19,.24,1.))


class HeliosShroud052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('No native/GL/network/workers')))

    def test_exact_product_and_observed_parts_preserve_unknown_manufacturing_values(self):
        case=get_case(CASE_ID);before=copy.deepcopy(case);meshes,front,meta=cover_fixture()
        self.assertEqual(case,before);self.assertEqual({m.part_id for m in (*meshes,front)},
            {'case:psu-rear-cover','case:psu-front-cover','case:psu-side-window'})
        self.assertTrue(all(m.component=='case' for m in (*meshes,front)))
        self.assertFalse(meta['cad_verified']);self.assertFalse(meta['positions_verified'])
        self.assertFalse(meta['thickness_verified']);self.assertFalse(meta['window_shape_verified'])
        self.assertFalse(meta['chamber_is_solid']);self.assertFalse(meta['window_is_display'])
        self.assertFalse(meta['actual_power_sensor_bound'])
        for case in CASES:
            if case['id']!=CASE_ID:self.assertEqual(prepare(case,DIMS,(0,0,0,1)),((),None,{}))
        self.assertEqual(sum(c['id']!=CASE_ID for c in CASES),95)

    def test_actual_window_aperture_and_thin_roof_leave_the_compartment_empty(self):
        meshes,front,meta=cover_fixture();rear,pane=meshes;window=meta['side_window_polygon_world_zy_mm']
        z=sum(p[0] for p in window)/4;y=sum(p[1] for p in window)/4
        a,b=(-121.,y,z),(-115.,y,z)
        self.assertFalse(hit(rear,a,b));self.assertTrue(hit(pane,a,b))
        self.assertGreater(pane.color[3],0.);self.assertLess(pane.color[3],.5)
        self.assertTrue(hit(rear,(-121.,-283.,-250.),(-115.,-283.,-250.)))
        self.assertTrue(hit(rear,(0.,-192.,-150.),(0.,-186.,-150.)))
        self.assertFalse(hit(rear,(-80.,-240.,-150.),(80.,-240.,-150.)))
        self.assertFalse(hit(front,(-80.,-240.,150.),(80.,-240.,150.)))

    def test_closed_surfaces_have_outward_normals_and_no_uncovered_boundary_edges(self):
        meshes,front,_=cover_fixture()
        for mesh in (*meshes,front):
            edges=[];volume=0.
            for index,t in enumerate(triangles(mesh)):
                a,b,c=t;ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
                n=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                self.assertGreater(sum(x*x for x in n),1e-14)
                normal=mesh.vertices[index*18+3:index*18+6];self.assertAlmostEqual(sum(x*x for x in normal),1.)
                self.assertGreater(sum(n[k]*normal[k] for k in range(3)),0.)
                volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
                edges.extend(zip(t,(*t[1:],t[0])))
            self.assertGreater(volume,0.)
            if mesh.part_id=='case:psu-front-cover':
                # 055 front uses an exact F32 boundary, with no T splits. Keep
                # the stricter linear check bounded as the new detail grows.
                directed=Counter(edges)
                for (a,b),count in directed.items():
                    self.assertEqual(count,1);self.assertEqual(directed[(b,a)],1)
                continue
            # Exact geometric closure, including an edge split by a disjoint
            # cap triangulation. Do not confuse a T tessellation with a hole.
            for index,(a,b) in enumerate(edges):
                delta=tuple(b[k]-a[k] for k in range(3));norm=sum(x*x for x in delta);cuts=[0.,1.];spans=[]
                for j,(c,d) in enumerate(edges):
                    if j==index:continue
                    ts=[]
                    for point in (c,d):
                        t=sum((point[k]-a[k])*delta[k] for k in range(3))/norm
                        if math.dist(point,tuple(a[k]+t*delta[k] for k in range(3)))>1e-6:break
                        ts.append(t)
                    if len(ts)!=2:continue
                    lo,hi=max(0.,min(ts)),min(1.,max(ts))
                    if hi-lo>1e-8:cuts.extend((lo,hi));spans.append((lo,hi,1 if ts[1]>ts[0] else -1))
                cuts=sorted(set(cuts))
                for lo,hi in zip(cuts,cuts[1:]):
                    if hi-lo<1e-8:continue
                    mid=(lo+hi)/2
                    self.assertEqual(sum(sign for x,y,sign in spans if x-1e-9<mid<y+1e-9),-1,(mesh.name,index,lo,hi))

    def test_only_real_lower_front_radiator_removes_front_candidate_from_physical_scene(self):
        meshes,front,meta=cover_fixture();rad=Mesh('real-radiator',box(120.,398.,38.),(0,0,0,1),(0.,0.,253.5),'cooler',part_id='cooler:radiator')
        row=dict(id='cooler:radiator',kind='radiator',mount='front',model_id='exact-reference')
        before=copy.deepcopy(meta)
        for rows,actual in (([],(rad,)),([row],()),([dict(row,mount='top')],(rad,))):
            result,state,_=finish(meshes,front,actual,dict(parts=rows),meta)
            self.assertIn(front,result);self.assertEqual(state['removed_parts'],[])
        result,state,_=finish((*meshes,rad),front,(rad,),dict(parts=[row]),meta)
        self.assertNotIn(front,result);self.assertEqual(meta,before)
        self.assertEqual(state['assembly_state'],'front_cover_removed_for_radiator_lower_bay')
        self.assertEqual(state['removed_parts'][0]['id'],'case:psu-front-cover')
        self.assertFalse(state['removed_parts'][0]['physical_mesh_present'])
        self.assertEqual({r['id'] for r in state['parts']},{'case:psu-rear-cover','case:psu-side-window'})
        self.assertTrue(all(r['assembly_state']=='installed' for r in state['parts']))

    def test_actual_three_lods_radiator_clearance_and_six_styles_keep_physical_identity(self):
        for level in ('eco','balanced','close'):
            scene=build_scene(dict(case=get_case(CASE_ID),memory=dict(count=2,diffuser=True),detail_level=level,lighting_preview='mint',
                                  cooling=dict(cpu_cooler='arctic-liquid-freezer-iii-360',radiator_mount='front')))
            state=scene.metadata['case_shroud'];self.assertEqual(state['assembly_state'],'front_cover_removed_for_radiator_lower_bay')
            covers=[m for m in scene.meshes if m.part_id.startswith('case:psu-')]
            self.assertEqual(len(covers),2);self.assertFalse(any(m.name=='psu-shroud' for m in scene.meshes))
            radiators=[m for m in scene.meshes if m.part_id=='cooler:radiator'];self.assertTrue(radiators)
            rear_front=max(p[2] for m in covers for t in triangles(m) for p in t)
            rad_rear=min(p[2] for m in radiators for t in triangles(m) for p in t)
            self.assertGreater(rad_rear-rear_front,100.)
            for style in SIX:
                styled,_=apply_model_styles(scene.meshes,style,{},scene.dimensions,get_case(CASE_ID)['panels'])
                for source in covers:
                    value=next(m for m in styled if m.part_id==source.part_id)
                    self.assertIs(value.vertices,source.vertices);self.assertEqual(value.position,source.position)
            rows=scene.metadata['hardware']['parts'];self.assertEqual(sum(r['kind'] in ('case_cover','case_window') for r in rows),2)
            zones=scene.metadata['lighting_preview']['zones']
            self.assertEqual(len(zones),2)
            self.assertEqual({zone['part_id'] for zone in zones},{'memory:0','memory:1'})
            for zone in zones:
                mesh=scene.meshes[zone['mesh_index']]
                self.assertEqual(mesh.name,'ram-diffuser');self.assertEqual(mesh.part_id,zone['part_id'])

    def test_show_psu_shared_visibility_covers_solid_ink_pick_without_structural_loss(self):
        meshes,front,meta=cover_fixture();all_meshes=(*meshes,front)
        self.assertEqual(psu_cover_mesh_ids(all_meshes),frozenset(map(id,all_meshes)))
        for cutaway in (False,True):
            self.assertTrue(all(mesh_visible(m,cutaway,False) for m in all_meshes))
            self.assertFalse(any(mesh_visible(m,cutaway,True) for m in all_meshes))
        rail=Mesh('case-upright',box(5,100,5),(0,0,0,1),component='case')
        self.assertTrue(mesh_visible(rail,True,True))

    def test_real_renderer_solid_ink_and_click_use_the_same_three_cover_flags(self):
        from assembly_viewer import AssemblyRenderer,GL_TRIANGLES,GL_LINES
        class Backend:
            def __init__(self):self.calls=[]
            def __getattr__(self,name):
                def call(*args):self.calls.append((name,args))
                return call
        meshes,front,meta=cover_fixture();window=meta['side_window_polygon_world_zy_mm']
        z=sum(p[0] for p in window)/4;y=sum(p[1] for p in window)/4
        psu=Mesh('actual-reference-psu',box(150.,60.,120.),(.2,.3,.4,1.),(0.,y,z),'psu',part_id='psu:0')
        originals=(*meshes,front,psu);cover_ids={m.part_id for m in originals if m.component=='case'}
        for style in SIX:
            physical,draw_meta=apply_model_styles(originals,style,{},DIMS,{'front':'open'})
            scene=Scene(physical,DIMS,draw_meta)
            r=AssemblyRenderer();r.program=Backend();r.buffer=Backend();r.vao=Backend();r.functions=Backend()
            r._uniforms={'backgroundMode':1,'shadeMix':2};r.upload(scene)
            self.addCleanup(r.close);data=vertex_bytes(scene);ranges=r.ranges;edges=r.edge_ranges
            calls=[]
            r._draw_part=lambda row,*args,**kwargs:calls.append((row[0].part_id,kwargs.get('mode',GL_TRIANGLES)))
            for shown in (False,True,False):
                calls.clear();r.draw(640,480,yaw=-90.,pitch=0.,inspection_cutaway=True,show_psu=shown)
                point=r.project_point((0.,y,z));self.assertIsNotNone(point)
                self.assertEqual(r.pick(*point[:2]),'psu:0' if shown else 'case:psu-side-window')
                self.assertIn(('psu:0',GL_TRIANGLES),calls)
                solid_ids=cover_ids-({'case:psu-side-window'} if style=='notebook_line' else set())
                self.assertEqual({p for p,mode in calls if p in cover_ids and mode==GL_TRIANGLES},set() if shown else solid_ids)
                if style=='notebook_line':
                    self.assertEqual({p for p,mode in calls if p in cover_ids and mode==GL_LINES},set() if shown else cover_ids)
            self.assertEqual(r.upload_count,1);self.assertIs(r.ranges,ranges);self.assertIs(r.edge_ranges,edges)
            self.assertEqual(vertex_bytes(scene),data)
            self.assertEqual(sum(name=='allocate' for name,args in r.buffer.calls),1)
            r.close()

    def test_front_120_140_fixed_roof_retains_factory_support_and_neighbor_groups(self):
        from assembly_parts import fit_messages
        baseline_neighbors={}
        for model in ('arctic-p12-pwm','arctic-p14-pwm'):
            for cooler in ('','noctua-nh-d15','nzxt-kraken-360-2023'):
                groups=[dict(model=model,count=3,mount='front',direction='intake'),
                        dict(model='arctic-p12-pwm',count=1,mount='rear',direction='exhaust')]
                if cooler!='nzxt-kraken-360-2023':groups.append(dict(model='arctic-p12-pwm',count=2,mount='top',direction='exhaust'))
                spec=dict(case=get_case(CASE_ID),gpu=dict(present=False),memory=dict(count=0),detail_level='eco',
                    cooling=dict(cpu_cooler=cooler,radiator_mount='top',case_fans=groups))
                scene=build_scene(spec);meta=scene.metadata['cooling']
                fronts=[m for m in scene.meshes if m.part_id.startswith('fans:front:')]
                self.assertTrue(fronts)
                neighbors={m.part_id for m in scene.meshes if m.component=='fans' and not m.part_id.startswith('fans:front:')}
                if model=='arctic-p12-pwm':baseline_neighbors[cooler]=neighbors
                self.assertEqual(neighbors,baseline_neighbors[cooler])
                if not cooler:self.assertEqual(neighbors,{'fans:rear:0','fans:top:0','fans:top:1'})
                if cooler=='nzxt-kraken-360-2023':self.assertTrue(any(r['kind']=='radiator' and r['mount']=='top' for r in meta['parts']))
                self.assertEqual(meta['mesh_count'],sum(m.component in ('cooler','fans') for m in scene.meshes))
                self.assertEqual(meta['triangle_count'],sum(m.vertex_count//3 for m in scene.meshes if m.component in ('cooler','fans')))
                self.assertEqual(scene.metadata['case_shroud']['assembly_state'],'both_covers_installed')
                self.assertTrue(scene.metadata['case_shroud']['official_front_fans']['supported'])
                ids={'fans:front:'+str(index)for index in range(3)}
                self.assertTrue(ids.issubset({row.get('id')for row in meta['parts']}))
                self.assertTrue(ids.issubset({row.get('part_id')for row in meta['fans']}))
                self.assertFalse(scene.metadata['case_shroud']['front_fan_reference_clearance_reviews'])
                self.assertFalse(any(r['reason']in('case_cover_reference_clearance_unverified','front_cover_material_unverified')
                                     for r in meta['rejected']))
                messages=fit_messages(spec,scene.metadata)
                self.assertNotIn('前置风扇与当前电源罩参考模型相交，整组暂未放入。机箱官方支持规格仍保留，需继续核实罩板位置。',messages)


if __name__=='__main__':unittest.main()
