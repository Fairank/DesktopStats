"""New structures preserve physical identity in every drawing scheme."""
import math
import unittest

from accessory_art import art,clear_cache
from assembly_cooling import add_cooling
from assembly_geometry import build_scene
from assembly_motherboard import final_anchors
from chassis_catalog import get_case
from cooling_catalog import get_fan
from top_bar_config import HARDWARE_ICON_STYLES

ANCHORS={'cpu':{'position':(0.,0.,0.),'normal':(0.,1.,0.),'up':(0.,0.,1.)},'case_dimensions':(600.,800.,800.)}


class AccessoryDetails039Tests(unittest.TestCase):
    def tearDown(self):clear_cache()

    def test_passive_sink_is_actually_fanless_in_all_styles_and_native_geometry(self):
        for style in HARDWARE_ICON_STYLES:
            row=art('cooler','noctua-nh-p1',style)
            self.assertEqual(row['rotors'],[])
            self.assertIn('thirteen-passive-fins',row['svg'])
        for level in ('eco','balanced','close'):
            meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'noctua-nh-p1'}},level,ANCHORS)
            self.assertTrue(meshes)
            self.assertFalse(any(m.rotor for m in meshes))
            self.assertEqual(meta['fans'],[])
            self.assertFalse(meta['cpu_fan_tach_usable'])
            self.assertEqual(meta['real_cpu_rotor_parts'],[])
            self.assertFalse(meta['rejected'])
            self.assertTrue(all(math.isfinite(v) for m in meshes for v in m.vertices))

    def test_fuma_keeps_different_front_and_centre_fans(self):
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'scythe-fuma3'}},'eco',ANCHORS)
        self.assertEqual([f['model_id'] for f in meta['fans']],['scythe-kaze-flex-ii120-slim','scythe-kaze-flex-ii120'])
        for style in HARDWARE_ICON_STYLES:
            row=art('cooler','scythe-fuma3',style)
            self.assertEqual(len(row['rotors']),2)
            self.assertIn('data-blade-count="9"',row['rotors'][0]['svg'])
            self.assertIn('data-blade-count="11"',row['rotors'][1]['svg'])

    def test_lcd_and_grille_are_stationary_but_blades_remain_separate(self):
        for model,marker in (('lian-li-uni-tllcd120','stationary-blank-lcd'),('silverstone-ap183','stationary-reference')):
            for style in HARDWARE_ICON_STYLES:
                row=art('fan',model,style)
                self.assertEqual(len(row['rotors']),1)
                self.assertIn(marker,row['foreground_svg'])
                self.assertNotIn(marker,row['rotors'][0]['svg'])
            meshes,meta=add_cooling((),{'cooling':{'case_fans':[dict(model=model,mount='front',count=1)]}},'eco',ANCHORS)
            self.assertEqual(len([m for m in meshes if m.rotor]),1)
            self.assertTrue(any('stationary' in m.name and not m.rotor for m in meshes))
            self.assertIsNone(meta['fans'][0]['rpm'])

    def test_reverse_pitch_changes_leaves_without_inventing_reverse_rpm(self):
        for style in HARDWARE_ICON_STYLES:
            reverse=art('fan','phanteks-d30-120-reverse',style)
            regular=art('fan','phanteks-d30-120-regular',style)
            self.assertIn('reverse-pitch',reverse['rotors'][0]['svg'])
            self.assertNotEqual(reverse['rotors'][0]['svg'],regular['rotors'][0]['svg'])
            self.assertEqual(reverse['rotors'][0]['direction'],1)
            self.assertFalse(reverse['rotation_direction_verified'])

    def test_translated_board_anchor_positions_do_not_translate_unit_directions(self):
        anchors={'board':{'position':(10.,20.,30.),'normal':(-1.,0.,0.),'up':(0.,1.,0.)},
                 'connectors':{'fan':[dict(position=(1.,2.,3.),normal=(1.,0.,0.),along=(0.,1.,0.))]}}
        vector=lambda p:(p[1],-p[0],p[2])
        pose=lambda p:tuple(v+shift for v,shift in zip(vector(p),(5.,70.,-8.)))
        result=final_anchors(anchors,pose,pose,None,None,{},board_vector=vector)
        self.assertEqual(result['board']['position'],(25.,60.,22.))
        self.assertEqual(result['board']['normal'],(0.,1.,0.))
        self.assertEqual(result['connectors']['fan'][0]['position'],(7.,69.,-5.))
        self.assertEqual(result['connectors']['fan'][0]['normal'],(0.,-1.,0.))

    def test_test_bench_board_is_full_size_and_above_its_platform(self):
        scene=build_scene({'case':get_case('streacom-bc1-v2'),'gpu':{'present':False},'memory':{'count':0}})
        board=next(m for m in scene.meshes if m.name=='motherboard-reference')
        self.assertEqual(scene.dimensions,(370.,115.,260.))
        self.assertAlmostEqual(board.position[1],66.3)
        self.assertAlmostEqual(min(board.vertices[1::6])+board.position[1],65.5)
        self.assertGreater(max(board.vertices[0::6])-min(board.vertices[0::6]),100)

    def test_front_chamber_poses_only_an_explicit_gpu_and_preserves_card_dimensions(self):
        case=get_case('lian-li-sup01')
        empty=build_scene({'case':case,'gpu':{'present':False},'memory':{'count':0}})
        self.assertFalse(any(m.component=='gpu' for m in empty.meshes))
        full=build_scene({'case':case,'gpu':{'present':True},'memory':{'count':0}})
        self.assertEqual(full.metadata['gpu_mount'],'front_vertical')
        gpu=full.metadata['attachment_anchors']['gpu']
        self.assertEqual(gpu['normal'],(0.,0.,1.))
        self.assertEqual(gpu['along'],(0.,1.,0.))
        self.assertEqual(full.metadata['attachment_anchors']['board']['normal'],(-1.,0.,0.))
        self.assertFalse(full.metadata['gpu_mount_observation']['position_dimensions_verified'])


if __name__=='__main__':unittest.main()
