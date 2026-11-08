"""Actual AIO mouth/lead triangles; software geometry only, no sensors or UI."""
import copy
import math
import unittest
from unittest.mock import patch

import assembly_cooling as cooling
from cooling_catalog import choices_coolers,get_cooler


ANCHORS={'cpu':{'position':(-35.,35.,10.),'normal':(-1.,0.,0.),'up':(0.,1.,0.)},
         'case_dimensions':(600.,800.,800.)}


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def add(a,b):return tuple(x+y for x,y in zip(a,b))
def mul(a,s):return tuple(x*s for x in a)
def length(a):return math.sqrt(dot(a,a))
def unit(a):return mul(a,1/length(a))
def world(mesh):return [add(mesh.vertices[i:i+3],mesh.position) for i in range(0,len(mesh.vertices),6)]


def mouths(meshes,name,origin,split_axis,axis):
    """Recover outlet mouths from the actual connector triangles, not routing controls."""
    vertices=[p for mesh in meshes if mesh.name==name for p in world(mesh)]
    result=[]
    for sign in (-1,1):
        half=[p for p in vertices if dot(sub(p,origin),split_axis)*sign>1e-5]
        assert half,(name,sign)
        extreme=max(dot(p,axis) for p in half)
        ring={tuple(round(x,7) for x in p) for p in half if abs(dot(p,axis)-extreme)<1e-5}
        center=tuple(sum(p[i] for p in ring)/len(ring) for i in range(3))
        result.append((center,unit(axis)))
    return result


def planar_hit(triangles,point,axis):
    # Barycentric inclusion on true generated mouth faces, irrespective of winding.
    for a,b,c in triangles:
        if any(abs(dot(sub(p,point),axis))>1e-5 for p in (a,b,c)):continue
        u,v,w=sub(b,a),sub(c,a),sub(point,a)
        uu,uv,vv,wu,wv=dot(u,u),dot(u,v),dot(v,v),dot(w,u),dot(w,v)
        denominator=uu*vv-uv*uv
        if denominator<1e-12:continue
        s=(vv*wu-uv*wv)/denominator;t=(uu*wv-uv*wu)/denominator
        if s>=-1e-6 and t>=-1e-6 and s+t<=1+1e-6:return True
    return False


class AioConnections048Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No hardware, network, window or worker')))

    def build(self,identity,level='balanced',mount='top',anchors=None):
        anchors=anchors or ANCHORS
        before=copy.deepcopy(anchors)
        meshes,meta=cooling.add_cooling((),{'cooling':{'cpu_cooler':identity,'radiator_mount':mount}},level,anchors)
        self.assertEqual(anchors,before);self.assertFalse(meta['rejected'])
        return meshes,meta

    def assert_mouth_join(self,meshes,mouth,level):
        center,axis=mouth
        hose=next(m for m in meshes if m.name=='cooler-liquid-tubes')
        points=world(hose);segments={'eco':6,'balanced':8,'close':10}[level]
        outer={tuple(round(x,6) for x in p) for p in points
               if abs(dot(sub(p,center),axis))<2e-5 and abs(length(sub(p,center))-6.2)<2e-5}
        self.assertEqual(len(outer),segments,('No complete terminal hose ring',center,level))
        # Actual end-ring edges must form one complete cycle, never isolated tips.
        edges=set();lead_faces=[]
        for i in range(0,len(points),3):
            tri=points[i:i+3]
            for j in range(3):
                a,b=(tuple(round(x,6) for x in tri[k]) for k in (j,(j+1)%3))
                if a in outer and b in outer:edges.add(tuple(sorted((a,b))))
            if any(tuple(round(x,6) for x in p) in outer for p in tri):
                projection=[dot(sub(p,center),axis) for p in tri]
                if max(projection)>1e-4:
                    self.assertGreaterEqual(min(projection),-2e-5)
                    lead_faces.append(i)
        self.assertEqual(len(edges),segments)
        self.assertTrue(all(sum(p in e for e in edges)==2 for p in outer))
        self.assertTrue(lead_faces,'No actual straight lead enters the outlet axis')
        for i in lead_faces:
            for offset in (0,6,12):
                normal=hose.vertices[i*6+offset+3:i*6+offset+6]
                self.assertAlmostEqual(dot(normal,axis),0.,places=6)
        # The visible hose boundary joins a real flange or its same-mesh end
        # wall. Check true triangle coverage, including mid-edge polygon points.
        triangles=[]
        for mesh in meshes:
            if mesh.name in ('cooler-liquid-tubes','cooler-lfiii-twin-hose-elbows',
                              'cooler-block-fittings','cooler-radiator-fittings'):
                values=world(mesh);triangles.extend(values[i:i+3] for i in range(0,len(values),3))
        triangles=[tri for tri in triangles
                   if all(abs(dot(sub(p,center),axis))<1e-5 for p in tri)]
        self.assertTrue(triangles,'Neither flange nor hose end wall closes this mouth')
        for a,b in edges:
            for t in (.2,.5,.8):
                boundary=add(mul(a,1-t),mul(b,t))
                inside=add(center,mul(sub(boundary,center),.999))
                self.assertTrue(planar_hit(triangles,inside,axis),('Unclosed radial seam',center,inside))

    def inspect_connections(self,identity,level='balanced',mount='top',anchors=None):
        anchors=anchors or ANCHORS
        meshes,meta=self.build(identity,level,mount,anchors)
        p,basis=cooling._cpu_frame(anchors);u,v,n=basis
        row=get_cooler(identity)
        name='cooler-lfiii-twin-hose-elbows' if row['pump_style']=='arctic_vrm' else 'cooler-block-fittings'
        #049 primary installation/side views replace the old straight-v elbow:
        #the whole LFIII head clocks toward PCIe and its final mouth exits+n.
        outlets=mouths(meshes,name,p,v,n) if row['pump_style']=='arctic_vrm' else mouths(meshes,name,p,u,v)
        _,rad_basis,_=cooling._mount_plane(mount,anchors['case_dimensions'],0.,anchors.get('case_mount_planes'))
        rad_axis=mul(rad_basis[2],-1.)
        rad_origin=cooling._mount_plane(mount,anchors['case_dimensions'],0.,anchors.get('case_mount_planes'))[0]
        outlets+=mouths(meshes,'cooler-radiator-fittings',rad_origin,rad_basis[0],rad_axis)
        self.assertEqual(len(outlets),4)
        issues=[row for row in meta['connection_issues'] if row.get('reason')=='aio_hose_route_unverified']
        if issues:
            # The old800mm-tall schematic fixture is not a450mm routing proof.
            #049 must fail closed here instead of drawing a short hose and
            #silently calling it the factory length. Actual NorthXL fits and
            #full shared-ring topology are covered in test_aio_hose_geometry049.
            self.assertIn(identity,cooling._LFIII_FACTORY_IDS)
            self.assertTrue(all(row.get('hoses_omitted') for row in issues))
            self.assertFalse(any(m.name=='cooler-liquid-tubes' for m in meshes))
            self.assertFalse(meta['aio_hoses'])
            return meshes,meta
        for mouth in outlets:self.assert_mouth_join(meshes,mouth,level)
        return meshes,meta

    def test_all_builtin_aio_families_join_or_explicitly_reject_factory_length_at_three_lods(self):
        for item in choices_coolers():
            row=get_cooler(item['id'])
            if row['kind']!='aio':continue
            for level in ('eco','balanced','close'):
                with self.subTest(model=row['id'],lod=level):self.inspect_connections(row['id'],level)

    def test_authored_oblique_rad_planes_and_cpu_pose_keep_both_mouth_axes(self):
        anchors=copy.deepcopy(ANCHORS)
        anchors['cpu']=dict(position=(12.,36.,-17.),normal=unit((-1.,.3,.2)),up=(0.,1.,0.))
        for mount,normal in (('top',(.2,1.,.1)),('front',(.1,.2,1.)),('side',(1.,.1,.2))):
            anchors['case_mount_planes']={mount:dict(position=(140.,240.,180.),normal=unit(normal),up=(0.,0.,1.),span_mm=(900.,900.))}
            for identity in ('arctic-liquid-freezer-iii-240','nzxt-kraken-360-2023'):
                with self.subTest(model=identity,mount=mount):self.inspect_connections(identity,'balanced',mount,anchors)

    def test_lfiii_keeps_vrm_crown_unknown_impeller_and_factory_radiator_fans(self):
        # Use the actual NorthXL reference CPU pose, rather than the old bare
        #(-35,35,10) schematic point whose downward elbows sit below the CPU.
        anchors=dict(cpu=dict(position=(80.4,76.975,-103.056),normal=(-1.,0.,0.),up=(0.,1.,0.)),
                     case_dimensions=(240.,509.,503.))
        meshes,meta=self.inspect_connections('arctic-liquid-freezer-iii-240',anchors=anchors)
        self.assertEqual(len(meta['aio_hoses']),2)
        row=get_cooler('arctic-liquid-freezer-iii-240')
        self.assertEqual(row['radiator_mm'],dict(length=277,width=120,thickness=38))
        self.assertEqual(row['fan_model'],'arctic-p12-pwm')
        self.assertEqual(meta['radiator_fan_count'],2);self.assertEqual(meta['documented_cooler_fans'],3)
        crown=next(m for m in meshes if m.name=='cooler-lfiii-static-radial-crown')
        self.assertFalse(crown.rotor)
        vrm=next(f for f in meta['fans'] if f['role']=='vrm_independent')
        self.assertEqual(vrm['diameter_mm'],60);self.assertFalse(vrm['blade_count_verified'])
        self.assertFalse(meta['cpu_fan_tach_usable']);self.assertEqual(meta['real_cpu_rotor_parts'],[])
        self.assertTrue(all(f.get('rpm') is None and f.get('rotation_default')=='static' for f in meta['fans']))
        self.assertFalse(any('heatpipe' in m.name or m.name in ('cooler-fin-stack','cooler-tower-fins') for m in meshes))

    def test_air_and_old_reference_loop_never_enter_aio_connection_builder(self):
        with patch.object(cooling,'_aio_hose',side_effect=AssertionError('AIO-only repair leaked')):
            for identity in ('noctua-nh-d15','noctua-nh-l12s','custom-loop-360-reference'):
                with self.subTest(model=identity):self.build(identity,'eco')

    def test_repair_merges_end_walls_into_existing_hose_part_without_new_draws(self):
        meshes,_=self.build('nzxt-kraken-360-2023')
        hoses=[m for m in meshes if m.name=='cooler-liquid-tubes']
        self.assertEqual(len(hoses),1);self.assertEqual(hoses[0].part_id,'cooler:cpu')
        self.assertFalse(hoses[0].rotor)
        self.assertFalse(any('cuff' in m.name or 'aio-hose' in m.name for m in meshes))
        self.assertTrue(all(math.isfinite(v) for v in hoses[0].vertices))


if __name__=='__main__':unittest.main()
