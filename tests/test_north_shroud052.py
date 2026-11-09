"""Observed North XL cover surfaces and real fan clearance; no GUI or devices."""
from collections import Counter,defaultdict
from dataclasses import replace
import copy
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,Scene,box,build_scene,color
from assembly_north_tray049 import shroud
from assembly_auxiliary import _segment_triangle
from assembly_style import apply_model_styles
from assembly_visibility048 import mesh_visible
from chassis_catalog import CASES,get_case

DIMENSIONS=(240.,509.,503.)
STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def world_triangles(mesh):
    return tuple(tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3))
                       for j in (0,6,12)) for i in range(0,len(mesh.vertices),18))


def cover():
    vertices,meta=shroud(get_case('fractal-north-xl-mesh'),DIMENSIONS)
    return Mesh('psu-shroud',vertices,color('#25313e'),meta['position_mm'],'case'),meta


def segment_hits(mesh,a,b):
    return any(_segment_triangle(a,b,triangle) for triangle in world_triangles(mesh))


def fan_scene(level='balanced',old_solid=False,obstacle=False):
    from assembly_cooling import _Builder,_fan
    from cooling_catalog import get_fan
    target='fans:front:0';center=(0.,-120.,229.)
    builder=_Builder(level)
    _fan(builder,get_fan('arctic-p12-pwm'),center,(0.,0.,1.),(0.,1.,0.),part=target)
    mesh,_=cover()
    if old_solid:mesh=Mesh('psu-shroud',box(228.,509.*.17,491.),mesh.color,(0.,-509.*.405,0.),'case')
    meshes=(*builder.finish(),mesh,
            Mesh('reference-board',box(1.,20.,20.),color('#445566'),(100.,0.,-200.),'board',part_id='board:0'),
            Mesh('reference-fan4-loom',box(2.,2.,10.),color('#445566'),(95.,20.,-100.),'cables',part_id='cables:all'))
    if obstacle:
        meshes+= (Mesh('independent-solid-obstacle',box(150.,150.,.1),color('#445566'),(0.,-120.,200.),'case'),)
    metadata=dict(attachment_anchors={},auxiliary=dict(cable_count=1,cables=[dict(source_owner=target,target_owner='board',
        role='case',kind='fan4',mesh_prefix='reference-fan4',routing_failed=False,external_route=False)]),cooling=dict(
        parts=[dict(id=target,kind='case_fan',model_id='arctic-p12-pwm',mount='front',
                    compatibility='documented_fan_mount',placement_method='centered_mount_reference')],
        fans=[dict(part_id=target,role='case',model_id='arctic-p12-pwm',position=center,axis=(0.,0.,1.))],
        wire_anchors=builder.wire_anchors,mount_plane_sources={}))
    return Scene(meshes,DIMENSIONS,metadata)


class NorthShroud052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('No native/window/network/worker')))

    def test_exact_case_only_fixed_photo_reference_and_no_selected_hardware_dependency(self):
        case=get_case('fractal-north-xl-mesh');before=copy.deepcopy(case)
        vertices,meta=shroud(case,DIMENSIONS)
        self.assertTrue(vertices);self.assertEqual(case,before)
        self.assertFalse(meta['cad_verified']);self.assertFalse(meta['dimensions_verified'])
        self.assertFalse(meta['positions_verified']);self.assertFalse(meta['thickness_verified'])
        self.assertFalse(meta['far_side_wall_added']);self.assertFalse(meta['selected_component_geometry_used'])
        self.assertFalse(meta['chamber_is_solid']);self.assertTrue(meta['front_bay_open'])
        self.assertFalse(meta['lower_front_deck_added']);self.assertFalse(meta['exact_vent_pattern_modeled'])
        self.assertEqual(meta['normalized_reference']['deck_end_depth_fraction'],.34)
        profile=meta['relief_profile_world_yz_mm']
        self.assertEqual(profile[0][1],profile[1][1])
        self.assertGreater(profile[0][0]-profile[1][0],20.)
        self.assertLessEqual(profile[-2][1]-profile[1][1],5.)
        for other in CASES:
            if other['id']!=case['id']:self.assertEqual(shroud(other,DIMENSIONS),((),{}))
        self.assertEqual(sum(c['id']!=case['id'] for c in CASES),95)
        for dims in ((240.,float('nan'),503.),(240.,509.),(True,509.,503.)):
            self.assertEqual(shroud(case,dims),((),{}))

    def test_real_cavity_front_relief_and_retained_thin_surfaces(self):
        mesh,meta=cover();top=-509.*.32;low=top-509.*.06
        self.assertFalse(segment_hits(mesh,(-80.,-210.,0.),(80.,-210.,0.)))
        self.assertFalse(segment_hits(mesh,(0.,-245.,220.),(0.,-150.,220.)))
        self.assertFalse(segment_hits(mesh,(-115.,low+2.,220.),(-111.,low+2.,220.)))
        self.assertTrue(segment_hits(mesh,(-115.,low-2.,220.),(-111.,low-2.,220.)))
        self.assertTrue(segment_hits(mesh,(-115.,-210.,0.),(-111.,-210.,0.)))
        self.assertTrue(segment_hits(mesh,(0.,top-3.,0.),(0.,top+3.,0.)))
        # Former positive-volume witness is now empty, not a decorative skin
        # concealing the old full compartment box.
        self.assertFalse(segment_hits(mesh,(40.,-175.,229.),(50.,-175.,229.)))
        # No unobserved mirrored full-height wall at the far side.
        self.assertFalse(segment_hits(mesh,(111.,-210.,0.),(115.,-210.,0.)))

    def test_cover_is_one_closed_connected_thick_solid_with_consistent_normals(self):
        mesh,_=cover();edges=Counter();directions=Counter();neighbors=defaultdict(set);triangles=world_triangles(mesh)
        face_edges=defaultdict(list);volume=0.
        for index,tri in enumerate(triangles):
            a,b,c=tri;ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
            n=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
            area=math.sqrt(sum(v*v for v in n));self.assertGreater(area,1e-7)
            stored=mesh.vertices[index*18+3:index*18+6]
            self.assertAlmostEqual(sum(x*x for x in stored),1.)
            self.assertGreater(sum(n[k]*stored[k] for k in range(3)),0.)
            volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
            for p,q in zip(tri,(*tri[1:],tri[0])):
                key=tuple(sorted((p,q)));edges[key]+=1;directions[key]+=1 if p<q else -1;face_edges[key].append(index)
        self.assertTrue(all(n==2 for n in edges.values()))
        self.assertTrue(all(n==0 for n in directions.values()))
        self.assertGreater(volume,10000.);self.assertLess(volume,250000.)
        for faces in face_edges.values():
            a,b=faces;neighbors[a].add(b);neighbors[b].add(a)
        visited=set();pending=[0]
        while pending:
            i=pending.pop()
            if i in visited:continue
            visited.add(i);pending.extend(neighbors[i]-visited)
        self.assertEqual(len(visited),len(triangles));self.assertEqual(len(triangles),76)

    def test_real_fan_zero_pose_and_complete_path_rechecked_not_force_allowed(self):
        from assembly_part_motion052 import plan_part_motion
        target='fans:front:0'
        for level in ('eco','balanced','close'):
            old=plan_part_motion(fan_scene(level,old_solid=True),target,released_mounts=(target,))
            self.assertFalse(old['available']);self.assertEqual(old['safe_distance_mm'],0.)
            new=plan_part_motion(fan_scene(level),target,released_mounts=(target,))
            self.assertTrue(new['available'],new)
            self.assertTrue(new['clearance']['continuous_full_path_checked'])
            blocked=plan_part_motion(fan_scene(level,obstacle=True),target,released_mounts=(target,))
            self.assertFalse(blocked['available']);self.assertEqual(blocked['reason'],'motion_path_blocked')
            self.assertGreater(blocked['safe_distance_mm'],0.);self.assertLess(blocked['safe_distance_mm'],25.)
            self.assertEqual(blocked['blocked_by'][0]['mesh_name'],'independent-solid-obstacle')

    def test_original_single_mesh_identity_visibility_color_and_no_anchor_motion(self):
        case=get_case('fractal-north-xl-mesh')
        scene=build_scene(dict(case=case,memory=dict(count=0),detail_level='eco'))
        covers=[m for m in scene.meshes if m.name=='psu-shroud']
        self.assertEqual(len(covers),1);mesh=covers[0];expected,meta=cover()
        self.assertEqual(mesh,expected);self.assertEqual(scene.metadata['case_shroud'],meta)
        self.assertEqual(scene.dimensions,DIMENSIONS)
        self.assertEqual(mesh.component,'case');self.assertEqual(mesh.part_id,'')
        for cutaway in (False,True):
            self.assertTrue(mesh_visible(mesh,cutaway,False));self.assertFalse(mesh_visible(mesh,cutaway,True))
        self.assertEqual(meta['position_mm'],(0.,-509.*.405,0.))

    def test_all_six_styles_and_three_lods_share_the_same_physical_cover(self):
        case=get_case('fractal-north-xl-mesh');reference,_=cover()
        for level in ('eco','balanced','close'):
            scene=build_scene(dict(case=case,memory=dict(count=0),detail_level=level))
            original=next(m for m in scene.meshes if m.name=='psu-shroud')
            self.assertEqual(original.vertices,reference.vertices)
            for style in STYLES:
                meshes,_=apply_model_styles(scene.meshes,style,{},scene.dimensions,case.get('panels',{}))
                styled=next(m for m in meshes if m.name=='psu-shroud')
                self.assertIs(styled.vertices,original.vertices)
                self.assertEqual(styled.position,original.position)
                self.assertEqual(styled.part_id,original.part_id)


if __name__=='__main__':unittest.main()
