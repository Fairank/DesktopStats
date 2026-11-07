"""One sampled foil serves SVG and 3D; rectangular holes remain open."""
import copy
import math
import re
import unittest
from unittest.mock import patch
from accessory_art import _rotor,_fan_holes
from assembly_geometry import blade_polygon,blade_contour
from assembly_cooling import _Builder,_fan,_leaf_geometry
from cooling_catalog import get_fan
from tests.test_assembly_cooling import _hit


class CoolingFoilTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No runtime/device work')))

    def model(self):
        row=get_fan('noctua-nf-a12x25-pwm');row.update(family='sample-foil',foil_profile=dict(sweep_deg=31,leading=.29,trailing=.17,root=.21),foil_profile_accuracy='qualitative_reference')
        return row

    def test_svg_outline_is_the_same_physical_curve_as_the_3d_input_for_every_style(self):
        from top_bar_config import HARDWARE_ICON_STYLES
        model=self.model();poly=blade_polygon(model)
        for style in HARDWARE_ICON_STYLES:
            svg=_rotor(model,style,0,0,100,100)['svg']
            # The first leaf after the data-leaf marker is the sampled shared path.
            path=re.search(r'data-leaf="1"[^>]*><path d="([^"]+)"',svg).group(1)
            numbers=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',path)))
            self.assertEqual(len(numbers),len(poly)*2)
            for (x,y),a,b in zip(poly,numbers[0::2],numbers[1::2]):
                self.assertAlmostEqual(a,50+x*45*1.07/3,delta=.002)
                self.assertAlmostEqual(b,50+y*45*1.07/3,delta=.002)
        mesh=_leaf_geometry(model,50,3)
        self.assertTrue(mesh);self.assertTrue(all(math.isfinite(v) for v in mesh))
        self.assertLess(max(math.hypot(mesh[n],mesh[n+1]) for n in range(0,len(mesh),6)),50)
        changed=copy.deepcopy(model);changed['foil_profile']['sweep_deg']=-16
        self.assertNotEqual(blade_polygon(model),blade_polygon(changed))
        self.assertNotEqual(mesh,_leaf_geometry(changed,50,3))

    def test_dual_axis_round_mounts_have_four_real_through_holes_and_correct_svg_positions(self):
        row=self.model();row.update(frame='round',mount_pitch_mm=None,mount_pitch_verified=False,mount_pitch_axes_mm=[93.,83.],mount_pitch_axes_verified=True,mount_pitch_axes_orientation_verified=False)
        builder=_Builder('balanced');_fan(builder,row,(0,0,0),(0,0,1),(0,1,0))
        meshes=[m for m in builder.finish() if m.name.endswith(('-frame','-pads'))]
        # Basis X/Y are exchanged by the existing mounting transform.
        for x in (-83/2,83/2):
            for y in (-93/2,93/2):
                for dx,dy in ((0,0),(.8,0),(0,.8)):
                    self.assertFalse(any(_hit(m.vertices,(x+dx,y+dy,100),(0,0,-1)) for m in meshes))
        xs={round(p[0],6) for p in _fan_holes(row)};ys={round(p[1],6) for p in _fan_holes(row)}
        self.assertEqual(xs,{.1125,.8875});self.assertEqual(ys,{round(.5-83/240,6),round(.5+83/240,6)})

    def test_papercut_rotor_motion_remains_visible_with_legacy_overlapping_leaves(self):
        from PySide6.QtCore import QByteArray,QRectF,Qt
        from PySide6.QtGui import QImage,QPainter
        from PySide6.QtSvg import QSvgRenderer
        model=get_fan('noctua-nf-a12x25-pwm')
        model.update(family='reference',blades=7)
        svg=_rotor(model,'papercut',0,0,100,100)['svg']
        self.assertEqual(svg.count('data-cut-edge="visible"'),7)
        renderer=QSvgRenderer(QByteArray(svg.encode('utf8')))
        self.assertTrue(renderer.isValid())
        samples=[]
        for angle in (0,11):
            image=QImage(200,200,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
            painter=QPainter(image)
            try:
                painter.setRenderHint(QPainter.Antialiasing)
                painter.translate(100,100);painter.rotate(angle);painter.translate(-100,-100)
                renderer.render(painter,QRectF(0,0,200,200))
            finally:painter.end()
            samples.append(image)
        changed=sum(samples[0].pixel(x,y)!=samples[1].pixel(x,y)
                    for x in range(200) for y in range(200) if 30<math.hypot(x-100,y-100)<80)
        self.assertGreater(changed,1000,'A rotating plain disc does not show model-specific leaves')


if __name__=='__main__':unittest.main()
