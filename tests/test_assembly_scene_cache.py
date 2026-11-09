"""Changing artwork does not repeat geometry, cable routing or QML profiling."""
import copy
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,Scene,box
from assembly_scene_cache import SceneCache
from top_bar_config import HARDWARE_ICON_STYLES


class AssemblySceneCacheTests(unittest.TestCase):
    def test_style_and_single_part_changes_keep_one_original_geometry_snapshot(self):
        base=Scene((Mesh('ram-pcb',box(10,20,1),(.2,.4,.3,1.),component='memory',part_id='memory:0'),),
                   (200,400,400),dict(visual_style='miniature',cooling={'parts':[]},auxiliary={'parts':[]}))
        cache=SceneCache();spec={'memory':{'count':1},'case':{'panels':{'front':'open'}},'cooling':{'cpu_cooler':'none'}}
        before=copy.deepcopy(spec)
        with patch('assembly_scene_cache.build_scene',return_value=base) as build:
            for style in HARDWARE_ICON_STYLES:
                result=cache.build(dict(spec,visual_style=style,part_styles={'memory:0':'notebook_color'}))
                self.assertIs(result.meshes[0].vertices,base.meshes[0].vertices)
                self.assertEqual(result.metadata['part_style_map']['memory:0'],'notebook_color')
                self.assertEqual(result.dimensions,base.dimensions)
            self.assertIs(cache.build(spec),base)
            build.assert_called_once()
            self.assertEqual(build.call_args.args[0]['visual_style'],'miniature')
            self.assertEqual(build.call_args.args[0]['part_styles'],{})
            cache.build(dict(spec,cooling={'cpu_cooler':'noctua-nh-u12a'}))
            self.assertEqual(build.call_count,2)
        self.assertEqual(spec,before)
        cache.clear();self.assertIsNone(cache.base);self.assertIsNone(cache.key)

    def test_rejected_configuration_preserves_the_previous_geometry_and_cache_identity(self):
        cache=SceneCache();base=Scene((Mesh('case',box(10,10,10),(1,1,1,1)),),(200,400,400),{'visual_style':'miniature'})
        with patch('assembly_scene_cache.build_scene',side_effect=[base,ValueError('detail budget')]) as build:
            cache.build({'case':{'id':'first'}});key=cache.key
            with self.assertRaises(ValueError):cache.build({'case':{'id':'second'}})
            self.assertIs(cache.base,base);self.assertEqual(cache.key,key)
            self.assertIs(cache.build({'case':{'id':'first'}}),base)
            self.assertEqual(build.call_count,2)


if __name__=='__main__':unittest.main()
