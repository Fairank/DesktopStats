"""Independently reviewed official front images, exact SKU-only corrections."""
import unittest
import xml.etree.ElementTree as ET
from hardware_appearance import appearance_for
from tests import test_gpu_model_art041 as fixture

ROWS=(('biostar-radeon-rx7600-va7606rm81',9,2),
      ('biostar-radeon-rx7600-oc-va76s6rm81',11,2),
      ('intel-limited-arc-a770-16g',15,2),('powercolor-reaper-9070xt',9,3),
      ('nvidia-gtx1080-founders',53,1),('msi-r9-290x-4gd5-reference',45,1))


class VerifiedGpu043Tests(unittest.TestCase):
    setUpClass=classmethod(fixture.GpuModelArt041Tests.setUpClass.__func__)
    setUp=fixture.GpuModelArt041Tests.setUp
    tearDown=fixture.GpuModelArt041Tests.tearDown
    evaluate=fixture.GpuModelArt041Tests.evaluate
    artwork=fixture.GpuModelArt041Tests.artwork

    def test_exact_models_keep_their_individually_reviewed_leaf_counts_all_styles(self):
        for identity,blades,fans in ROWS:
            a=fixture.exact(identity)
            self.assertTrue(a['fan_profile']['render_ready'])
            self.assertEqual(a['fan_count'],fans)
            for style in fixture.HARDWARE_ICON_STYLES:
                layers=self.artwork(identity,style)['layers']
                self.assertEqual(len(layers['rotors']),fans,(identity,style))
                for rotor in layers['rotors']:
                    nodes=list(ET.fromstring(fixture.decode(rotor['source'])).iter())
                    self.assertEqual(sum(n.get('class')=='hardware-fan-blade' for n in nodes),blades,(identity,style))
                self.assertEqual([n['direction'] for n in layers['rotors']],[1]*fans)

    def test_biostar_models_have_distinct_covers_and_no_borrowed_internal_facts(self):
        base=fixture.exact(ROWS[0][0]);oc=fixture.exact(ROWS[1][0])
        self.assertEqual(base['board_details']['recipe'],'b_biostar7600_base')
        self.assertEqual(oc['board_details']['recipe'],'b_biostar7600_oc')
        for style in ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
            a=self.artwork(base['id'],style);b=self.artwork(oc['id'],style)
            self.assertNotEqual(a['layers']['baseSource'],b['layers']['baseSource'])
        for a in (base,oc):
            self.assertEqual(a['board_details']['pcb_length'],'unknown')
            self.assertEqual(a['board_details']['power_position'],'unknown')
            self.assertIsNone(a['board_details']['slot_width'])
        self.assertNotEqual(appearance_for('gpu','BIOSTAR RX 7600')['confidence'],'model')
        self.assertNotEqual(appearance_for('gpu','Intel Arc A770')['confidence'],'model')


if __name__=='__main__':unittest.main()
