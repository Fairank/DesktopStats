"""Actual optional loop records to bounded vector cards, no Qt or collectors."""
import copy
import json
import math
import re
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import liquid_svg046 as svg
from liquid_component_runtime046 import get_component
from tests import test_loop_assembly046 as fixtures

BLOCK=fixtures.BLOCK


class LiquidSvg046Tests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LoopAssembly046Tests.setUpClass.__func__)
    setUp=fixtures.LoopAssembly046Tests.setUp
    tearDown=fixtures.LoopAssembly046Tests.tearDown

    def test_one_light_index_pass_has_all_kinds_and_never_fetches_every_model(self):
        with patch.object(self.store,'choices',wraps=self.store.choices) as index,\
             patch.object(self.store,'get_model',side_effect=AssertionError('Choices must not preload models')):
            rows=svg.choices()
        self.assertEqual(index.call_count,1);self.assertEqual(set(rows),set(svg.KINDS))
        self.assertEqual(sum(map(len,rows.values())),len(self.library))
        self.assertEqual({r['id'] for values in rows.values() for r in values},{r['id'] for r in self.library})
        self.assertFalse(any('reference' in row or 'sources' in row for values in rows.values() for row in values))
        first=next(values[0] for values in rows.values() if values);first['label']='Changed'
        self.assertNotEqual(svg.choices()[first['part_kind']][0]['label'],'Changed')

    def test_all_real_models_all_thirteen_styles_share_geometry_and_safe_finite_svg(self):
        # Stream one card at a time; the test does not retain an atlas of SVGs.
        for wrapped in self.library:
            kind=wrapped['reference']['part_kind'];identity=wrapped['id'];baseline=None
            for style in svg.STYLES:
                with self.subTest(model=identity,style=style):
                    result=svg.art(kind,identity,style);self.assertTrue(result)
                    details=result['art_details']
                    physical=(details['geometry_digest'],details['shape_path_digest'],details['triangle_count'],
                              details['dimensions_mm'],details['reference_envelope_mm'])
                    if baseline is None:baseline=physical
                    self.assertEqual(physical,baseline)
                    self.assertEqual(result['id'],identity);self.assertEqual(result['kind'],kind)
                    self.assertEqual(result['sources'],wrapped['sources'])
                    self.assertEqual(result['svg'],result['body_svg']);self.assertEqual(result['foreground_svg'],'')
                    self.assertEqual(result['rotors'],[]);self.assertEqual(result['original_face'],'none')
                    self.assertFalse(details['telemetry_bound']);self.assertFalse(details['coordinates_verified'])
                    self.assertTrue(details['occlusion_clipping'])
                    self.assertLessEqual(details['triangle_count'],svg.MAX_TRIANGLES)
                    self.assertLessEqual(details['crease_edge_count'],svg.MAX_EDGES)
                    self.assertLessEqual(details['occlusion_work'],svg.MAX_CLIP_WORK)
                    self.assertLessEqual(len(result['svg'].encode()),svg.MAX_SVG_BYTES)
                    tree=ET.fromstring(result['svg']);self.assertEqual(tree.attrib['viewBox'],'0 0 120 100')
                    self.assertGreater(len(tree),0)
                    for node in tree.iter():
                        self.assertIn(node.tag.rsplit('}',1)[-1],('svg','path'))
                        self.assertFalse(any('href' in key or key.startswith('on') for key in node.attrib))
                        for key in ('fill','stroke'):
                            if key in node.attrib:self.assertRegex(node.attrib[key],r'^(none|#[0-9a-f]{6})$')
                        if 'd' not in node.attrib:continue
                        values=[float(v) for v in re.findall(r'-?\d+(?:\.\d+)?',node.attrib['d'])]
                        self.assertEqual(len(values)%2,0)
                        self.assertTrue(all(math.isfinite(v) for v in values))
                        self.assertTrue(all(4.<x<116. for x in values[::2]))
                        self.assertTrue(all(4.<y<96. for y in values[1::2]))
                    if style=='miniature':self.assertEqual(details['crease_edge_count'],0)
                    if style=='notebook_line':self.assertTrue(all(n.attrib.get('fill','#ffffff') in ('none','#ffffff') for n in tree.iter()))
                    json.dumps(result,allow_nan=False)

    def test_real_shapes_are_not_a_recolored_universal_block_and_paper_uses_ink_strokes(self):
        pairs=(('fitting','alphacool-eiszapfen-soft-13-10','alphacool-eiszapfen-soft-90-13-10'),
               ('tubing','alphacool-carbon-13-10','alphacool-carbon-16-13'),
               ('reservoir','watercool-heatkiller-tube100','watercool-heatkiller-tube200'))
        for kind,a,b in pairs:
            aa=svg.art(kind,a);bb=svg.art(kind,b)
            self.assertNotEqual(aa['art_details']['geometry_digest'],bb['art_details']['geometry_digest'])
            self.assertNotEqual(aa['art_details']['shape_path_digest'],bb['art_details']['shape_path_digest'])
        original=svg.art('cpu_block',BLOCK);paper=svg.art('cpu_block',BLOCK,'notebook_color')
        self.assertNotIn(' Q',original['svg']);self.assertIn(' Q',paper['svg'])
        self.assertEqual(original['art_details']['geometry_digest'],paper['art_details']['geometry_digest'])

    def test_invalid_inputs_fail_before_mesh_work_and_source_result_mutations_are_detached(self):
        with patch('liquid_component_runtime046.get_component',side_effect=AssertionError('Invalid input must not fetch')):
            for kind,identity,style in (([],BLOCK,'miniature'),('case',BLOCK,'miniature'),
                ('cpu_block','../x','miniature'),('cpu_block','x'*65,'miniature'),('cpu_block',BLOCK,[]),
                ('cpu_block',BLOCK,'unknown'),('cpu_block','<script>','miniature')):
                self.assertEqual(svg.art(kind,identity,style),{})
        before=get_component('cpu_block',BLOCK);result=svg.art('cpu_block',BLOCK)
        result['sources'].clear();result['art_details']['dimensions_mm'].clear()
        self.assertEqual(get_component('cpu_block',BLOCK),before)
        self.assertEqual(svg.art('cpu_block','missing-model'),{})

    def test_no_inner_cache_or_stale_svg_survives_optional_pack_removal(self):
        result=svg.art('cpu_block',BLOCK);self.assertTrue(result)
        self.assertEqual(svg.cache_info()['entries'],0);self.assertEqual(svg.cache_info()['max_entries'],0)
        self.assertTrue(self.store.remove('test-loop046'))
        self.assertEqual(svg.art('cpu_block',BLOCK),{})
        self.assertEqual(sum(map(len,svg.choices().values())),0)
        svg.clear_cache();self.assertEqual(svg.cache_info()['entries'],0)

    def test_legal_reference_geometry_budget_rejection_returns_no_fake_or_retained_card(self):
        from liquid_pack_schema046 import validate_reference
        from assembly_geometry import Mesh,box
        legal=get_component('cpu_block',BLOCK);validate_reference(legal)
        with patch('liquid_geometry046.build_component',side_effect=ValueError('Geometry detail budget')),\
             patch.object(svg,'_Visibility',side_effect=AssertionError('Rejected geometry must not project')):
            self.assertEqual(svg.art('cpu_block',BLOCK),{})
        oversized=Mesh('synthetic-over-budget',box(10.,10.,10.)*(svg.MAX_TRIANGLES//12+1),(.2,.3,.4,1.))
        with patch('liquid_geometry046.build_component',return_value=((oversized,),{})),\
             patch.object(svg,'_Visibility',side_effect=AssertionError('Over-budget geometry must not project')):
            self.assertEqual(svg.art('cpu_block',BLOCK),{})
        self.assertEqual(svg.cache_info()['entries'],0)
        self.assertEqual(get_component('cpu_block',BLOCK),legal)

    def test_thin_reference_walls_keep_native_double_sided_visibility(self):
        from assembly_geometry import Mesh,box
        vertices=box(12.,8.,10.)
        inverted=tuple(-v if i%6>=3 else v for i,v in enumerate(vertices))
        physical=dict(dimensions_mm=dict(width=12.,height=8.,depth=10.),
                      reference_envelope_mm=dict(width=12.,height=8.,depth=10.))
        results=[]
        for values in (vertices,inverted):
            mesh=Mesh('loop-synthetic-double-sided-wall',values,(.3,.4,.5,1.))
            with patch('liquid_geometry046.build_component',return_value=((mesh,),physical)):
                results.append(svg.art('cpu_block',BLOCK,'miniature'))
        self.assertTrue(all(results))
        a,b=(r['art_details'] for r in results)
        self.assertEqual(a['projected_triangle_count'],12)
        self.assertEqual(a['shape_path_digest'],b['shape_path_digest'])
        self.assertEqual(a['visible_face_polygons'],b['visible_face_polygons'])
        # Shading may respond to a normal; a thin receiving wall and its depth
        # occlusion may not disappear. Actual native/C# paths do not cull it.
        self.assertNotEqual(results[0]['svg'],results[1]['svg'])

    def test_shared_half_plane_classification_matches_the_independent_reference(self):
        import random
        from assembly_detail import _subtract
        randomizer=random.Random(46063);checked=0
        for _ in range(500):
            polygons=[]
            for _ in range(2):
                count=randomizer.randrange(3,10);cx,cy=(randomizer.uniform(-4.,4.) for _ in range(2))
                radius=randomizer.uniform(1.,8.);turn=randomizer.random()*math.tau
                polygons.append(tuple((cx+radius*math.cos(turn+i*math.tau/count),cy+radius*math.sin(turn+i*math.tau/count)) for i in range(count)))
            subject,hole=polygons
            if not svg._overlaps(subject,hole):continue
            edges=tuple((b[0]-a[0],b[1]-a[1],a[0],a[1]) for a,b in zip(hole,(*hole[1:],hole[0])))
            self.assertEqual(tuple(svg._subtract_cover(subject,edges)),_subtract(subject,hole))
            checked+=1
        self.assertGreater(checked,300)

    def test_fixed_view_rejects_hidden_smooth_candidates_before_depth_work(self):
        from assembly_geometry import Mesh,box
        from liquid_silhouette046 import encode_normals
        mesh=Mesh('loop-camera-gated-reference',box(12.,8.,10.),(.3,.4,.5,1.))
        physical=dict(dimensions_mm=dict(width=12.,height=8.,depth=10.),
                      reference_envelope_mm=dict(width=12.,height=8.,depth=10.))
        rejected=encode_normals(svg._EYE,svg._EYE)
        retained=encode_normals(svg._EYE,tuple(-n for n in svg._EYE))
        # Same physical edge, six blocked repeats share a single local gate.
        a,b=(-6.,4.,-5.),(6.,4.,-5.)
        vertices=tuple(v for tag in (*([rejected]*6),retained) for v in (*a,*tag,*b,*tag))
        with patch('liquid_geometry046.build_component',return_value=((mesh,),physical)),\
             patch('assembly_style.edge_batches',return_value=((mesh,vertices),)),\
             patch.object(svg._Visibility,'partition_edge',return_value=False) as partition,\
             patch.object(svg._Visibility,'visible_line',side_effect=lambda x,y:((x,y),)) as depth:
            result=svg.art('cpu_block',BLOCK,'notebook_line')
        self.assertTrue(result)
        self.assertEqual(partition.call_count,1);self.assertEqual(depth.call_count,1)
        self.assertEqual(result['art_details']['view_filtered_smooth_edges'],6)
        self.assertEqual(result['art_details']['smooth_tag_memo_entries'],2)
        self.assertEqual(svg.cache_info()['entries'],0)

    def test_exact_depth_clipping_keeps_a_real_open_center_and_discards_coplanar_diagonals(self):
        def face(poly,depth,material=0):
            return dict(polygon=tuple(poly),plane=(0.,0.,depth),bounds=svg._bounds(poly),near=depth,far=depth,
                        depth=depth,fill='#ffffff',alpha=1.,material=material)
        # A rectangular receiving opening is framed by real disjoint strips.
        back=face(((40.,35.),(80.,35.),(80.,65.),(40.,65.)),0.)
        frame=[face(poly,1.,1) for poly in (
            ((44.,39.),(56.,39.),(56.,61.),(44.,61.)),
            ((64.,39.),(76.,39.),(76.,61.),(64.,61.)),
            ((56.,39.),(64.,39.),(64.,47.),(56.,47.)),
            ((56.,53.),(64.,53.),(64.,61.),(56.,61.)))]
        visibility=svg._Visibility([back,*frame]);visible=visibility.visible_face(0)
        # The rear remains visible outside the frame AND through its center.
        expected=40.*30.-(32.*22.-8.*6.)
        self.assertAlmostEqual(sum(abs(svg._area(p)) for p in visible),expected,places=5)
        self.assertFalse(visibility.partition_edge((56.,47.,1.),(64.,47.,1.)))
        triangles=[face(((40.,35.),(80.,35.),(80.,65.)),0.),face(((40.,35.),(80.,65.),(40.,65.)),0.)]
        merged,work=svg._merge_faces(triangles)
        self.assertEqual(len(merged),1);self.assertAlmostEqual(abs(svg._area(merged[0]['polygon'])),1200.)
        visibility=svg._Visibility(triangles)
        self.assertTrue(visibility.partition_edge((40.,35.,0.),(80.,65.,0.)))
        # A cap/receiving ring meeting another physical material is a real
        # join, even when both lie on the same plane. Keep it as native does.
        triangles[1]['material']=1;visibility=svg._Visibility(triangles)
        self.assertFalse(visibility.partition_edge((40.,35.,0.),(80.,65.,0.),0))
        self.assertFalse(visibility.partition_edge((40.,35.,0.),(80.,65.,0.),1))


if __name__=='__main__':unittest.main()
