"""Independent nominal tube clearance and real-case fail-closed regressions."""
import copy
import math
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

import hardware_packs as packs
from assembly_geometry import build_scene
from assembly_spec import build_spec
from liquid_clearance046 import segment_distance, route_pair_overlap, self_overlap
from stats_config import DEFAULT


class TubeClearance046Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No device/network/window/worker')))

    def test_finite_segments_parallel_skew_crossing_and_degenerate_points(self):
        fixtures=(
            (((0,0,0),(10,0,0),(5,-5,0),(5,5,0)),0),
            (((0,0,0),(10,0,0),(5,-5,3),(5,5,3)),3),
            (((0,0,0),(10,0,0),(0,4,0),(10,4,0)),4),
            (((0,0,0),(10,0,0),(30,0,0),(20,0,0)),10),
            (((0,0,0),(1,0,0),(2,1,0),(2,2,0)),math.sqrt(2)),
            (((0,0,0),(0,0,0),(0,3,0),(0,5,0)),3),
            (((2,0,0),(2,0,0),(2,3,4),(2,3,4)),5),
            (((0,0,0),(1000,0,0),(0,-.00005,0),(1000,.00005,0)),0),
        )
        for (a,b,c,d),expected in fixtures:
            self.assertAlmostEqual(segment_distance(a,b,c,d),expected,places=10)
            self.assertAlmostEqual(segment_distance(c,d,a,b),expected,places=10)
            self.assertAlmostEqual(segment_distance(b,a,d,c),expected,places=10)

    def test_two_actual_radii_determine_penetration_not_one_nominal_radius(self):
        first=[(0,0,0),(100,0,0)]
        self.assertTrue(route_pair_overlap(first,6.5,[(0,11.55,0),(100,11.55,0)],6.5))
        self.assertFalse(route_pair_overlap(first,6.5,[(0,13,0),(100,13,0)],6.5))
        self.assertTrue(route_pair_overlap(first,6.5,[(0,12.9999,0),(100,12.9999,0)],6.5))
        self.assertTrue(route_pair_overlap(first,10,[(0,12,0),(100,12,0)],3))
        self.assertFalse(route_pair_overlap(first,2,[(101,10,0),(101,30,0)],3))
        self.assertTrue(route_pair_overlap(first,2,[(100.5,-10,0),(100.5,10,0)],1))

    def test_local_arclength_neighborhood_is_independent_of_sampling(self):
        for count in (2,20,80,160):
            points=[(100*n/(count-1),0,0) for n in range(count)]
            self.assertFalse(self_overlap(points,2))
        for count in (9,33,97):
            points=[(20*math.cos(n*math.pi/(count-1)),20*math.sin(n*math.pi/(count-1)),0) for n in range(count)]
            self.assertFalse(self_overlap(points,2))
        self.assertFalse(self_overlap([(0,0,0),(100,0,0),(100,10,0),(0,10,0)],2))

    def test_self_crossing_coils_and_long_backtracking_are_not_hidden_by_shared_end(self):
        self.assertTrue(self_overlap([(0,0,0),(50,50,0),(0,50,0),(50,0,0)],2))
        self.assertTrue(self_overlap([(0,0,0),(100,0,0),(0,0,0)],2))
        dense=[(n*5,0,0) for n in range(21)]+[(100-n*5,0,0) for n in range(1,21)]
        self.assertTrue(self_overlap(dense,2))
        coil=[(20*math.cos(n*5*math.pi/95),20*math.sin(n*5*math.pi/95),3*n/95) for n in range(96)]
        self.assertTrue(self_overlap(coil,2))
        self.assertTrue(self_overlap([(0,0,0),(100,0,0),(100,3,0),(0,3,0)],2))

    def test_invalid_or_unbounded_input_cannot_be_treated_as_safe(self):
        valid=[(0,0,0),(100,0,0)]
        for radius in (None,False,0,-1,float('nan'),float('inf'),1001):
            with self.assertRaises(ValueError):self_overlap(valid,radius)
            with self.assertRaises(ValueError):route_pair_overlap(valid,radius,valid,2)
        for points in ([],[(0,0,0)],[(0,0,0)]*2,[(0,0,0)]*161,[(0,0,0),(0,0,float('nan'))],[(0,0,0),(10**7,0,0)]):
            with self.assertRaises(ValueError):self_overlap(points,2)
            with self.assertRaises(ValueError):route_pair_overlap(valid,2,points,2)
        with self.assertRaises(ValueError):segment_distance((0,0),(1,0,0),(0,0,0),(1,1,0))

    def test_tangent_fillets_keep_requested_radius_instead_of_compressing_short_doglegs(self):
        from liquid_path046 import _rounded
        from liquid_routes046 import _radius
        path=[(0.,0.,0.),(40.,0.,0.),(40.,40.,0.),(80.,40.,0.)]
        points=_rounded(path,10.)
        self.assertEqual(points[0],path[0]);self.assertEqual(points[-1],path[-1])
        self.assertAlmostEqual(_radius(points),10.,places=9)
        self.assertAlmostEqual(points[1][1],0.);self.assertAlmostEqual(points[-2][1],40.)
        self.assertFalse(self_overlap(points,6.5))
        # A nine-mm middle leg cannot hold two ten-mm tangent trims. Returning
        # no route is required; shrinking both bends would fold a 13-mm hose.
        self.assertIsNone(_rounded([(0.,0.,0.),(40.,0.,0.),(40.,9.,0.),(80.,9.,0.)],10.))

    def test_finite_open_mouth_has_no_fictitious_axial_end_sphere(self):
        from liquid_routes046 import tube_segment_intersection
        box=((-90.,-20.,-20.),(20.,20.,20.))
        self.assertFalse(tube_segment_intersection((-92.5,0.,0.),(-120.,0.,0.),box,6.5))
        self.assertTrue(tube_segment_intersection((-88.,0.,0.),(-120.,0.,0.),box,6.5))
        # Radial clearance still matters along the whole finite segment.
        self.assertTrue(tube_segment_intersection((-120.,24.,0.),(40.,24.,0.),box,6.5))

    def test_optimized_axis_edges_preserve_original_finite_projection_filter(self):
        from liquid_routes046 import tube_segment_intersection,bounds_intersection
        rng=random.Random(460114)
        for number in range(1500):
            a=tuple(rng.uniform(-100,100) for _ in range(3));b=list(a)
            if number%3:
                axis=number%3;b[axis]+=rng.uniform(-80,80)
            else:b=[rng.uniform(-100,100) for _ in range(3)]
            low=tuple(rng.uniform(-80,80) for _ in range(3))
            high=tuple(v+rng.uniform(1,80) for v in low);radius=rng.uniform(.1,15)
            length=math.dist(a,b);direction=tuple((b[i]-a[i])/length for i in range(3))
            projection_low=sum(((low[i] if direction[i]>=0 else high[i])-a[i])*direction[i] for i in range(3))
            projection_high=sum(((high[i] if direction[i]>=0 else low[i])-a[i])*direction[i] for i in range(3))
            reference=(projection_high>1e-7 and projection_low<length-1e-7 and
                       bounds_intersection(a,b,(low,high),radius))
            self.assertEqual(tube_segment_intersection(a,b,(low,high),radius),reference)

    def test_solver_edge_memo_is_bounded_local_and_does_not_change_paths(self):
        import liquid_path046
        from liquid_routes046 import route
        from tests.test_liquid_path046 import TUBE,START,END,CASE,OBSTACLE
        reference,reason=route(START,END,TUBE,obstacles=(OBSTACLE,),case_bounds=CASE,allow_detour=True)
        self.assertFalse(reason);sizes=[];previous=sys.getprofile()
        def profile(frame,event,arg):
            if event=='return' and frame.f_code is liquid_path046.detour.__code__:
                sizes.append(len(frame.f_locals['edge_validity']))
        try:
            sys.setprofile(profile)
            with patch.object(liquid_path046,'MAX_EDGE_CACHE',3):
                limited,reason=route(START,END,TUBE,obstacles=(OBSTACLE,),case_bounds=CASE,allow_detour=True)
        finally:sys.setprofile(previous)
        self.assertFalse(reason);self.assertEqual(limited,reference)
        self.assertEqual(sizes,[3])
        self.assertFalse(hasattr(liquid_path046,'edge_validity'))


class ActualCaseLoopClearance046Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_loop_packs046 import pack_models
        cls.data=packs.make_pack('clearance-test046','Actual case clearance',pack_models(),kind='loop')

    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No device/network/window/worker')))
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        source=root/'source.dspack';source.write_bytes(self.data)
        self.store=packs.PackStore(root/'installed');self.store.install(source)
        self.enterContext(patch.object(packs,'_store',self.store))

    def test_haf700_and_5000d_cannot_claim_connected_with_overlapping_or_self_folded_tubes(self):
        for case in ('cooler-master-haf-700-evo','corsair-5000d-airflow'):
            with self.subTest(case=case):
                config=copy.deepcopy(DEFAULT)
                config['assembly'].update(case_model=case,cpu_model='intel-13700kf',gpu_model='asus-astral-5090',
                    board_model='asus-rog-strix-z790-a-wifi-d4',cooler_model='custom-loop-360-reference',cooler_mount='top',
                    detail_level='eco',gpu_waterblock=False,loop_components_mode='selected',cpu_block_model='alphacool-core1-black',
                    pump_reservoir_model='corsair-xd5-rgb-gen2',fitting_model='alphacool-eiszapfen-soft-13-10',
                    tubing_model='alphacool-alphatube-hf-13-10',radiator_model='corsair-xr5-360',
                    radiator_fan_layout='single',radiator_fan_model='arctic-p12-pwm')
                scene=build_scene(build_spec({},config,{},[]));loop=scene.metadata['cooling']['selected_loop'];routes=loop['routes']
                if not loop['connected_reference_loop']:
                    self.assertEqual(routes,[])
                    self.assertTrue(loop['issues'])
                    self.assertFalse(any(m.name=='loop-reference-routed-tube' for m in scene.meshes))
                    self.fail(('Known reference configuration lost its clear routes',case,loop['issues']))
                self.assertEqual(len(routes),3)
                for route in routes:
                    self.assertLessEqual(len(route['points']),160)
                    if route['minimum_radius_mm'] is not None:
                        self.assertGreaterEqual(route['minimum_radius_mm']+1e-5,6.5*1.2)
                    self.assertFalse(self_overlap(route['points'],6.5),(case,route['from_port']))
                for i,first in enumerate(routes):
                    for second in routes[i+1:]:
                        self.assertFalse(route_pair_overlap(first['points'],6.5,second['points'],6.5),
                            (case,first['from_port'],second['from_port']))


if __name__=='__main__':unittest.main()
