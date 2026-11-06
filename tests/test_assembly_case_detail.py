"""Case construction detail retains dimensions and honest port identities."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_case_detail import chamfer_box,enrich_case,rounded_frame
from assembly_geometry import Mesh,box,build_scene
from chassis_catalog import CASES
from chassis_detail_catalog import details_for


class AssemblyCaseDetailTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(target,side_effect=AssertionError('No device or worker access')))

    def test_bevel_is_closed_outward_wound_and_keeps_all_exterior_edges(self):
        vertices=chamfer_box(10,20,30,1)
        self.assertEqual(len(vertices)//18,44)
        for axis,half in enumerate((5,10,15)):
            self.assertAlmostEqual(min(vertices[axis::6]),-half)
            self.assertAlmostEqual(max(vertices[axis::6]),half)
        edges={}
        for start in range(0,len(vertices),18):
            row=vertices[start:start+18];points=[tuple(round(v,7) for v in row[n:n+3]) for n in (0,6,12)]
            self.assertAlmostEqual(sum(v*v for v in row[3:6]),1.)
            center=[sum(p[n] for p in points)/3 for n in range(3)]
            self.assertGreater(sum(center[n]*row[n+3] for n in range(3)),0)
            for a,b in ((0,1),(1,2),(2,0)):
                key=tuple(sorted((points[a],points[b])));edges[key]=edges.get(key,0)+1
        self.assertTrue(edges);self.assertEqual(set(edges.values()),{2})

    def test_type_c_frame_has_an_open_stadium_aperture_and_unit_normals(self):
        vertices=rounded_frame(8.8,3.5,.45,1)
        self.assertGreater(len(vertices),200)
        self.assertTrue(all(math.isfinite(v) for v in vertices))
        for start in range(0,len(vertices),6):
            x,y,_z=vertices[start:start+3]
            self.assertFalse(abs(x)<2 and abs(y)<1)
            self.assertAlmostEqual(sum(v*v for v in vertices[start+3:start+6]),1.)

    def test_all_case_details_stay_bounded_and_preserve_component_meshes(self):
        for case in CASES:
            base=build_scene({'case':case,'detail_level':'eco'})
            before=copy.deepcopy(case)
            with self.subTest(case=case['id']):
                for level,cap in (('balanced',12000),('close',24000)):
                    detailed=enrich_case(base.meshes,base.dimensions,case,level)
                    self.assertEqual(case,before)
                    self.assertEqual(tuple(m for m in detailed if m.component not in ('case','panel')),
                                     tuple(m for m in base.meshes if m.component not in ('case','panel')))
                    self.assertLess(sum(m.vertex_count//3 for m in detailed if m.component in ('case','panel')),cap)
                    self.assertTrue(all(math.isfinite(v) for m in detailed for v in m.vertices))
                    self.assertFalse(any(m.rotor for m in detailed))

    def test_eco_keeps_existing_geometry_and_unknown_ports_never_appear(self):
        base=build_scene({'case':CASES[0],'detail_level':'eco'})
        self.assertEqual(enrich_case(base.meshes,base.dimensions,CASES[0],'eco'),base.meshes)
        case={'exterior_details':{'io':{'usb_a':2}}}
        self.assertFalse(any(m.name.startswith('case-io-') for m in enrich_case(base.meshes,base.dimensions,case)))

    def test_verified_usb_counts_are_preserved_and_batched_without_contact_draw_explosion(self):
        meshes=[Mesh('front-panel',box(230,450,2),(.3,.4,.5,1.))]
        case={'exterior_details':{'io':{'position':'top','usb_a':2,'usb_c':1,'audio':1}}}
        rows=enrich_case(meshes,(230,470,460),case)
        wells=next(m for m in rows if m.name=='case-io-usb_a-well')
        self.assertEqual(wells.vertex_count//3,2*44)
        self.assertEqual(sum(m.name=='case-io-usb_a-contact' for m in rows),1)
        self.assertTrue(any(m.name=='case-io-usb_c-rim' for m in rows))
        self.assertFalse(any(m.name.startswith('case-io-buttons') for m in rows))
        self.assertLess(sum(m.name.startswith('case-io-') for m in rows),15)

    def test_fine_perforation_is_one_draw_batch_instead_of_sparse_shutters(self):
        case=next(c for c in CASES if c['id']=='asus-prime-ap201-mesh')
        base=build_scene({'case':case,'detail_level':'eco'})
        rows=enrich_case(base.meshes,base.dimensions,case)
        self.assertFalse(any(m.name in ('front-vent','left-mesh-vent') for m in rows))
        self.assertEqual(sum(m.name=='case-perforation' for m in rows),2)
        self.assertFalse(any(m.name=='case-front-glass-screw' for m in rows))

    def test_front_io_evidence_is_detached_and_lower_left_panel_keeps_its_side(self):
        verified=[case for case in CASES if case.get('exterior_details')]
        self.assertEqual(len(verified),12)
        for case in verified:
            details=details_for(case['id'])
            self.assertTrue(details['sources'])
            self.assertTrue(all(url.startswith('https://') for url in details['sources']))
            self.assertIs(details['io']['layout_schematic'],True)
            details['io']['usb_a']=99
            self.assertNotEqual(details_for(case['id'])['io']['usb_a'],99)
        self.assertEqual(details_for('not-a-known-case'),{})
        case=next(c for c in CASES if c['id']=='deepcool-ch160')
        base=build_scene({'case':case,'detail_level':'eco'})
        rows=enrich_case(base.meshes,base.dimensions,case)
        port=next(m for m in rows if m.name=='case-io-usb_c-rim')
        self.assertLess(max(port.vertices[0::6]),-base.dimensions[0]/2)
        self.assertLess(max(port.vertices[1::6]),0)
        self.assertGreater(min(port.vertices[2::6]),0)


if __name__=='__main__':unittest.main()
