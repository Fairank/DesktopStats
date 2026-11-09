"""Static light preview changes observed zones without extra geometry or clocks."""
import unittest
from unittest.mock import Mock,patch

from assembly_config import validate_assembly
from assembly_geometry import Mesh,Scene,box
from assembly_lighting import MODES,COLORS,apply_lighting,light_kind
from assembly_scene_cache import SceneCache
from assembly_style import apply_model_styles
from assembly_viewer import AssemblyRenderer
from top_bar_config import HARDWARE_ICON_STYLES


class LightingPreviewTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No device or background work')))
        self.meshes=tuple(Mesh(name,box(8,12,1),(.3,.5,.6,1.),component=kind,part_id=part)
            for name,kind,part in (('ram-diffuser','memory','memory:0'),
                ('case-fan-0-static-rgb-hub','fans','fans:0'),
                ('cooler-pump-white-light-ring','cooler','cooler:0'),
                ('case-fan-0-argb-connector','fans','fans:0'),
                ('gpu-pcb','gpu','gpu:0')))

    def test_all_styles_keep_geometry_counts_and_only_explicit_light_zones_change(self):
        for style in HARDWARE_ICON_STYLES:
            artwork,baseline=apply_model_styles(self.meshes,style,{},(100,100,100),{'front':'open'})
            for mode in MODES:
                meshes,meta=apply_model_styles(self.meshes,style,{},(100,100,100),{'front':'open'},mode)
                self.assertEqual(len(meshes),len(self.meshes))
                self.assertEqual([r['mesh_index'] for r in meta['lighting_preview']['zones']],[0,1,2])
                self.assertFalse(meta['lighting_preview']['animated'])
                self.assertFalse(meta['lighting_preview']['device_control'])
                for source,target,original in zip(self.meshes,meshes,artwork):
                    self.assertIs(source.vertices,target.vertices)
                    self.assertEqual((target.position,target.axis,target.rotor),(source.position,source.axis,source.rotor))
                    if not light_kind(source):self.assertEqual(target.color,original.color)
                if mode not in ('artwork','off'):
                    self.assertEqual(meshes[0].color,COLORS[mode])
                    self.assertEqual(meshes[2].color,(1.,.96,.87,1.))

    def test_palette_changes_reuse_one_physical_snapshot_and_lines_use_colored_ink(self):
        cache=SceneCache();base=Scene(self.meshes,(100,100,100),{'visual_style':'miniature'})
        with patch('assembly_scene_cache.build_scene',return_value=base) as build:
            for mode in MODES:
                scene=cache.build(dict(visual_style='notebook_line',lighting_preview=mode))
                self.assertIs(scene.meshes[0].vertices,base.meshes[0].vertices)
            build.assert_called_once()
        renderer=AssemblyRenderer();renderer.program=Mock();renderer.buffer=Mock();renderer.vao=Mock();renderer.functions=Mock()
        renderer._uniforms={'backgroundMode':1,'shadeMix':2}
        self.addCleanup(renderer.close)
        renderer.upload(scene)
        self.assertEqual(renderer._preview_light_tones[id(scene.meshes[0])],COLORS['violet'])
        renderer.draw(320,240)
        self.assertEqual(renderer.upload_count,1)
        renderer.close();self.assertEqual(renderer._preview_light_tones,{})

    def test_actual_infinity_hub_rings_all_turn_off_without_touching_rotors(self):
        from assembly_cooling import add_cooling
        from tests.test_assembly_cooling import ANCHORS
        spec=dict(case=dict(fan_mounts=[dict(position='front',count=1,size_mm=[120])]),
            cooling=dict(cpu_cooler='none',case_fans=[dict(model='lian-li-uni-slinf120',mount='front',count=1,direction='intake')]))
        meshes,_=add_cooling((),spec,'balanced',ANCHORS)
        rings=[m for m in meshes if m.name.endswith('-infinity-hub-rings')]
        self.assertEqual(len(rings),1)  # Existing three rings share one retained mesh.
        for mode in ('off','mint','violet'):
            result,metadata=apply_lighting(meshes,mode)
            self.assertEqual([m.color for m in result if m.name.endswith('-infinity-hub-rings')],[COLORS[mode]]*len(rings))
            self.assertEqual([m for m in result if m.rotor],[m for m in meshes if m.rotor])
            self.assertEqual(len(result),len(meshes))
            self.assertFalse(metadata['lighting_preview']['geometry_added'])

    def test_unknown_preference_cannot_create_a_device_action(self):
        self.assertEqual(validate_assembly()['lighting_preview'],'artwork')
        for mode in MODES:self.assertEqual(validate_assembly({'lighting_preview':mode})['lighting_preview'],mode)
        for value in ('rainbow',True,None,{},['off']):
            with self.assertRaises(ValueError):validate_assembly({'lighting_preview':value})
            meshes,meta=apply_lighting(self.meshes,value)
            self.assertEqual(meta['lighting_preview']['mode'],'artwork')
            self.assertEqual(meshes,self.meshes)


if __name__=='__main__':unittest.main()
