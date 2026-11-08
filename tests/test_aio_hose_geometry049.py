"""Factory-length reference AIO sweeps, not hardware/CAD fit or live telemetry."""
from collections import Counter
import copy
import math
import unittest
from unittest.mock import patch

import assembly_cooling as cooling
from assembly_geometry import Mesh,box,color
from chassis_catalog import get_case
from liquid_clearance046 import self_overlap,route_pair_overlap,segment_distance
import test_aio_connections048 as connections


ANCHORS={'cpu':{'position':(80.4,76.975,-103.056),'normal':(-1.,0.,0.),'up':(0.,1.,0.)},
         'case_dimensions':(240.,509.,503.)}


def physical_edges(vertices):
    edges=Counter()
    for offset in range(0,len(vertices),18):
        tri=[tuple(round(v,9) for v in vertices[offset+j:offset+j+3]) for j in (0,6,12)]
        for a,b in zip(tri,tri[1:]+tri[:1]):edges[tuple(sorted((a,b)))]+=1
    return edges


class AioHoseGeometry049Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('Geometry only; no device/UI/network/worker')))

    def build(self,identity='arctic-liquid-freezer-iii-360',level='balanced',meshes=(),anchors=None):
        return cooling.add_cooling(meshes,{'case':get_case('fractal-north-xl-mesh'),
            'cooling':{'cpu_cooler':identity,'radiator_mount':'top'}},level,anchors or ANCHORS)

    def test_shared_rings_have_no_internal_open_edges_on_three_dimensional_bends(self):
        points=[(0.,0.,0.),(0.,0.,6.),(4.,1.,20.),(18.,12.,28.),(31.,25.,20.),(31.,31.,20.)]
        for sides in (6,8,10):
            values,rings=cooling._aio_sweep(points,6.2,sides,(0.,0.,1.),(0.,-1.,0.))
            edges=physical_edges(values);boundary={edge for edge,count in edges.items() if count==1}
            expected={tuple(sorted((tuple(round(x,9) for x in ring[i]),tuple(round(x,9) for x in ring[(i+1)%sides]))))
                      for ring in (rings[0],rings[-1]) for i in range(sides)}
            self.assertEqual(boundary,expected)
            self.assertTrue(all(count in (1,2) for count in edges.values()))
            self.assertEqual(len(values)//18,2*sides*(len(points)-1))
            self.assertTrue(all(math.isfinite(value) for value in values))
            for i in range(3,len(values),6):self.assertAlmostEqual(sum(n*n for n in values[i:i+3]),1.,places=6)

    def test_actual_lfiii_240_and360_keep450mm_at_all_lods_without_pair_or_self_overlap(self):
        for identity in ('arctic-liquid-freezer-iii-240','arctic-liquid-freezer-iii-360'):
            for level in ('eco','balanced','close'):
                meshes,meta=self.build(identity,level)
                with self.subTest(model=identity,level=level):
                    self.assertFalse(meta['connection_issues']);self.assertEqual(len(meta['aio_hoses']),2)
                    for hose in meta['aio_hoses']:
                        self.assertAlmostEqual(hose['centerline_length_mm'],450.,delta=4.5)
                        self.assertEqual(hose['outer_radius_mm'],6.2);self.assertTrue(hose['nominal_length_preserved'])
                        self.assertLessEqual(len(hose['points']),35)
                        self.assertFalse(self_overlap(hose['points'],6.2))
                        self.assertTrue(all(abs(p[k])+6.2<=ANCHORS['case_dimensions'][k]/2 for p in hose['points'] for k in range(3)))
                    first,second=(h['points'] for h in meta['aio_hoses'])
                    self.assertFalse(route_pair_overlap(first,6.2,second,6.2))
                    minimum=min(segment_distance(a,b,c,d) for a,b in zip(first,first[1:]) for c,d in zip(second,second[1:]))
                    self.assertGreater(minimum,12.4)
                    self.assertEqual(len([m for m in meshes if m.name=='cooler-liquid-tubes']),1)

    def test_real_terminal_triangles_keep_outlet_planes_axes_and_closed_annular_seams(self):
        probe=connections.AioConnections048Tests()
        for identity in ('arctic-liquid-freezer-iii-240','arctic-liquid-freezer-iii-360'):
            for level in ('eco','balanced','close'):
                with self.subTest(model=identity,level=level):
                    probe.inspect_connections(identity,level,anchors=ANCHORS)

    def test_lfiii_close_pair_is_explicit_photo_reference_and_generic_aio_is_unchanged(self):
        _,meta=self.build()
        rad=next(p for p in meta['parts'] if p['kind']=='radiator')
        ref=rad['hose_port_reference'];self.assertEqual(ref['spacing_mm'],26.)
        self.assertEqual(ref['previous_generic_spacing_mm'],67.2)
        self.assertFalse(ref['position_verified']);self.assertFalse(ref['long_offset_verified'])
        self.assertIn('arctic.de/media/',ref['source'])
        self.assertEqual(ref['accuracy'],'photo_reference_not_dimensioned_pitch')
        self.assertEqual(ref['radiator_rigid_rotation_degrees'],180);self.assertFalse(ref['mount_clocking_verified'])
        _,other=self.build('nzxt-kraken-360-2023')
        self.assertTrue(all('hose_port_reference' not in p for p in other['parts']))
        self.assertTrue(all(h['nominal_length_mm'] is None and not h['nominal_length_preserved'] for h in other['aio_hoses']))

    def test_obstructed_or_overlong_reference_guide_is_not_shortened_into_a_false_fit(self):
        from assembly_parts import fit_messages
        length_notice='原厂长度的水冷软管未找到可用路线，未缩短或强行连接。'
        port_notice='部分冷排接口位置尚未核实，对应管路未强行连接。'
        blocker=Mesh('memory-spreader',box(220.,240.,260.),color('#445566'),(0.,130.,-80.),'memory',part_id='memory:0')
        meshes,meta=self.build(meshes=(blocker,))
        self.assertFalse(meta['aio_hoses']);self.assertFalse(any(m.name=='cooler-liquid-tubes' for m in meshes))
        self.assertTrue(any(r.get('reason')=='aio_hose_route_unverified' and r.get('hoses_omitted') for r in meta['connection_issues']))
        self.assertIn('rigid_envelope:memory-spreader',meta['connection_issues'][0]['details'])
        notices=fit_messages({},dict(cooling=meta))
        self.assertIn(length_notice,notices);self.assertNotIn(port_notice,notices)
        mixed=copy.deepcopy(meta);mixed['connection_issues'].append(dict(reason='radiator_ports_unverified'))
        notices=fit_messages({},dict(cooling=mixed));self.assertIn(length_notice,notices);self.assertIn(port_notice,notices)
        anchors=copy.deepcopy(ANCHORS);anchors['case_dimensions']=(600.,1000.,800.)
        _,meta=self.build(anchors=anchors)
        self.assertFalse(meta['aio_hoses']);self.assertTrue(meta['connection_issues'])
        notices=fit_messages({},dict(cooling=meta));self.assertIn(length_notice,notices);self.assertNotIn(port_notice,notices)

    def test_aio_only_sweep_does_not_replace_generic_tube_air_or_selected_reference_loop(self):
        with patch.object(cooling,'_aio_sweep',side_effect=AssertionError('AIO sweep leaked to other geometry')):
            for identity in ('noctua-nh-d15','noctua-nh-l12s','custom-loop-360-reference'):
                meshes,_=self.build(identity,'eco');self.assertTrue(meshes)
            self.assertTrue(cooling._tube([(0.,0.,0.),(1.,2.,3.)],2.))

    def test_detached_route_metadata_does_not_mutate_physical_mesh_or_add_moving_parts(self):
        meshes,meta=self.build();hose=next(m for m in meshes if m.name=='cooler-liquid-tubes');before=hose.vertices
        self.assertFalse(hose.rotor);self.assertEqual(hose.part_id,'cooler:cpu')
        self.assertTrue(all(h['endpoints_position_verified'] is False for h in meta['aio_hoses']))
        self.assertTrue(all(h['path_accuracy']=='original_routing_reference' for h in meta['aio_hoses']))
        self.assertTrue(all(f.get('rpm') is None for f in meta['fans']))
        self.assertEqual(meta['new_pollers'],0)
        meta['aio_hoses'][0]['points'][0][0]+=1000.
        self.assertEqual(hose.vertices,before)
        self.assertFalse(any(p['id'].startswith('cooler:cpu:hose:') for p in meta['parts']))

    def test_complete_head_clocks_rigidly_and_real_hollow_elbows_exit_the_board_normal(self):
        meshes,meta=self.build();p,basis=cooling._cpu_frame(ANCHORS);u,v,n=basis
        expected_basis=(v,cooling._mul(u,-1.),n)
        old=cooling._Builder('balanced');cooling._lfiii_pump(old,p,basis,'cooler:pump')
        expected=cooling._Builder('balanced');ports=cooling._lfiii_pump(expected,p,expected_basis,'cooler:pump')
        def rotate(vector):return tuple(sum(cooling._dot(vector,basis[k])*expected_basis[k][j] for k in range(3)) for j in range(3))
        for a,b in zip(old.finish(),expected.finish()):
            self.assertEqual(a.name,b.name);self.assertEqual(len(a.vertices),len(b.vertices))
            self.assertEqual(a.rotor,b.rotor)
            for offset in range(0,len(a.vertices),6):
                before=cooling._add(a.vertices[offset:offset+3],a.position)
                target=cooling._add(p,rotate(cooling._sub(before,p)))
                after=cooling._add(b.vertices[offset:offset+3],b.position)
                self.assertLess(math.dist(target,after),1e-6)
        actual={m.name:m for m in meshes}
        for expected_mesh in expected.finish():
            self.assertEqual(actual[expected_mesh.name],expected_mesh)
        for sign,port in zip((-1,1),ports):
            self.assertLess(math.dist(port,cooling._local_point(p,expected_basis,sign*13,54.5,68.5)),1e-7)
        self.assertEqual([h['points'][0] for h in meta['aio_hoses']],[list(port) for port in ports])
        pose=next(part for part in meta['parts'] if part['id']=='cooler:pump')['factory_pose_reference']
        self.assertEqual(pose['hose_exit_axis'],list(n));self.assertFalse(pose['position_verified'])
        # New elbow geometry stays inside the documented enclosure, while its
        # unlabelled internal coordinates remain an explicit photo reference.
        points=[cooling._add(m.vertices[i:i+3],m.position) for m in old.finish() for i in range(0,len(m.vertices),6)]
        local=[tuple(cooling._dot(cooling._sub(q,p),axis) for axis in basis) for q in points]
        spans=[max(q[k] for q in local)-min(q[k] for q in local) for k in range(3)]
        self.assertLessEqual(spans[0],91.+1e-6);self.assertLessEqual(spans[1],108.5+1e-6);self.assertLessEqual(spans[2],68.5+1e-6)


if __name__=='__main__':unittest.main()
