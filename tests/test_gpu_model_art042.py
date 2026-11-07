"""All catalog GPU model views: source panels, retained planes, finite budgets.

Private software SVG checks; no native desktop, collector or sampler.
"""
import json
import math
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from tests import test_gpu_model_art041 as fixture
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]


def state(identity,style):
    a=fixture.exact(identity,style)
    return dict(kind='gpu',model_id=identity,series_id=a['series_id'],model_mode=True,
        board_vendor=a['board_vendor'],style=a['style'],shroud=a['shroud'],
        fan_count=a.get('visible_fan_count') or a['fan_count'],icon_set=style,ink='#303a48')


class GpuModelArt042Tests(unittest.TestCase):
    setUpClass=classmethod(fixture.GpuModelArt041Tests.setUpClass.__func__)
    setUp=fixture.GpuModelArt041Tests.setUp
    tearDown=fixture.GpuModelArt041Tests.tearDown
    evaluate=fixture.GpuModelArt041Tests.evaluate
    artwork=fixture.GpuModelArt041Tests.artwork

    def test_every_catalog_sku_has_a_guarded_source_record_and_explicit_unknowns(self):
        count=0;traced=0
        for identity in fixture.GPU_ROWS:
            value=state(identity,'miniature')
            row=self.evaluate('Details.modelProfile('+json.dumps(value)+')')
            self.assertEqual(row['profile_ref'],identity)
            self.assertEqual(row['series_id'],value['series_id'])
            self.assertTrue(row['sources'],identity)
            self.assertIsInstance(row['unknown'],list)
            self.assertLessEqual(len(row['traces']),8)
            traced+=bool(row['traces']);count+=1
            wrong=dict(value,series_id='not_the_same_series')
            self.assertIsNone(self.evaluate('Details.modelProfile('+json.dumps(wrong)+')'))
        self.assertEqual(count,147)
        self.assertEqual(traced,145)

    def test_every_style_preserves_original_fan_planes_and_reviewed_blade_counts(self):
        for identity in fixture.GPU_ROWS:
            appearance=fixture.exact(identity)
            for style in HARDWARE_ICON_STYLES:
                current=self.artwork(identity,style)
                previous=self.artwork(identity,'solid' if style in ('classic','outline') else style,False)
                rotors=current['layers']['rotors']
                pose=lambda rows:[tuple(r[k] for k in ('cx','cy','radius','kind','direction')) for r in rows]
                self.assertEqual(pose(rotors),pose(previous['layers']['rotors']),(identity,style))
                base=fixture.decode(current['layers']['baseSource'])
                ET.fromstring(base)
                self.assertNotIn('NaN',base);self.assertNotIn('Infinity',base)
                self.assertLess(len(base.encode('utf8')),180_000,(identity,style))
                # A trace can be fully hidden by a real aperture. Unknown
                # casing entries keep an empty list, never a fake detail mark.
                row=self.evaluate('Details.modelProfile('+json.dumps(state(identity,style))+')')
                if not row['traces']:self.assertIn('casing_geometry',row['unknown'])
                ordered=sorted(rotors,key=lambda r:r['cx'])
                complete=len(rotors)==(appearance.get('visible_fan_count') or appearance['fan_count'])
                for rotor in rotors:
                    self.assertTrue(all(math.isfinite(rotor[k]) for k in ('cx','cy','radius','direction')))
                    tree=ET.fromstring(fixture.decode(rotor['source']))
                    if not complete:continue
                    profile=self.evaluate('profile('+json.dumps(state(identity,style))+','+str(ordered.index(rotor))+','+json.dumps(rotor['kind'])+')')
                    leaves=[n for n in tree.iter() if n.get('class')=='hardware-fan-blade']
                    expected=profile['blades'] if profile['blades'] is not None and profile['shape']!='neutral' else 0
                    self.assertEqual(len(leaves),expected,(identity,style,ordered.index(rotor)))

    def test_source_panel_transform_and_aperture_clipping_keep_each_style_plane(self):
        trace=dict(series_id='synthetic',traces=[dict(d='M0 50H100M0 10H100',width=.1)])
        for style in HARDWARE_ICON_STYLES:
            value=state('asus-rog-strix-4090-oc',style)
            g=self.evaluate('Details.faceGeometry('+json.dumps(value)+')')
            hole=dict(cx=g['x']+g['w']/2,cy=g['y']+g['h']/2,radius=2.)
            source=self.evaluate('Details.contours('+json.dumps(value)+','+json.dumps(trace)+','+json.dumps([hole])+')')
            tree=ET.fromstring('<svg>'+source+'</svg>')
            paths=[node.get('d') for node in tree.iter('path')]
            segments=[tuple(map(float,m)) for d in paths for m in re.findall(r'M([-+.0-9]+) ([-+.0-9]+)L([-+.0-9]+) ([-+.0-9]+)',d)]
            self.assertTrue(segments,style)
            for x,y,u,v in segments:
                dx=u-x;dy=v-y;l=dx*dx+dy*dy
                t=max(0,min(1,((hole['cx']-x)*dx+(hole['cy']-y)*dy)/l)) if l else 0
                self.assertGreaterEqual(math.hypot(x+t*dx-hole['cx'],y+t*dy-hole['cy']),2.04,(style,x,y,u,v))
            original=self.evaluate('Details.faceGeometry('+json.dumps(dict(value,icon_set='solid'))+')')
            self.assertAlmostEqual(g['x'],original['x']-(.8 if style=='miniature' else 0))

    def test_unverified_exteriors_stay_neutral_and_no_original_gets_a_face(self):
        records=self.evaluate('Object.keys(Details.modelProfile('+json.dumps(state('asus-rog-strix-4090-oc','solid'))+'))')
        self.assertIn('unknown',records)
        for identity in fixture.GPU_ROWS:
            for style in ('miniature','solid','notebook_color','notebook_line'):
                text=fixture.decode(self.artwork(identity,style)['source'])
                self.assertNotIn('hardware-notebook-expression',text)
                self.assertNotIn('hardware-cartoon-expression',text)
                self.assertNotIn('<image',text);self.assertNotIn('<filter',text)

    def test_pascal_source_facets_stay_inside_the_retained_notebook_cover(self):
        for identity in ('nvidia-gtx1080-founders','asus-dual-4060-oc','msi-suprim-x-4090-24g'):
            for style in ('notebook_line','notebook_color','notebook_smile','inkwash'):
                value=state(identity,style)
                code=json.dumps(value)
                g=self.evaluate('Details.faceGeometry('+code+')')
                polygon=self.evaluate('Details.contourRegion('+code+','+json.dumps(g)+',[])')
                self.assertGreater(len(polygon),4,(identity,style))
                row=self.evaluate('Details.modelProfile('+code+')')
                source=self.evaluate('Details.contours('+code+','+json.dumps(row)+',[])')
                paths=[node.get('d') for node in ET.fromstring('<svg>'+source+'</svg>').iter('path')]
                points=[]
                for path in paths:
                    for x,y,u,v in re.findall(r'M([-+.0-9]+) ([-+.0-9]+)L([-+.0-9]+) ([-+.0-9]+)',path):
                        points.extend(((float(x),float(y)),(float(u),float(v))))
                self.assertTrue(points,(identity,style))
                for x,y in points:
                    inside=False
                    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
                        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
                    self.assertTrue(inside,(identity,style,x,y))


if __name__=='__main__':unittest.main()
