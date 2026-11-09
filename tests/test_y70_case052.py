"""Exact non-Touch Y70 open material; no Scene, device or renderer creation."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,box,color
from assembly_y70_case052 import CASE_ID,PRODUCT,BUILD_GUIDE,FEATURES,build,layout_reference
from chassis_catalog import CASES,get_case
import test_shroud_other052 as material


DIMENSIONS=(320.,470.,470.)
RAYS=((1.,.173,.317),(.317,1.,.173),(.173,.317,1.))
STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def _inside(point,mesh):return all(material._ray_inside(point,material._world(mesh),d) for d in RAYS)


def _shape(mesh):
    triangles=material._world(mesh)
    return triangles,tuple(material._bounds(t) for t in triangles),material._mesh_bounds(mesh)


def _surface_crossing(first,second):
    triangles,boxes,aa=first;others,other_boxes,bb=second
    overlaps=lambda a,b:all(a[1][k]>=b[0][k]-1.e-8 and b[1][k]>=a[0][k]-1.e-8 for k in range(3))
    if not overlaps(aa,bb):return False
    for triangle,bounds in zip(triangles,boxes):
        if not overlaps(bounds,bb):continue
        for other,other_bounds in zip(others,other_boxes):
            if overlaps(bounds,other_bounds) and material._surface_intersection(triangle,other):return True
    return False


class Y70Case052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start','assembly_geometry.build_scene'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure material construction only')))
        self.case=get_case(CASE_ID);self.meshes,self.meta=build(self.case,DIMENSIONS,color('#25313e'))

    def test_exact_non_touch_only_detached_fixed_replacement_contract(self):
        before=copy.deepcopy(self.case)
        self.assertTrue(self.meshes);self.assertEqual(self.case,before)
        for row in CASES:
            if row['id']!=CASE_ID:
                dims=tuple(row['dimensions_mm'][k] for k in ('width','height','depth'))
                self.assertEqual(build(row,dims,color('#25313e')),((),{}))
                self.assertEqual(layout_reference(row,dims),{})
        for bad in ((True,470,470),(320,float('nan'),470),(320,470,9000),(320,470),None):
            self.assertEqual(build(self.case,bad,color('#25313e')),((),{}))
        changed=copy.deepcopy(self.case);changed.update(selected_fan={'size':500},selected_gpu={'width':500},selected_psu={'length':300})
        self.assertEqual(build(changed,DIMENSIONS,color('#25313e')),(self.meshes,self.meta))
        self.assertEqual(self.meta['source_variant'],'non_touch')
        self.assertEqual(self.meta['source_urls'],(PRODUCT,BUILD_GUIDE,FEATURES))
        self.assertFalse(any('touch' in source.lower() for source in self.meta['source_urls']))
        for field in ('replaces_case_bottom','replaces_case_feet','replaces_rear_chamber_shroud'):
            self.assertIs(self.meta[field],True)
        self.assertEqual(self.meta['replaced_generic_mesh_names'],('case-bottom','case-foot','rear-chamber-shroud'))
        for field in ('dimensions_verified','positions_verified','thickness_verified','cad_verified',
                      'selected_component_geometry_used','chamber_is_solid','psu_chamber_is_solid','exact_foot_count_verified'):
            self.assertIs(self.meta[field],False)
        self.assertEqual({m.part_id for m in self.meshes},{p['id'] for p in self.meta['parts']})
        self.assertEqual(len({m.part_id for m in self.meshes}),len(self.meshes))
        self.assertTrue(all(p['kind']=='case_structure' and p['source_url']==PRODUCT for p in self.meta['parts']))
        self.assertFalse(any(m.name in self.meta['replaced_generic_mesh_names'] for m in self.meshes))

    def test_original_mount_coordinates_retained_primary_limits_separate_from_unverified_pose(self):
        layout=layout_reference(self.case,DIMENSIONS);planes=layout['mount_planes']
        self.assertEqual(planes['bottom']['position'],(-61.5,-225.,0.))
        self.assertEqual(planes['bottom']['span_mm'],(181.,438.))
        self.assertEqual(planes['bottom']['normal'],(0.,-1.,0.));self.assertEqual(planes['bottom']['up'],(0.,0.,1.))
        self.assertEqual(planes['top']['position'],(-61.5,223.,0.))
        self.assertEqual(planes['side']['position'],(108.80000000000001,0.,108.10000000000001))
        for plane in planes.values():
            self.assertEqual(plane['source'],PRODUCT);self.assertFalse(plane['dimensions_verified'])
            self.assertFalse(plane['positions_verified']);self.assertFalse(plane['mounting_hole_positions_verified'])
        for mount in ('top','side'):self.assertEqual(planes[mount]['method'],'observed_shared_frame_unverified')
        limit=layout['fan_constraints']['bottom']
        self.assertEqual(limit['case_id'],CASE_ID);self.assertEqual(limit['max_count_by_size_mm'],{'120':3,'140':2})
        self.assertEqual(limit['max_depth_mm'],32.);self.assertTrue(limit['source_capacity_verified'])
        self.assertFalse(planes['bottom']['related_manual_manufacturing_identity_verified'])
        self.assertEqual(layout['source_max_psu_length_mm'],235.)
        detached=copy.deepcopy(layout);layout['mount_planes']['bottom']['position']=(0.,0.,0.)
        self.assertEqual(layout_reference(self.case,DIMENSIONS),detached)

    def test_finite_normal_coherent_bounded_material_and_perimeter_foot_extent(self):
        count=0
        for mesh in self.meshes:
            self.assertEqual(mesh.component,'case');self.assertEqual(mesh.position,(0.,0.,0.))
            self.assertEqual(len(mesh.vertices)%18,0);count+=len(mesh.vertices)//18
            bounds=material._mesh_bounds(mesh)
            self.assertGreaterEqual(bounds[0][0],-160.);self.assertLessEqual(bounds[1][0],160.)
            self.assertGreaterEqual(bounds[0][1],-235.);self.assertLessEqual(bounds[1][1],-219.)
            self.assertGreaterEqual(bounds[0][2],-235.);self.assertLessEqual(bounds[1][2],235.)
            for at,triangle in zip(range(0,len(mesh.vertices),18),material._world(mesh)):
                n=material._cross(material._sub(triangle[1],triangle[0]),material._sub(triangle[2],triangle[0]))
                self.assertGreater(material._dot(n,n),1.e-16)
                for offset in (0,6,12):
                    normal=mesh.vertices[at+offset+3:at+offset+6]
                    self.assertAlmostEqual(material._dot(normal,normal),1.,places=8)
                    self.assertGreater(material._dot(n,normal),0.)
                self.assertTrue(all(math.isfinite(v) for p in triangle for v in p))
            if mesh.name=='case-y70-perimeter-foot':
                self.assertAlmostEqual(bounds[1][1],self.meta['bottom_pan_bottom_world_y_mm'])
                self.assertLess(bounds[1][1],-225.)
        self.assertLessEqual(count,1200)

    def test_real_intake_void_neighbouring_material_and_no_filled_rear_psu_chamber(self):
        pan_y=-226.6
        tray=next(m for m in self.meshes if m.part_id=='case:bottom-fan-tray')
        frame=next(m for m in self.meshes if m.part_id=='case:base-frame')
        self.assertFalse(_inside((-61.5,pan_y,0.),tray))
        self.assertFalse(_inside((-61.5,pan_y,0.),frame))
        self.assertTrue(_inside((-6.5,pan_y,0.),tray))
        self.assertTrue(_inside((108.,pan_y,-145.),frame))
        point=(108.,-148.,-145.)
        for mesh in self.meshes:self.assertFalse(_inside(point,mesh))
        legacy=Mesh('legacy-filled-rear-chamber',box(89.6,108.1,206.8),color('#25313e'),(108.8,-150.4,-117.5),'case')
        self.assertTrue(_inside(point,legacy))
        # The current diagonal intake corner is a real clipped outline, not
        # a rectangular tray protruding through the front chamfer.
        for mesh in self.meshes:
            for at in range(0,len(mesh.vertices),6):
                x,_,z=mesh.vertices[at:at+3]
                self.assertLessEqual(z-x,321.4+1.e-7)

    def test_all_six_styles_preserve_every_physical_material_array_and_identity(self):
        from assembly_style import apply_model_styles
        for style in STYLES:
            values,meta=apply_model_styles(self.meshes,style,{},DIMENSIONS,self.case['panels'])
            physical=[m for m in values if not m.name.startswith('style-')]
            self.assertEqual(len(physical),len(self.meshes));self.assertEqual(meta['visual_style'],style)
            for new,old in zip(physical,self.meshes):
                self.assertIs(new.vertices,old.vertices)
                self.assertEqual((new.part_id,new.position,new.axis,new.rotor),(old.part_id,old.position,old.axis,old.rotor))

    def test_real_psu_details_keep_original_pose_and_clear_thin_frame_divider_all_lods(self):
        from assembly_auxiliary import add_auxiliary
        from assembly_case_shrouds052 import apply_layout_anchors
        spec=dict(case=self.case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=False))
        old_anchors=dict(case=self.case,case_dimensions=DIMENSIONS,connectors={})
        anchors=apply_layout_anchors(old_anchors,spec,layout_reference(self.case,DIMENSIONS))
        self.assertEqual(anchors['psu']['position'],(108.,-148.,-145.))
        divider=Mesh('conservative-existing-divider-slab',box(2.,458.,458.),color('#25313e'),(37.,0.,0.),'case')
        obstacles=tuple((m,_shape(m)) for m in (*self.meshes,divider))
        for level in ('eco','balanced','close'):
            old,_=add_auxiliary(spec,old_anchors,level);current,meta=add_auxiliary(spec,anchors,level)
            self.assertEqual(current,old);self.assertEqual(meta['rejected'],[])
            self.assertEqual(meta['device_counts']['psu'],1)
            for psu in current:
                if psu.component!='psu':continue
                shape=_shape(psu)
                for other,obstacle in obstacles:
                    # Actual PSU triangles and actual thin frame facets, not
                    # the big filled AABB enclosing a pierced base.
                    self.assertFalse(_surface_crossing(shape,obstacle),(level,psu.name,other.name))

    def test_actual_bottom_frames_rotors_and_connectors_keep_existing_mount_pose_all_lods(self):
        from assembly_cooling import add_cooling
        from assembly_case_shrouds052 import apply_layout_anchors
        rows=0;obstacles=tuple((m,_shape(m)) for m in self.meshes)
        for model,count in (('arctic-p12-pwm',3),('arctic-p14-pwm',2)):
            spec=dict(case=self.case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024')),
                cooling=dict(cpu_cooler='none',case_fans=[dict(model=model,mount='bottom',count=count,direction='intake')]))
            anchors=apply_layout_anchors(dict(case=self.case,case_dimensions=DIMENSIONS),spec,layout_reference(self.case,DIMENSIONS))
            for level in ('eco','balanced','close'):
                values,meta=add_cooling(self.meshes,spec,level,anchors)
                self.assertEqual(meta['rejected'],[]);self.assertEqual(len(meta['fans']),count)
                self.assertEqual(sum(m.rotor for m in values),count)
                self.assertEqual(sum(m.name=='case-fan-power-connector' for m in values),count)
                self.assertTrue(all(f['rpm'] is None and f['rotation_default']=='static' for f in meta['fans']))
                for mesh in values:
                    self.assertGreater(material._mesh_bounds(mesh)[0][1],self.meta['bottom_pan_top_world_y_mm'])
                    shape=_shape(mesh)
                    for other,obstacle in obstacles:
                        self.assertFalse(_surface_crossing(shape,obstacle),(model,level,mesh.name,other.name))
                self.assertEqual({f['position'][0] for f in meta['fans']},{-61.5})
                self.assertEqual({f['axis'] for f in meta['fans']},{(0.,-1.,0.)})
                if model=='arctic-p12-pwm' and level=='eco':
                    frames=[m for m in values if m.name=='case-fan-frame']
                    for legacy,point in (
                        (Mesh('historical-case-bottom',box(320.,3.,470.),color('#25313e'),(0.,-217.5,0.),'case'),
                         (-77.19079516851522,-216.00141421356238,179.99858578643762)),
                        (Mesh('historical-case-foot',box(23.,12.,30.),color('#25313e'),(-108.8,-229.,159.8),'case'),
                         (-120.29858578643764,-224.99858578643762,170.0556349186104))):
                        self.assertTrue(_inside(point,legacy))
                        self.assertTrue(any(_inside(point,frame) for frame in frames))
                        self.assertTrue(any(_surface_crossing(_shape(frame),_shape(legacy)) for frame in frames))
                rows+=1
        self.assertEqual(rows,6)


if __name__=='__main__':unittest.main()
