"""Production convex-cutout controls with independent surface/closure witnesses.

No historical/private module is imported. Original candidate byte comparisons
remain separate historical evidence, not a dependency of these formal tests.
"""
from collections import defaultdict
import math
import struct
import unittest

from assembly_gpu_panels051 import partition, _convex_cutout, MAX_CUTTERS, MAX_FRAGMENTS, MAX_PANEL_TRIANGLES


def cap_area(vertices, sign):
    total=0.
    for n in range(0,len(vertices),18):
        if not all(vertices[n+k+5]*sign>.999 for k in (0,6,12)):continue
        a,b,c=(vertices[n+k:n+k+2] for k in (0,6,12))
        total+=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2.
    return total


def atomic_edge_incidence(vertices):
    """Independent oriented 3D edge closure, including cap T subdivisions.

    Split every actual triangle edge at all collinear actual vertices. A shared
    long edge and its two shorter neighbours are one closed interval boundary,
    not a false open edge merely because triangulation chose a T junction.
    """
    point=lambda n:tuple(round(vertices[n+k],9) for k in range(3))
    triangles=[tuple(point(n+k) for k in (0,6,12)) for n in range(0,len(vertices),18)]
    points=set(p for triangle in triangles for p in triangle)
    incidence=defaultdict(list)
    for triangle in triangles:
        for a,b in zip(triangle,(*triangle[1:],triangle[0])):
            delta=tuple(y-x for x,y in zip(a,b));length2=sum(v*v for v in delta)
            if length2<=1e-20:raise AssertionError('Degenerate surface edge')
            cuts=[(0.,a),(1.,b)]
            for p in points:
                t=sum((p[k]-a[k])*delta[k] for k in range(3))/length2
                if not 1e-9<t<1.-1e-9:continue
                error=sum((p[k]-a[k]-t*delta[k])**2 for k in range(3))
                if error<=1e-16:cuts.append((t,p))
            cuts.sort()
            for (_,first),(_,last) in zip(cuts,cuts[1:]):
                if first==last:continue
                key=tuple(sorted((first,last)))
                incidence[key].append(1 if first<last else -1)
    return incidence


class GpuCutout053Tests(unittest.TestCase):
    def test_normal_rectangle_default_and_orientations_have_independent_area_and_closed_surface(self):
        outer=((-5.,-3.),(5.,-3.),(5.,3.),(-5.,3.))
        hole=((-2.,-1.),(2.,-1.),(2.,1.),(-2.,1.))
        default,default_meta=partition((outer,),(),.3)
        explicit,explicit_meta=partition((outer,),(),.3,front_cutouts=())
        self.assertEqual((default,default_meta),(explicit,explicit_meta))
        self.assertTrue(default[0])
        self.assertAlmostEqual(cap_area(default[0],1),60.,places=9)
        self.assertAlmostEqual(cap_area(default[0],-1),60.,places=9)
        default_edges=atomic_edge_incidence(default[0])
        self.assertTrue(default_edges)
        self.assertTrue(all(len(values)==2 and sum(values)==0 for values in default_edges.values()))
        results=[]
        for cutout in (hole,tuple(reversed(hole))):
            shapes,meta=partition((outer,),(),.3,front_cutouts=(cutout,))
            self.assertFalse(meta['omitted_source_paint'])
            self.assertEqual(len(shapes),1)
            self.assertTrue(shapes[0])
            self.assertAlmostEqual(cap_area(shapes[0],1),52.,places=9)  #60 minus true8 area
            self.assertAlmostEqual(cap_area(shapes[0],-1),52.,places=9)
            edges=atomic_edge_incidence(shapes[0])
            self.assertTrue(edges)
            self.assertTrue(all(len(values)==2 and sum(values)==0 for values in edges.values()))
            results.append(struct.pack('<'+'f'*len(shapes[0]),*shapes[0]))
        self.assertEqual(results[0],results[1])
        self.assertEqual(_convex_cutout(hole),_convex_cutout(tuple(reversed(hole))))

    def test_concave_and_nonzero_area_self_crossing_pentagram_rejected(self):
        concave=((0.,0.),(3.,0.),(1.,1.),(3.,3.),(0.,3.))
        ring=tuple((math.cos(i*math.tau/5),math.sin(i*math.tau/5)) for i in range(5))
        star=tuple(ring[i] for i in (0,2,4,1,3))
        independent_twice_area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(star,(*star[1:],star[0])))
        self.assertGreater(abs(independent_twice_area),1e-8)
        for poly in (concave,star,tuple(reversed(star))):
            with self.assertRaises(ValueError):_convex_cutout(poly)

    def test_repeated_points_zero_edges_and_double_loop_rejected(self):
        rect=((0.,0.),(3.,0.),(3.,3.),(0.,3.))
        for poly in ((rect[0],rect[0],*rect[1:]),(*rect,rect[0]),(*rect,*rect)):
            with self.assertRaises(ValueError):_convex_cutout(poly)

    def test_overflow_nonfinite_and_huge_integer_fail_as_value_error(self):
        for value in (1e200,-1e200,float('inf'),float('nan'),10**400,1000001.):
            with self.assertRaises(ValueError):_convex_cutout(((0.,0.),(value,0.),(0.,1.)))

    def test_original_point_cutout_and_partition_budgets_remain(self):
        self.assertEqual((MAX_CUTTERS,MAX_FRAGMENTS,MAX_PANEL_TRIANGLES),(128,2048,8192))
        poly=tuple((math.cos(i*math.tau/64),math.sin(i*math.tau/64)) for i in range(64))
        self.assertEqual(len(_convex_cutout(poly)),64)
        with self.assertRaises(ValueError):_convex_cutout((*poly,(.5,.5)))
        outer=((-5.,-3.),(5.,-3.),(5.,3.),(-5.,3.))
        with self.assertRaises(ValueError):partition((outer,),(),.3,front_cutouts=(poly,)*9)


if __name__=='__main__':unittest.main()
