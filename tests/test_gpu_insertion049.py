"""Pure plan/state verification; no renderer, window, clocks or sensor access."""
import copy
from dataclasses import replace
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,Scene,box,color
from assembly_gpu_insertion049 import GpuInsertion,insertion_plan


def fixture(normal=(-1.,0.,0.),dimensions=(240.,509.,503.)):
    # Saved NorthXL/Astral reference envelope: fixed case/board/RAM plus the
    # actual card envelope, not a whole native/CAD installation acceptance.
    low=(-59.914,-92.715,-237.5);high=(89.386,-16.715,120.1)
    center=tuple((a+b)/2 for a,b in zip(low,high));size=tuple(b-a for a,b in zip(low,high))
    meshes=(Mesh('gpu-pcb',box(*size),color('#778899'),center,'gpu',part_id='gpu:0'),
            Mesh('motherboard-reference',box(2.,305.,244.),color('#223344'),(85.,10.,-115.),'board',part_id='board:0'),
            Mesh('memory-spreader',box(12.,40.,133.),color('#445566'),(72.,76.,-30.),'memory',part_id='memory:0'))
    metadata=dict(gpu_mount='horizontal',attachment_anchors={'board':{'normal':normal}},auxiliary={'cables':[],'cable_count':0})
    return Scene(meshes,dimensions,metadata)


def cable(scene,prefix='cable-3-gpu16',owner='gpu'):
    meta=copy.deepcopy(scene.metadata)
    meta['auxiliary']={'cables':[dict(target_owner=owner,mesh_prefix=prefix)],'cable_count':1}
    mesh=Mesh(prefix+'-rounded-loom',box(5.,5.,15.),color('#222222'),component='cables',part_id='cables:all')
    return replace(scene,meshes=scene.meshes+(mesh,),metadata=meta)


class GpuInsertion049Tests(unittest.TestCase):
    def setUp(self):
        for target in ('builtins.open','socket.socket','threading.Thread.start','subprocess.Popen','ctypes.WinDLL'):
            self.enterContext(patch(target,side_effect=AssertionError('Pure plan/state only')))

    def test_normal_north_reference_plan_direction_margin_and_detached_inputs(self):
        scene=cable(fixture());before=copy.deepcopy(scene)
        plan=insertion_plan(scene)
        self.assertTrue(plan['available']);self.assertEqual(plan['direction'],(-1.,0.,0.))
        self.assertEqual(plan['distance_mm'],52.);self.assertEqual(plan['gpu_cable_prefixes'],('cable-3-gpu16',))
        self.assertGreaterEqual(-59.914-plan['distance_mm'],-120.+8.)
        self.assertEqual(scene,before)
        plan['direction']=(1.,0.,0.);self.assertEqual(scene,before)

    def test_diagonal_board_normal_uses_first_case_boundary_and_requires16mm(self):
        scene=fixture(normal=(-3.,0.,4.),dimensions=(240.,509.,503.))
        plan=insertion_plan(scene);self.assertTrue(plan['available'])
        self.assertEqual(plan['direction'],(-.6,0.,.8))
        self.assertLessEqual(plan['distance_mm'],52.)
        tiny=replace(scene,dimensions=(150.,509.,503.))
        self.assertFalse(insertion_plan(tiny)['available'])
        narrow=fixture(dimensions=(167.,509.,503.))
        self.assertEqual(insertion_plan(narrow)['reason'],'gpu_outside_case_envelope')
        card=Mesh('gpu-pcb',box(100.,40.,200.),color('#223344'),(-55.,0.,0.),'gpu')
        narrow=replace(fixture(),meshes=(card,))
        self.assertEqual(insertion_plan(narrow)['reason'],'insufficient_side_clearance')

    def test_rotor_bound_contains_every_phase_rather_than_only_current_leaf_pose(self):
        # Current blade points are narrow inX, but rotating aboutZ sweeps the
        # full35mm radius and leaves only7mm before the8mm side margin.
        verts=(0.,-35.,0.,0.,0.,1., 1.,35.,0.,0.,0.,1., -1.,35.,0.,0.,0.,1.)
        rotor=Mesh('gpu-fan-rotor',verts,color('#222222'),(-70.,0.,0.),'gpu',True,axis=(0.,0.,1.))
        scene=replace(fixture(),meshes=(rotor,))
        self.assertEqual(insertion_plan(scene)['reason'],'insufficient_side_clearance')
        rotor=replace(rotor,position=(-40.,0.,0.));scene=replace(scene,meshes=(rotor,))
        plan=insertion_plan(scene);self.assertTrue(plan['available'])
        self.assertAlmostEqual(plan['distance_mm'],120.-8.-40.-math.sqrt(1226.))

    def test_vertical_unknown_empty_invalid_and_watercooled_scenes_fail_closed(self):
        self.assertFalse(insertion_plan(None)['available'])
        for mount in ('vertical','front_vertical','case_vertical','unknown',None):
            scene=fixture();scene.metadata['gpu_mount']=mount
            self.assertEqual(insertion_plan(scene)['reason'],'gpu_mount_unsupported')
        scene=fixture();scene.metadata['attachment_anchors']['board']['normal']=(0.,0.,0.)
        self.assertEqual(insertion_plan(scene)['reason'],'board_normal_unverified')
        scene.metadata['attachment_anchors']['board']['normal']=(1.7e308,1.7e308,1.7e308)
        self.assertEqual(insertion_plan(scene)['reason'],'board_normal_unverified')
        scene=fixture();scene.metadata['cooling']={'replace_gpu_cooler':True}
        self.assertEqual(insertion_plan(scene)['reason'],'gpu_waterblock_unsupported')
        scene=fixture();water=Mesh('gpu-waterblock-cover',box(1.,1.,1.),color('#123456'),component='cooler')
        self.assertEqual(insertion_plan(replace(scene,meshes=scene.meshes+(water,)))['reason'],'gpu_waterblock_unsupported')
        self.assertEqual(insertion_plan(replace(fixture(),meshes=()))['reason'],'gpu_geometry_unverified')
        self.assertEqual(insertion_plan(replace(fixture(),dimensions=(float('nan'),509.,503.)))['reason'],'case_dimensions_unverified')

    def test_gpu_power_requires_exact_owned_prefix_and_actual_matching_geometry(self):
        scene=cable(fixture());scene.metadata['auxiliary']['cables'][0].pop('mesh_prefix')
        self.assertEqual(insertion_plan(scene)['reason'],'gpu_cable_prefix_missing')
        scene=cable(fixture());scene.metadata['auxiliary']['cables']=[]
        self.assertFalse(insertion_plan(scene)['available'])
        scene=cable(fixture());scene.metadata['auxiliary']['cables'][0]['mesh_prefix']='missing'
        self.assertEqual(insertion_plan(scene)['reason'],'gpu_cable_geometry_unverified')
        scene=cable(fixture());scene.metadata['auxiliary']['cables'].append(dict(target_owner='board',mesh_prefix='cable-3'))
        self.assertEqual(insertion_plan(scene)['reason'],'gpu_cable_prefix_ambiguous')
        scene=fixture();unknown=Mesh('unmapped-power-loom',box(1.,1.,1.),color('#123456'),component='cables')
        self.assertEqual(insertion_plan(replace(scene,meshes=scene.meshes+(unknown,)))['reason'],'cable_owner_unverified')

    def test_gpu_prefix_does_not_match_different_number_or_non_gpu_power(self):
        scene=cable(fixture(),'cable-3-gpu16')
        other=Mesh('cable-30-eps8-rounded-loom',box(1.,1.,1.),color('#123456'),component='cables')
        scene=replace(scene,meshes=scene.meshes+(other,))
        scene.metadata['auxiliary']['cables'].append(dict(target_owner='board',mesh_prefix='cable-30-eps8'))
        plan=insertion_plan(scene);self.assertTrue(plan['available'])
        self.assertEqual(plan['gpu_cable_prefixes'],('cable-3-gpu16',))
        other_only=cable(fixture(),'cable-1-eps8','board')
        self.assertEqual(insertion_plan(other_only)['gpu_cable_prefixes'],())

    def test_finite960ms_smoothstep_completion_has_no_automatic_return(self):
        state=GpuInsertion();plan=insertion_plan(fixture())
        self.assertTrue(state.start(True));self.assertFalse(state.start(True));self.assertTrue(state.active)
        for _ in range(30):self.assertTrue(state.advance(16.))
        self.assertAlmostEqual(state.progress,.5);self.assertEqual(state.target,1.)
        for _ in range(30):state.advance(16.)
        self.assertEqual(state.progress,1.);self.assertFalse(state.active)
        self.assertEqual(state.offset(plan),(-52.,0.,0.))
        for _ in range(100):self.assertFalse(state.advance(136.))
        self.assertEqual(state.progress,1.)

    def test_reverse_keeps_current_position_and_finishes_at_inserted_endpoint(self):
        state=GpuInsertion();state.start(True)
        for _ in range(3):state.advance(120.)
        old=state.progress;self.assertGreater(old,0.);self.assertLess(old,1.)
        self.assertTrue(state.start(False));self.assertEqual(state.progress,old)
        samples=[]
        for _ in range(8):state.advance(136.);samples.append(state.progress)
        self.assertTrue(all(a>=b for a,b in zip([old]+samples,samples)))
        self.assertEqual(state.progress,0.);self.assertFalse(state.active)

    def test_invalid_ticks_are_inert_large_tick_capped_and_reset_idempotent(self):
        state=GpuInsertion();self.assertFalse(state.reset());self.assertFalse(state.start('remove'))
        state.start(True)
        for value in (None,True,False,0.,-1.,float('nan'),float('inf'),'16'):
            self.assertFalse(state.advance(value));self.assertEqual(state.progress,0.)
        self.assertTrue(state.advance(100000.))
        phase=136./960.;self.assertAlmostEqual(state.progress,phase*phase*(3.-2.*phase))
        self.assertTrue(state.reset());self.assertFalse(state.active);self.assertEqual(state.progress,0.)
        self.assertEqual(state.target,0.);self.assertFalse(state.reset())

    def test_disabled_or_invalid_offset_is_zero_and_no_state_owns_scene_references(self):
        state=GpuInsertion();state.start(True)
        for _ in range(8):state.advance(136.)
        for plan in (None,{},dict(available=False),dict(available=True,direction=(1,0,float('nan')),distance_mm=30),
                     dict(available=True,direction=(1,0,0),distance_mm=float('inf')),
                     dict(available=True,direction=(3,0,0),distance_mm=52)):
            self.assertEqual(state.offset(plan),(0.,0.,0.))
        self.assertTrue(all(isinstance(v,(bool,int,float)) for v in state.__dict__.values()))


if __name__=='__main__':unittest.main()
