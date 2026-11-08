"""Finite fallback routes must be clear along whole segments, not sample dots."""
import unittest
from unittest.mock import patch
from liquid_routes046 import route,bounds_intersection

TUBE=dict(tube_type='soft',tube_inner_mm=6.,tube_outer_mm=8.,material='PVC',min_bend_radius_mm=None)
START=dict(position=(-40.,0.,0.),normal=(1.,0.,0.))
END=dict(position=(40.,0.,0.),normal=(-1.,0.,0.))
CASE=((-60.,-60.,-60.),(60.,60.,60.))
OBSTACLE=((-2.,-9.,-9.),(2.,9.,9.))

class LiquidPath046Tests(unittest.TestCase):
    def test_detour_keeps_exact_mouths_tangents_and_complete_tube_clearance(self):
        line,reason=route(START,END,TUBE,obstacles=(OBSTACLE,),case_bounds=CASE,allow_detour=True)
        self.assertEqual(reason,'');self.assertTrue(line['bounded_reference_detour'])
        points=line['points'];self.assertEqual(points[0],START['position']);self.assertEqual(points[-1],END['position'])
        self.assertGreater(points[1][0],points[0][0]);self.assertGreater(points[-1][0],points[-2][0])
        self.assertLessEqual(len(points),160)
        self.assertTrue(all(not bounds_intersection(a,b,OBSTACLE,4.) for a,b in zip(points,points[1:])))
        self.assertTrue(all(all(-56<=v<=56 for v in p) for p in points))

    def test_sealed_barrier_known_bend_limit_and_visit_limit_fail_closed(self):
        barrier=((-2.,-100.,-100.),(2.,100.,100.))
        line,reason=route(START,END,TUBE,obstacles=(barrier,),case_bounds=CASE,allow_detour=True)
        self.assertIsNone(line);self.assertEqual(reason,'tube_route_obstructed')
        with patch('liquid_path046.MAX_VISITED',1):
            line,reason=route(START,END,TUBE,obstacles=(OBSTACLE,),case_bounds=CASE,allow_detour=True)
            self.assertIsNone(line)
        line,reason=route(START,END,dict(TUBE,min_bend_radius_mm=500.),obstacles=(OBSTACLE,),case_bounds=CASE,allow_detour=True)
        self.assertIsNone(line)

    def test_default_fast_path_and_hard_tubing_never_enter_the_detour_solver(self):
        with patch('liquid_path046.detour',side_effect=AssertionError('No implicit or hard-tube rerouting')):
            line,reason=route(START,END,TUBE,case_bounds=CASE,allow_detour=True)
            self.assertEqual(line['points'],[START['position'],END['position']])
            self.assertFalse(line['bounded_reference_detour'])
            for tube,allow in ((TUBE,False),(dict(TUBE,tube_type='hard',material='PMMA'),True)):
                line,reason=route(START,END,tube,obstacles=(OBSTACLE,),case_bounds=CASE,allow_detour=allow)
                self.assertIsNone(line);self.assertEqual(reason,'tube_route_obstructed')

if __name__=='__main__':unittest.main()
