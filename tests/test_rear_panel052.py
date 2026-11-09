"""Exact rear-wall PSU openings: actual voids, retained metal, no Scene."""
from collections import Counter
import copy
from dataclasses import asdict,replace
import hashlib
import json
import math
import struct
import unittest
from unittest.mock import patch

from assembly_geometry import color
from assembly_rear_panel052 import ATX_REFERENCE_MM,CASE_IDS,MAX_TRIANGLES,build
from chassis_catalog import CASES,get_case
import test_shroud_other052 as material


VERTICAL=((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.))
IDENTITY=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
RAYS=((1.,.173,.317),(.317,1.,.173),(.173,.317,1.))


def _dimensions(case):return tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))


def _layout(case,dimensions,*,upper=False,basis=VERTICAL):
    w,h,d=dimensions
    psu=dict(basis=basis,align_x='right',boundary_x_mm=w/2-9.,rear_z_mm=-d/2+10.)
    psu['ceiling_y_mm' if upper else 'floor_y_mm']=h/2-18. if upper else -h/2+28.
    return dict(case_id=case['id'],source=case['sources'][0],source_urls=(case['sources'][0],),
        reference_only=True,positions_verified=False,dimensions_verified=False,psu=psu)


def _inside(point,mesh):
    triangles=material._world(mesh)
    return all(material._ray_inside(point,triangles,ray) for ray in RAYS)


def _area(poly):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,(*poly[1:],poly[0]))))/2


def _closed_edges(mesh):
    """Split all existing collinear vertices to count real atomic edges.

    This accommodates cap-triangulation T junctions without accepting a gap.
    No producer clipping or connectivity helper supplies the expected result.
    """
    triangles=material._world(mesh)
    point=lambda p:tuple(round(x,7) for x in p)
    unique=tuple({point(p) for tri in triangles for p in tri})
    counts=Counter()
    for triangle in triangles:
        for a,b in zip(triangle,(*triangle[1:],triangle[0])):
            # Endpoints and candidate vertices must share one coordinate
            # grid. Mixing rounded candidates with an unrounded short edge
            # can spuriously put its own endpoint beyond t=1.
            a,b=point(a),point(b)
            if a==b:continue
            delta=material._sub(b,a);squared=material._dot(delta,delta)
            nodes=[]
            for p in unique:
                along=material._dot(material._sub(p,a),delta)/squared
                projection=tuple(a[k]+along*delta[k] for k in range(3))
                if -1.e-7<=along<=1.+1.e-7 and sum((p[k]-projection[k])**2 for k in range(3))<1.e-12:
                    nodes.append((max(0.,min(1.,along)),p))
            nodes.sort()
            for (_,p),(_,q) in zip(nodes,nodes[1:]):
                if p!=q:counts[tuple(sorted((p,q)))]+=1
    return counts


class RearPanel052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start',
                     'assembly_geometry.build_scene'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure panel construction only')))
        self.case=get_case('nzxt-h6-flow-2023');self.dimensions=_dimensions(self.case)

    def test_whitelist_is_eighteen_exact_variants_other_seventy_eight_untouched(self):
        self.assertEqual(len(CASE_IDS),18);self.assertEqual(len(set(CASE_IDS)),18)
        self.assertEqual(len(CASES),96)
        untouched=0
        for case in CASES:
            dimensions=_dimensions(case);layout=_layout(case,dimensions)
            mesh,meta=build(case,dimensions,layout,color('#25313e'))
            if case['id'] not in CASE_IDS:
                self.assertEqual((mesh,meta),(None,{}));untouched+=1
            else:
                self.assertIsNotNone(mesh,case['id']);self.assertEqual(meta['case_id'],case['id'])
                self.assertEqual(mesh.name,'case-back');self.assertEqual(mesh.part_id,'case:rear-wall')
        self.assertEqual(untouched,78)

    def test_fixed_atx_lower_upper_and_center_x_datums_not_selected_hardware(self):
        w,h,d=self.dimensions
        lower=_layout(self.case,self.dimensions);upper=_layout(self.case,self.dimensions,upper=True)
        for layout,expected_y in ((lower,-h/2+28.+75.),(upper,h/2-18.-75.)):
            old=copy.deepcopy(layout);mesh,meta=build(self.case,self.dimensions,layout,color('#25313e'))
            self.assertEqual(layout,old);self.assertEqual(meta['atx_reference_dimensions_mm'],ATX_REFERENCE_MM)
            self.assertEqual(meta['reference_psu_world_dimensions_mm'],(86.,150.,160.))
            self.assertEqual(meta['reference_psu_center_mm'],(w/2-9.-43.,expected_y,-d/2+90.))
            self.assertEqual(mesh.position,(0.,8.,-d/2+1.))
            mutated=copy.deepcopy(layout);mutated['selected_psu']={'width':900,'height':900,'length':900}
            changed=copy.deepcopy(self.case);changed['selected_psu']='different-model'
            self.assertEqual(build(changed,self.dimensions,mutated,color('#25313e')),(mesh,meta))
        centered=copy.deepcopy(upper);centered['psu'].pop('boundary_x_mm');centered['psu'].pop('align_x')
        centered['psu']['center_x_mm']=47.
        self.assertEqual(build(self.case,self.dimensions,centered,color('#25313e'))[1]['reference_psu_center_mm'][0],47.)

    def test_actual_group_a_and_group_b_layouts_keep_source_datums(self):
        from assembly_rear_bay_group_a052 import CASE_IDS as a_ids,layout_reference as a_layout
        from assembly_rear_bay_group_b052 import CASE_IDS as b_ids,layout_reference as b_layout
        from assembly_y70_case052 import layout_reference as y_layout
        rows=[*( (identity,a_layout) for identity in a_ids),*( (identity,b_layout) for identity in b_ids),('hyte-y70',y_layout)]
        self.assertEqual(len(rows),11)
        for identity,describe in rows:
            case=get_case(identity);dimensions=_dimensions(case);layout=describe(case,dimensions)
            mesh,meta=build(case,dimensions,layout,color('#25313e'))
            self.assertIsNotNone(mesh,identity);self.assertEqual(meta['source'],layout['source'])
            cy=meta['reference_psu_center_mm'][1];psu=layout['psu']
            if 'ceiling_y_mm' in psu:self.assertEqual(cy,psu['ceiling_y_mm']-75.)
            else:self.assertEqual(cy,psu['floor_y_mm']+75.)
            cx=meta['reference_psu_center_mm'][0]
            self.assertFalse(_inside((cx,cy,mesh.position[2]),mesh),identity)
            if identity=='nzxt-h6-flow-2023':self.assertGreater(cy,0.)
        # This is a pure descriptor test, not a fresh complete chassis build.

    def test_orthonormal_right_handed_and_rear_exhaust_contract_fail_closed(self):
        good=_layout(self.case,self.dimensions)
        for basis in (IDENTITY,VERTICAL,
                ((math.sqrt(.5),math.sqrt(.5),0.),(-math.sqrt(.5),math.sqrt(.5),0.),(0.,0.,1.))):
            row=copy.deepcopy(good);row['psu']['basis']=basis;row['psu']['center_x_mm']=0.
            self.assertIsNotNone(build(self.case,self.dimensions,row,color('#25313e'))[0])
        for basis in (((-1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),
                      ((-1.,0.,0.),(0.,1.,0.),(0.,0.,-1.)),
                      ((1.,0.,0.),(0.,2.,0.),(0.,0.,1.)),
                      ((1.,0.,0.),(1.,1.,0.),(0.,0.,1.)),
                      ((1.,0.,0.),(0.,1.,0.),(0.,0.,float('nan')))):
            row=copy.deepcopy(good);row['psu']['basis']=basis
            self.assertEqual(build(self.case,self.dimensions,row,color('#25313e')),(None,{}))

    def test_invalid_identity_source_ambiguous_or_unbounded_inputs_return_no_replacement(self):
        good=_layout(self.case,self.dimensions)
        variants=[]
        for source in ('http://example.com/a','file:///local','https://host/a\nscript','https://user@host/a','https://host/<script>'):
            row=copy.deepcopy(good);row['source']=source;variants.append(row)
        row=copy.deepcopy(good);row['case_id']='hyte-y70';variants.append(row)
        row=copy.deepcopy(good);row['source_urls']=['javascript:code'];variants.append(row)
        row=copy.deepcopy(good);row['psu']['ceiling_y_mm']=200.;variants.append(row)
        for field,value in (('floor_y_mm',True),('floor_y_mm',float('inf')),('center_x_mm',10000),('rear_z_mm',float('nan'))):
            row=copy.deepcopy(good);row['psu'][field]=value;variants.append(row)
        row=copy.deepcopy(good);row['psu']['align_x']='left';variants.append(row)
        row=copy.deepcopy(good);row['psu'].pop('rear_z_mm');variants.append(row)
        for row in variants:self.assertEqual(build(self.case,self.dimensions,row,color('#25313e')),(None,{}))
        for dims in (None,(True,435,415),(287,float('nan'),415),(287,435,10000),(287,435)):
            self.assertEqual(build(self.case,dims,good,color('#25313e')),(None,{}))
        for tone in ((1.,1.,1.),(1.,1.,1.,float('nan')),(1.,1.,1.,-1.)):
            self.assertEqual(build(self.case,self.dimensions,good,tone),(None,{}))

    def test_real_through_void_adjacent_metal_old_extent_and_reference_only_scope(self):
        w,h,d=self.dimensions;layout=_layout(self.case,self.dimensions,upper=True)
        mesh,meta=build(self.case,self.dimensions,layout,color('#25313e'))
        cx,cy,_=meta['reference_psu_center_mm'];z=-d/2+1.
        self.assertFalse(_inside((cx,cy,z),mesh))
        self.assertTrue(_inside((-w/2+5.,8.,z),mesh))
        self.assertEqual(material._mesh_bounds(mesh),((-w/2,-h/2+16.,-d/2),(w/2,h/2,-d/2+2.)))
        self.assertEqual(meta['opening_scope'],'fixed_psu_reference_interface_only')
        self.assertEqual(meta['parts'][0]['kind'],'case_structure')
        for flag in ('dimensions_verified','positions_verified','mounting_hole_positions_verified','manufacturing_cad',
                     'selected_hardware_read','pcie_openings_modeled','motherboard_io_openings_modeled',
                     'projecting_rear_flange_modeled','source_15mm_bracket_projection_modeled','edge_open_reference'):
            self.assertIs(meta[flag],False)
        detached=copy.deepcopy(meta);meta['parts'][0]['positions_verified']=True
        self.assertEqual(build(self.case,self.dimensions,layout,color('#25313e'))[1],detached)
        json.dumps(detached,allow_nan=False)

    def test_edge_intersection_is_an_open_notch_not_an_uncut_side_curtain(self):
        w,h,d=self.dimensions;layout=_layout(self.case,self.dimensions)
        layout['psu']['center_x_mm']=w/2-10.;layout['psu']['floor_y_mm']=-75.
        mesh,meta=build(self.case,self.dimensions,layout,color('#25313e'))
        self.assertTrue(meta['edge_open_reference'])
        self.assertFalse(_inside((w/2-5.,0.,mesh.position[2]),mesh))
        self.assertTrue(_inside((w/2-60.,0.,mesh.position[2]),mesh))
        # The aperture at the outer edge is truly traversable sideways too.
        tri=material._world(mesh);point=(w/2-5.,0.,mesh.position[2])
        self.assertFalse(material._ray_inside(point,tri,(1.,0.,0.)))
        self.assertTrue(all(n==2 for n in _closed_edges(mesh).values()))

    def test_nondegenerate_outward_unit_normals_closed_edges_volume_and_fixed_budget(self):
        w,h,_=self.dimensions
        for basis in (IDENTITY,VERTICAL):
            layout=_layout(self.case,self.dimensions,basis=basis);layout['psu']['center_x_mm']=0.
            mesh,meta=build(self.case,self.dimensions,layout,color('#25313e'));volume=0.
            for at,triangle in zip(range(0,len(mesh.vertices),18),material._world(mesh)):
                cross=material._cross(material._sub(triangle[1],triangle[0]),material._sub(triangle[2],triangle[0]))
                self.assertGreater(material._dot(cross,cross),1.e-16)
                for offset in (0,6,12):
                    normal=mesh.vertices[at+offset+3:at+offset+6]
                    self.assertAlmostEqual(material._dot(normal,normal),1.,places=8)
                    self.assertGreater(material._dot(normal,cross),0.)
                volume+=material._dot(triangle[0],material._cross(triangle[1],triangle[2]))/6.
            expected=(w*(h-16.)-150.*86.)*2.
            self.assertAlmostEqual(volume,expected,places=5)
            self.assertTrue(all(n==2 for n in _closed_edges(mesh).values()))
            self.assertLessEqual(len(mesh.vertices)//18,MAX_TRIANGLES)

    def test_king95_actual_source_descriptor_opens_only_psu_reference_interface(self):
        from assembly_rear_bay_group_b052 import layout_reference
        case=get_case('montech-king-95');dimensions=_dimensions(case);layout=layout_reference(case,dimensions)
        mesh,meta=build(case,dimensions,layout,color('#25313e'))
        self.assertIsNotNone(mesh);self.assertEqual(meta['case_id'],'montech-king-95')
        x,y,_=meta['reference_psu_center_mm'];z=mesh.position[2];w,h,d=dimensions
        self.assertFalse(_inside((x,y,z),mesh));self.assertTrue(_inside((-w/2+5.,8.,z),mesh))
        self.assertEqual(mesh.position,(0.,8.,-d/2+1.))
        self.assertEqual(material._mesh_bounds(mesh),((-w/2,-h/2+16.,-d/2),(w/2,h/2,-d/2+2.)))
        self.assertTrue(all(n==2 for n in _closed_edges(mesh).values()))
        self.assertFalse(meta['pcie_openings_modeled']);self.assertFalse(meta['motherboard_io_openings_modeled'])

    def test_light_base_body_excludes_twenty_mm_stand_and_hole_stays_world_fixed(self):
        from assembly_rear_bay_group_c052 import layout_reference
        case=get_case('be-quiet-light-base-600-lx');dimensions=_dimensions(case)
        self.assertEqual(dimensions,(305,455,450))
        layout=layout_reference(case,dimensions);mesh,meta=build(case,dimensions,layout,color('#25313e'))
        self.assertIsNotNone(mesh);self.assertEqual(mesh.position,(0.,10.,-224.))
        self.assertEqual(meta['source_body_height_mm'],435.);self.assertEqual(meta['source_feet_height_mm'],20.)
        self.assertEqual(meta['body_center_y_mm'],10.)
        self.assertEqual(material._mesh_bounds(mesh),((-152.5,-207.5,-225.),(152.5,227.5,-223.)))
        x,y,_=meta['reference_psu_center_mm'];z=mesh.position[2]
        self.assertEqual(y,layout['psu']['floor_y_mm']+75.)
        self.assertFalse(_inside((x,y,z),mesh));self.assertTrue(_inside((-140.,10.,z),mesh))
        self.assertTrue(all(n==2 for n in _closed_edges(mesh).values()))
        volume=sum(material._dot(t[0],material._cross(t[1],t[2]))/6 for t in material._world(mesh))
        self.assertAlmostEqual(volume,(305.*435.-150.*86.)*2.,places=5)
        for flag in ('dimensions_verified','positions_verified','manufacturing_cad','pcie_openings_modeled',
                     'motherboard_io_openings_modeled','source_15mm_bracket_projection_modeled'):
            self.assertIs(meta[flag],False)

    def test_other_sixteen_f64_mesh_fields_and_full_metadata_match_previous_frozen_source(self):
        # Captured from source7c3208ac before KING95/body-datum changes, not an
        # updated expectation for each current output. It includes every F64
        # vertex/normal, all other Mesh fields and the complete metadata.
        digest=hashlib.sha256();count=0
        for identity in CASE_IDS:
            if identity in ('montech-king-95','be-quiet-light-base-600-lx'):continue
            case=get_case(identity);dimensions=_dimensions(case)
            mesh,meta=build(case,dimensions,_layout(case,dimensions),color('#25313e'))
            fields=asdict(mesh);fields.pop('vertices')
            raw=(struct.pack('<'+'d'*len(mesh.vertices),*mesh.vertices)
                +json.dumps(dict(mesh=fields,metadata=meta),sort_keys=True,separators=(',',':')).encode())
            digest.update((identity+'\0'+hashlib.sha256(raw).hexdigest()).encode());count+=1
        self.assertEqual(count,16)
        self.assertEqual(digest.hexdigest(),'443b3f5a5548c5fe43f0bc7390084a5efba02bfb510fc74e945a1b0dd17f412b')

    def test_all_eighteen_current_source_layouts_void_metal_closed_material_and_normal_budget(self):
        from assembly_case_shrouds052 import layout_reference
        for identity in CASE_IDS:
            case=get_case(identity);dimensions=_dimensions(case);layout=layout_reference(case,dimensions)
            mesh,meta=build(case,dimensions,layout,color('#25313e'))
            self.assertIsNotNone(mesh,identity)
            x,y,_=meta['reference_psu_center_mm'];z=mesh.position[2];w,_,_=dimensions
            self.assertFalse(_inside((x,y,z),mesh),identity)
            self.assertTrue(_inside((-w/2+5.,mesh.position[1],z),mesh),identity)
            self.assertTrue(all(n==2 for n in _closed_edges(mesh).values()),identity)
            self.assertLessEqual(len(mesh.vertices)//18,MAX_TRIANGLES)
            for at,triangle in zip(range(0,len(mesh.vertices),18),material._world(mesh)):
                face=material._cross(material._sub(triangle[1],triangle[0]),material._sub(triangle[2],triangle[0]))
                self.assertGreater(material._dot(face,face),1.e-16,identity)
                for offset in (0,6,12):
                    normal=mesh.vertices[at+offset+3:at+offset+6]
                    self.assertAlmostEqual(material._dot(normal,normal),1.,places=8)
                    self.assertGreater(material._dot(face,normal),0.)
            self.assertFalse(meta['pcie_openings_modeled']);self.assertFalse(meta['motherboard_io_openings_modeled'])

    def test_closed_edge_checker_rejects_a_real_point_zero_one_mm_split(self):
        mesh,_=build(self.case,self.dimensions,_layout(self.case,self.dimensions),color('#25313e'))
        self.assertTrue(all(n==2 for n in _closed_edges(mesh).values()))
        damaged=list(mesh.vertices);damaged[0]+=.01
        opened=replace(mesh,vertices=tuple(damaged))
        self.assertTrue(any(n!=2 for n in _closed_edges(opened).values()))


if __name__=='__main__':unittest.main()
