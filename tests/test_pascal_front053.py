"""Production pure controls for an exact source-observed Pascal FE front.

Source contours are list-valid fixed reference data. The known53 metadata feeds
an existing reference fan_rotor fixture; these tests do not freshly read QML or
verify a manufactured blade shape. The separate actual-profile/Scene bridge
and software images remain distinct evidence. No historical/private loader.
"""
import copy
import math
import struct
import unittest
from collections import Counter

LEVELS=('eco','balanced','close')
STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
ADDED=('detail-gpu-pascal-fin-samples','detail-gpu-pascal-clear-reference',
       'detail-gpu-pascal-fixed-heads','detail-gpu-pascal-head-recesses')
NEUTRAL='test-unrelated-pascal-control'

APPEARANCE={'id': 'nvidia-gtx1080-founders',
 'kind': 'gpu',
 'vendor': 'nvidia',
 'board_vendor': 'nvidia',
 'label': 'NVIDIA GeForce GTX 1080 Founders Edition',
 'style': 'gpu_blower',
 'fan_count': 1,
 'shroud': 'angular',
 'source_url': 'https://www.nvidia.com/en-us/geforce/news/geforce-gtx-1080-founders-edition/',
 'confidence': 'model',
 'accent': '#6e993d',
 'series_id': 'nvidia_founders_pascal',
 'series_label': 'NVIDIA Founders · Pascal',
 'features': ['多边形切面', '一体式框架'],
 'visible_fan_count': 1,
 'legacy': True,
 'era': 'gtx10',
 'tier': 'reference',
 'fan_profile': {'label': '公版径流叶轮',
                 'technology': 'reference_radial',
                 'blades': 53,
                 'blade_pattern': None,
                 'hub_tone': None,
                 'source_url': 'https://www.nvidia.com/en-us/geforce/news/geforce-gtx-1080-founders-edition/',
                 'blade_counts': [],
                 'render_ready': True,
                 'artwork_status': 'reviewed',
                 'verified': True},
 'board_details': {'kind': 'gpu',
                   'series_id': 'nvidia_founders_pascal',
                   'model_ids': ['nvidia-gtx1080-founders'],
                   'shroud_tone': 'mixed',
                   'illustration_status': 'simplified',
                   'pcb_tone': 'unknown',
                   'recipe': '',
                   'backplate_recipe': '',
                   'accessory_backplate_recipe': '',
                   'ports': [{'type': 'displayport', 'count': 3},
                             {'type': 'hdmi', 'count': 1},
                             {'type': 'dvi', 'count': 1}],
                   'power_connectors': [{'type': '8pin', 'count': 1}],
                   'slot_width': 2,
                   'backplate': True,
                   'pcb_length': 'unknown',
                   'dimensions_mm': {'length': None, 'height': None, 'thickness': None},
                   'host_interface': {'bus': 'pcie', 'generation': 3, 'lanes': None},
                   'edge_key_count': None,
                   'power_position': 'top',
                   'alternative_power': False,
                   'source_urls': ['https://www.nvidia.com/content/geforce-gtx/GEFORCE_GTX_1080_USER_GUIDE_v02.pdf',
                                   'https://www.nvidia.com/en-us/geforce/news/geforce-gtx-1080-founders-edition/'],
                   'ports_text': 'DP × 3 · HDMI × 1 · DVI × 1',
                   'power_text': '8 pin × 1',
                   'pcb_text': 'PCB 内部布局未核实',
                   'host_text': 'PCIe 3'}}

REFERENCE_PROFILE={'fans': [{'cx': 18.05,
           'cy': 11.741,
           'radius': 3.367,
           'kind': 'blower',
           'profile': {'blades': 53,
                       'group_size': 1,
                       'hub_ratio': 0.53,
                       'outer_ring': False,
                       'shape': 'radial',
                       'technology': 'reference_radial',
                       'tone': 'dark',
                       'direction': 1,
                       'hub_shape': 'circle',
                       'blade_pattern': 'uniform',
                       'hub_mark': '',
                       'paintKey': 'nvidia_founders_pascal_0',
                       'kind': 'blower'},
           'known': True,
           'direction': 1,
           'hub_ratio': 0.53,
           'outer_ring': False,
           'group_size': 1,
           'colors': {'rim': '#48535b',
                      'disk': '#1f262c',
                      'blade': '#45515a',
                      'hub': '#343d44',
                      'edge': '#63727d',
                      'ridge': '#809099',
                      'shade': '#2b343c',
                      'light': '#5b6974'}}]}

REFERENCE_MAP={'shell_polygon': [[0.0, 0.1875],
                   [0.06, 0.0],
                   [0.92, 0.0],
                   [1.0, 0.177083],
                   [1.0, 0.822917],
                   [0.92, 1.0],
                   [0.06, 1.0],
                   [0.0, 0.8125]],
 'face_box': [1.75, 7.282, 20.8, 8.736],
 'rows': [{'points': [[0.14, 0.21875],
                      [0.49, 0.135417],
                      [0.6, 0.3125],
                      [0.6, 0.739583],
                      [0.47, 0.864583],
                      [0.15, 0.864583]],
           'color': '#26323d'},
          {'points': [[0.49, 0.135417], [0.35, 0.0], [0.6, 0.0], [0.68, 0.114583], [0.6, 0.3125]],
           'color': '#d4dee5'},
          {'points': [[0.6, 0.0], [0.92, 0.0], [1.0, 0.177083], [0.9, 0.135417], [0.81, 0.25], [0.68, 0.114583]],
           'color': '#435562'},
          {'points': [[0.06, 1.0], [0.14, 0.78125], [0.47, 0.864583], [0.6, 1.0]], 'color': '#ebf1f5'},
          {'points': [[0.18, 0.260417],
                      [0.51, 0.260417],
                      [0.5175, 0.263021],
                      [0.518594, 0.264486],
                      [0.519375, 0.266276],
                      [0.52, 0.270833],
                      [0.52, 0.71875],
                      [0.519375, 0.723307],
                      [0.518594, 0.725098],
                      [0.5175, 0.726562],
                      [0.51, 0.729167],
                      [0.18, 0.729167],
                      [0.1725, 0.726562],
                      [0.171406, 0.725098],
                      [0.170625, 0.723307],
                      [0.17, 0.71875],
                      [0.17, 0.270833],
                      [0.170625, 0.266276],
                      [0.171406, 0.264486],
                      [0.1725, 0.263021]],
           'color': '#435562'},
          {'points': [[0.1825, 0.267708],
                      [0.1929, 0.267708],
                      [0.194775, 0.268359],
                      [0.1954, 0.270312],
                      [0.1954, 0.719271],
                      [0.1929, 0.721875],
                      [0.1825, 0.721875],
                      [0.180625, 0.721224],
                      [0.18, 0.719271],
                      [0.18, 0.270312]],
           'color': '#bbc9d3'}]}

REFERENCE_PHOTO={'window_heads': [{'photo_head_px': [518.0, 231.0], 'head_uv': [0.2258852258852259, 0.1397727903958016]},
                  {'photo_head_px': [919.0, 251.0], 'head_uv': [0.4706959706959707, 0.07479578776420266]},
                  {'photo_head_px': [518.0, 634.0], 'head_uv': [0.2258852258852259, 0.9298003913043478]},
                  {'photo_head_px': [919.0, 614.0], 'head_uv': [0.4706959706959707, 0.9157532622906636]}],
 'fan_heads': [{'photo_head_px': [1101.0, 241.0], 'head_uv': [0.6414072039072038, 0.1826574693422519]},
               {'photo_head_px': [1573.0, 242.0], 'head_uv': [0.9295634920634921, 0.1843297101449275]},
               {'photo_head_px': [1101.0, 631.0], 'head_uv': [0.6414072039072038, 0.8348313823857302]},
               {'photo_head_px': [1573.0, 631.0], 'head_uv': [0.9295634920634921, 0.8348313823857302]}]}

def _f32(values):return struct.pack('<'+str(len(values))+'f',*values)

def _physical(m):return (m.name,m.vertices,m.color,m.position,m.component,m.rotor,m.direction,m.axis,m.part_id)

def _bounds(meshes):
    return tuple((min(m.vertices[n]+m.position[k] for m in meshes for n in range(k,len(m.vertices),6)),
                  max(m.vertices[n]+m.position[k] for m in meshes for n in range(k,len(m.vertices),6))) for k in range(3))

def _hits(meshes,x,z,front=True):
    rows=[]
    for m in meshes:
        for n in range(0,len(m.vertices),18):
            if not all(m.vertices[n+k+4]<-.999 if front else m.vertices[n+k+4]>.999 for k in (0,6,12)):continue
            p=[(m.vertices[n+k]+m.position[0],m.vertices[n+k+2]+m.position[2]) for k in (0,6,12)]
            area=(p[1][0]-p[0][0])*(p[2][1]-p[0][1])-(p[1][1]-p[0][1])*(p[2][0]-p[0][0])
            if abs(area)<1e-14:continue
            signs=[(p[(i+1)%3][0]-p[i][0])*(z-p[i][1])-(p[(i+1)%3][1]-p[i][1])*(x-p[i][0]) for i in range(3)]
            if min(signs)>=-1e-9 or max(signs)<=1e-9:rows.append((m.vertices[n+1]+m.position[1],m))
    return sorted(rows,key=lambda r:r[0])

def _fixture(appearance,profile,layer_map):
    from assembly_geometry import Mesh,box,color,extrude,fan_rotor,gpu_plane,ring,unit_polygon
    # Existing unknown-dimension reference envelope, not GTX1080 measured mm.
    length,width,thickness=310.,135.,55.;center=(12.,-40.,15.);gx,gy,gz=center
    gpu=dict(appearance=copy.deepcopy(appearance),shell_polygon=copy.deepcopy(layer_map['shell_polygon']),
        detail_polygons=[dict(points=copy.deepcopy(row['points']),color=row['color']) for row in layer_map['rows']],
        fans=[dict(blades=53,profile=copy.deepcopy(profile['fans'][0]['profile']),face='front')])
    assert gpu['appearance']['board_details']['dimensions_mm']==dict(length=None,height=None,thickness=None)
    assert all(isinstance(row['points'],list) and unit_polygon(row['points'],length,width,margin=.3) for row in gpu['detail_polygons'])
    shell=unit_polygon(gpu['shell_polygon'],length,width);assert shell
    meshes=[Mesh('gpu-shroud',gpu_plane(extrude(shell,thickness)),color('#536779'),center,'gpu',part_id='gpu:0')]
    for row in gpu['detail_polygons']:
        points=unit_polygon(row['points'],length,width,margin=.3)
        meshes.append(Mesh('gpu-cover-panel',gpu_plane(extrude(points,.3)),color(row['color']),center,'gpu',part_id='gpu:0'))
    f=profile['fans'][0];x,y,w,h=layer_map['face_box']
    u,v=(f['cx']-x)/w,(f['cy']-y)/h
    radius=min(f['radius']/w*length,f['radius']/h*width)
    p=(gx+(v-.5)*width,gy-thickness/2-1.5,gz+(u-.5)*length)
    fan_profile=copy.deepcopy(f['profile']);assert fan_profile['blades']==53
    rotor=fan_rotor(fan_profile,radius);assert rotor
    meshes.extend((Mesh('gpu-fan-opening',gpu_plane(ring(radius,radius*.92,2.)),color(f['colors']['rim']),p,'gpu',part_id='gpu:0'),
        Mesh('gpu-fan-recess',gpu_plane(ring(radius*.91,0.,.5)),color(f['colors']['disk']),(p[0],p[1]+1,p[2]),'gpu',part_id='gpu:0'),
        Mesh('gpu-fan-hub',gpu_plane(ring(radius*f['hub_ratio'],0.,2.7)),color(f['colors']['hub']),(p[0],p[1]-.8,p[2]),'gpu',part_id='gpu:0'),
        Mesh('gpu-fan-rotor',gpu_plane(rotor),color(f['colors']['blade']),p,'gpu',rotor=True,direction=f['direction'],axis=(0,1,0),part_id='gpu:0'),
        Mesh('gpu-power-inlet-0',box(8.,5.,10.),color('#29333b'),(gx,gy+10,gz+50),'gpu',part_id='gpu:0')))
    return tuple(meshes),dict(gpu=gpu)

class TestPascalFront053(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import assembly_detail
        import assembly_gpu_pascal053
        cls.detail=assembly_detail
        cls.helper=assembly_gpu_pascal053
        cls.appearance=APPEARANCE
        cls.profile=REFERENCE_PROFILE
        cls.map=REFERENCE_MAP
        cls.photo=REFERENCE_PHOTO

    def pair(self,level='balanced'):
        # Only the copied identity differs. Every source polygon, known fan
        # profile, envelope, fact and input Mesh is otherwise the same.
        meshes,spec=_fixture(self.appearance,self.profile,self.map)
        saved=copy.deepcopy(spec);baseline=copy.deepcopy(spec)
        baseline['gpu']['appearance']['id']=NEUTRAL
        prior=copy.deepcopy(baseline);input_proof=tuple(map(_physical,meshes))
        old=self.detail._gpu_detail(meshes,baseline,level)
        new=self.detail._gpu_detail(meshes,spec,level)
        self.assertEqual(spec,saved);self.assertEqual(baseline,prior)
        self.assertEqual(tuple(map(_physical,meshes)),input_proof)
        baseline['gpu']['appearance']['id']=saved['gpu']['appearance']['id']
        self.assertEqual(baseline,saved)
        return old,new,meshes,spec

    def reference(self,spec,meshes):
        shell=next(m for m in meshes if m.name=='gpu-shroud');gx,gy,gz=shell.position
        width,thickness,length=(b-a for a,b in _bounds((shell,)))
        opening=next(m for m in meshes if m.name=='gpu-fan-opening')
        holes=((opening.position[2]-gz,-(opening.position[0]-gx),max(abs(v) for v in opening.vertices[0::6])*1.005),)
        return self.helper.front_reference(spec['gpu'],length,width,thickness,holes),holes

    def test_exact_bound_actual_layers_list_types_unknown_dimensions_and_negative_inputs(self):
        meshes,spec=_fixture(self.appearance,self.profile,self.map);ref,holes=self.reference(spec,meshes);self.assertTrue(ref)
        self.assertEqual(ref['source_bound_layers'],(0,4,5));self.assertEqual(ref['replaced_source_layers'],(4,5))
        self.assertEqual(ref['preserved_source_frame_layers'],(1,2,3));self.assertEqual(len(ref['window_outline']),6)
        self.assertGreater(len({p[0] for p in ref['window_outline']}),2)
        for target in (0,4,5):
            bad=copy.deepcopy(spec['gpu']);bad['detail_polygons'][target]['points'][0][0]+=.000001
            self.assertEqual(self.helper.front_reference(bad,310.,135.,55.,holes),{})
        bad=copy.deepcopy(spec['gpu']);bad['detail_polygons'][0]['points']=tuple(bad['detail_polygons'][0]['points'])
        self.assertEqual(self.helper.front_reference(bad,310.,135.,55.,holes),{})
        for identity in (NEUTRAL,'nvidia-gtx1080ti-founders','nvidia-gtx1080-founders-unrelated'):
            bad=copy.deepcopy(spec['gpu']);bad['appearance']['id']=identity
            self.assertEqual(self.helper.front_reference(bad,310.,135.,55.,holes),{})
        for dimensions in ((float('nan'),135.,55.),(310.,0.,55.),(310.,135.,-1.)):
            self.assertEqual(self.helper.front_reference(spec['gpu'],*dimensions,holes),{})
        self.assertEqual(self.helper.front_reference(spec['gpu'],310.,135.,55.,()),{})
        huge=10**400
        for dimensions in ((huge,135.,55.),(310.,huge,55.),(310.,135.,huge)):
            self.assertEqual(self.helper.front_reference(spec['gpu'],*dimensions,holes),{})
        for malformed in (((huge,0.,1.),),((0.,-huge,1.),),((0.,0.,huge),)):
            self.assertEqual(self.helper.front_reference(spec['gpu'],310.,135.,55.,malformed),{})
        bad=copy.deepcopy(spec['gpu']);bad['detail_polygons'][0]['points'][0][0]=huge
        self.assertEqual(self.helper.front_reference(bad,310.,135.,55.,holes),{})
        self.assertIsNone(spec['gpu']['appearance']['board_details']['dimensions_mm']['thickness'])

    def test_real_window_positive_negative_rays_preserved_facet_materials_and_first_opaque_fin(self):
        (old,_),(new,_),inputs,spec=self.pair()
        shell=next(m for m in new if m.name=='gpu-shroud');gx,gy,gz=shell.position
        old_shell=tuple(m for m in old if m.name=='gpu-shroud')
        for u,v,open_expected in ((.18,.5,True),(.58,.5,True),(.59,.16,False),(.145,.15,False)):
            x,z=gx+(v-.5)*135.,gz+(u-.5)*310.
            self.assertTrue(_hits(old_shell,x,z));self.assertEqual(not bool(_hits((shell,),x,z)),open_expected)
        paint=tuple(m for m in new if m.name=='gpu-cover-panel');original_paint=tuple(m for m in inputs if m.name=='gpu-cover-panel')
        for index,u,v in ((1,.49,.03),(2,.8,.05),(3,.35,.97)):
            hits=_hits(paint,gx+(v-.5)*135.,gz+(u-.5)*310.)
            self.assertTrue(any(m.color==original_paint[index].color for y,m in hits),(index,u,v))
        fin=next(m for m in new if m.name=='detail-gpu-pascal-fin-samples')
        n=next(n for n in range(0,len(fin.vertices),18) if fin.vertices[n+4]<-.999)
        x=sum(fin.vertices[n+k] for k in (0,6,12))/3+fin.position[0];z=sum(fin.vertices[n+k+2] for k in (0,6,12))/3+fin.position[2]
        self.assertEqual(_hits(tuple(m for m in new if m.color[3]>=.999),x,z)[0][1].name,fin.name)
        self.assertNotEqual(_hits(old,x,z)[0][1].name,fin.name)

    def test_three_lod_dynamic_inventory_nonempty_f32_normals_closed_face_and_same_bounds(self):
        for level,count in zip(LEVELS,(16,32,48)):
            (old,_),(new,metadata),_,_=self.pair(level)
            self.assertEqual(_bounds(old),_bounds(new));self.assertEqual(metadata['fin_sampling_count'],count)
            additions=tuple(m for m in new if m.name in ADDED)
            self.assertEqual({m.name for m in additions},set(ADDED));self.assertEqual(len(additions),4)
            # Actual inventory is derived rather than assuming Kepler's seven.
            observed=tuple(m for m in new if m.name in (*ADDED,'gpu-shroud','gpu-cover-panel'))
            self.assertTrue(observed)
            for m in observed:
                self.assertGreater(len(m.vertices),0);self.assertEqual(len(m.vertices)%18,0)
                for values in (m.vertices,struct.unpack('<'+str(len(m.vertices))+'f',_f32(m.vertices))):
                    self.assertTrue(all(math.isfinite(v) for v in values))
                    for n in range(0,len(values),18):
                        a,b,c=(values[n+k:n+k+3] for k in (0,6,12))
                        u=tuple(b[k]-a[k] for k in range(3));v=tuple(c[k]-a[k] for k in range(3))
                        face=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                        self.assertGreater(sum(x*x for x in face),0.)
                        for k in (0,6,12):
                            normal=values[n+k+3:n+k+6];self.assertAlmostEqual(sum(x*x for x in normal),1.,places=5)
                            self.assertGreater(sum(x*y for x,y in zip(normal,face)),0.)
            pane=next(m for m in additions if m.name=='detail-gpu-pascal-clear-reference');self.assertEqual(pane.color[3],.12)
            values=struct.unpack('<'+str(len(pane.vertices))+'f',_f32(pane.vertices));incidence=Counter();winding=Counter()
            for n in range(0,len(values),18):
                points=[tuple(values[n+k:n+k+3]) for k in (0,6,12)]
                for a,b in zip(points,(*points[1:],points[0])):
                    edge=tuple(sorted((a,b)));incidence[edge]+=1;winding[edge]+=1 if a<b else -1
            self.assertTrue(incidence);self.assertTrue(all(v==2 for v in incidence.values()));self.assertTrue(all(v==0 for v in winding.values()))

    def test_existing_known53_input_rotor_rim_hub_ports_power_pose_and_spec_are_preserved(self):
        (old,_),(new,metadata),inputs,spec=self.pair()
        self.assertEqual(spec['gpu']['fans'][0]['blades'],53);self.assertEqual(spec['gpu']['fans'][0]['profile'],self.profile['fans'][0]['profile'])
        self.assertGreater(next(m for m in inputs if m.name=='gpu-fan-rotor').vertex_count,0)
        protected=lambda m:m.name.startswith(('gpu-fan-','gpu-reference-port','gpu-power-inlet')) or m.name=='gpu-bracket'
        a=tuple(m for m in old if protected(m));b=tuple(m for m in new if protected(m))
        self.assertEqual(tuple(map(_physical,a)),tuple(map(_physical,b)))
        self.assertEqual(tuple(_f32(m.vertices) for m in a),tuple(_f32(m.vertices) for m in b))
        self.assertEqual(sum(m.rotor for m in b),1);self.assertFalse(any(m.rotor for m in new if m.name in ADDED))
        self.assertFalse(metadata['blade_counts_changed']);self.assertEqual(metadata['source_existing_blade_count'],53);self.assertFalse(metadata['rotor_geometry_changed'])
        self.assertFalse(metadata['manufacturer_dimensions_verified']);self.assertFalse(metadata['full_tessellated_body_3D_modelled'])

    def test_eight_independent_photo_sites_positive_area_contacts_and_six_actual_shared_arrays(self):
        from assembly_style import apply_colors
        (_, _),(new,_),_,spec=self.pair();ref,_=self.reference(spec,new)
        expected=self.photo['window_heads']+self.photo['fan_heads'];self.assertEqual(len(expected),8)
        self.assertEqual(tuple(tuple(r['photo_head_px']) for r in expected),self.helper.HEAD_PHOTO_PIXELS)
        self.assertEqual(len(set(ref['head_centers'])),8)
        for center,row in zip(ref['head_centers'],expected):
            self.assertAlmostEqual(center[0],(row['head_uv'][0]-.5)*310.,places=10)
            self.assertAlmostEqual(center[1],(.5-row['head_uv'][1])*135.,places=10)
        shell=next(m for m in new if m.name=='gpu-shroud');gx,gy,gz=shell.position
        heads=tuple(m for m in new if m.name=='detail-gpu-pascal-fixed-heads');paint=tuple(m for m in new if m.name=='gpu-cover-panel')
        for u,v in ref['head_centers']:
            for du,dv in ((.9,.9),(1.3,.9),(.9,1.3)):
                x,z=gx-v-dv,gz+u+du;body=_hits((shell,),x,z);cap=_hits(heads,x,z,front=False)
                self.assertTrue(body);self.assertTrue(cap)
                self.assertAlmostEqual(body[0][0],cap[-1][0],places=9);self.assertFalse(_hits(paint,x,z))
        for style in STYLES:
            values=apply_colors(new,style);self.assertEqual(len(values),len(new))
            for a,b in zip(new,values):
                self.assertIs(a.vertices,b.vertices);self.assertEqual((a.position,a.axis,a.rotor,a.part_id),(b.position,b.axis,b.rotor,b.part_id))
            self.assertFalse(any(m.name.startswith(('style-','gpu-expression-','detail-gpu-expression-')) for m in values))

    def test_unrelated_ids_are_noop_and_neutral_consumer_retains_a_real_solid_cap(self):
        meshes,spec=_fixture(self.appearance,self.profile,self.map)
        original=tuple(map(_physical,meshes))
        for identity in (NEUTRAL,'nvidia-gtx780ti-reference','msi-n480gtx-m2d15','leadtek-hurricane-4090-24g'):
            other=copy.deepcopy(spec);other['gpu']['appearance']['id']=identity;saved=copy.deepcopy(other)
            for level in LEVELS:
                result,metadata=self.helper.refine(meshes,other,level)
                self.assertIs(result,meshes);self.assertEqual(metadata,{})
                self.assertEqual(tuple(map(_physical,result)),original);self.assertEqual(other,saved)
        other=copy.deepcopy(spec);other['gpu']['appearance']['id']=NEUTRAL
        for level in LEVELS:
            result,metadata=self.detail._gpu_detail(meshes,other,level)
            self.assertFalse(any(m.name in ADDED for m in result))
            shell=next(m for m in result if m.name=='gpu-shroud');gx,gy,gz=shell.position
            for u,v in ((.18,.5),(.58,.5)):
                self.assertTrue(_hits((shell,),gx+(v-.5)*135.,gz+(u-.5)*310.))
            self.assertNotIn('source_existing_blade_count',metadata)


if __name__=='__main__':unittest.main()
