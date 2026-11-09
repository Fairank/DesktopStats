"""Pure synthetic regression for an exact source-observed GTX 780 Ti window.

The rotor fixture is an identity sentinel, never evidence for an unknown retail
blower blade. No Scene/QML/profile, source download, hidden cooling path or
manufacturer-thickness/clear-material certification is implied by these tests.
"""
from collections import Counter
import copy
import math
import struct
import unittest

LEVELS=('eco','balanced','close')
STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
NEW_NAMES=('detail-gpu-window-fin-samples','detail-gpu-window-face',
           'detail-gpu-window-screw-heads','detail-gpu-window-screw-recesses')
NEUTRAL_ID='test-unrelated-gpu-default'

def _f32(v):return struct.pack('<'+str(len(v))+'f',*v)

def _physical(m):return (m.name,m.vertices,m.color,m.position,m.component,m.rotor,m.direction,m.axis,m.part_id)

def _bounds(meshes):
    return tuple((min(m.vertices[n]+m.position[k] for m in meshes for n in range(k,len(m.vertices),6)),
                  max(m.vertices[n]+m.position[k] for m in meshes for n in range(k,len(m.vertices),6))) for k in range(3))

def _plane_hits(meshes,x,z,front=True):
    result=[]
    for m in meshes:
        for n in range(0,len(m.vertices),18):
            normals=[m.vertices[n+k+4] for k in (0,6,12)]
            if not all(v<-.999 if front else v>.999 for v in normals):continue
            tri=[(m.vertices[n+k]+m.position[0],m.vertices[n+k+2]+m.position[2]) for k in (0,6,12)]
            signs=[(tri[(i+1)%3][0]-tri[i][0])*(z-tri[i][1])-(tri[(i+1)%3][1]-tri[i][1])*(x-tri[i][0]) for i in range(3)]
            if min(signs)>=-1e-9 or max(signs)<=1e-9:result.append((m.vertices[n+1]+m.position[1],m.name))
    return sorted(result)

def _fixture(marker=False):
    from assembly_geometry import Mesh,box,color,gpu_plane,ring
    length,width,thickness=266.7,111.1504,55.;center=(12.,-40.,15.);gx,gy,gz=center
    polys=(((.08,.13),(.51,.13),(.60,.25),(.60,.75),(.51,.87),(.08,.87)),
           ((.10,.20),(.13,.17),(.51,.17),(.54,.20),(.54,.80),(.51,.83),(.13,.83),(.10,.80)),
           ((.13,.20),(.51,.20),(.51,.80),(.13,.80)),
           ((.14,.207),(.153,.207),(.153,.793),(.14,.793)),
           ((.173,.207),(.186,.207),(.186,.793),(.173,.793)),
           ((.206,.207),(.219,.207),(.219,.793),(.206,.793)))
    spec=dict(gpu=dict(appearance=dict(id='nvidia-gtx780ti-reference',confidence='model',style='gpu_blower',fan_count=1,
        board_details=dict(dimensions_mm=dict(length=length,height=width,thickness=None),backplate=None,
            ports=[dict(type='displayport',count=1),dict(type='hdmi',count=1),dict(type='dvi',count=2)],
            host_interface=dict(bus='pcie'))),detail_polygons=[dict(points=list(p)) for p in polys],
        fans=[dict(blades=None,profile=dict(blades=None,shape='radial',hub_ratio=.39),face='front')]))
    meshes=[Mesh('gpu-shroud',box(width,thickness,length),color('#aab6bf'),center,'gpu',part_id='gpu:0')]
    meshes.extend(Mesh('gpu-cover-panel',box(1.,.3,1.),color('#35434c'),center,'gpu',part_id='gpu:0') for _ in polys)
    radius=42.69764423076923
    p=(gx+(.5104166666666666-.5)*width,gy-thickness/2-1.5,gz+(.7836538461538461-.5)*length)
    meshes.extend((Mesh('gpu-fan-opening',gpu_plane(ring(radius,radius*.92,2.)),color('#c6ccd0'),p,'gpu',part_id='gpu:0'),
        Mesh('gpu-fan-recess',gpu_plane(ring(radius*.91,0.,.5)),color('#273039'),(p[0],p[1]+1.,p[2]),'gpu',part_id='gpu:0'),
        Mesh('gpu-fan-hub',gpu_plane(ring(radius*.39,0.,2.7)),color('#7c8992'),(p[0],p[1]-.8,p[2]),'gpu',part_id='gpu:0'),
        Mesh('gpu-power-inlet-0',box(8.,5.,10.),color('#29333b'),(gx,gy+10,gz+30),'gpu'),
        Mesh('gpu-power-inlet-1',box(8.,5.,10.),color('#29333b'),(gx,gy+10,gz+50),'gpu')))
    if marker:
        # This is only an input identity sentinel, never a claimed unknown
        # retail blower blade. The actual unknown fixture above has no rotor.
        meshes.append(Mesh('gpu-fan-rotor',gpu_plane(ring(radius*.7,radius*.65,.8)),color('#596b78'),
                           p,'gpu',rotor=True,axis=(0,1,0),part_id='gpu:0'))
    return tuple(meshes),spec

class TestKeplerWindow053(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import assembly_detail
        import assembly_gpu_exterior053
        cls.detail=assembly_detail
        cls.helper=assembly_gpu_exterior053

    def pair(self,level='balanced',marker=False):
        # One input fixture; the neutral default differs in only its explicit
        # unrelated test identity. Board facts, outline, fan opening, ports and
        # sentinel geometry stay identical. No historical module is loaded.
        meshes,spec=_fixture(marker)
        from assembly_geometry import unit_polygon
        polygons=spec['gpu']['detail_polygons']
        self.assertEqual(len(polygons),6)
        for row in polygons:
            self.assertIsInstance(row['points'],list)
            self.assertTrue(unit_polygon(row['points'],266.7,111.1504,margin=.3))
        saved=copy.deepcopy(spec)
        original=tuple(map(_physical,meshes))
        neutral=copy.deepcopy(spec)
        neutral['gpu']['appearance']['id']=NEUTRAL_ID
        neutral_saved=copy.deepcopy(neutral)
        old=self.detail._gpu_detail(meshes,neutral,level)
        new=self.detail._gpu_detail(meshes,spec,level)
        self.assertEqual(neutral,neutral_saved)
        self.assertEqual(spec,saved)
        self.assertEqual(tuple(map(_physical,meshes)),original)
        restored=copy.deepcopy(neutral)
        restored['gpu']['appearance']['id']=saved['gpu']['appearance']['id']
        self.assertEqual(restored,saved)
        return old,new,meshes,spec

    def test_exact_gate_nonrectangular_aperture_and_bad_inputs(self):
        _,spec=_fixture();gpu=spec['gpu'];hole=((75.65,-1.1578,42.91),);saved=copy.deepcopy(gpu)
        r=self.helper.kepler_front_reference(gpu,266.7,111.1504,55.,hole,6)
        self.assertEqual(len(r['window_outline']),9);self.assertEqual(len(r['head_centers']),8)
        self.assertEqual(r['replaced_source_layers'],(2,3,4,5));self.assertEqual(gpu,saved)
        self.assertIsNone(gpu['appearance']['board_details']['dimensions_mm']['thickness'])
        self.assertGreater(len({p[0] for p in r['window_outline']}),2)
        for holes,count in (((),6),(hole,5),(((0.,0.,float('nan')),),6),(((0.,0.,-2.),),6)):
            self.assertEqual(self.helper.kepler_front_reference(gpu,266.7,111.1504,55.,holes,count),{})
        other=copy.deepcopy(gpu);other['appearance']['id']='nvidia-gtx780-reference'
        self.assertEqual(self.helper.kepler_front_reference(other,266.7,111.1504,55.,hole,6),{})
        for identity in (NEUTRAL_ID,'nvidia-gtx780ti-reference-unrelated-variant'):
            other=copy.deepcopy(gpu);other['appearance']['id']=identity
            self.assertEqual(self.helper.kepler_front_reference(other,266.7,111.1504,55.,hole,6),{})
        for length,width,thickness in ((float('nan'),111.1504,55.),(266.7,0.,55.),(266.7,111.1504,-1.)):
            self.assertEqual(self.helper.kepler_front_reference(gpu,length,width,thickness,hole,6),{})
        invalid=copy.deepcopy(gpu);invalid['appearance']['board_details']['dimensions_mm']['length']=None
        self.assertEqual(self.helper.kepler_front_reference(invalid,266.7,111.1504,55.,hole,6),{})
        self.assertEqual(self.helper.kepler_front_reference(None,266.7,111.1504,55.,hole,6),{})
        # The public profile boundary deliberately accepts outer lists, not
        # tuple lookalikes. Rejecting a tuple must not leave this fixture's
        # six source rows silently untested again.
        from assembly_geometry import unit_polygon
        self.assertEqual(len(gpu['detail_polygons']),6)
        for row in gpu['detail_polygons']:
            self.assertIsInstance(row['points'],list)
            self.assertTrue(unit_polygon(row['points'],266.7,111.1504,margin=.3))
            self.assertEqual(unit_polygon(tuple(row['points']),266.7,111.1504,margin=.3),())


    def test_open_window_rays_and_actual_first_opaque_fin(self):
        (old,_),(new,_),_,_spec=self.pair()
        self.assertFalse(any(m.name in NEW_NAMES for m in old))
        old_body=tuple(m for m in old if m.name=='gpu-shroud');new_body=tuple(m for m in new if m.name=='gpu-shroud')
        gx,gy,gz=old_body[0].position;length,width=266.7,111.1504
        for uv,open_expected in (((.13,.50),True),((.13,.21),False),((.35,.50),True)):
            x,z=gx+(uv[1]-.5)*width,gz+(uv[0]-.5)*length
            self.assertTrue(_plane_hits(old_body,x,z));self.assertEqual(not bool(_plane_hits(new_body,x,z)),open_expected)
        fin=next(m for m in new if m.name=='detail-gpu-window-fin-samples')
        n=next(n for n in range(0,len(fin.vertices),18) if fin.vertices[n+4]<-.999)
        x=sum(fin.vertices[n+k] for k in (0,6,12))/3+fin.position[0]
        z=sum(fin.vertices[n+k+2] for k in (0,6,12))/3+fin.position[2]
        opaque=tuple(m for m in new if m.color[3]>=.999)
        self.assertEqual(_plane_hits(opaque,x,z)[0][1],'detail-gpu-window-fin-samples')
        self.assertNotEqual(_plane_hits(old,x,z)[0][1],'detail-gpu-window-fin-samples')

    def test_three_lod_seven_changed_meshes_normals_closed_face_and_bounds(self):
        for level,count in zip(LEVELS,(16,32,48)):
            (old,_),(new,meta),_,_=self.pair(level)
            self.assertEqual(_bounds(old),_bounds(new));self.assertEqual(meta['fin_sampling_count'],count)
            self.assertTrue(meta['fin_count_is_sampling']);self.assertFalse(meta['manufacturer_thickness_verified'])
            self.assertFalse(meta['hidden_heatpipes_modelled']);self.assertIn('unverified',meta['window_face_accuracy'])
            self.assertEqual(meta['source_observed_screw_heads'],8)
            changed=tuple(m for m in new if m.name in (*NEW_NAMES,'gpu-shroud','gpu-cover-panel'))
            self.assertEqual(len(changed),7)  # shell + two frame layers + four new meshes
            self.assertEqual(Counter(m.name for m in changed)['gpu-cover-panel'],2)
            self.assertEqual({m.name for m in changed},set(NEW_NAMES)|{'gpu-shroud','gpu-cover-panel'})
            fins=next(m for m in new if m.name=='detail-gpu-window-fin-samples')
            self.assertEqual(len(fins.vertices),count*12*18)
            # Count observed front-cap X midpoints from actual triangles,
            # independently of metadata and the helper's sampling loop. This
            # is the authored longitudinal visual-bank contract, not a real
            # manufactured fin count or pitch assertion.
            for values in (fins.vertices,struct.unpack('<'+str(len(fins.vertices))+'f',_f32(fins.vertices))):
                centers=set()
                for n in range(0,len(values),18):
                    if all(values[n+k+4]<-.999 for k in (0,6,12)):
                        xs=tuple(values[n+k] for k in (0,6,12))
                        centers.add((min(xs)+max(xs))/2)
                self.assertEqual(len(centers),count)
            for m in changed:
                self.assertGreater(len(m.vertices),0)
                self.assertEqual(len(m.vertices)%18,0)
                for values in (m.vertices,struct.unpack('<'+str(len(m.vertices))+'f',_f32(m.vertices))):
                    self.assertTrue(all(math.isfinite(v) for v in values))
                    for n in range(0,len(values),18):
                        a,b,c=(values[n+k:n+k+3] for k in (0,6,12))
                        u=tuple(b[k]-a[k] for k in range(3));v=tuple(c[k]-a[k] for k in range(3))
                        face=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                        self.assertGreater(sum(x*x for x in face),0.)
                        for k in (0,6,12):
                            normal=values[n+k+3:n+k+6]
                            self.assertAlmostEqual(sum(x*x for x in normal),1.,places=5)
                            self.assertGreater(sum(x*y for x,y in zip(normal,face)),0.)
                if m.name=='detail-gpu-window-face':
                    values=struct.unpack('<'+str(len(m.vertices))+'f',_f32(m.vertices));edges=Counter();winding=Counter()
                    for n in range(0,len(values),18):
                        points=[tuple(values[n+k:n+k+3]) for k in (0,6,12)]
                        for a,b in zip(points,(*points[1:],points[0])):
                            key=tuple(sorted((a,b)));edges[key]+=1;winding[key]+=1 if a<b else -1
                    self.assertTrue(edges);self.assertTrue(all(n==2 for n in edges.values()));self.assertTrue(all(n==0 for n in winding.values()))
                    self.assertEqual(m.color[3],.12)
            self.assertFalse(any(m.rotor for m in new if m.name in NEW_NAMES))

    def test_fixed_rim_hub_rotor_sentinel_ports_power_and_unknown_inputs_preserved(self):
        (old,_),(new,meta),original,spec=self.pair(marker=True)
        protected=lambda m:m.name.startswith(('gpu-fan-','gpu-reference-port','gpu-power-inlet')) or m.name=='gpu-bracket'
        a=tuple(m for m in old if protected(m));b=tuple(m for m in new if protected(m))
        self.assertEqual(tuple(map(_physical,a)),tuple(map(_physical,b)))
        self.assertEqual(tuple(_f32(m.vertices) for m in a),tuple(_f32(m.vertices) for m in b))
        self.assertTrue(any(m.rotor for m in b))
        self.assertEqual(sum(m.name=='gpu-fan-rotor' for m in b),1)
        self.assertEqual(sum(m.name=='gpu-fan-opening' for m in b),1)
        self.assertEqual(sum(m.name.startswith('gpu-power-inlet') for m in b),2)
        self.assertTrue(any(m.name.startswith('gpu-reference-port') for m in b))
        self.assertIsNone(spec['gpu']['appearance']['board_details']['dimensions_mm']['thickness'])
        self.assertIsNone(spec['gpu']['fans'][0]['profile']['blades'])
        self.assertIsNone(spec['gpu']['fans'][0]['blades']);self.assertFalse(meta['blade_counts_changed'])
        self.assertTrue(meta['fixed_rim_geometry_preserved'])
        (_, _),(unknown, _),_,_=self.pair(marker=False)
        self.assertFalse(any(m.name=='gpu-fan-rotor' for m in unknown))

    def test_six_actual_style_arrays_and_eight_positive_area_head_contacts(self):
        from assembly_style import apply_colors
        (_, _),(new,_),_,spec=self.pair()
        for style in STYLES:
            values=apply_colors(new,style)
            self.assertEqual(len(values),len(new))
            for a,b in zip(new,values):
                self.assertIs(a.vertices,b.vertices)
                self.assertEqual((a.position,a.axis,a.rotor,a.part_id),(b.position,b.axis,b.rotor,b.part_id))
            self.assertFalse(any('expression' in m.name for m in values))
        shell=next(m for m in new if m.name=='gpu-shroud');gx,gy,gz=shell.position
        opening=next(m for m in new if m.name=='gpu-fan-opening')
        hole=((opening.position[2]-gz,-(opening.position[0]-gx),max(abs(v) for v in opening.vertices[0::6])*1.005),)
        ref=self.helper.kepler_front_reference(spec['gpu'],266.7,111.1504,55.,hole,6)
        heads=tuple(m for m in new if m.name=='detail-gpu-window-screw-heads')
        paint=tuple(m for m in new if m.name=='gpu-cover-panel')
        plane=gy-55./2+ref['head_back_y']
        self.assertEqual(len(ref['head_centers']),8)
        self.assertEqual(len(set(ref['head_centers'])),8)
        for u,v in ref['head_centers']:
            # Three noncollinear points on a real annular head-back cap and
            # the opposing retained structural front cap: positive area.
            witnesses=((.9,.9),(1.3,.9),(.9,1.3))
            self.assertGreater(abs((witnesses[1][0]-witnesses[0][0])*(witnesses[2][1]-witnesses[0][1])-
                                   (witnesses[1][1]-witnesses[0][1])*(witnesses[2][0]-witnesses[0][0])),0.)
            for du,dv in witnesses:
                x,z=gx-v-dv,gz+u+du
                body=_plane_hits((shell,),x,z);cap=_plane_hits(heads,x,z,front=False)
                self.assertTrue(body);self.assertTrue(cap)
                self.assertAlmostEqual(body[0][0],plane,places=9);self.assertAlmostEqual(cap[-1][0],plane,places=9)
                self.assertFalse(_plane_hits(paint,x,z))

if __name__=='__main__':unittest.main()
