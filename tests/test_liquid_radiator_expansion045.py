"""Optional radiator references: finite pure-data construction and real shells."""
import ast
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import liquid_radiator_expansion045 as catalog
from assembly_radiator044 import build_radiator_detail, TRIANGLE_BUDGETS
from assembly_style import apply_model_styles
from top_bar_config import HARDWARE_ICON_STYLES
from tests.test_assembly_radiator044 import StaticBuilder, build, segment_hit, add, sub, mul, dot, cross, IDENTITY


class RadiatorExpansion045Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL', 'subprocess.Popen', 'threading.Thread.start', 'socket.socket'):
            self.enterContext(patch(target, side_effect=AssertionError('Optional radiator references do not perform I/O')))

    def test_optional_import_and_invalid_lookup_stay_lazy_and_detached(self):
        source=Path(catalog.__file__).read_text(encoding='utf8');isolated={}
        exec(compile(source,catalog.__file__,'exec'),isolated)
        self.assertIsNone(isolated['_ROWS'])
        for invalid in (None,False,0,[],{},'unknown','../../radiator'):
            self.assertIsNone(isolated['get_radiator'](invalid));self.assertIsNone(isolated['_ROWS'])
        rows=isolated['records']();self.assertIsInstance(rows,tuple);self.assertIs(rows,isolated['records']())
        row=isolated['get_radiator'](catalog.IDS[0]);row['dimensions_mm']['width']=1;row['ports'].clear()
        self.assertNotEqual(row,isolated['get_radiator'](catalog.IDS[0]))
        imports=[n for n in ast.walk(ast.parse(source)) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertEqual([(n.module,tuple(a.name for a in n.names)) for n in imports],[('copy',('deepcopy',))])

    def test_named_skus_unique_not_colours_and_all_common_capacities_present(self):
        from liquid_cooling_catalog044 import IDS as base_ids
        rows=catalog.records();self.assertEqual(len(rows),104);self.assertEqual(len(set(catalog.IDS)),len(rows))
        self.assertFalse(set(catalog.IDS)&set(base_ids))
        self.assertEqual({r['id'] for r in rows},set(catalog.IDS))
        self.assertEqual(len({(r['brand'],r['model_number']) for r in rows}),len(rows))
        self.assertEqual({r['nominal_size_mm'] for r in rows},{120,140,240,280,360,420,480,560})
        self.assertEqual({r['brand'] for r in rows},{'Alphacool','Bitspower','Bykski','Watercool','XSPC','EK','CORSAIR','Barrow'})
        self.assertTrue(any(r['fan_size_mm']==120 and r['fan_count']==1 for r in rows))
        self.assertTrue(any(r['fan_size_mm']==140 and r['fan_count']==1 for r in rows))
        for row in rows:
            json.dumps(row,allow_nan=False)
            self.assertEqual(row['nominal_size_mm'],row['fan_count']*row['fan_size_mm'])
            self.assertFalse(row['fan_count_is_installed']);self.assertFalse(row['installed_hardware_inferred'])
            self.assertEqual(row['fan_mount_capacity_per_side'],row['fan_count'])
            self.assertTrue(row['dimensions_verified']);self.assertFalse(row['port_positions_verified'])
            self.assertFalse(row['default_caps_installed']);self.assertFalse(row['shell_geometry_verified'])
            self.assertTrue(row['sources']);self.assertTrue(row['notes'])
            for url in row['sources']:
                self.assertTrue(url.startswith('https://') or (row['brand']=='Barrow' and url.startswith('http://www.barrowint.com/')))
            for port in row['ports']:
                self.assertFalse(port['positions_verified']);self.assertTrue(port['source'])

    def test_revision_conflicts_and_distributor_authority_remain_explicit(self):
        self.assertNotIn('alphacool-xt45-v2-420',catalog.IDS)
        self.assertEqual(catalog.get_radiator('alphacool-st30-v2-240')['dimensions_mm']['length'],275)
        self.assertEqual(catalog.get_radiator('ek-quantum-surface-p240m')['dimensions_mm']['thickness'],48)
        self.assertIn('44mm',catalog.get_radiator('ek-quantum-surface-p240m')['notes'])
        for row in catalog.records():
            if row['brand']=='Bykski':
                self.assertEqual(row['source_authority'],'exclusive_us_distributor')
                self.assertIn('not factory CAD',row['notes'])
            if row.get('documented_connection_threads')==6:
                self.assertEqual(row['ports_count'],7);self.assertIn('auxiliary',row['notes'])
        self.assertEqual(catalog.get_radiator('bykski-cr-rd280rc-tn-v3')['dimensions_mm'],dict(length=309.,width=140.,thickness=30.))
        self.assertEqual(catalog.get_radiator('barrow-dabel60d-480')['dimensions_mm'],dict(length=514,width=121.5,thickness=60.5))

    def test_all_104_three_lods_real_geometry_envelopes_normals_and_budgets(self):
        for row in catalog.records():
            before=copy.deepcopy(row);previous=0
            for level in ('eco','balanced','close'):
                with self.subTest(model=row['id'],level=level):
                    meshes,result,builder=build(row,level);meta=result['metadata']
                    self.assertLessEqual(meta['triangle_count'],TRIANGLE_BUDGETS[level]);self.assertGreater(meta['triangle_count'],previous);previous=meta['triangle_count']
                    self.assertLessEqual(len(meshes),9);self.assertGreaterEqual(len(meshes),6)
                    self.assertEqual(len(result['fan_faces']),row['fan_count']*2)
                    self.assertEqual(len(result['mount_holes']),row['fan_count']*8)
                    self.assertEqual(len(result['ports']),len(row['ports']))
                    self.assertEqual(builder.parts,['caller-part']);self.assertEqual(builder.fans,['caller-fan']);self.assertEqual(builder.rotors,['caller-rotor'])
                    bounds=row['dimensions_mm'];limits=(bounds['width']/2,bounds['length']/2,bounds['thickness']/2)
                    for mesh in meshes:
                        self.assertFalse(mesh.rotor);self.assertEqual(mesh.component,'cooler')
                        vertices=mesh.vertices
                        for n in range(0,len(vertices),6):
                            point,normal=vertices[n:n+3],vertices[n+3:n+6]
                            self.assertTrue(all(math.isfinite(v) for v in point+normal));self.assertAlmostEqual(dot(normal,normal),1.,places=6)
                            self.assertTrue(all(abs(a)<=b+1e-5 for a,b in zip(point,limits)))
                        for n in range(0,len(vertices),18):
                            a,b,c=(vertices[n+k:n+k+3] for k in (0,6,12));self.assertGreater(dot(cross(sub(b,a),sub(c,a)),vertices[n+3:n+6]),1e-10)
            self.assertEqual(before,row)

    def test_new_headers_are_real_geometry_with_open_mouths_and_mounts(self):
        for identity in ('bitspower-leviathan-ii-120-27','barrow-dabel28b-360','barrow-dabel40a-480','barrow-dabel60d-480','bykski-cr-rd120rc-tn-v2'):
            row=catalog.get_radiator(identity);meshes,result,_=build(row)
            for port in result['ports']:
                p,normal=port['position'],port['normal'];up=(0.,1.,0.);tangent=cross(up,normal)
                for offset in ((0.,0.,0.),mul(tangent,3.8),mul(tangent,-3.8),mul(up,3.8),mul(up,-3.8)):
                    sample=add(p,offset);self.assertFalse(segment_hit(meshes,add(sample,mul(normal,2)),sub(sample,mul(normal,7))),(identity,offset))
            thickness=row['dimensions_mm']['thickness']
            for hole in result['mount_holes']:
                p=hole['position'];self.assertFalse(segment_hit(meshes,(p[0],p[1],thickness),(p[0],p[1],-thickness)),identity)
            removed=copy.deepcopy(row);removed['shell_features']=[f for f in row['shell_features'] if f not in ('angular_tank_shoulders','central_header_notch')]
            if identity.startswith(('bitspower','barrow')):
                plain,_,_=build(removed);self.assertNotEqual([m.vertices for m in meshes],[m.vertices for m in plain])
            if identity.startswith('barrow'):
                y=row['dimensions_mm']['length']/2-1.
                self.assertFalse(segment_hit(meshes,(0.,y,thickness),(0.,y,-thickness)))
                plain,_,_=build(removed);self.assertTrue(segment_hit(plain,(0.,y,thickness),(0.,y,-thickness)))

    def test_six_xspc_own_mechanical_pitches_do_not_promote_unmeasured_positions(self):
        for identity in ('xspc-tx120','xspc-tx360','xspc-tx480','xspc-ex120','xspc-ex240','xspc-ex360'):
            row=catalog.get_radiator(identity)
            self.assertEqual(row['fan_mount_pitch_mm'],105);self.assertTrue(row['fan_mount_pitch_verified'])
            self.assertIn(row['mount_dimensions_source'],row['sources'])
            self.assertIn('105',row['notes']);self.assertFalse(row['mounting_positions_verified'])
            self.assertFalse(row['port_positions_verified']);self.assertTrue(all(not p['positions_verified'] for p in row['ports']))
            self.assertEqual(row['fan_center_spacing_mm'],120 if row['fan_count']>1 else None)
            for level in ('eco','balanced','close'):
                with self.subTest(model=identity,level=level):
                    meshes,result,_=build(row,level);self.assertTrue(result['metadata']['mount_pitch_verified'])
                    self.assertEqual(result['metadata']['mount_pitch_mm'],105)
                    thickness=row['dimensions_mm']['thickness']
                    for hole in result['mount_holes']:
                        p=hole['position'];self.assertAlmostEqual(abs(p[0]),52.5)
                        self.assertFalse(segment_hit(meshes,(p[0],p[1],thickness),(p[0],p[1],-thickness)))

    def test_all_thirteen_styles_reuse_the_same_physical_parts_and_vertices(self):
        self.assertEqual(len(HARDWARE_ICON_STYLES),13)
        for identity in ('barrow-dabel40a-240','bitspower-leviathan-ii-140-40','alphacool-monsta-120','alphacool-hpe-20-360','bykski-cr-rd280rc-tn-v3','watercool-heatkiller-rad-480-l'):
            meshes,_,_=build(catalog.get_radiator(identity));physical=tuple((m.vertices,m.part_id,m.component) for m in meshes)
            for style in HARDWARE_ICON_STYLES:
                d=catalog.get_radiator(identity)['dimensions_mm']
                styled,_=apply_model_styles(meshes,style,{},(d['width'],d['length'],d['thickness']),{'front':'open'})
                self.assertEqual(tuple((m.vertices,m.part_id,m.component) for m in styled),physical)

    def test_all_104_screw_axes_and_observed_mouth_centres_have_no_hidden_blocking_sheet(self):
        for row in catalog.records():
            with self.subTest(model=row['id']):
                meshes,result,_=build(row)
                thickness=row['dimensions_mm']['thickness']
                seen=set()
                for hole in result['mount_holes']:
                    p=hole['position'];key=p[:2]
                    if key in seen:continue
                    seen.add(key)
                    self.assertFalse(segment_hit(meshes,(p[0],p[1],thickness),(p[0],p[1],-thickness)),(row['id'],p))
                for port in result['ports']:
                    p,normal=port['position'],port['normal']
                    self.assertFalse(segment_hit(meshes,add(p,mul(normal,2)),sub(p,mul(normal,7))),(row['id'],port['id']))

    def test_legacy_radical360_420_bore_edges_are_open_across_both_terminal_sheets(self):
        from liquid_cooling_catalog044 import get_radiator
        for identity in ('aquacomputer-airplex-radical2-360','aquacomputer-airplex-radical2-420'):
            row=get_radiator(identity)
            for level in ('eco','balanced','close'):
                with self.subTest(model=identity,level=level):
                    meshes,result,_=build(row,level);thickness=row['dimensions_mm']['thickness']
                    self.assertLessEqual(result['metadata']['triangle_count'],TRIANGLE_BUDGETS[level])
                    seen=set()
                    for hole in result['mount_holes']:
                        p=hole['position']
                        if p[:2] in seen:continue
                        seen.add(p[:2])
                        # These points are inside the actual sampled reference
                        # capsule; this checks whole bore clearance, not only
                        # a centre ray through an apparently open flange.
                        for dx,dy in ((0.,0.),(1.2,0.),(-1.2,0.),(0.,1.6),(0.,-1.6)):
                            self.assertFalse(segment_hit(meshes,(p[0]+dx,p[1]+dy,thickness),(p[0]+dx,p[1]+dy,-thickness)),(identity,level,p,dx,dy))


if __name__=='__main__':unittest.main()
