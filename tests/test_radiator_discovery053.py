"""Real gallery inventory and bounded dispatch without a profile or graphics."""
import builtins
import copy
import unittest
from unittest.mock import patch

import accessory_art as art
import cooling_catalog
import cooling_pack_runtime045
import liquid_component_runtime046
from liquid_cooling_catalog044 import IDS,records


class RadiatorDiscovery053Tests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(art,'_CHOICES',None))
        self.enterContext(patch.object(art,'_CHOICES_GENERATION',-1))
        self.enterContext(patch.object(art,'_library_generation',return_value=53))
        self.enterContext(patch.object(cooling_catalog,'choices_coolers',return_value=copy.deepcopy(cooling_catalog._COOLERS)))
        self.enterContext(patch.object(cooling_catalog,'choices_fans',return_value=copy.deepcopy(cooling_catalog._FANS)))
        self.enterContext(patch.object(liquid_component_runtime046,'grouped_choices',return_value={kind:[] for kind in art._LOOP_KINDS}))
        self.optional=self.enterContext(patch.object(cooling_pack_runtime045,'radiator_choices',return_value=[]))
        self.original_import=builtins.__import__
        def guard(name,*args,**kwargs):
            if name in ('hardware_packs','assembly_radiator044','assembly_geometry','radiator_svg053','liquid_svg046','PySide6','stats_config','psutil'):
                raise AssertionError('Inventory must not load a profile, projection or device module: '+name)
            return self.original_import(name,*args,**kwargs)
        self.enterContext(patch('builtins.__import__',side_effect=guard))

    def test_bundled_radiators_are_discoverable_without_building_any_mesh(self):
        result=art.choices()
        self.assertEqual([r['id'] for r in result['radiators']],list(IDS))
        self.assertEqual({r['brand'] for r in result['radiators']},{r['brand'] for r in records()})
        self.assertEqual(len(result['radiators']),24)
        self.assertTrue(all(set(r)=={'id','label','brand','fidelity'} for r in result['radiators']))
        self.assertEqual(art.cache_info()['entries'],0)
        result['radiators'].clear()
        self.assertEqual(len(art.choices()['radiators']),24)

    def test_optional_radiator_metadata_appears_after_generation_change(self):
        self.assertEqual(len(art.choices()['radiators']),24)
        self.optional.return_value=[dict(id='sample-optional-radiator',label='Optional reference',brand='Example')]
        art._library_generation.return_value=54
        rows=art.choices()['radiators']
        self.assertEqual(len(rows),25)
        self.assertEqual(rows[-1]['id'],'sample-optional-radiator')
        self.assertEqual(art.cache_info()['entries'],0)
        self.assertEqual(art.model_key('radiator','sample-optional-radiator','miniature'),
                         ('radiator','sample-optional-radiator','miniature',54))

    def test_invalid_radiator_requests_do_not_resolve_or_render(self):
        for identity in ('../other','',None,'x'*65):
            self.assertEqual(art.art('radiator',identity,'miniature'),{})
        self.assertEqual(art.art('radiator',IDS[0],'unknown-style'),{})
        self.assertEqual(art.cache_info()['max_entries'],16)


if __name__=='__main__':unittest.main()
