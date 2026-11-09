"""Exact NZXT/Lancool lower material, source truth and actual fan surfaces."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,box,color
from assembly_shroud_nzxt_lianli052 import CASE_IDS,H5,H7,LANCOOL,build,finish,layout_reference
from assembly_visibility048 import mesh_visible,psu_cover_mesh_ids
from chassis_catalog import CASES,get_case

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def dims(case):return tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def world(mesh):
    return tuple(tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3))for j in (0,6,12))
                 for i in range(0,len(mesh.vertices),18))
def bounds(tri):return tuple(tuple(f(p[k]for p in tri)for k in range(3))for f in (min,max))


def inside(point,triangles,direction=(1.,.173,.317)):
    hits=[]
    for a,b,c in triangles:
        e1,e2=sub(b,a),sub(c,a);h=cross(direction,e2);det=dot(e1,h)
        if abs(det)<1e-10:continue
        inv=1./det;s=sub(point,a);u=inv*dot(s,h)
        if not -1e-10<=u<=1.+1e-10:continue
        q=cross(s,e1);v=inv*dot(direction,q)
        if v < -1e-10 or u+v > 1.+1e-10:continue
        t=inv*dot(e2,q)
        if t>1e-8:hits.append(t)
    unique=[]
    for hit in sorted(hits):
        if not unique or abs(hit-unique[-1])>1e-7:unique.append(hit)
    return len(unique)%2==1


def surface_crossing(a,b):
    """Static triangle SAT, including coplanar in-plane separation."""
    aa,bb=bounds(a),bounds(b)
    if any(aa[1][k]<bb[0][k]-1e-8 or bb[1][k]<aa[0][k]-1e-8 for k in range(3)):return False
    ea=tuple(sub(a[(i+1)%3],a[i])for i in range(3));eb=tuple(sub(b[(i+1)%3],b[i])for i in range(3))
    na,nb=cross(ea[0],ea[1]),cross(eb[0],eb[1])
    axes=(na,nb,*(cross(x,y)for x in ea for y in eb),*(cross(na,x)for x in ea),*(cross(nb,x)for x in eb))
    for axis in axes:
        length=math.sqrt(dot(axis,axis))
        if length<1e-10:continue
        pa=[dot(p,axis)/length for p in a];pb=[dot(p,axis)/length for p in b]
        if max(pa)<min(pb)-1e-8 or max(pb)<min(pa)-1e-8:return False
    return True


class NZXTLianliShroud052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('No native/GL/network/workers')))

    def test_exact_three_models_no_mutation_no_made_up_manufacturing_or_installed_fans(self):
        for key in CASE_IDS:
            case=get_case(key);before=copy.deepcopy(case);meshes,meta=build(case,dims(case),color('#25313e'))
            self.assertEqual(case,before);self.assertTrue(meshes)
            self.assertFalse(meta['cad_verified']);self.assertFalse(meta['dimensions_verified'])
            self.assertFalse(meta['positions_verified']);self.assertFalse(meta['thickness_verified'])
            self.assertFalse(meta['exact_vent_pattern_modeled']);self.assertFalse(meta['chamber_is_solid'])
            self.assertFalse(meta['selected_component_geometry_used']);self.assertLessEqual(meta['triangle_count'],4500)
            self.assertLessEqual(len(meshes),8);self.assertTrue(all(m.component=='case' and not m.rotor for m in meshes))
            self.assertEqual({m.part_id for m in meshes},{row['id']for row in meta['parts']})
            self.assertTrue(all(row['source_url'].startswith('https://')for row in meta['parts']))
        for case in CASES:
            if case['id']not in CASE_IDS:self.assertEqual(build(case,dims(case),(0,0,0,1)),((),{}))
        for invalid in ((1,2),('244',544,468),(244,float('nan'),468),(True,544,468)):
            self.assertEqual(build(get_case(H7),invalid,(0,0,0,1)),((),{}))

    def test_h5_round_perforation_front_recess_and_actual_empty_bay(self):
        case=get_case(H5);w,h,d=dims(case);meshes,meta=build(case,dims(case),color('#25313e'))
        roof,side=meshes;roof_triangles=world(roof);side_triangles=world(side)
        # Exact sampled vent really passes through both skins, not a dark disk.
        z=-(d-12.)/2+d*.17;point=(-w*.255,meta['roof_world_y_mm']-.6,z)
        self.assertFalse(inside(point,roof_triangles,(0,1,0)))
        self.assertTrue(inside((0.,meta['roof_world_y_mm']-.6,-(d-12.)/2+3.),roof_triangles,(0,1,0)))
        z0,z1=meta['front_recess_world_mm']['z']
        self.assertFalse(inside((0.,meta['roof_world_y_mm']-.6,(z0+z1)/2),roof_triangles,(0,1,0)))
        self.assertFalse(any(inside((0.,-h*.405,0.),world(m))for m in meshes))
        self.assertTrue(inside((-(w-12.)/2+.6,-h*.49+2.,0.),side_triangles))
        self.assertFalse(meta['old_diagonal_gpu_intake_added'])

    def test_h7_only_lower_back_partition_open_floor_and_explicit_host_contract(self):
        case=get_case(H7);w,h,d=dims(case);meshes,meta=build(case,dims(case),color('#25313e'))
        self.assertFalse(meta['horizontal_psu_cover_present']);self.assertTrue(meta['main_lower_bay_open'])
        self.assertTrue(meta['replaces_case_bottom'])
        self.assertTrue(meta['psu_layout_requires_exact_host_pose'])
        basis=meta['psu_basis_reference'];self.assertEqual(basis,((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)))
        self.assertEqual(tuple(-basis[1][k]for k in range(3)),(1.,0.,0.))
        x=meta['bottom_fan_center_world_x_reference_mm'];floor=meshes[1]
        self.assertLess(x,0.);self.assertFalse(inside((x,meta['floor_world_y_mm'],0.),world(floor),(0,1,0)))
        self.assertFalse(any(inside((x,-h*.36,0.),world(m))for m in meshes))
        # No wall at board/CPU height, and no fake full-height dual chamber.
        self.assertLess(max(meshes[0].vertices[1::6]),-h*.18)
        self.assertFalse(meta['psu_positions_verified']);self.assertFalse(meta['bottom_fan_positions_verified'])
        self.assertEqual(floor.name,'case-bottom-intake-frame')

    def test_h7_fixed_fold_separates_upright_150mm_psu_and_305mm_board_reference(self):
        # These are explicit test component envelopes, never a claim that all
        # selected supplies or boards fit. The helper has no component input.
        case=get_case(H7);_,h,_=dims(case);meshes,meta=build(case,dims(case),color('#25313e'))
        top=meta['lower_partition_top_world_y_mm'];under=top-meta['thickness_mm']
        nominal_psu_top=-h/2+12.+150.
        nominal_board_bottom=h*.10-305./2
        self.assertGreater(under-nominal_psu_top,5.)
        self.assertGreater(nominal_board_bottom-top,5.)
        self.assertEqual(top,-h*.19);self.assertFalse(meta['positions_verified'])

    def test_h7_host_reference_matches_fixed_material_and_psu_rigid_dimensions(self):
        case=get_case(H7);size=dims(case);before=copy.deepcopy(case);layout=layout_reference(case,size)
        meshes,meta=build(case,size,color('#25313e'));self.assertEqual(case,before)
        self.assertEqual(layout_reference({'id':'nzxt-h7-flow'},size),{})
        self.assertEqual(layout_reference({'id':'unknown'},size),{})
        self.assertFalse(layout['verified']);self.assertFalse(layout['positions_verified'])
        self.assertTrue(layout['reference_only']);self.assertAlmostEqual(layout['board_y_mm'],54.4)
        self.assertEqual(layout['lower_partition_top_y_mm'],meta['lower_partition_top_world_y_mm'])
        self.assertEqual(layout['floor_frame_y_mm'],meta['floor_world_y_mm'])
        plane=layout['mount_planes']['bottom'];self.assertEqual(plane['normal'],(0.,-1.,0.))
        self.assertEqual(plane['up'],(0.,0.,-1.));self.assertTrue(plane['halfturn_for_main_chamber_lead'])
        self.assertTrue(plane['installation_orientation_reference']);self.assertFalse(plane['positions_verified'])
        self.assertEqual(plane['position'][0],meta['bottom_fan_center_world_x_reference_mm'])
        self.assertAlmostEqual(plane['position'][1]-max(meshes[1].vertices[1::6]),1.)
        self.assertEqual(plane['span_mm'],(128.,436.));self.assertFalse(plane['drawing_gap_verified'])
        psu=layout['psu'];world_width,world_height,world_depth=86.,150.,160.
        center=(psu['boundary_x_mm']-world_width/2,psu['floor_y_mm']+world_height/2,
                psu['rear_z_mm']+world_depth/2)
        self.assertEqual(center,(70.,-185.,-144.));self.assertEqual(psu['basis'],meta['psu_basis_reference'])

    def test_h5_and_lancool_different_manual_psu_orientation_floor_and_roof(self):
        for key,fan_normal,raise_mm in ((H5,(0.,1.,0.),20.),(LANCOOL,(0.,-1.,0.),21.)):
            case=get_case(key);w,h,d=dims(case);layout=layout_reference(case,(w,h,d));meshes,meta=build(case,(w,h,d),color('#25313e'))
            self.assertFalse(layout['positions_verified']);self.assertTrue(layout['reference_only'])
            self.assertEqual(layout['board_y_mm'],h*.10);self.assertFalse(layout['board_positions_verified'])
            self.assertEqual(layout['roof_world_y_mm'],meta['roof_world_y_mm'])
            self.assertGreater(layout['board_y_mm']-305./2-meta['roof_world_y_mm'],10.)
            psu=layout['psu'];self.assertEqual(psu['center_x_mm'],0.)
            self.assertEqual(psu['floor_y_mm'],-h/2+raise_mm)
            self.assertEqual(tuple(-psu['basis'][1][i]for i in range(3)),fan_normal)
            self.assertGreater(meta['roof_world_y_mm']-1.2-(psu['floor_y_mm']+86.),1.)
            self.assertEqual(psu['basis'][2],(0.,0.,1.)) # IEC/rear and modular/front not exchanged.
            if key==H5:
                plane=layout['mount_planes']['bottom']
                self.assertEqual(plane['source_capacity_count'],2);self.assertEqual(plane['source_capacity_size_mm'],120)
                self.assertEqual(plane['position'][1]-meta['roof_world_y_mm'],1.)
                self.assertEqual(plane['normal'],(0.,-1.,0.));self.assertFalse(plane['drawing_gap_verified'])
            else:self.assertEqual(tuple(layout['mount_planes']),('above_psu_shroud',))

    def test_lancool_above_shroud_fixed_fan_only_frame_not_a_radiator_or_motion_claim(self):
        case=get_case(LANCOOL);w,h,d=dims(case)
        layout=layout_reference(case,(w,h,d));plane=layout['mount_planes']['above_psu_shroud']
        self.assertAlmostEqual(plane['position'][0],-22.68)
        self.assertAlmostEqual(plane['position'][1],-150.67)
        self.assertEqual(plane['position'][2],0.)
        self.assertEqual(plane['position'][1]-layout['roof_world_y_mm'],1.)
        self.assertEqual(plane['normal'],(0.,-1.,0.));self.assertEqual(plane['up'],(0.,0.,1.))
        self.assertEqual(plane['source_capacity_count'],3);self.assertEqual(plane['source_capacity_size_mm'],120)
        self.assertEqual(plane['source_manual_pdf_page'],9)
        self.assertIn('1kd9ku_raF2uXWeLD7voGfT4ZZ10XOizy',plane['source'])
        self.assertEqual(plane['supported_part_kinds'],('case_fan',))
        self.assertFalse(plane['radiator_runtime_supported']);self.assertEqual(plane['source_radiator_capacity_mm'],360)
        self.assertFalse(plane['motion_supported']);self.assertFalse(plane['mechanical_removal_direction_verified'])
        self.assertTrue(plane['reference_only'])
        for field in ('verified','dimensions_verified','positions_verified','drawing_gap_verified'):
            self.assertFalse(plane[field])
        left,right=-(w-12.)/2.,(w-12.)/2.
        for actual,expected in zip(plane['span_mm'],(right-w*.22-(left+7.),d*.78-12.)):
            self.assertAlmostEqual(actual,expected)
        # The documented capacity is not an installed group or a selected-part
        # adaptive plane.  Those inputs are deliberately outside this API.
        alternate=dict(case,gpu_model='unrelated',fan_model='arctic-p14-pwm',fan_count=1)
        self.assertEqual(layout_reference(alternate,(w,h,d)),layout)
        before=copy.deepcopy(plane)
        layout['mount_planes']['above_psu_shroud']['position']=(0.,0.,0.)
        self.assertEqual(layout_reference(case,(w,h,d))['mount_planes']['above_psu_shroud'],before)
        self.assertNotIn('above_psu_shroud',layout_reference(get_case(H5),dims(get_case(H5)))['mount_planes'])
        self.assertNotIn('above_psu_shroud',layout_reference(get_case(H7),dims(get_case(H7)))['mount_planes'])
        self.assertEqual(layout_reference(dict(case,id='lian-li-lancool-207'),(w,h,d)),{})

    def test_lancool_manual_separate_plates_and_two_hinged_mesh_doors(self):
        case=get_case(LANCOOL);meshes,meta=build(case,dims(case),color('#25313e'))
        self.assertEqual(meta['lower_mesh_doors_observed'],2);self.assertEqual(meta['installed_mounting_plates'],3)
        self.assertEqual(meta['source_front_bracket_modes'],4)
        self.assertEqual(len(meta['deferred_part_ids']),3)
        self.assertEqual(len({m.part_id for m in meshes}),6)
        self.assertFalse(any(inside((0.,-dims(case)[1]*.405,0.),world(m))for m in meshes))
        bracket=meshes[0];self.assertFalse(inside((-40.,meta['roof_world_y_mm']-.6,-150.),world(bracket),(0,1,0)))
        self.assertEqual(sum(row.get('hinged_observed')is True for row in meta['parts']),2)

    def test_finish_requires_actual_upper_cooling_and_only_removes_documented_plates(self):
        case=get_case(LANCOOL);meshes,meta=build(case,dims(case),color('#25313e'));before=copy.deepcopy(meta)
        fake=Mesh('case-fan-frame',box(120,25,120),(0,0,0,1),component='fans',part_id='fans:above_psu_shroud:0')
        row=dict(id=fake.part_id,kind='case_fan',mount='above_psu_shroud',model_id='arctic-p12-pwm')
        for rows,actual in (([],(fake,)),([row],()),([dict(row,mount='front')],(fake,))):
            output,state=finish(meshes,actual,dict(parts=rows),meta)
            self.assertEqual(output,meshes);self.assertEqual(state['removed_parts'],[])
        output,state=finish((*meshes,fake),(fake,),dict(parts=[row]),meta)
        self.assertEqual(meta,before);self.assertEqual(state['installed_mounting_plates'],0)
        self.assertEqual(len(state['removed_parts']),3);self.assertIn(fake,output)
        self.assertEqual({m.part_id for m in output if m is not fake},
                         {'case:psu-top-bracket','case:psu-side-door:left','case:psu-side-door:right'})
        self.assertTrue(all(row['physical_mesh_present']is False for row in state['removed_parts']))
        result,_=finish(meshes,(fake,),dict(parts=[row]),dict(meta,case_id=H5));self.assertIs(result,meshes)

    def test_normals_winding_positive_closed_material_and_empty_reference_points(self):
        for key in CASE_IDS:
            case=get_case(key);meshes,meta=build(case,dims(case),color('#25313e'))
            for mesh in meshes:
                volume=0.
                for index,(a,b,c)in enumerate(world(mesh)):
                    n=cross(sub(b,a),sub(c,a));stored=mesh.vertices[index*18+3:index*18+6]
                    self.assertTrue(all(math.isfinite(value)for value in (*a,*b,*c,*stored)))
                    self.assertGreater(dot(n,n),1e-14);self.assertGreater(dot(n,stored),0.)
                    self.assertAlmostEqual(dot(stored,stored),1.,places=7)
                    volume+=dot(a,cross(b,c))/6.
                self.assertGreater(volume,0.,(key,mesh.part_id))
                # Ray parity must agree in three non-coplanar directions for
                # a real material point; open shells fail this independent check.
                a,b,c=world(mesh)[0];center=tuple((a[k]+b[k]+c[k])/3 for k in range(3))
                n=mesh.vertices[3:6];probe=tuple(center[k]-n[k]*.05 for k in range(3))
                for direction in ((1.,.173,.317),(.219,1.,.127),(.133,.287,1.)):
                    self.assertTrue(inside(probe,world(mesh),direction),(key,mesh.part_id,probe,direction))

    def test_actual_front_fan_material_all_declared_sizes_three_lods_no_solid_intersection(self):
        from assembly_cooling import add_cooling
        rows=0;old_positive=0
        for key in CASE_IDS:
            case=get_case(key);size3=dims(case);w,h,d=size3;covers,_=build(case,size3,color('#25313e'))
            cover_triangles=[(t,bounds(t))for m in covers for t in world(m)]
            for size,model,depth in ((120,'arctic-p12-pwm',25.),(140,'arctic-p14-pwm',27.)):
                declarations=[row for row in case['fan_mounts']if row['position']=='front'and size in row['size_mm']]
                if not declarations:continue
                count=min(3,max(row['count']for row in declarations));spec=dict(case=case,cooling=dict(cpu_cooler='none',
                    case_fans=[dict(model=model,mount='front',count=count,direction='intake')]))
                for level in ('eco','balanced','close'):
                    fans,meta=add_cooling(covers,spec,level,dict(case=case,case_dimensions=size3))
                    self.assertEqual(meta['rejected'],[],(key,size,level))
                    frames=[m for m in fans if m.name=='case-fan-frame'];self.assertEqual(len(frames),count)
                    for frame in frames:
                        for triangle in world(frame):
                            bb=bounds(triangle)
                            candidates=[t for t,tb in cover_triangles if all(bb[1][k]>=tb[0][k]-1e-8 and tb[1][k]>=bb[0][k]-1e-8 for k in range(3))]
                            self.assertFalse(any(surface_crossing(triangle,t)for t in candidates),(key,size,level,frame.part_id))
                    if level=='eco':
                        point=(45.,-count*size/2+2.,d/2-depth/2-10.)
                        old=Mesh('old-solid',box(w-12,h*.17,d-12),color('#25313e'),(0.,-h*.405,0.))
                        if inside(point,world(old))and any(inside(point,world(frame))for frame in frames):old_positive+=1
                    rows+=1
        self.assertEqual(rows,18);self.assertGreaterEqual(old_positive,4)

    def test_all_six_styles_same_vertices_and_pose_show_psu_and_pick_gate_shared(self):
        from assembly_style import apply_model_styles
        for key in CASE_IDS:
            case=get_case(key);meshes,_=build(case,dims(case),color('#25313e'))
            original=tuple((m.vertices,m.position,m.part_id,m.axis,m.rotor)for m in meshes)
            covers=psu_cover_mesh_ids(meshes)
            self.assertEqual(covers,frozenset(id(m)for m in meshes if m.name=='psu-shroud'))
            for mesh in meshes:
                self.assertTrue(mesh_visible(mesh,True,False))
                self.assertEqual(mesh_visible(mesh,True,True),mesh.name!='psu-shroud')
            for style in SIX:
                styled,_=apply_model_styles(meshes,style,{},dims(case),case['panels'])
                physical=[m for m in styled if not m.name.startswith('style-')]
                self.assertEqual(tuple((m.vertices,m.position,m.part_id,m.axis,m.rotor)for m in physical),original)
                self.assertTrue(all(a.vertices is b.vertices for a,b in zip(physical,meshes)))


if __name__=='__main__':unittest.main()
