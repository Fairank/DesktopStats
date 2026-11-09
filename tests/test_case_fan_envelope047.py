"""Actual fan construction and full rotor sweep inside one-build scalar bounds."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import hardware_packs
from hardware_packs import PackStore,make_pack
from cooling_catalog import _FANS,get_fan
from tools.export_cooling_packs045 import pack_models
from assembly_cooling import _Builder,_fan,_basis
from assembly_geometry import Mesh,box
from case_fan_clearance047 import _SKIP,blockers,conflicts,envelope,half_extents


def rigid_meshes(builder):
    return tuple(mesh for mesh in builder.finish() if mesh.vertices and not any(word in mesh.name for word in _SKIP))


def assert_contains(test,model,level,normal,up,center):
    builder=_Builder(level);_fan(builder,model,center,normal,up,component='fans',part='fans:rear:0')
    basis=_basis(normal,up);bounds=envelope(model,center,basis);meshes=rigid_meshes(builder)
    test.assertTrue(meshes)
    for mesh in meshes:
        if mesh.rotor:
            # The exact support of each vertex's circular orbit around its
            # actual axis covers every angle, not just the retained phase0.
            axis=mesh.axis;test.assertAlmostEqual(sum(v*v for v in axis),1.)
            lows=[math.inf]*3;highs=[-math.inf]*3
            for n in range(0,len(mesh.vertices),6):
                point=mesh.vertices[n:n+3];along=sum(a*b for a,b in zip(point,axis))
                radial=math.sqrt(max(0.,sum(v*v for v in point)-along*along))
                for k in range(3):
                    reach=radial*math.sqrt(max(0.,1.-axis[k]*axis[k]))
                    origin=mesh.position[k]+axis[k]*along
                    lows[k]=min(lows[k],origin-reach);highs[k]=max(highs[k],origin+reach)
        else:
            lows=[min(mesh.vertices[k::6])+mesh.position[k] for k in range(3)]
            highs=[max(mesh.vertices[k::6])+mesh.position[k] for k in range(3)]
        for k in range(3):
            test.assertGreaterEqual(lows[k]+1e-7,bounds[0][k],(model['id'],level,mesh.name,k,lows[k],bounds))
            test.assertLessEqual(highs[k]-1e-7,bounds[1][k],(model['id'],level,mesh.name,k,highs[k],bounds))
    test.assertIsNone(builder.fans[0]['rpm']);test.assertEqual(builder.fans[0]['rotation_default'],'static')
    return meshes,bounds


class CaseFanEnvelope047Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='desktopstats-fan-envelope047-')
        folder=Path(cls.temp.name);cls.store=PackStore(folder/'private-profile/packs')
        rows=pack_models()['fan'];assert len(rows)==40
        archive=folder/'fans.dspack';archive.write_bytes(make_pack('envelope-fans047','Private fan envelope controls',rows,kind='fan'))
        cls.store.install(archive)
        cls.patcher=patch.object(hardware_packs,'_store',cls.store);cls.patcher.start()
        cls.models=[get_fan(row['id']) for row in _FANS]+[get_fan(row['id']) for row in rows]
        cls.optional_ids={row['id'] for row in rows}
        assert len(cls.models)==110 and len({row['id'] for row in cls.models})==110

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop();cls.temp.cleanup()

    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('Pure geometry only')))

    def test_all70_base_and40_actual_optional_models_three_lods_contain_rigid_and_swept_vertices(self):
        original=copy.deepcopy(self.models)
        for index,model in enumerate(self.models):
            normal=((.3,.4,.8),(-.7,.2,-.4),(0.,1.,0.))[index%3]
            up=((.2,1.,.3),(1.,.4,.2),(0.,2.,.1))[index%3]
            for level in ('eco','balanced','close'):
                with self.subTest(model=model['id'],optional=model['id'] in self.optional_ids,lod=level):
                    assert_contains(self,model,level,normal,up,(13.,-27.,41.))
        self.assertEqual(self.models,original)
        self.assertEqual(self.store.memory_status()['background_workers'],0)

    def test_round_ears_reach_beyond_the_old_nominal_box_without_changing_geometry(self):
        expected={'noctua-nf-a14x25r-g2-pwm':(76.05,76.05,15.5),
                  'thermalright-ty147a':(76.5,76.05,16.25),
                  'thermaltake-pure20-argb':(102.5,102.5,18.),
                  'bequiet-tf2-upper135':(69.35,69.35,15.5),
                  'bequiet-tf2-lower135':(69.35,69.35,14.)}
        for identity,half in expected.items():
            model=get_fan(identity)
            for actual,value in zip(half_extents(model),half):self.assertAlmostEqual(actual,value)
        model=get_fan('noctua-nf-a14x25r-g2-pwm')
        full=envelope(model,(0.,0.,0.),((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)))
        obstacle=[('gpu:0','gpu-backplate',((73.,73.,-2.),(75.,75.,2.)))]
        self.assertEqual(conflicts(((-70.5,-70.5,-15.5),(70.5,70.5,15.5)),obstacle),[])
        self.assertEqual(conflicts(full,obstacle),['gpu:0'])
        builder=_Builder('close');_fan(builder,model,(0.,0.,0.),(0.,0.,1.),(1.,0.,0.))
        frame=next(m for m in builder.finish() if m.name=='case-fan-frame')
        self.assertAlmostEqual(max(frame.vertices[0::6]),75.55)
        self.assertAlmostEqual(max(frame.vertices[1::6]),75.55)

    def test_verified_two_axis_round_mounts_and_non_square_width_use_the_real_local_axes(self):
        model=get_fan('noctua-nf-a12x25-pwm')
        model.update(frame='round',width_mm=140.,size_mm=120.,mount_pitch_axes_mm=[150.,70.],
                     mount_pitch_axes_verified=True,mount_pitch_axes_orientation_verified=False)
        self.assertAlmostEqual(half_extents(model)[0],86.9)
        self.assertAlmostEqual(half_extents(model)[1],60.5)
        for level in ('eco','balanced','close'):
            assert_contains(self,model,level,(.4,.7,-.2),(0.,1.,.3),(-11.,6.,20.))
        # Unknown orientation stays reference; matching the drawing order is
        # not a new claim that this constitutes a verified installation pose.
        model['mount_pitch_axes_verified']=False
        self.assertNotAlmostEqual(half_extents(model)[0],86.9)
        wide=get_fan('lian-li-uni-tllcd120')
        self.assertEqual(half_extents(wide),(62.5,60.5,17.))

    def test_thin_large_camber_and_permitted_polygon_controls_cover_all_rotor_phases(self):
        model=get_fan('arctic-p12-pwm');model.update(size_mm=250.,width_mm=100.,depth_mm=5.,
            frameless=True,frame='square',pads=False,mount_pitch_mm=None)
        self.assertGreater(half_extents(model)[2],model['depth_mm']/2+3.)
        assert_contains(self,model,'close',(.4,-.2,.7),(.1,1.,.3),(7.,3.,-12.))
        polygon=get_fan('arctic-p12-pwm');polygon.update(blades=2,
            blade_polygons=[[[4.,4.],[3.,4.],[3.,3.]],[[4.,-4.],[3.,-4.],[3.,-3.]]])
        self.assertGreater(half_extents(polygon)[0],100.)
        assert_contains(self,polygon,'balanced',(1.,2.,3.),(0.,1.,0.),(0.,0.,0.))

    def test_standard_reference_allowances_stay_stable_and_helper_builds_no_mesh(self):
        model=get_fan('arctic-p12-pwm')
        with (patch('assembly_cooling._fan',side_effect=AssertionError('No mesh build')),
              patch('assembly_geometry.ring',side_effect=AssertionError('No mesh build'))):
            self.assertEqual(half_extents(model),(60.5,60.5,15.5))
            first=envelope(model,(2.,3.,4.),_basis((0.,0.,1.),(0.,1.,0.)))
            self.assertEqual(first,((-58.5,-57.5,-11.5),(62.5,63.5,19.5)))

    def test_only_declared_flexible_names_are_excluded_and_rigid_tubes_fittings_remain(self):
        self.assertEqual(_SKIP,('wire','lead','connector','cooler-liquid-tubes','loop-reference-routed-tube'))
        vertices=box(3.,4.,5.);tint=(.2,.3,.4,1.)
        names=('cooler-liquid-tubes','loop-reference-routed-tube','cooler-power-lead','cooler-wire','cooler-power-connector',
               'cooler-heatpipes','cooler-liquid-tube-elbow','loop-rigid-tube','loop-compression-fitting')
        static={(name,tint,'cooler','cooler:cpu'):vertices for name in names}
        retained=blockers((),static,[])
        self.assertEqual({name for _,name,_ in retained},set(names[-4:]))


if __name__=='__main__':unittest.main()
