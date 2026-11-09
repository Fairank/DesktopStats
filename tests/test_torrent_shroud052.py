"""Torrent's actual open material references; no Qt, device or whole-host QA."""
from collections import Counter,defaultdict
import copy
import math
import unittest
from unittest.mock import patch

from assembly_auxiliary import add_auxiliary,_segment_triangle
from assembly_cooling import add_cooling
from assembly_geometry import Mesh,box,build_scene
from assembly_case_shrouds052 import apply_layout_anchors
from assembly_style import apply_model_styles
from assembly_torrent_shroud052 import CASE_ID,MANUAL,build,layout_reference
from assembly_visibility048 import mesh_visible
from chassis_catalog import CASES,get_case

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
DIMENSIONS=(242.,530.,544.)
TONE=(.1,.2,.3,1.)


def triangles(mesh):
    return tuple(tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3))
        for j in (0,6,12)) for i in range(0,len(mesh.vertices),18))


def bounds(mesh):
    return tuple(tuple(op(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for op in (min,max))


def hit(mesh,a,b):return any(_segment_triangle(a,b,t) for t in triangles(mesh))


def separated(first,second):
    return any(first[1][k]<=second[0][k] or second[1][k]<=first[0][k] for k in range(3))


def every_surface_triangle_separated(mesh,body_bounds):
    # Strict per-triangle box separation is a sufficient proof of no crossing;
    # it is not an assertion that overlapping compartment AABBs are solid.
    for triangle in triangles(mesh):
        b=tuple(tuple(op(p[k] for p in triangle) for k in range(3)) for op in (min,max))
        if not separated(b,body_bounds):return False
    return True


class TorrentShroud052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure construction only')))
        self.case=get_case(CASE_ID)

    def test_exact_only_reference_parts_detached_metadata_and_invalid_dimensions(self):
        for case in CASES:
            dims=tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))
            before=copy.deepcopy(case);meshes,meta=build(case,dims,TONE)
            self.assertEqual(case,before)
            if case['id']!=CASE_ID:
                self.assertEqual((meshes,meta),((),{}));self.assertEqual(layout_reference(case,dims),{});continue
            self.assertEqual(len(meshes),2)
            self.assertEqual({m.part_id for m in meshes},{'case:psu-top-cover','case:bottom-intake-frame'})
            self.assertEqual({m.part_id for m in meshes},{r['id'] for r in meta['parts']})
            self.assertTrue(meta['replaces_case_bottom']);self.assertTrue(meta['replaces_top_psu_shroud'])
            for key in ('dimensions_verified','positions_verified','thickness_verified','cad_verified',
                        'chamber_is_solid','far_side_wall_added','selected_component_geometry_used'):
                self.assertIs(meta[key],False)
            self.assertTrue(all(r['assembly_state']=='installed' and r['component']=='case' for r in meta['parts']))
            self.assertEqual([r['kind'] for r in meta['parts']],['case_cover','case_structure'])
            self.assertIn(MANUAL,meta['source_urls'])
            meta['parts'][0]['label']='local mutation'
            self.assertNotEqual(build(case,dims,TONE)[1]['parts'][0]['label'],'local mutation')
        for value in (None,(242.,530.),(True,530.,544.),(242.,float('nan'),544.),(242.,530.,-1.)):
            self.assertEqual(build(self.case,value,TONE),((),{}));self.assertEqual(layout_reference(self.case,value),{})

    def test_both_materials_closed_connected_outward_nondegenerate_and_bounded(self):
        for mesh in build(self.case,DIMENSIONS,TONE)[0]:
            edges=Counter();direction=Counter();edge_faces=defaultdict(list);volume=0.
            ts=triangles(mesh)
            for i,(a,b,c) in enumerate(ts):
                ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
                n=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                self.assertGreater(math.hypot(*n),1e-8)
                stored=mesh.vertices[i*18+3:i*18+6]
                self.assertAlmostEqual(math.hypot(*stored),1.)
                self.assertGreater(sum(n[k]*stored[k] for k in range(3)),0.)
                volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6.
                for p,q in ((a,b),(b,c),(c,a)):
                    key=tuple(sorted((p,q)));edges[key]+=1;direction[key]+=1 if p<q else -1;edge_faces[key].append(i)
            self.assertEqual(set(edges.values()),{2});self.assertEqual(set(direction.values()),{0})
            self.assertGreater(volume,1000.);self.assertLess(volume,150000.)
            graph=defaultdict(set)
            for a,b in edge_faces.values():graph[a].add(b);graph[b].add(a)
            seen=set();pending=[0]
            while pending:
                n=pending.pop()
                if n not in seen:seen.add(n);pending.extend(graph[n]-seen)
            self.assertEqual(len(seen),len(ts))
        self.assertEqual(sum(m.vertex_count//3 for m in build(self.case,DIMENSIONS,TONE)[0]),256)

    def test_short_empty_psu_bay_rising_end_intake_and_three_bottom_windows(self):
        (cover,bracket),meta=build(self.case,DIMENSIONS,TONE)
        # Do not hide a full-depth cuboid by colouring it: the front and the
        # rear PSU compartment interior must really contain no triangles.
        self.assertLess(bounds(cover)[1][2],50.)
        self.assertFalse(hit(cover,(-90.,210.,-180.),(90.,210.,-180.)))
        self.assertFalse(hit(cover,(90.,210.,-180.),(120.,210.,-180.)))
        self.assertTrue(hit(cover,(-118.,210.,-180.),(-112.,210.,-180.)))
        self.assertFalse(hit(cover,(0.,150.,-180.),(0.,170.,-180.)))
        self.assertTrue(hit(cover,(90.,150.,-180.),(90.,170.,-180.)))
        self.assertFalse(hit(cover,(0.,140.,245.),(0.,260.,245.)))
        self.assertGreater(meta['rising_floor_end_y_mm'],meta['rear_floor_y_mm'])
        for z in (-170.,0.,170.):self.assertFalse(hit(bracket,(0.,-252.,z),(0.,-240.,z)))
        self.assertTrue(hit(bracket,(100.,-252.,0.),(100.,-240.,0.)))
        self.assertTrue(meta['psu_intake_ventilation_observed'])
        self.assertFalse(meta['psu_intake_exact_pattern_modeled'])
        self.assertTrue(meta['source_top_shroud_argb_strip_observed'])
        self.assertFalse(meta['top_shroud_lighting_modeled'])

    def test_actual_front_and_bottom_three_fan_groups_all_lods_clear_real_material(self):
        covers,_=build(self.case,DIMENSIONS,TONE)
        layout=layout_reference(self.case,DIMENSIONS)
        anchors=dict(case=self.case,case_dimensions=DIMENSIONS,case_mount_planes=layout['mount_planes'])
        for level in ('eco','balanced','close'):
            for size,model in ((120,'arctic-p12-pwm'),(140,'arctic-p14-pwm')):
                for mount in ('front','bottom'):
                    spec=dict(case=self.case,cooling=dict(cpu_cooler='none',case_fans=[dict(model=model,mount=mount,count=3)]))
                    before=copy.deepcopy(spec);meshes,meta=add_cooling(covers,spec,level,anchors)
                    self.assertEqual(spec,before);self.assertEqual(meta['rejected'],[])
                    frames=[m for m in meshes if m.name=='case-fan-frame']
                    self.assertEqual(len(frames),3)
                    self.assertEqual({m.part_id for m in frames},{'fans:'+mount+':'+str(i) for i in range(3)})
                    self.assertEqual(sum(r['kind']=='case_fan' for r in meta['parts']),3)
                    for frame in frames:
                        for material in covers:
                            self.assertTrue(separated(bounds(frame),bounds(material)),(level,size,mount,frame.part_id,material.name))
                    if mount=='bottom':
                        for frame in frames:self.assertAlmostEqual(bounds(frame)[0][1],-246.)
                        self.assertGreater(min(bounds(f)[0][1] for f in frames)-bounds(covers[1])[1][1],.99)

    def test_actual_rm1000x_and_two_generic_top_psu_controls_without_moving_supply(self):
        cover=build(self.case,DIMENSIONS,TONE)[0][0]
        base_anchors=dict(case=self.case,case_dimensions=DIMENSIONS)
        for level in ('eco','balanced','close'):
            spec=dict(case=self.case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=False))
            anchors=apply_layout_anchors(base_anchors,spec,layout_reference(self.case,DIMENSIONS))
            meshes,meta=add_auxiliary(spec,anchors,level)
            self.assertEqual(meta['rejected'],[])
            shell=next(m for m in meshes if m.name=='psu-shell')
            self.assertEqual((shell.position[0],shell.position[2]),(0.,-182.))
            self.assertAlmostEqual(shell.position[1],212.15)
            self.assertGreater(min(bounds(m)[0][1] for m in meshes if m.component=='psu')
                               -(DIMENSIONS[1]*.315+1.2),.57)
            self.assertLess(max(bounds(m)[1][1] for m in meshes if m.component=='psu'),263.)
            for mesh in meshes:
                if mesh.component=='psu':self.assertTrue(every_surface_triangle_separated(cover,bounds(mesh)),mesh.name)
            self.assertFalse(hit(cover,(0.,150.,shell.position[2]),(0.,166.,shell.position[2])))
            for length in (140.,230.):
                control=Mesh('generic-top-envelope',box(150.,86.,length),TONE,(0.,212.15,-272.+length/2+10.),'psu')
                self.assertTrue(every_surface_triangle_separated(cover,bounds(control)))
                self.assertTrue(separated(bounds(control),bounds(build(self.case,DIMENSIONS,TONE)[0][1])))
        self.assertFalse(layout_reference(self.case,DIMENSIONS)['board_pose_changed'])

    def test_public_default_atx_pcb_keeps_its_pose_and_clears_the_fixed_upper_floor(self):
        # This is the real public builder's default 305x244 ATX reference PCB,
        # not a claim that a simplified board covers every VRM/IO envelope.
        scene=build_scene(dict(case=self.case,gpu=dict(present=False),memory=dict(count=0),
            board=dict(dimensions_mm=dict(height=305.,width=244.),form_factor='atx'),
            cooling=dict(cpu_cooler='none'),detail_level='eco'))
        pcb=next(m for m in scene.meshes if m.name=='motherboard-reference')
        self.assertEqual(pcb.position,(242.*.36,530.*.02,-136.))
        cover=next(m for m in scene.meshes if m.part_id=='case:psu-top-cover')
        self.assertGreater(bounds(cover)[0][1]-bounds(pcb)[1][1],3.8)
        self.assertTrue(separated(bounds(cover),bounds(pcb)))

    def test_six_styles_share_material_arrays_and_shared_psu_visibility_keeps_bracket(self):
        meshes,_=build(self.case,DIMENSIONS,TONE)
        self.assertTrue(mesh_visible(meshes[0],True,False));self.assertFalse(mesh_visible(meshes[0],True,True))
        for cutaway in (False,True):
            for show in (False,True):self.assertTrue(mesh_visible(meshes[1],cutaway,show))
        for style in SIX:
            styled,_=apply_model_styles(meshes,style,{},DIMENSIONS,self.case['panels'])
            for original,actual in zip(meshes,styled):
                self.assertIs(actual.vertices,original.vertices)
                self.assertEqual((actual.position,actual.axis,actual.rotor,actual.part_id),
                                 (original.position,original.axis,original.rotor,original.part_id))
        layout=layout_reference(self.case,DIMENSIONS);plane=layout['mount_planes']['bottom']
        self.assertEqual(plane['normal'],(0.,-1.,0.));self.assertEqual(plane['up'],(0.,0.,1.))
        self.assertFalse(plane['positions_verified']);self.assertFalse(plane['normal_verified'])
        self.assertEqual(plane['position'][1],bounds(meshes[1])[1][1]+1.)


if __name__=='__main__':unittest.main()
