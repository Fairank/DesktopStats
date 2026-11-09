"""Pure SVG/layer contracts for the four specific 0.40 air cooler drawings."""
import ast
import math
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from accessory_art import _Pen,_cooler_fan,_rotor,_svg,STYLES
from accessory_cooling_details040 import draw_air,_annulus
from cooling_catalog import get_cooler

MODELS=('noctua-nh-l12s','noctua-nh-c14s','bequiet-dark-rock-tf2','zalman-cnps9900-max')
SVG='{http://www.w3.org/2000/svg}'


def draw(identity,style='miniature'):
    body,front=_Pen(style),_Pen(style)
    rotors=draw_air(body,front,get_cooler(identity),style,_cooler_fan,_rotor)
    return body.finish(),rotors,front.finish()


class RecordingPen:
    body='#bfcbd0';dark='#626c7b';light='#edf2f4';accent='#d4a17f';ink='#394250'
    def __init__(self):self.polygons=[];self.ellipses=[]
    def poly(self,points,fill='none',*args,**kwargs):self.polygons.append((points,fill))
    def ellipse(self,cx,cy,rx,ry,fill='none',*args,**kwargs):self.ellipses.append((cx,cy,rx,ry,fill))


def inside(point,polygon):
    x,y=point;hit=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit


class AccessoryCoolingDetails040Tests(unittest.TestCase):
    def test_helper_has_only_standard_library_dependencies_and_no_io(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'accessory_cooling_details040.py').read_text(encoding='utf-8'))
        imports={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        self.assertEqual(imports,{'math'})
        self.assertFalse(any(isinstance(n,ast.ImportFrom) for n in ast.walk(tree)))
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                             and n.func.id in ('open','eval','exec') for n in ast.walk(tree)))

    def test_other_products_remain_unmodified_for_the_existing_renderer(self):
        for identity in ('noctua-nh-d15','noctua-nh-p1','scythe-fuma3'):
            p,fg=_Pen('miniature'),_Pen('miniature')
            self.assertIsNone(draw_air(p,fg,get_cooler(identity),'miniature',_cooler_fan,_rotor))
            self.assertEqual((p.finish(),fg.finish()),('',''))

    def test_all_thirteen_styles_keep_every_mechanical_fan_plane_and_count(self):
        for identity in MODELS:
            baseline=None
            for style in STYLES:
                body,rotors,front=draw(identity,style)
                self.assertEqual(len(rotors),get_cooler(identity)['fan_count'])
                planes=[tuple(r[k] for k in ('x','y','width','height','direction'))+tuple(r['affine']) for r in rotors]
                if baseline is None:baseline=planes
                self.assertEqual(planes,baseline)
                for rotor in rotors:
                    self.assertEqual(rotor['direction'],1)
                    self.assertTrue(all(math.isfinite(rotor[k]) for k in ('x','y','width','height')))
                    self.assertTrue(0<rotor['x']<120-rotor['width'])
                    self.assertTrue(0<rotor['y']<100-rotor['height'])
                    self.assertGreater(abs(rotor['affine'][0]*rotor['affine'][3]-rotor['affine'][1]*rotor['affine'][2]),.01)
                for source in (body,front,*[r['svg'] for r in rotors],*[r['after_svg'] for r in rotors if r.get('after_svg')]):
                    xml=ET.fromstring(source if source.startswith('<svg') else _svg(source))
                    self.assertLess(len(source),100000)
                    for element in xml.iter():
                        self.assertNotIn(element.tag.removeprefix(SVG),('script','image','use','foreignObject','filter'))
                        self.assertFalse(any(k.endswith('href') or k.lower().startswith('on') for k in element.attrib))

    def test_tf2_uses_separate_upper_and_middle_fan_models_and_never_adds_leaves(self):
        _,rotors,_=draw('bequiet-dark-rock-tf2')
        self.assertEqual(len(rotors),2)
        # The lower fan is painted first; the upper fin bank occludes it
        # before the upper fan is painted. A plain two-layer overlay is wrong.
        self.assertIn('data-blade-count="9"',rotors[0]['svg'])
        self.assertIn('data-blade-count="7"',rotors[1]['svg'])
        self.assertTrue(rotors[0]['after_svg'])
        self.assertNotIn('data-blade-count',rotors[0]['after_svg'])
        self.assertNotIn('after_svg',rotors[1])
        self.assertGreater(rotors[0]['y'],rotors[1]['y'])
        for source,count in ((rotors[0]['svg'],9),(rotors[1]['svg'],7)):
            self.assertEqual(source.count('data-leaf='),count)

    def test_lower_and_upper_fan_installations_are_visibly_different(self):
        body_under,under,front_under=draw('noctua-nh-l12s')
        body_above,above,front_above=draw('noctua-nh-c14s')
        # An underside view reveals the physically bottom-mounted L12S fan;
        # the C14S uses its documented above-fin installation. Their positions
        # and projected axes differ, without changing either fan's local circle.
        self.assertNotEqual(under[0]['affine'],above[0]['affine'])
        for body,rotors,front in ((body_under,under,front_under),(body_above,above,front_above)):
            self.assertGreater(len(body),1000)
            self.assertTrue(front)
            self.assertNotIn('data-blade-count',body+front)
            self.assertEqual(ET.fromstring(rotors[0]['svg']).get('viewBox'),'0 0 100 100')

    def test_ring_fin_wedges_leave_a_real_empty_bore(self):
        p=RecordingPen();_annulus(p,49,51,29.5,31.5,20.4,22.3,'#6c7478')
        self.assertEqual(len(p.polygons),32)
        for points,fill in p.polygons:
            self.assertNotEqual(fill,'none')
            self.assertFalse(inside((49,51),points))
            self.assertFalse(inside((59,51),points))
        self.assertTrue(all(fill=='none' for *_,fill in p.ellipses))
        body,rotors,front=draw('zalman-cnps9900-max')
        self.assertEqual(len(rotors),1)
        self.assertNotIn('data-blade-count',body+front)
        self.assertNotIn('<rect',front,'No opaque rectangular front frame on a frameless radial cooler')

    def test_originals_remain_expression_free_and_line_style_has_no_colored_pipe_strokes(self):
        for identity in MODELS:
            for style in STYLES:
                body,rotors,front=draw(identity,style)
                source=body+front+''.join(r['svg'] for r in rotors)
                self.assertEqual('data-art-face="smile"' in source,style in ('cartoon','notebook_smile'))
            body,_,front=draw(identity,'notebook_line')
            strokes=re.findall(r' stroke="([^"]+)"',body+front)
            self.assertEqual(set(strokes),{'#394250'})


if __name__=='__main__':unittest.main()
