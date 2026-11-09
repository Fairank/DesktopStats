"""Current generic-floor reference datums; no Qt, native API or fit claim."""
from collections.abc import Sequence
import copy
from dataclasses import replace
import math
import unittest
from unittest.mock import patch

from assembly_floor_pose052 import MAX_MESHES,MAX_SOURCE_VERTICES,reference_bottom_pose
from assembly_geometry import Mesh,box,build_scene
from case_fan_clearance047 import half_extents
from chassis_catalog import get_case
from cooling_catalog import get_fan


def minimal(case_id):
    case=get_case(case_id)
    spec=dict(case=case,gpu=dict(present=False),memory=dict(count=0),
        cpu=dict(telemetry_bound=False),cooling=dict(cpu_cooler='none',case_fans=[]),
        detail_level='eco')
    return build_scene(spec)


def bounds(mesh):
    return tuple(tuple(op(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for op in (min,max))


class Oversized(Sequence):
    def __len__(self):return MAX_SOURCE_VERTICES*6+18
    def __getitem__(self,key):raise AssertionError('Reject source size before scanning')


class Counted(tuple):
    def __new__(cls,value):
        result=super().__new__(cls,value);result.slices=0;return result
    def __getitem__(self,key):
        if isinstance(key,slice):self.slices+=1
        return super().__getitem__(key)


class FloorPose052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure reference geometry only')))
        self.dimensions=(300.,500.,500.)
        self.floor=Mesh('case-bottom',box(300.,3.,500.),(.1,.2,.3,1.),(0.,-232.5,0.))

    def test_actual_generic_floor_highest_surface_sets_full_axial_clearance(self):
        scene=minimal('corsair-4000d-airflow')
        floor=next(m for m in scene.meshes if m.name=='case-bottom')
        half=half_extents(get_fan('arctic-p12-pwm'))
        result=reference_bottom_pose(scene.meshes,scene.dimensions,half,{})
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['center'][1]-half[2],bounds(floor)[1][1]+.25)
        self.assertEqual((result['center'][0],result['center'][2]),(0.,0.))
        self.assertEqual(result['basis'],((1.,0.,0.),(0.,0.,1.),(0.,-1.,0.)))
        self.assertEqual(result['span'],(scene.dimensions[0]-24.,scene.dimensions[2]-32.))
        self.assertEqual(result['meta']['source_geometry_names'],('case-bottom',))
        self.assertFalse(result['meta']['complete_fit_verified'])
        self.assertFalse(result['meta']['manufacturer_plane_verified'])
        self.assertIsNone(reference_bottom_pose((),scene.dimensions,half,{}))

    def test_actual_dual_chamber_uses_left_skin_and_divider_not_selected_component(self):
        # An explicitly unregistered synthetic case exercises the generic
        # fallback. Exact O11D now owns an authored plane/open lower tray and
        # must not be silently repurposed as a generic closed-floor fixture.
        case=copy.deepcopy(get_case('lian-li-o11d-evo-rgb'))
        case.update(id='synthetic-unregistered-dual-reference',
                    label='Synthetic generic dual reference',sources=[])
        spec=dict(case=case,gpu=dict(present=False),memory=dict(count=0),
                  cpu=dict(telemetry_bound=False),cooling=dict(cpu_cooler='none',case_fans=[]),
                  detail_level='eco')
        scene=build_scene(spec)
        self.assertEqual(scene.metadata['case_id'],'synthetic-unregistered-dual-reference')
        self.assertNotIn('bottom',scene.metadata['attachment_anchors'].get('case_mount_planes',{}))
        floor=next(m for m in scene.meshes if m.name=='case-bottom')
        divider=next(m for m in scene.meshes if m.name=='rear-chamber-divider')
        glass=next(m for m in scene.meshes if m.name=='left-glass')
        result=reference_bottom_pose(scene.meshes,scene.dimensions,(70.,70.,14.),{})
        self.assertIsNotNone(result)
        left=bounds(glass)[1][0]+.25;right=bounds(divider)[0][0]-.25
        self.assertEqual(result['meta']['main_bay_x_window_mm'],(left,right))
        self.assertEqual(result['span'][0],right-left)
        self.assertEqual(result['center'][0],(left+right)/2)
        self.assertLess(result['center'][0]+70.,bounds(divider)[0][0])
        self.assertGreater(result['center'][0]-70.,bounds(glass)[1][0])
        self.assertAlmostEqual(result['center'][1]-14.,bounds(floor)[1][1]+.25)
        wide=reference_bottom_pose(scene.meshes,scene.dimensions,(150.,200.,14.),{})
        self.assertEqual(wide['center'],result['center']);self.assertEqual(wide['span'],result['span'])
        self.assertGreater(300.,wide['span'][0]) # Caller must reject, never shrink the window/fan.
        tall=reference_bottom_pose(scene.meshes,scene.dimensions,(70.,70.,20.),{})
        self.assertEqual(tall['span'],result['span'])
        self.assertEqual(tall['center'][0],result['center'][0])
        self.assertAlmostEqual(tall['center'][1]-result['center'][1],6.)
        unrelated=Mesh('selected-gpu-reference',box(900.,900.,900.),(.1,.2,.3,1.),component='gpu')
        self.assertEqual(reference_bottom_pose((*scene.meshes,unrelated),scene.dimensions,(70.,70.,14.),{}),result)
        authored=minimal('lian-li-o11d-evo-rgb')
        self.assertFalse(any(m.name=='case-bottom' for m in authored.meshes))
        planes=authored.metadata['attachment_anchors']['case_mount_planes']
        self.assertIn('bottom',planes);before=copy.deepcopy(planes)
        self.assertIsNone(reference_bottom_pose(authored.meshes,authored.dimensions,(70.,70.,14.),planes))
        self.assertEqual(planes,before)

    def test_existing_bottom_source_plane_including_real_y70_never_overridden(self):
        class Unreadable:
            def __getattribute__(self,name):raise AssertionError('Authored plane must exit first')
        for bottom in (None,{},dict(position=(1.,2.,3.),source='https://example.invalid/reference')):
            self.assertIsNone(reference_bottom_pose((Unreadable(),),self.dimensions,(60.,60.,13.),{'bottom':bottom}))
        scene=minimal('hyte-y70')
        planes=scene.metadata['attachment_anchors']['case_mount_planes']
        self.assertIn('bottom',planes);before=copy.deepcopy(planes)
        self.assertIsNone(reference_bottom_pose(scene.meshes,scene.dimensions,(60.,60.,13.),planes))
        self.assertEqual(planes,before)

    def test_missing_left_skin_has_explicit_floor_reference_fallback(self):
        divider=Mesh('rear-chamber-divider',box(2.,488.,488.),(.1,.2,.3,1.),(35.,0.,0.))
        result=reference_bottom_pose((self.floor,divider),self.dimensions,(60.,60.,13.),{})
        self.assertIsNotNone(result)
        self.assertEqual(result['meta']['left_boundary_basis'],'generic_floor_left_extent_plus_12mm_reference')
        self.assertEqual(result['meta']['main_bay_x_window_mm'],(-138.,33.75))
        self.assertEqual(result['meta']['source_geometry_names'],('case-bottom','rear-chamber-divider'))
        self.assertFalse(result['meta']['positions_verified'])

    def test_invalid_ambiguous_unknown_owners_and_non_generic_material_fail_closed(self):
        for meshes in ((),(self.floor,self.floor),(replace(self.floor,component='psu'),),
                       (replace(self.floor,name=[]),),(replace(self.floor,component=[]),),
                       (replace(self.floor,rotor=True),),(replace(self.floor,name='custom-open-floor'),),
                       (replace(self.floor,vertices=box(300.,40.,500.)),),
                       (replace(self.floor,vertices=box(100.,3.,100.)),),
                       (replace(self.floor,position=(0.,50.,0.)),)):
            self.assertIsNone(reference_bottom_pose(meshes,self.dimensions,(60.,60.,13.),{}))
        divider=Mesh('rear-chamber-divider',box(2.,488.,488.),(.1,.2,.3,1.),(35.,0.,0.))
        invalid=(replace(divider,component='gpu'),replace(divider,vertices=box(200.,2.,488.)),
                 replace(divider,position=(200.,0.,0.)))
        for source in invalid:
            self.assertIsNone(reference_bottom_pose((self.floor,source),self.dimensions,(60.,60.,13.),{}))
        self.assertIsNone(reference_bottom_pose((self.floor,divider,divider),self.dimensions,(60.,60.,13.),{}))
        for dims in ((True,500.,500.),(300.,float('nan'),500.),(300.,500.),(300.,500.,4000.)):
            self.assertIsNone(reference_bottom_pose((self.floor,),dims,(60.,60.,13.),{}))
        for half in ((60.,60.,0.),(60.,60.,True),(60.,60.,float('inf')),(60.,60.)):
            self.assertIsNone(reference_bottom_pose((self.floor,),self.dimensions,half,{}))
        self.assertIsNone(reference_bottom_pose((self.floor,),self.dimensions,(60.,60.,13.),None))
        bad=list(self.floor.vertices);bad[0]=float('nan')
        self.assertIsNone(reference_bottom_pose((replace(self.floor,vertices=tuple(bad)),),self.dimensions,(60.,60.,13.),{}))

    def test_only_selected_sources_scanned_once_with_hard_geometry_and_mesh_budgets(self):
        class Unrelated:
            name='case-upright';component='case'
            @property
            def vertices(self):raise AssertionError('Unrelated geometry must not be scanned')
        vertices=Counted(self.floor.vertices);floor=replace(self.floor,vertices=vertices)
        result=reference_bottom_pose((floor,Unrelated()),self.dimensions,(60.,60.,13.),{})
        self.assertIsNotNone(result)
        self.assertEqual(vertices.slices,len(vertices)//6)
        self.assertEqual(result['meta']['source_geometry_scans'],1)
        huge=replace(self.floor,vertices=Oversized())
        self.assertIsNone(reference_bottom_pose((huge,),self.dimensions,(60.,60.,13.),{}))
        self.assertIsNone(reference_bottom_pose([Unrelated()]*(MAX_MESHES+1),self.dimensions,(60.,60.,13.),{}))
        self.assertIsNone(reference_bottom_pose(iter((self.floor,)),self.dimensions,(60.,60.,13.),{}))

    def test_detached_small_result_contains_no_mesh_array_cache_or_mutated_input(self):
        planes=dict(side=dict(position=(1.,0.,0.)))
        before=copy.deepcopy(planes);vertices=self.floor.vertices
        result=reference_bottom_pose((self.floor,),self.dimensions,(60.,60.,13.),planes)
        result['meta']['source_geometry_names']=('changed',)
        result['meta']['floor_bounds_mm']=None
        again=reference_bottom_pose((self.floor,),self.dimensions,(60.,60.,13.),planes)
        self.assertEqual(again['meta']['source_geometry_names'],('case-bottom',))
        self.assertEqual(planes,before);self.assertIs(self.floor.vertices,vertices)
        self.assertEqual(again['meta']['new_meshes'],0)
        self.assertEqual(again['meta']['new_clocks'],0);self.assertEqual(again['meta']['new_pollers'],0)
        def contains_reference(value):
            if isinstance(value,Mesh) or value is vertices:return True
            if isinstance(value,dict):return any(contains_reference(v) for v in value.values())
            if isinstance(value,(list,tuple)):return any(contains_reference(v) for v in value)
            return False
        self.assertFalse(contains_reference(again))


if __name__=='__main__':unittest.main()
