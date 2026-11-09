"""Offline contracts for twelve primary-manual motherboard observations."""
import ast
import copy
import json
import math
import unittest
from collections import Counter
from unittest.mock import patch

import motherboard_catalog as catalog
import motherboard_expansion045 as expansion


def rows():
    return expansion.records(catalog._record, catalog._slot, catalog._m2, catalog._connector,
                             catalog._cover, catalog._rect, catalog._rear_observation)


EXPECTED = {
    'asus-rog-strix-b650e-i-wifi': (2,1,2,2),
    'msi-mpg-b650i-edge-wifi': (2,1,2,4),
    'asrock-b550m-itx-ac': (2,1,1,4),
    'asrock-h670m-itx-ax': (2,1,2,4),
    'asus-tuf-b650m-plus-wifi': (4,3,2,4),
    'asus-prime-b760m-a-wifi-d4': (4,3,2,4),
    'msi-b550m-pro-vdh-wifi': (4,3,2,4),
    'gigabyte-b550m-ds3h-rev15': (4,3,2,4),
    'msi-mag-b550-tomahawk': (4,4,2,6),
    'asus-tuf-z690-plus-wifi-d4': (4,5,4,4),
    'asrock-b650-pg-lightning': (4,4,3,4),
    'asrock-x870-pro-rs': (4,2,3,4),
}


class MotherboardExpansion045Tests(unittest.TestCase):
    def test_twelve_unique_records_four_per_form_and_no_seed_replacement(self):
        data=rows()
        self.assertEqual(set(EXPECTED), {r['id'] for r in data})
        self.assertEqual(len(data),12)
        self.assertEqual(Counter(r['form_factor'] for r in data),dict(itx=4,matx=4,atx=4))
        seeds={r['id'] for r in catalog.MODELS}-set(EXPECTED)
        self.assertFalse(seeds.intersection(EXPECTED))
        self.assertEqual({r['brand'] for r in data},{'ASUS','MSI','ASRock','GIGABYTE'})
        self.assertEqual({r['socket'] for r in data},{'AM4','AM5','LGA1700'})
        self.assertEqual({r['memory_type'] for r in data},{'DDR4','DDR5'})

    def test_primary_manual_counts_and_rear_layouts(self):
        for row in rows():
            actual=(len(row['dimm_uv']),len(row['pcie']),len(row['m2']),
                    sum(c['count'] for c in row['connectors'] if c['kind']=='sata'))
            self.assertEqual(actual,EXPECTED[row['id']])
            self.assertEqual(Counter(p['kind'] for p in row['rear_layout']),row['rear_ports'])
            self.assertIn(row['manual'],expansion.MANUALS.values())
            self.assertTrue(row['manual'].startswith(('https://download','https://dlcdnets')))
            self.assertTrue(all(s.startswith('https://') for s in row['sources']))
            self.assertGreater(row['layout_page'],0)
            self.assertGreater(row['rear_layout_page'],0)
            self.assertTrue(row['series'])
            self.assertFalse(row['cad_verified'])
            self.assertFalse(row['pcb_routing_verified'])
            self.assertTrue(row['small_package_positions_schematic'])
            self.assertFalse(row['heatsink_depths_verified'])
            self.assertFalse(row['accessory_cards_assumed_installed'])

    def test_dimensions_and_landmarks_are_finite_and_not_one_scaled_template(self):
        patterns=set()
        for row in rows():
            h,w=(row['dimensions_mm'][k] for k in ('height','width'))
            expected=(170.,170.) if row['form_factor']=='itx' else (244.,244.) if row['form_factor']=='matx' else (304.8,243.84) if row['brand']=='MSI' else (305.,244.)
            self.assertEqual((h,w),expected)
            points=[row['cpu_uv'],*row['dimm_uv'],*row['mount_uv']]
            points += [r['uv'] for k in ('pcie','m2','connectors') for r in row[k]]
            points += [p for r in row['heatsinks'] for p in r['polygon']]
            for point in points:
                self.assertEqual(len(point),2)
                self.assertTrue(all(math.isfinite(v) and 0<=v<=1 for v in point),(row['id'],point))
            self.assertLess(row['cpu_uv'][0],min(p[0] for p in row['dimm_uv']))
            self.assertLess(row['cpu_uv'][1],row['pcie'][0]['uv'][1])
            patterns.add((row['cpu_uv'],tuple(row['dimm_uv']),tuple((s['kind'],s['uv']) for s in row['pcie'])))
        self.assertEqual(len(patterns),12)

    def test_unknown_photo_mount_and_battery_are_not_upgraded_to_verified(self):
        data=rows()
        self.assertEqual(sum(r['finish_status']=='photo_reviewed' for r in data),12)
        for row in data:
            if row['finish_status']!='photo_reviewed':
                self.assertEqual(row['finish_status'],'pending_primary_photo')
                self.assertEqual(row['heatsinks'],())
                self.assertEqual(row['heatsink_polygons_method'],'not_added_without_primary_photo')
            if not row['mount_uv']:
                self.assertEqual(row['mount_method'],'not_verified_no_holes_inferred')
            else:
                self.assertEqual(row['mount_method'],'official_manual_layout_diagram_observed')
        self.assertEqual([len(r['mount_uv']) for r in data if r['brand']=='ASUS'],[4,8,8,9])
        self.assertIsNone(next(r for r in data if r['id']=='asrock-b550m-itx-ac')['battery_uv'])

    def test_physical_slot_length_is_independent_of_electrical_lanes(self):
        data={r['id']:r for r in rows()}
        ds3h=data['gigabyte-b550m-ds3h-rev15']
        self.assertEqual(ds3h['pcie'][-1]['kind'],'x16')
        self.assertEqual(ds3h['pcie'][-1]['length_mm'],89.)
        self.assertEqual(ds3h['pcie'][-1]['electrical_lanes'],1)
        prime=data['asus-prime-b760m-a-wifi-d4']
        self.assertEqual([r['kind'] for r in prime['pcie']],['x16']*3)
        self.assertEqual([r['electrical_lanes'] for r in prime['pcie']],[16,4,1])
        z690=data['asus-tuf-z690-plus-wifi-d4']
        self.assertEqual(Counter(r['kind'] for r in z690['pcie']),dict(x16=2,x1=2,x4=1))

    def test_revision_and_wifi_identity_are_exact_no_false_alias(self):
        data=rows()
        with patch.object(catalog,'MODELS',tuple(catalog.MODELS)+tuple(data)):
            self.assertIsNone(catalog.identify('GIGABYTE','B550M DS3H')['model'])
            self.assertEqual(catalog.identify('GIGABYTE','B550M DS3H (rev. 1.5)')['model']['id'],'gigabyte-b550m-ds3h-rev15')
            self.assertIsNone(catalog.identify('GIGABYTE','B550M DS3H AC')['model'])
            self.assertIsNone(catalog.identify('ASRock','X870 Pro RS WiFi')['model'])
            self.assertEqual(catalog.identify('ASRock','X870 Pro RS')['model']['id'],'asrock-x870-pro-rs')
            self.assertIsNone(catalog.identify('MSI','B550M PRO-VDH WIFI6')['model'])
        x870=next(r for r in data if r['id']=='asrock-x870-pro-rs')
        self.assertNotIn('antenna',x870['rear_ports'])

    def test_backside_m2_is_mirrored_and_wifi_slots_not_ssd_slots(self):
        data={r['id']:r for r in rows()}
        for identity in ('asus-rog-strix-b650e-i-wifi','msi-mpg-b650i-edge-wifi'):
            backs=[r for r in data[identity]['m2'] if r['side']=='rear']
            self.assertEqual(len(backs),1)
            self.assertGreater(backs[0]['uv'][0],.65)
            self.assertGreater(backs[0]['uv'][1],.8)
            self.assertEqual(backs[0]['along'],(-1,0))
        for identity in ('asrock-b550m-itx-ac','asrock-h670m-itx-ax','asrock-b650-pg-lightning','asrock-x870-pro-rs'):
            self.assertTrue(all(r['side']=='front' for r in data[identity]['m2']))
        self.assertEqual(len(data['asrock-b550m-itx-ac']['m2']),1)
        for identity in ('asrock-b550m-itx-ac','asrock-h670m-itx-ax','asrock-b650-pg-lightning','asrock-x870-pro-rs'):
            self.assertTrue(all(r['allowed_lengths_mm']==(80.,) for r in data[identity]['m2']))
        self.assertTrue(all(r['allowed_lengths_mm']==(60.,80.) for r in data['msi-mpg-b650i-edge-wifi']['m2']))
        self.assertTrue(all(r['allowed_lengths_mm']==(42.,60.,80.) for r in data['asus-rog-strix-b650e-i-wifi']['m2']))

    def test_records_are_detached_json_and_leaf_module_has_no_import_io(self):
        first=rows();before=copy.deepcopy(first)
        first[0]['rear_ports']['usb_a']=100
        first[0]['connectors'][0]['uv']=(0,0)
        self.assertEqual(rows(),before)
        self.assertEqual(len(json.loads(json.dumps(before))),12)
        with open(expansion.__file__,encoding='utf8') as handle:tree=ast.parse(handle.read())
        self.assertFalse(any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(tree)))
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('open','eval','exec','compile','__import__') for n in ast.walk(tree)))

    def test_all_twelve_build_in_pure_renderer_dvi_has_its_own_frame(self):
        from assembly_geometry import build_scene
        data=rows()
        with patch.object(catalog,'MODELS',tuple(catalog.MODELS)+data):
            for row in data:
                spec=dict(case=dict(layout='tower',dimensions_mm=dict(width=250,height=500,depth=500)),
                          board=dict(model_id=row['id']),memory=dict(count=0),detail_level='eco')
                scene=build_scene(spec)
                counts=scene.metadata['motherboard']['documented_slot_counts']
                self.assertEqual(counts['dimm'],len(row['dimm_uv']))
                self.assertEqual(counts['m2'],len(row['m2']))
                self.assertEqual(scene.metadata['motherboard']['documented_rear_ports'],row['rear_ports'])
                for mesh in scene.meshes:
                    self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
                    self.assertEqual(len(mesh.vertices)%18,0)
                dvi=[m for m in scene.meshes if m.name=='detail-board-rear-dvi']
                self.assertEqual(bool(dvi),row['id']=='gigabyte-b550m-ds3h-rev15')
                if dvi:
                    self.assertTrue(next(p for p in row['rear_layout'] if p['kind']=='dvi')['rotated'])
                    self.assertTrue(any(m.name=='detail-board-rear-keyed-pin-inserts' and m.vertices for m in scene.meshes))

    def test_source_front_sata_pairs_have_clear_receiving_mouths_and_correct_long_axis(self):
        from assembly_geometry import build_scene
        from assembly_viewer import ray_triangle
        data=rows()
        with patch.object(catalog,'MODELS',tuple(catalog.MODELS)+data):
            for row in data[:4]:
                scene=build_scene(dict(case=dict(layout='tower',dimensions_mm=dict(width=250,height=500,depth=500)),
                                       board=dict(model_id=row['id']),memory=dict(count=0),detail_level='eco'))
                sockets=[m for m in scene.meshes if m.name=='detail-board-sata-socket']
                self.assertEqual(len(sockets),EXPECTED[row['id']][-1])
                for socket in sockets:
                    y=socket.vertices[1::6];z=socket.vertices[2::6]
                    self.assertAlmostEqual(max(y)-min(y),13.)
                    self.assertAlmostEqual(max(z)-min(z),8.)
                    for offset in (-.6,0.,.6):
                        origin=(socket.position[0]-20.,socket.position[1],socket.position[2]+offset)
                        for obstacle in sockets:
                            for start in range(0,len(obstacle.vertices),18):
                                triangle=[tuple(obstacle.vertices[start+j+k]+obstacle.position[k] for k in range(3)) for j in (0,6,12)]
                                self.assertIsNone(ray_triangle(origin,(1.,0.,0.),*triangle),row['id'])

    def test_original_sata_default_mesh_payload_remains_byte_identical(self):
        import struct
        from assembly_geometry import build_scene,rotate_vertices
        from assembly_detail import perforated_plate,chamfer_rect,_port_shape
        spec=dict(case=dict(layout='tower',dimensions_mm=dict(width=250,height=500,depth=500)),
                  board=dict(model_id='asrock-z790-pg-itx-tb4'),memory=dict(count=0),detail_level='eco')
        scene=build_scene(spec)
        shape=rotate_vertices(perforated_plate(chamfer_rect(13.,8.,.7),(_port_shape('sata',9.,4.6),),4.),'left')
        old=struct.pack('<'+'f'*len(shape),*shape)
        sockets=[m for m in scene.meshes if m.name=='detail-board-sata-socket']
        self.assertEqual(len(sockets),3)
        self.assertTrue(all(struct.pack('<'+'f'*len(m.vertices),*m.vertices)==old for m in sockets))

    def test_am4_uses_plastic_pga_receivers_and_zif_lever_without_lga_load_plate(self):
        from assembly_motherboard import layout_anchors,enrich_motherboard
        from assembly_geometry import build_scene
        from assembly_viewer import ray_triangle
        data=rows()
        with patch.object(catalog,'MODELS',tuple(catalog.MODELS)+data):
            for row in (r for r in data if r['socket']=='AM4'):
                for level in ('eco','balanced','close'):
                    spec=dict(board=dict(model_id=row['id']),memory=dict(count=0))
                    anchors=layout_anchors(spec,250,500,500,90,0,-236)
                    meshes,meta=enrich_motherboard([],spec,anchors,level)
                    names=Counter(m.name for m in meshes)
                    self.assertEqual(names['board-am4-pga-receiving-wells'],1)
                    self.assertEqual(names['board-am4-zif-locking-lever'],1)
                    self.assertEqual(names['board-am4-cooler-retention'],2)
                    self.assertEqual(names['board-am4-retention-screw'],4)
                    self.assertEqual(names['board-socket-spring-heads'],0)
                    self.assertEqual(names['detail-board-retention-frame'],0)
                    self.assertEqual(names['board-socket-captive-bolts'],0)
                    wells=next(m for m in meshes if m.name=='board-am4-pga-receiving-wells')
                    self.assertNotEqual(wells.color,(.7254901960784313,.615686274509804,.4,1.))
                    for i in range(0,len(wells.vertices),6):
                        self.assertAlmostEqual(sum(v*v for v in wells.vertices[i+3:i+6]),1.,places=5)
                    # Exercise the complete scene attachment path as well as
                    # direct enrichment: sampled mouths must truly open onto
                    # the recessed floor, including wells beyond helper cap24.
                    scene=build_scene(dict(case=dict(layout='tower',dimensions_mm=dict(width=250,height=500,depth=500)),
                                           board=dict(model_id=row['id']),memory=dict(count=0),detail_level=level))
                    cp=scene.metadata['attachment_anchors']['cpu']['position']
                    for dy,dz in ((0.,0.),(17.,17.),(-17.,17.)):
                        origin=(cp[0]-100.,cp[1]+dy,cp[2]+dz);hits=[]
                        for mesh in scene.meshes:
                            if mesh.component!='board':continue
                            for start in range(0,len(mesh.vertices),18):
                                tri=[tuple(mesh.vertices[start+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12)]
                                distance=ray_triangle(origin,(1.,0.,0.),*tri)
                                if distance is not None:hits.append((distance,mesh.name))
                        self.assertTrue(hits)
                        self.assertEqual(min(hits)[1],'board-am4-dark-recess-floor',(row['id'],level,dy,dz))

    def test_b650e_i_does_not_borrow_another_rog_boards_transparent_io_inset(self):
        from assembly_motherboard import layout_anchors,enrich_motherboard
        data=rows()
        with patch.object(catalog,'MODELS',tuple(catalog.MODELS)+data):
            spec=dict(board=dict(model_id='asus-rog-strix-b650e-i-wifi'),memory=dict(count=0))
            a=layout_anchors(spec,250,500,500,90,0,-236)
            meshes,_=enrich_motherboard([],spec,a,'balanced')
            self.assertFalse(any(m.name=='board-io-clear-inset' for m in meshes))

    def test_dvi_d_all_twenty_four_receivers_and_flat_key_are_actually_open(self):
        from assembly_geometry import build_scene
        from assembly_viewer import ray_triangle
        data=rows()
        with patch.object(catalog,'MODELS',tuple(catalog.MODELS)+data):
            scene=build_scene(dict(case=dict(layout='tower',dimensions_mm=dict(width=250,height=500,depth=500)),
                                   board=dict(model_id='gigabyte-b550m-ds3h-rev15'),memory=dict(count=0),detail_level='eco'))
        board=next(r for r in data if r['id']=='gigabyte-b550m-ds3h-rev15')
        port=next(p for p in board['rear_layout'] if p['kind']=='dvi')
        insert=next(m for m in scene.meshes if m.name=='detail-board-rear-keyed-pin-inserts')
        points=[(-7.+c*1.8,(r-1)*1.8) for r in range(3) for c in range(8)]+[(9.,0.)]
        self.assertEqual(len(points),25)
        for x,y in points:
            if port['rotated']:x,y=-y,-x
            origin=(insert.position[0]+port['x_mm']+x,insert.position[1]+port['y_mm']+y,insert.position[2]-20.)
            for at in range(0,len(insert.vertices),18):
                tri=[tuple(insert.vertices[at+j+k]+insert.position[k] for k in range(3)) for j in (0,6,12)]
                self.assertIsNone(ray_triangle(origin,(0.,0.,1.),*tri),(x,y))
        # An empty/dropped inset must not make the aperture checks pass.
        origin=(insert.position[0]+port['x_mm']-3.,insert.position[1]+port['y_mm'],insert.position[2]-20.)
        solid=[]
        for at in range(0,len(insert.vertices),18):
            tri=[tuple(insert.vertices[at+j+k]+insert.position[k] for k in range(3)) for j in (0,6,12)]
            distance=ray_triangle(origin,(0.,0.,1.),*tri)
            if distance is not None:solid.append(distance)
        self.assertTrue(solid)


if __name__=='__main__':
    unittest.main()
