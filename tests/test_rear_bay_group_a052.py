"""Source-bounded thin rear structures; no Scene, GUI or hardware creation."""
import copy
import json
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,box,color
from assembly_rear_bay_group_a052 import CASE_IDS,build,layout_reference
from chassis_catalog import CASES,get_case
import test_shroud_other052 as material


STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
RAYS=((1.,.173,.317),(.317,1.,.173),(.173,.317,1.))


def _dimensions(case):return tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))


def _inside(point,mesh):
    triangles=material._world(mesh)
    return all(material._ray_inside(point,triangles,direction) for direction in RAYS)


def _shape(mesh):
    triangles=material._world(mesh)
    return triangles,tuple(material._bounds(t) for t in triangles),material._mesh_bounds(mesh)


def _overlap(a,b,*,strict=False):
    return all(a[1][k]>b[0][k] and b[1][k]>a[0][k] for k in range(3)) if strict else all(
        a[1][k]>=b[0][k] and b[1][k]>=a[0][k] for k in range(3))


def _material_collision(first,second,stats=None):
    """Actual facets plus three-ray interior witnesses, not filled bounds.

    This finite material check is not a manufacturing-clearance certificate.
    Strict mesh bounds reject only separated volumes; every surviving surface
    candidate receives triangle SAT and containment samples use actual facets.
    """
    aa,ab,aw=first;ba,bb,bw=second
    if not _overlap(aw,bw,strict=True):return False
    if stats is not None:stats['mesh_candidates']+=1
    for tri,bounds in zip(aa,ab):
        if stats is not None:stats['facet_bound_checks']+=1
        if not _overlap(bounds,bw):continue
        for other,other_bounds in zip(ba,bb):
            if stats is not None:stats['facet_bound_checks']+=1
            if not _overlap(bounds,other_bounds):continue
            if stats is not None:stats['triangle_candidates']+=1
            if material._surface_intersection(tri,other):return True
    for triangles,other,limits in ((aa,ba,bw),(ba,aa,aw)):
        for triangle in triangles:
            center=tuple(sum(p[k] for p in triangle)/3 for k in range(3))
            if not all(limits[0][k]<center[k]<limits[1][k] for k in range(3)):continue
            n=material._cross(material._sub(triangle[1],triangle[0]),material._sub(triangle[2],triangle[0]))
            length=math.sqrt(material._dot(n,n))
            if length<1.e-12:continue
            for sign in (-1.,1.):
                point=tuple(center[k]+sign*1.e-5*n[k]/length for k in range(3))
                if all(material._ray_inside(point,other,ray) for ray in RAYS):return True
    return False


def _actual_auxiliary(case,dimensions,level):
    from assembly_auxiliary import add_auxiliary
    from assembly_case_shrouds052 import apply_layout_anchors
    spec=dict(case=case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=False))
    anchors=apply_layout_anchors(dict(case=case,case_dimensions=dimensions,connectors={}),
        spec,layout_reference(case,dimensions))
    values,meta=add_auxiliary(spec,anchors,level)
    return spec,anchors,values,meta


class RearBayGroupA052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start',
                     'assembly_geometry.build_scene'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure construction only')))
        self.rows=[]
        for identity in CASE_IDS:
            case=get_case(identity);dimensions=_dimensions(case)
            meshes,meta=build(case,dimensions,color('#25313e'))
            self.rows.append((case,dimensions,meshes,meta))

    def test_exact_five_variants_only_fixed_and_detached(self):
        self.assertEqual(len(CASE_IDS),5)
        for case in CASES:
            if case['id'] not in CASE_IDS:
                self.assertEqual(build(case,_dimensions(case),color('#25313e')),((),{}))
                self.assertEqual(layout_reference(case,_dimensions(case)),{})
        for case,dimensions,meshes,meta in self.rows:
            before=copy.deepcopy(case)
            changed=copy.deepcopy(case)
            changed.update(selected_fan={'depth':500},selected_psu={'length':500},selected_gpu={'width':500})
            self.assertEqual(build(changed,dimensions,color('#25313e')),(meshes,meta))
            self.assertEqual(case,before)
            other=build(case,dimensions,color('#25313e'))[1]
            other['parts'][0]['positions_verified']=True
            self.assertFalse(build(case,dimensions,color('#25313e'))[1]['parts'][0]['positions_verified'])
            for bad in (None,(True,435,415),(287,float('nan'),415),(287,435,10000),(287,435)):
                self.assertEqual(build(case,bad,color('#25313e')),((),{}))
            json.dumps(meta,allow_nan=False)

    def test_official_identity_and_unverified_manufacturing_are_never_upgraded(self):
        for case,_,meshes,meta in self.rows:
            self.assertTrue(meta['replaces_rear_chamber_shroud']);self.assertTrue(meta['replaces_case_bottom'])
            self.assertEqual(meta['replaced_generic_mesh_names'],('rear-chamber-shroud','case-bottom'))
            self.assertEqual({m.part_id for m in meshes},{p['id'] for p in meta['parts']})
            self.assertTrue(all(p['kind']=='case_structure' and p['model_id']==case['id'] for p in meta['parts']))
            self.assertTrue(all(s.startswith('https://') for s in meta['source_urls']))
            for flag in ('dimensions_verified','positions_verified','thickness_verified','cad_verified',
                         'chamber_is_solid','psu_chamber_is_solid','selected_component_geometry_used',
                         'exact_vent_pattern_modeled'):
                self.assertIs(meta[flag],False)
            self.assertFalse(any(m.name in ('rear-chamber-shroud','case-bottom') for m in meshes))
        by_id={c['id']:m for c,_,_,m in self.rows}
        self.assertEqual(by_id['nzxt-h6-flow-2023']['source_variant'],'2023_231027_v2')
        self.assertEqual(by_id['asus-tuf-gt502']['source_variant'],'original_non_horizon')
        self.assertFalse(any('y70' in s for s in by_id['hyte-y60']['source_urls']))

    def test_psu_interfaces_distinguish_upper_h6_and_four_lower_bays(self):
        from assembly_case_shrouds052 import apply_layout_anchors
        for case,dimensions,_,meta in self.rows:
            w,h,d=dimensions;layout=layout_reference(case,dimensions);psu=layout['psu']
            self.assertEqual(psu['basis'],((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)))
            self.assertEqual(psu['boundary_x_mm'],w/2-10.)
            self.assertEqual(psu['rear_z_mm'],-d/2+10.)
            spec=dict(case=case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024')))
            anchors=apply_layout_anchors(dict(case=case,case_dimensions=dimensions),spec,layout)
            self.assertEqual(anchors['psu']['world_dimensions_mm'],(86.,150.,160.))
            low,high=meta['psu_reference_bounds_mm']
            self.assertEqual(tuple((a+b)/2 for a,b in zip(low,high)),anchors['psu']['position'])
            self.assertGreater(low[0],w*.10+6.)
            if case['id']=='nzxt-h6-flow-2023':
                self.assertIn('ceiling_y_mm',psu);self.assertNotIn('floor_y_mm',psu)
                self.assertGreater(low[1],0.);self.assertEqual(meta['psu_bay'],'upper_rear')
            else:
                self.assertIn('floor_y_mm',psu);self.assertNotIn('ceiling_y_mm',psu)
                self.assertLess(high[1],0.);self.assertEqual(meta['psu_bay'],'lower_rear')
            self.assertFalse(layout['positions_verified']);self.assertFalse(layout['board_datum_changed'])
        lian=layout_reference(get_case(CASE_IDS[0]),_dimensions(get_case(CASE_IDS[0])))
        self.assertEqual(lian['source_rear_bracket_projection_mm'],15.)
        self.assertFalse(lian['source_rear_bracket_projection_applied_to_psu_pose'])

    def test_actual_psu_volume_is_open_and_rear_frame_is_not_a_filled_cap(self):
        for _,_,meshes,meta in self.rows:
            low,high=meta['psu_reference_bounds_mm'];center=tuple((a+b)/2 for a,b in zip(low,high))
            for mesh in meshes:self.assertFalse(_inside(center,mesh),(meta['case_id'],mesh.name))
            frame=next(m for m in meshes if m.part_id=='case:psu-rear-frame')
            mouth=(center[0],center[1],low[2]-1.5)
            self.assertFalse(_inside(mouth,frame))
            self.assertTrue(_inside((low[0]-2.5,center[1],mouth[2]),frame))
            bearing=next(m for m in meshes if m.part_id=='case:psu-bearing-lands')
            self.assertTrue(_inside((low[0]+8.,low[1]-1.2,low[2]+62.),bearing))
            self.assertLess(material._mesh_bounds(bearing)[1][1],low[1])

    def test_fixed_open_floor_has_real_void_and_psu_floor_material_below_mount(self):
        for case,dimensions,meshes,meta in self.rows:
            w,h,_=dimensions;floor=next(m for m in meshes if m.part_id=='case:open-floor')
            plane=layout_reference(case,dimensions)['mount_planes']['bottom']
            self.assertEqual(plane['normal'],(0.,-1.,0.));self.assertEqual(plane['up'],(0.,0.,1.))
            self.assertEqual(plane['position'][1],-h/2+20.25)
            self.assertGreater(plane['position'][1],meta['bottom_pan_top_world_y_mm'])
            self.assertFalse(plane['positions_verified']);self.assertFalse(plane['mounting_hole_positions_verified'])
            hole=meta['intake_openings_xz_reference'][1]
            x=sum(p[0] for p in hole)/len(hole);z=sum(p[1] for p in hole)/len(hole)
            self.assertFalse(_inside((x,-h/2+18.4,z),floor))
            self.assertTrue(_inside((w/2-20.,-h/2+18.4,-30.),floor))
            low=meta['psu_reference_bounds_mm'][0]
            self.assertGreater(low[1],meta['bottom_pan_top_world_y_mm'])
            # No borrowed Y70 limit or current fan dimensions enter this plane.
            self.assertNotIn('source_max_fan_depth_mm',plane)

    def test_distinct_observed_storage_and_hybrid_frames_remain_empty(self):
        for case,_,meshes,meta in self.rows:
            rows=[p for p in meta['parts'] if p['id'] in ('case:storage-frame','case:rear-hybrid-bracket')]
            self.assertEqual(len(rows),1)
            row=rows[0];mesh=next(m for m in meshes if m.part_id==row['id'])
            bounds=material._mesh_bounds(mesh);center=tuple((a+b)/2 for a,b in zip(*bounds))
            self.assertFalse(_inside(center,mesh))
            if case['id']=='asus-tuf-gt502':
                self.assertEqual(row['source_capacity_mm'],360.);self.assertFalse(row['installed_accessories'])
            else:
                self.assertFalse(row['drive_devices_installed']);self.assertFalse(row['exact_storage_revision_verified'])
                psu_low,psu_high=meta['psu_reference_bounds_mm']
                if case['id']=='nzxt-h6-flow-2023':self.assertLess(bounds[1][1],psu_low[1])
                else:self.assertGreater(bounds[0][1],psu_high[1])

    def test_finite_nondegenerate_outward_facets_and_bounded_geometry(self):
        for case,dimensions,meshes,_ in self.rows:
            count=0;w,h,d=dimensions
            for mesh in meshes:
                self.assertEqual(mesh.component,'case');self.assertFalse(mesh.rotor)
                self.assertEqual(mesh.position,(0.,0.,0.));self.assertEqual(len(mesh.vertices)%18,0)
                count+=len(mesh.vertices)//18
                for at,triangle in zip(range(0,len(mesh.vertices),18),material._world(mesh)):
                    face=material._cross(material._sub(triangle[1],triangle[0]),material._sub(triangle[2],triangle[0]))
                    self.assertGreater(material._dot(face,face),1.e-16,(case['id'],mesh.name))
                    for offset in (0,6,12):
                        normal=mesh.vertices[at+offset+3:at+offset+6]
                        self.assertAlmostEqual(material._dot(normal,normal),1.,places=8)
                        self.assertGreater(material._dot(face,normal),0.)
                    for p in triangle:
                        self.assertTrue(all(math.isfinite(v) for v in p))
                        self.assertTrue(-w/2<=p[0]<=w/2 and -h/2<=p[1]<=h/2 and -d/2<=p[2]<=d/2)
            self.assertLessEqual(count,1800);self.assertLessEqual(len(meshes),6)

    def test_six_styles_share_every_source_physical_array(self):
        from assembly_style import apply_model_styles
        for case,dimensions,meshes,_ in self.rows:
            for style in STYLES:
                values,meta=apply_model_styles(meshes,style,{},dimensions,case['panels'])
                physical=[m for m in values if not m.name.startswith('style-')]
                self.assertEqual(meta['visual_style'],style);self.assertEqual(len(physical),len(meshes))
                for actual,original in zip(physical,meshes):
                    self.assertIs(actual.vertices,original.vertices)
                    self.assertEqual((actual.part_id,actual.position,actual.axis,actual.rotor),
                                     (original.part_id,original.position,original.axis,original.rotor))

    def test_actual_rm1000x_every_submesh_three_lods_against_thin_material(self):
        stats=dict(mesh_candidates=0,facet_bound_checks=0,triangle_candidates=0);rows=0
        for case,dimensions,meshes,meta in self.rows:
            obstacles=tuple((m,_shape(m)) for m in meshes)
            for level in ('eco','balanced','close'):
                _,anchors,values,aux=_actual_auxiliary(case,dimensions,level)
                self.assertEqual(aux['rejected'],[]);self.assertEqual(aux['device_counts']['psu'],1)
                selected=[m for m in values if m.component=='psu']
                self.assertEqual(len(selected),len(values));self.assertTrue(selected)
                self.assertEqual({m.part_id for m in selected},{'psu:0'})
                names={m.name for m in selected}
                for required in ('psu-shell','psu-fan-panel','psu-fan-blades','psu-fan-hub',
                                 'psu-rear-io-frame','psu-modular-connector-panel'):
                    self.assertIn(required,names)
                lo,hi=meta['psu_reference_bounds_mm']
                self.assertEqual(anchors['psu']['position'],tuple((a+b)/2 for a,b in zip(lo,hi)))
                for psu in selected:
                    shape=_shape(psu)
                    for structure,other in obstacles:
                        self.assertFalse(_material_collision(shape,other,stats),
                            (case['id'],level,psu.name,structure.name))
                # The rear ring's AABB encloses the mouth. Testing its true
                # material rather than treating that AABB as a plug matters.
                self.assertEqual(len(meta['parts']),4)
                self.assertFalse(any(p.get('drive_devices_installed') for p in meta['parts']))
                rows+=1
        self.assertEqual(rows,15)
        self.assertGreater(stats['mesh_candidates'],0)
        # Surviving mesh bounds enclose open space. The actual facets may all
        # be separated before SAT; requiring a SAT candidate invents contact.
        self.assertGreater(stats['facet_bound_checks'],0)

    def test_actual_declared_bottom_fans_all_lods_rotors_leads_psu_and_source_material(self):
        from assembly_cooling import add_cooling
        # The exact GT502 manual printed35 confirms three bottom120 fans.
        # No140 bottom capacity is inferred from the separate top140 bank.
        groups={'lian-li-o11d-evo-rgb':(('arctic-p12-pwm',3),('arctic-p14-pwm',3)),
                'nzxt-h6-flow-2023':(('arctic-p14-pwm',2),),
                'corsair-6500x':(('arctic-p12-pwm',3),('arctic-p14-pwm',3)),
                'hyte-y60':(('arctic-p12-pwm',2),('arctic-p14-pwm',2)),
                'asus-tuf-gt502':(('arctic-p12-pwm',3),)}
        rows=0
        for case,dimensions,meshes,meta in self.rows:
            fixtures={}
            for model,count in groups.get(case['id'],()):
                for level in ('eco','balanced','close'):
                    if level not in fixtures:fixtures[level]=_actual_auxiliary(case,dimensions,level)
                    base,anchors,psu,aux=fixtures[level];spec=dict(base)
                    spec['cooling']=dict(cpu_cooler='none',case_fans=[dict(model=model,mount='bottom',count=count,direction='intake')])
                    additions,cooling=add_cooling((*meshes,*psu),spec,level,anchors)
                    self.assertEqual(cooling['rejected'],[],(case['id'],model,level,cooling['rejected']))
                    self.assertEqual(len(cooling['fans']),count)
                    self.assertEqual(sum(m.rotor for m in additions),count)
                    self.assertEqual(sum(m.name=='case-fan-power-connector' for m in additions),count)
                    self.assertEqual(len({m.part_id for m in additions}),count)
                    self.assertTrue(all(f['rpm'] is None and f['rotation_default']=='static' for f in cooling['fans']))
                    self.assertEqual(len(cooling['parts']),count)
                    self.assertTrue(all(f['compatibility']=='documented_fan_mount' for f in cooling['parts']))
                    obstacles=tuple((m,_shape(m)) for m in (*meshes,*psu))
                    for fan in additions:
                        self.assertGreater(material._mesh_bounds(fan)[0][1],meta['bottom_pan_top_world_y_mm'])
                        shape=_shape(fan)
                        for structure,other in obstacles:
                            self.assertFalse(_material_collision(shape,other),(case['id'],model,level,fan.name,structure.name))
                    self.assertEqual(aux['device_counts']['psu'],1);rows+=1
        self.assertEqual(rows,24)
        gt502=next(row for row in self.rows if row[0]['id']=='asus-tuf-gt502')
        bottom=gt502[3]['layout_reference']['mount_planes']['bottom']
        self.assertTrue(bottom['source_capacity_verified'])
        self.assertEqual(bottom['source_capacity_count_by_size_mm'],{'120':3})

    def test_gt502_source_top_bank_all_lods_clears_intact_tray_with_every_fan_detail(self):
        from assembly_cooling import add_cooling
        case=get_case('asus-tuf-gt502');dims=_dimensions(case);w,h,d=dims
        meshes,_=build(case,dims,color('#25313e'));layout=layout_reference(case,dims)
        plane=layout['mount_planes']['top'];self.assertEqual(plane['normal'],(0.,1.,0.))
        self.assertEqual(plane['source_manual_pdf_pages'],(37,38))
        self.assertEqual(plane['source_capacity_count_by_size_mm'],{'120':3,'140':2})
        self.assertLess(plane['position'][0],0.)
        divider=Mesh('intact-full-height-tray',box(2.,h-12.,d-12.),color('#25313e'),(w*.10+5.,0.,0.),'case')
        for model,count in (('arctic-p12-pwm',3),('arctic-p14-pwm',2)):
            for level in ('eco','balanced','close'):
                spec,anchors,psu,_=_actual_auxiliary(case,dims,level)
                spec['cooling']=dict(cpu_cooler='none',case_fans=[dict(model=model,mount='top',count=count,direction='exhaust')])
                values,meta=add_cooling((*meshes,*psu),spec,level,anchors)
                self.assertEqual(meta['rejected'],[]);self.assertEqual(len(meta['fans']),count)
                self.assertEqual(sum(m.rotor for m in values),count)
                self.assertEqual(sum(m.name=='case-fan-power-connector' for m in values),count)
                obstacles=tuple(_shape(m) for m in (*meshes,*psu,divider))
                for fan in values:
                    shape=_shape(fan)
                    for obstacle in obstacles:self.assertFalse(_material_collision(shape,obstacle),(model,level,fan.name))

    def test_material_checker_catches_real_overlap_but_keeps_empty_frame_void(self):
        case,dimensions,meshes,meta=next(row for row in self.rows if row[0]['id']=='nzxt-h6-flow-2023')
        storage=next(m for m in meshes if m.part_id=='case:storage-frame')
        first=material._world(storage)[0]
        point=tuple(sum(p[k] for p in first)/3 for k in range(3))
        control=Mesh('strict-overlap-control',box(1.,1.,1.),color('#25313e'),point,'psu')
        self.assertTrue(_material_collision(_shape(control),_shape(storage)))
        # An actual box can occupy a pierced rear mouth without touching ring
        # material even though both mesh bounds positively overlap in 3D.
        frame=next(m for m in meshes if m.part_id=='case:psu-rear-frame')
        low,high=meta['psu_reference_bounds_mm']
        mouth=((low[0]+high[0])/2,(low[1]+high[1])/2,low[2]-1.5)
        void=Mesh('open-mouth-control',box(20.,20.,.5),color('#25313e'),mouth,'psu')
        self.assertTrue(_overlap(_shape(void)[2],_shape(frame)[2],strict=True))
        self.assertFalse(_material_collision(_shape(void),_shape(frame)))
        self.assertGreater(low[1],material._mesh_bounds(storage)[1][1])


if __name__=='__main__':unittest.main()
