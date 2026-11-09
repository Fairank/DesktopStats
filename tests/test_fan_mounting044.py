"""Verified mounting pitch pierces frame and pads without growing the fan body."""
import unittest
from unittest.mock import patch
from assembly_cooling import _Builder,_fan
from cooling_catalog import get_fan
from tests.test_assembly_cooling import _hit


class FanMountingTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No hardware work')))

    def test_verified_holes_remain_open_through_frame_and_offset_pads(self):
        for identity in ('noctua-nf-a12x25-pwm','noctua-nf-a14-pwm','noctua-nf-a15-pwm','arctic-p12-pwm'):
            row=get_fan(identity);builder=_Builder('balanced')
            _fan(builder,row,(0,0,0),(0,0,1),(0,1,0),component='cooler',part='cooler:radiator:front:0',role='radiator')
            parts=[m for m in builder.finish() if m.name.endswith(('-frame','-pads'))]
            self.assertTrue(parts)
            pitch=row['mount_pitch_mm']
            for x in (-pitch/2,pitch/2):
                for y in (-pitch/2,pitch/2):
                    for dx,dy in ((0,0),(.8,0),(0,.8)):
                        self.assertFalse(any(_hit(m.vertices,(x+dx,y+dy,100),(0,0,-1)) for m in parts),identity)
            # The basis swaps X/Y; the frame's size and width remain physical.
            for m in parts:
                self.assertLessEqual(max(map(abs,m.vertices[0::6])),row['size_mm']/2+.01)
                self.assertLessEqual(max(map(abs,m.vertices[1::6])),row.get('width_mm',row['size_mm'])/2+.01)


if __name__=='__main__':unittest.main()
