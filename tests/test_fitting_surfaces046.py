"""Low-detail grip marks follow real facets; elbow bodies stop behind collars."""
from collections import Counter
import math
import unittest
from liquid_grip046 import grip_strips
from liquid_fitting_tube_expansion046 import records
from liquid_geometry046 import build_component,_env

class FittingSurface046Tests(unittest.TestCase):
    def test_grip_marks_are_shallow_on_actual_facets_instead_of_floating_rods(self):
        for segments,count in ((16,8),(24,12),(32,16)):
            for diamond in (False,True):
                vertices=grip_strips(10.,12.,segments,count,diamond)
                self.assertTrue(vertices)
                for at in range(0,len(vertices),6):
                    x,y,z=vertices[at:at+3];phi=math.atan2(y,x);period=math.tau/segments
                    middle=(math.floor(phi/period)+.5)*period
                    distance=x*math.cos(middle)+y*math.sin(middle)-10*math.cos(period/2)
                    self.assertAlmostEqual(distance,.012,places=7)
                    self.assertLessEqual(abs(z),12*.32+1e-8)
                self.assertLess(len(vertices)//18,400)

    def test_each_elbow_open_boundary_is_at_collar_back_plane_with_exact_port_tangent(self):
        for row in records('fitting'):
            if not row.get('fitting_angle_deg'):continue
            for level in ('eco','balanced','close'):
                meshes,part=build_component(row,level);body=next(m for m in meshes if m.name=='loop-source-shaped-elbow-body')
                edges=Counter()
                for at in range(0,len(body.vertices),18):
                    tri=[tuple(round(v,7) for v in body.vertices[at+j:at+j+3]) for j in (0,6,12)]
                    for a,b in zip(tri,(*tri[1:],tri[0])):edges[tuple(sorted((a,b)))]+=1
                graph={}
                for (a,b),number in edges.items():
                    if number==1:graph.setdefault(a,set()).add(b);graph.setdefault(b,set()).add(a)
                left=set(graph);rings=[]
                while left:
                    pending=[left.pop()];ring=set(pending)
                    while pending:
                        for v in graph[pending.pop()]:
                            if v in left:left.remove(v);ring.add(v);pending.append(v)
                    rings.append(ring)
                self.assertEqual(len(rings),2)
                for port in part['ports']:
                    size=_env(row);h=size['height'];tube=port.get('tube_type') in ('soft','hard')
                    length=h*(.27 if tube else .20)
                    if not tube:
                        arm=abs(sum(port['position'][i]*port['normal'][i] for i in range(3)))
                        length=min(length,arm*.28)
                    length=max(2.,length)
                    expected=tuple(port['position'][i]-port['normal'][i]*length for i in range(3))
                    chosen=min(rings,key=lambda ring:math.dist(tuple(sum(p[i] for p in ring)/len(ring) for i in range(3)),expected))
                    center=tuple(sum(p[i] for p in chosen)/len(chosen) for i in range(3))
                    self.assertLess(math.dist(center,expected),1e-5,(row['id'],level))
                    self.assertTrue(all(abs(sum((p[i]-expected[i])*port['normal'][i] for i in range(3)))<1e-5 for p in chosen))

if __name__=='__main__':unittest.main()
