"""Exact original NV5/Evolv X2 material references; no scene or device work."""
from collections import Counter
import copy
import math
import unittest
from unittest.mock import patch

from assembly_auxiliary import _segment_triangle,add_auxiliary
from assembly_case_shrouds052 import apply_layout_anchors
from assembly_cooling import add_cooling
from assembly_phanteks_case052 import CASE_IDS,build,layout_reference
from assembly_style import apply_model_styles
from assembly_visibility048 import mesh_visible
from chassis_catalog import get_case

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
TONE=(.12,.14,.16,1.)


def dimensions(case):return tuple(float(case['dimensions_mm'][key]) for key in ('width','height','depth'))


def triangles(mesh):
    return tuple(tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3))
        for j in (0,6,12)) for i in range(0,len(mesh.vertices),18))


def hit(mesh,a,b):return any(_segment_triangle(a,b,t) for t in triangles(mesh))


def bounds(mesh):
    return tuple(tuple(op(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for op in (min,max))


def separated(a,b):
    return any(a[1][k]<=b[0][k]+1e-8 or b[1][k]<=a[0][k]+1e-8 for k in range(3))


def surface_separated_from_box(mesh,bb):
    if separated(bounds(mesh),bb):return True
    # A sufficient material proof, not treating an entire empty L/C bay as a
    # solid box. The helper's individual surface triangles must all separate.
    for t in triangles(mesh):
        tb=tuple(tuple(op(p[k] for p in t) for k in range(3)) for op in (min,max))
        if not separated(tb,bb):return False
    return True


class PhanteksCase052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure helper only')))

    def test_exact_identity_detached_parts_sources_and_invalid_inputs(self):
        self.assertEqual(CASE_IDS,('phanteks-nv5','phanteks-evolv-x2'))
        for identity,count in zip(CASE_IDS,(4,3)):
            case=get_case(identity);before=copy.deepcopy(case);dims=dimensions(case)
            meshes,meta=build(case,dims,TONE)
            self.assertEqual(case,before);self.assertEqual(len(meshes),count)
            self.assertEqual({m.part_id for m in meshes},{r['id'] for r in meta['parts']})
            self.assertTrue(meta['replaces_case_bottom'])
            self.assertIn('case:lower-support-floor',{m.part_id for m in meshes})
            self.assertIn('case:bottom-fan-bracket',{m.part_id for m in meshes})
            self.assertEqual(meta['source_model'],'PH-NV523TG_DBK01' if identity==CASE_IDS[0] else 'PH-ES524XTG_DBK01')
            for key in ('dimensions_verified','positions_verified','thickness_verified','cad_verified',
                        'chamber_is_solid','far_side_wall_added','selected_component_geometry_used','exact_vent_pattern_modeled'):
                self.assertIs(meta[key],False)
            for row in meta['parts']:
                self.assertEqual(row['component'],'case');self.assertEqual(row['assembly_state'],'installed')
                self.assertFalse(row['display_screen']);self.assertFalse(row['power_sensor_bound'])
                self.assertTrue(row['source_url'].startswith('https://phanteks.com/'))
            meta['parts'][0]['label']='detached'
            self.assertNotEqual(build(case,dims,TONE)[1]['parts'][0]['label'],'detached')
        self.assertEqual(build(get_case('fractal-north-mesh'),(215.,469.,447.),TONE),((),{}))
        for invalid in (None,(239.,528.),(True,528.,477.),(239.,float('nan'),477.),(239.,0.,477.)):
            self.assertEqual(build(get_case(CASE_IDS[0]),invalid,TONE),((),{}))
            self.assertEqual(layout_reference(get_case(CASE_IDS[0]),invalid),{})

    def test_closed_positive_materials_normals_and_sampled_open_holes(self):
        for identity in CASE_IDS:
            case=get_case(identity);meshes,_=build(case,dimensions(case),TONE)
            for mesh in meshes:
                edges=Counter();direction=Counter();volume=0.
                for i,(a,b,c) in enumerate(triangles(mesh)):
                    ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
                    n=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                    self.assertGreater(math.hypot(*n),1e-9,(identity,mesh.part_id))
                    stored=mesh.vertices[i*18+3:i*18+6]
                    self.assertAlmostEqual(math.hypot(*stored),1.)
                    self.assertGreater(sum(n[k]*stored[k] for k in range(3)),0.)
                    volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6.
                    rounded=[tuple(round(v,8) for v in p) for p in (a,b,c)]
                    for p,q in zip(rounded,(*rounded[1:],rounded[0])):
                        key=tuple(sorted((p,q)));edges[key]+=1;direction[key]+=1 if p<q else -1
                self.assertEqual(set(edges.values()),{2},(identity,mesh.part_id))
                self.assertEqual(set(direction.values()),{0},(identity,mesh.part_id))
                self.assertGreater(volume,100.);self.assertLess(volume,250000.)
            # The sample count denotes coarse original hexagonal apertures,
            # not a guessed catalogue of manufacturer perforations.
            tray=next(m for m in meshes if m.part_id=='case:bottom-fan-bracket')
            w,h,d=dimensions(case);top=layout_reference(case,(w,h,d))['mount_planes']['bottom']['position'][1]-1.
            z=d*.34-d*.29/4 if identity==CASE_IDS[0] else -5*(d-32.)/12
            self.assertFalse(hit(tray,(0.,top-3.,z),(0.,top+3.,z)))

    def test_empty_bays_retain_source_specific_flat_slope_and_elevated_tray(self):
        case=get_case(CASE_IDS[0]);w,h,d=dimensions(case);meshes,meta=build(case,(w,h,d),TONE)
        rear,front=meshes[:2];roof=-h*.275
        self.assertTrue(hit(rear,(0.,roof-3.,-d*.2),(0.,roof+3.,-d*.2)))
        self.assertFalse(hit(rear,(-w*.3,-h*.39,-d*.2),(w*.3,-h*.39,-d*.2)))
        self.assertTrue(hit(rear,(-w/2,-h*.39,-d*.2),(-w/2+10.,-h*.39,-d*.2)))
        self.assertFalse(hit(front,(0.,roof-3.,d*.17),(0.,roof+3.,d*.17)))
        self.assertTrue(meta['parts'][1]['factory_removable'])
        case=get_case(CASE_IDS[1]);w,h,d=dimensions(case);meshes,_=build(case,(w,h,d),TONE)
        side=meshes[0];top=-h*.225
        self.assertFalse(hit(side,(-w*.3,-h*.29,0.),(w*.3,-h*.29,0.)))
        self.assertTrue(hit(side,(-w/2,-h*.29,0.),(-w/2+10.,-h*.29,0.)))
        self.assertTrue(hit(side,(0.,-h*.29,d/2-15.),(0.,-h*.29,d/2-10.)))
        tray=next(m for m in meshes if m.part_id=='case:bottom-fan-bracket')
        self.assertAlmostEqual(max(tray.vertices[1::6]),top)
        self.assertGreater(top-(-h*.385+86.),7.)

    def test_fixed_reference_planes_psu_faces_and_board_pose_do_not_claim_factory_dimensions(self):
        for identity in CASE_IDS:
            case=get_case(identity);w,h,d=dimensions(case);layout=layout_reference(case,(w,h,d))
            self.assertFalse(layout['positions_verified']);self.assertFalse(layout['psu_fan_orientation_verified'])
            self.assertEqual(layout['psu']['basis'],((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)))
            self.assertEqual(layout['psu']['rear_z_mm'],-d/2+10.)
            plane=layout['mount_planes']['bottom']
            self.assertEqual(plane['normal'],(0.,-1.,0.));self.assertEqual(plane['up'],(0.,0.,1.))
            self.assertFalse(plane['positions_verified']);self.assertFalse(plane['normal_verified'])
            if identity==CASE_IDS[0]:
                self.assertEqual(plane['position'],(0.,-h/2+20.,d*.34))
                self.assertFalse(layout['board_pose_changed'])
                self.assertEqual(layout['mount_planes']['side']['position'],(w/2-10.,0.,d*.32))
            else:
                self.assertEqual(layout['board_y_mm'],h*.07)
                self.assertEqual(layout['psu']['floor_y_mm'],-h*.385)

    def test_six_styles_share_physical_arrays_and_cover_visibility_keeps_supports(self):
        for identity in CASE_IDS:
            case=get_case(identity);dims=dimensions(case);meshes,meta=build(case,dims,TONE)
            for style in SIX:
                styled,_=apply_model_styles(meshes,style,{},dims,case['panels'])
                for before,after in zip(meshes,styled):
                    self.assertIs(before.vertices,after.vertices)
                    self.assertEqual((before.position,before.axis,before.part_id),(after.position,after.axis,after.part_id))
            for mesh,row in zip(meshes,meta['parts']):
                self.assertTrue(mesh_visible(mesh,True,False))
                self.assertEqual(mesh_visible(mesh,True,True),row['kind']!='case_cover')

    def test_actual_rm1000x_all_children_three_lods_clear_fixed_support_and_skin(self):
        # The public auxiliary producer adds real grille/fastener envelopes;
        # checking only its 86-mm nominal body would miss their protrusion.
        for identity in CASE_IDS:
            case=get_case(identity);dims=dimensions(case);materials,_=build(case,dims,TONE)
            spec=dict(case=case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=False))
            anchors=apply_layout_anchors(dict(case=case,case_dimensions=dims),spec,layout_reference(case,dims))
            for level in ('eco','balanced','close'):
                meshes,meta=add_auxiliary(spec,anchors,level)
                self.assertEqual(meta['rejected'],[])
                supply=[m for m in meshes if m.component=='psu']
                self.assertEqual(sum(m.name=='psu-shell' for m in supply),1)
                self.assertTrue(any(m.name=='psu-fan-panel' for m in supply))
                self.assertTrue(any(m.name=='psu-fan-panel-fasteners' for m in supply))
                self.assertGreater(min(bounds(m)[0][1] for m in supply)-
                    max(materials[-2 if identity==CASE_IDS[0] else 1].vertices[1::6]),.57)
                for mesh in supply:
                    for material in materials:
                        self.assertTrue(surface_separated_from_box(material,bounds(mesh)),
                            (identity,level,mesh.name,material.part_id))

    def test_actual_supported_fan_banks_three_lods_keep_frames_rotors_and_real_material_gaps(self):
        for identity in CASE_IDS:
            case=get_case(identity);dims=dimensions(case);materials,_=build(case,dims,TONE)
            planes=layout_reference(case,dims)['mount_planes']
            anchors=dict(case=case,case_dimensions=dims,case_mount_planes=planes)
            requested=[('bottom',1),('side',3)] if identity==CASE_IDS[0] else [('bottom',3)]
            for level in ('eco','balanced','close'):
                for mount,count in requested:
                    spec=dict(case=case,cooling=dict(cpu_cooler='none',case_fans=[dict(model='arctic-p12-pwm',mount=mount,count=count)]))
                    meshes,meta=add_cooling(materials,spec,level,anchors)
                    self.assertEqual(meta['rejected'],[],(identity,level,mount))
                    frames=[m for m in meshes if m.name=='case-fan-frame']
                    rotors=[m for m in meshes if m.rotor]
                    self.assertEqual(len(frames),count);self.assertEqual(len(rotors),count)
                    self.assertEqual({m.part_id for m in frames},{'fans:'+mount+':'+str(i) for i in range(count)})
                    for mesh in meshes:
                        if any(word in mesh.name for word in ('wire','lead','connector')):continue
                        for material in materials:
                            self.assertTrue(surface_separated_from_box(material,bounds(mesh)),
                                (identity,level,mount,mesh.name,material.part_id))


if __name__=='__main__':unittest.main()
