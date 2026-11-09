"""Seven source bays: real material, unknown dimensions and unscaled parts."""
import copy
import math
import unittest
from unittest.mock import patch
from assembly_auxiliary import add_auxiliary
from assembly_case_shrouds052 import apply_layout_anchors
from assembly_cooling import add_cooling
from assembly_geometry import Mesh,box
from assembly_rear_bay_group_c052 import CASE_IDS,build,layout_reference
from assembly_style import apply_model_styles
from assembly_visibility048 import mesh_visible
from chassis_catalog import CASES,get_case
from test_case_layout_hosts052 import _geometry,_positive_overlap,_inside

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
TONE=(.2,.3,.4,1.)


class RearBayGroupC052Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('No device/window/worker')))
        self.shapes={}

    def geometry(self,mesh):
        if id(mesh) not in self.shapes:self.shapes[id(mesh)]=_geometry(mesh)
        return self.shapes[id(mesh)]

    def test_exact_seven_only_and_detached_inputs_preserve_source_conflicts(self):
        self.assertEqual(len(CASE_IDS),7)
        for case in CASES:
            dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
            before=copy.deepcopy((case,dims));meshes,meta=build(case,dims,TONE)
            self.assertEqual((case,dims),before)
            if case['id'] not in CASE_IDS:
                self.assertEqual((meshes,meta),((),{}));continue
            self.assertTrue(meshes);self.assertFalse(meta['selected_component_geometry_used'])
            self.assertFalse(meta['dimensions_verified']);self.assertFalse(meta['positions_verified'])
            self.assertEqual(len({m.part_id for m in meshes}),len(meshes))
            if case['id'] in ('corsair-2500x','lian-li-o11-vision-compact','jonsbo-tk2-black'):
                self.assertTrue(meta['source_conflicts']);self.assertFalse(meta['source_conflicts'][0]['resolved'])

    def test_real_triangles_have_positive_volume_and_unit_outward_normals(self):
        for identity in CASE_IDS:
            case=get_case(identity);dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
            meshes,meta=build(case,dims,TONE)
            self.assertLess(sum(m.vertex_count//3 for m in meshes),1600)
            for mesh in meshes:
                signed=0.
                for at in range(0,len(mesh.vertices),18):
                    a,b,c=(mesh.vertices[at+n:at+n+3] for n in (0,6,12))
                    ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
                    n=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                    self.assertGreater(sum(v*v for v in n),1.e-16)
                    for offset in (0,6,12):
                        normal=mesh.vertices[at+offset+3:at+offset+6]
                        self.assertAlmostEqual(sum(v*v for v in normal),1.,places=7)
                        self.assertGreater(sum(n[k]*normal[k] for k in range(3)),0.)
                    signed+=sum(a[k]*(b[(k+1)%3]*c[(k+2)%3]-b[(k+2)%3]*c[(k+1)%3]) for k in range(3))/6.
                self.assertTrue(all(math.isfinite(v) for v in mesh.vertices));self.assertGreater(signed,0.)

    def test_upper_middle_and_hybrid_lower_source_datums_are_distinct(self):
        for identity in CASE_IDS:
            case=get_case(identity);dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
            layout=layout_reference(case,dims);meshes,meta=build(case,dims,TONE)
            self.assertFalse(layout['positions_verified']);self.assertFalse(layout['source_limit_is_whole_fit_certificate'])
            self.assertTrue(meta['replaces_rear_chamber_shroud']);self.assertTrue(meta['replaces_case_bottom'])
            if identity=='nzxt-h9-flow-2023':self.assertIn('ceiling_y_mm',layout['psu'])
            if identity=='havn-hs-420':
                self.assertTrue(meta['replaces_case_feet']);self.assertIn('rear_divider_bottom_y_mm',layout)
                self.assertTrue(any(m.part_id=='case:psu-cover' for m in meshes))
            if identity=='deepcool-ch780':
                self.assertGreater(layout['psu']['floor_y_mm']-(-dims[1]/2),50.)
                self.assertGreater(layout['mount_planes']['bottom']['span_mm'][0],200.)
                self.assertTrue(layout['raised_tray_lower_edge_reference'])
                self.assertEqual(layout['rear_divider_bottom_y_mm'],-dims[1]/2+64.)

    def test_source_base_supports_meet_actual_floor_material_including_the_clipped_corner(self):
        for identity in ('havn-hs-420','be-quiet-light-base-600-lx'):
            case=get_case(identity);dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
            meshes,meta=build(case,dims,TONE);layout=layout_reference(case,dims)
            floor=next(m for m in meshes if m.part_id=='case:open-floor')
            support=next(m for m in meshes if m.part_id=='case:base-support-samples')
            self.assertEqual(len(support.vertices),4*216)
            floor_bottom=min(floor.vertices[1::6]);inside_y=(floor_bottom+max(floor.vertices[1::6]))/2
            for start in range(0,len(support.vertices),216):
                atom=support.vertices[start:start+216]
                self.assertAlmostEqual(max(atom[1::6]),floor_bottom,places=7)
                contacts=[]
                for at in range(0,len(atom),18):
                    if atom[at+4]<.99:continue
                    x=sum(atom[at+k] for k in (0,6,12))/3
                    z=sum(atom[at+k+2] for k in (0,6,12))/3
                    contacts.append(_inside((x,inside_y,z),self.geometry(floor)))
                self.assertTrue(any(contacts),(identity,'support must touch metal, not an intake void'))
            if identity=='be-quiet-light-base-600-lx':
                self.assertEqual(layout['source_body_height_mm'],435.)
                self.assertEqual(layout['source_feet_height_mm'],20.)
                self.assertGreaterEqual(floor_bottom,-dims[1]/2+20.-1.e-8)
                self.assertEqual(layout['source_psu_limit_operator'],'less_than')

    def test_havn_rotates_whole_bottom_fans_and_keeps_actual_old_wire_overlap_control(self):
        case=get_case('havn-hs-420');dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
        covers,_=build(case,dims,TONE);layout=layout_reference(case,dims)
        spec=dict(case=case,cooling=dict(cpu_cooler='none',case_fans=[dict(model='arctic-p14-pwm',mount='bottom',count=3,direction='intake')]))
        anchors=apply_layout_anchors(dict(case=case,case_dimensions=dims),spec,layout)
        current,meta=add_cooling(covers,spec,'eco',anchors)
        old=copy.deepcopy(anchors);old['case_mount_planes']['bottom']['up']=(0.,0.,1.)
        previous,previous_meta=add_cooling(covers,spec,'eco',old)
        self.assertEqual(meta['rejected'],[]);self.assertEqual(previous_meta['rejected'],[])
        self.assertEqual({tuple(f['position'])for f in meta['fans']},
                         {tuple(f['position'])for f in previous_meta['fans']})
        skin=next(m for m in covers if m.part_id=='case:psu-cover')
        old_leads=[m for m in previous if m.name in ('case-fan-power-lead','case-fan-power-connector')]
        self.assertTrue(any(_positive_overlap(self.geometry(m),self.geometry(skin)) is not None for m in old_leads))
        def rotate(p):return (-p[0],p[1],-p[2])
        for fan in previous_meta['fans']:
            matched=next(f for f in meta['fans'] if tuple(f['position'])==tuple(fan['position']))
            origin=fan['position'];a=[m for m in previous if m.part_id==fan['part_id']]
            b=[m for m in current if m.part_id==matched['part_id']]
            self.assertEqual(len(a),len(b))
            for before,after in zip(a,b):
                self.assertEqual((before.name,before.rotor),(after.name,after.rotor))
                # Static builder meshes bake world coordinates into vertices;
                # rotors keep local vertices and a separate rotation pivot.
                # Compare complete world points rather than requiring either
                # storage convention to transform its (possibly zero) offset.
                self.assertEqual(len(before.vertices),len(after.vertices))
                for offset in range(0,len(before.vertices),6):
                    relative=tuple(before.vertices[offset+k]+before.position[k]-origin[k] for k in range(3))
                    expected=rotate(relative)
                    for k in range(3):
                        self.assertAlmostEqual(after.vertices[offset+k]+after.position[k],origin[k]+expected[k],places=7)
                    for x,y in zip(rotate(before.vertices[offset+3:offset+6]),after.vertices[offset+3:offset+6]):
                        self.assertAlmostEqual(x,y,places=7)
                if before.rotor:
                    expected=rotate(tuple(before.position[k]-origin[k] for k in range(3)))
                    for k in range(3):self.assertAlmostEqual(after.position[k],origin[k]+expected[k],places=7)
                if before.rotor:self.assertEqual(rotate(before.axis),after.axis)

    def test_six_styles_share_arrays_and_only_actual_cover_hides_for_psu_inspection(self):
        for identity in CASE_IDS:
            case=get_case(identity);dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
            meshes,meta=build(case,dims,TONE);kinds={r['id']:r['kind'] for r in meta['parts']}
            for style in SIX:
                values,_=apply_model_styles(meshes,style,{},dims,case['panels'])
                physical=[m for m in values if not m.name.startswith('style-')]
                for old,new in zip(meshes,physical):
                    self.assertIs(old.vertices,new.vertices)
                    self.assertEqual((old.part_id,old.position,old.axis),(new.part_id,new.position,new.axis))
            for mesh in meshes:self.assertEqual(mesh_visible(mesh,True,True),kinds[mesh.part_id]!='case_cover')

    def test_actual_psu_all_details_three_lods_clear_material_and_source_divider(self):
        for identity in CASE_IDS:
            case=get_case(identity);dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'));w,h,d=dims
            covers,_=build(case,dims,TONE);layout=layout_reference(case,dims)
            bottom=layout.get('rear_divider_bottom_y_mm',-h/2+6.);top=h/2-6.
            divider=Mesh('conservative-source-divider',box(2.,top-bottom,d-12.),TONE,
                (layout.get('board_x_mm',w*.10)+5.,(top+bottom)/2,0.),'case')
            spec=dict(case=case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=False))
            anchors=apply_layout_anchors(dict(case=case,case_dimensions=dims,connectors={}),spec,layout)
            for level in ('eco','balanced','close'):
                values,meta=add_auxiliary(spec,anchors,level)
                self.assertEqual(meta['device_counts']['psu'],1);self.assertEqual(meta['rejected'],[])
                self.assertTrue(any(m.name=='psu-fan-panel' for m in values))
                for mesh in values:
                    if mesh.component!='psu':continue
                    for material in (*covers,divider):
                        self.assertIsNone(_positive_overlap(self.geometry(mesh),self.geometry(material)),
                            (identity,level,mesh.name,material.name))
                self.shapes.clear()

    def test_actual_declared_bottom_fans_keep_all_parts_and_clear_psu_and_case_material(self):
        configurations=0
        for identity in CASE_IDS:
            case=get_case(identity);dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
            covers,_=build(case,dims,TONE);layout=layout_reference(case,dims)
            for size,model in ((120,'arctic-p12-pwm'),(140,'arctic-p14-pwm')):
                support=[r for r in case['fan_mounts'] if r['position']=='bottom' and size in r['size_mm']]
                if not support:continue
                count=min(3,max(r['count'] for r in support))
                spec=dict(case=case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=False),
                    cooling=dict(cpu_cooler='none',case_fans=[dict(model=model,mount='bottom',count=count,direction='intake')]))
                anchors=apply_layout_anchors(dict(case=case,case_dimensions=dims,connectors={}),spec,layout)
                psu,_=add_auxiliary(spec,anchors,'eco')
                low=layout.get('rear_divider_bottom_y_mm',-dims[1]/2+6.);high=dims[1]/2-6.
                divider=Mesh('conservative-source-divider',box(2.,high-low,dims[2]-12.),TONE,
                    (layout.get('board_x_mm',dims[0]*.10)+5.,(high+low)/2,0.),'case')
                values,meta=add_cooling((*covers,*psu),spec,'eco',anchors)
                self.assertEqual(meta['rejected'],[],(identity,size));self.assertEqual(sum(m.rotor for m in values),count)
                self.assertEqual(sum(m.name=='case-fan-power-connector' for m in values),count)
                for mesh in values:
                    for material in (*covers,divider,*(m for m in psu if m.component=='psu')):
                        self.assertIsNone(_positive_overlap(self.geometry(mesh),self.geometry(material)),
                            (identity,size,mesh.name,material.name))
                self.shapes.clear();configurations+=1
        self.assertGreaterEqual(configurations,7)


if __name__=='__main__':unittest.main()
