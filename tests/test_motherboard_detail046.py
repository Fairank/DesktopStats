"""Primary-photo refinements; no hardware queries, assets, window or GL."""
import copy
import json
import math
import unittest

import motherboard_catalog as catalog
from assembly_motherboard import enrich_motherboard,layout_anchors


REFINED={
    'asrock-b550m-itx-ac':('vrm-io','m2-front'),
    'asrock-h670m-itx-ax':('vrm-io','m2-front'),
    'gigabyte-b550m-ds3h-rev15':('vrm-io','chipset'),
    'asrock-b650-pg-lightning':('vrm-io','vrm-top','m2-upper','chipset'),
    'asrock-x870-pro-rs':('vrm-io','vrm-top','m2-upper','chipset','m2-lower'),
}


def build(identity,level='balanced'):
    spec={'board':{'model_id':identity},'memory':{'count':0}}
    anchors=layout_anchors(spec,250.,500.,500.,90.,0.,-236.)
    meshes,meta=enrich_motherboard((),spec,anchors,level)
    return anchors,meshes,meta


def nearest(meshes,origin):
    from assembly_viewer import ray_triangle
    best=None
    for mesh in meshes:
        for at in range(0,len(mesh.vertices),18):
            triangle=[tuple(mesh.vertices[at+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12)]
            distance=ray_triangle(origin,(1.,0.,0.),*triangle)
            if distance is not None and (best is None or distance<best[0]):best=distance,mesh.name
    return best


class MotherboardDetail046Tests(unittest.TestCase):
    def test_five_observed_finishes_have_distinct_model_specific_covers(self):
        shapes=set()
        for identity,names in REFINED.items():
            row=catalog.get_model(identity)
            self.assertEqual(row['finish_status'],'photo_reviewed')
            self.assertEqual(row['finish_method'],'official_photo_observed')
            self.assertEqual(tuple(c['name'] for c in row['heatsinks']),names)
            self.assertTrue(any('/mb/photo/' in url or '/ProductRemoveBg/' in url for url in row['sources']))
            self.assertFalse(row['heatsink_depths_verified'])
            self.assertFalse(row['cad_verified'])
            self.assertFalse(row['pcb_routing_verified'])
            shapes.add(tuple(c['polygon'] for c in row['heatsinks']))
        self.assertEqual(len(shapes),5)
        x870=catalog.get_model('asrock-x870-pro-rs')
        self.assertEqual(x870['pcb_color'],'#d6d8d7')
        self.assertNotIn('antenna',x870['rear_ports'])
        self.assertFalse(any(c['name'].startswith('m2') for c in catalog.get_model('gigabyte-b550m-ds3h-rev15')['heatsinks']))

    def test_revision_specific_photo_does_not_create_a_bare_model_identification_alias(self):
        row=catalog.get_model('gigabyte-b550m-ds3h-rev15')
        self.assertIn('exact_revision_product_page',row['finish_revision_association'])
        self.assertTrue(row['requires_revision'])
        self.assertIsNone(catalog.identify('GIGABYTE','B550M DS3H')['model'])
        self.assertIsNone(catalog.identify('GIGABYTE','B550M DS3H rev. 1.4')['model'])
        self.assertEqual(catalog.identify('GIGABYTE','B550M DS3H (rev. 1.5)')['model']['id'],row['id'])

    def test_msi_round_aperture_opens_to_recess_and_center_is_a_static_hub(self):
        from assembly_detail import _point_inside
        row=catalog.get_model('msi-mpg-b650i-edge-wifi');cover=row['heatsinks'][1];fan=cover['static_fan']
        # All sampled mouth points lie inside the source-observed armor; this
        # prevents a fake empty ray just outside an undersized cover.
        for step in range(32):
            u=fan['uv'][0]+math.cos(step*math.tau/32)*fan['diameter_mm']/340.
            v=fan['uv'][1]+math.sin(step*math.tau/32)*fan['diameter_mm']/340.
            self.assertTrue(_point_inside((u,v),cover['polygon']))
        for level in ('eco','balanced','close'):
            anchors,meshes,meta=build(row['id'],level);board=anchors['board']
            cy=board['y']+(.5-fan['uv'][1])*170.;cz=board['rear_z']+fan['uv'][0]*170.
            center=(board['x']-80.,cy,cz)
            self.assertEqual(nearest(meshes,center)[1],'board-onboard-static-fan-hub')
            for angle in (0.,math.pi/2,math.pi,math.pi*1.5):
                offset=fan['diameter_mm']*.375
                origin=(center[0],cy+math.cos(angle)*offset,cz+math.sin(angle)*offset)
                self.assertEqual(nearest(meshes,origin)[1],'board-onboard-fan-recess-floor',(level,angle))
            self.assertFalse(any(m.rotor for m in meshes))
            self.assertFalse(meta['onboard_fan_telemetry_bound'])
            self.assertEqual(meta['onboard_fans'][0]['leaf_geometry'],'not_rendered_unknown')
            for key in ('blade_count','rotation_direction','rpm_source'):self.assertIsNone(meta['onboard_fans'][0][key])
            self.assertFalse(meta['onboard_fans'][0]['dimensions_verified'])
            self.assertEqual(len([m for m in meshes if m.name=='board-onboard-static-fan-hub']),1)

    def test_asus_visible_shroud_vent_remains_distinct_from_unknown_internal_fan(self):
        from assembly_detail import _point_inside
        row=catalog.get_model('asus-rog-strix-b650e-i-wifi');vent=row['heatsinks'][0]['surface_vent']
        self.assertFalse(vent['internal_fan_position_verified'])
        self.assertFalse(vent['hole_map_verified'])
        for level in ('eco','balanced','close'):
            anchors,meshes,meta=build(row['id'],level);board=anchors['board']
            cover=next(m for m in meshes if m.name=='board-vrm-io-heatsink')
            u0,u1=min(p[0] for p in vent['polygon']),max(p[0] for p in vent['polygon'])
            v0,v1=min(p[1] for p in vent['polygon']),max(p[1] for p in vent['polygon'])
            tested=0
            for line in range(5):
                for col in range(3):
                    u=u0+(u1-u0)*(.20+.30*col);v=v0+(v1-v0)*(.12+.19*line)
                    if not _point_inside((u,v),vent['polygon']):continue
                    origin=(board['x']-80.,board['y']+(.5-v)*board['height'],board['rear_z']+u*board['width'])
                    self.assertIsNone(nearest((cover,),origin));tested+=1
            self.assertGreater(tested,5)
            self.assertFalse(any(m.name.startswith('board-onboard-') for m in meshes))
            self.assertEqual(meta['onboard_fans'][0]['placement_status'],'concealed_under_shroud_unverified')
            self.assertIn('onboard_auxiliary_heatsink_fan_geometry',meta['unplaced_source_features'])
            self.assertFalse(meta['onboard_fan_telemetry_bound'])

    def test_new_covers_preserve_board_envelopes_source_dimensions_and_socket_opening(self):
        for identity in REFINED:
            for level in ('eco','balanced','close'):
                anchors,meshes,meta=build(identity,level);row=anchors['model'];board=anchors['board']
                self.assertLess(sum(len(m.vertices)//18 for m in meshes),80000)
                for mesh in meshes:
                    self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
                    self.assertEqual(len(mesh.vertices)%18,0)
                    for at in range(0,len(mesh.vertices),6):
                        self.assertAlmostEqual(sum(v*v for v in mesh.vertices[at+3:at+6]),1.,places=5)
                pcb=next(m for m in meshes if m.name=='motherboard-reference')
                for axis,wanted in ((1,row['dimensions_mm']['height']),(2,row['dimensions_mm']['width'])):
                    self.assertAlmostEqual(max(pcb.vertices[axis::6])-min(pcb.vertices[axis::6]),wanted)
                cp=anchors['cpu']['position'];hit=nearest(meshes,(board['x']-100.,cp[1],cp[2]))
                self.assertTrue(hit)
                self.assertNotIn(hit[1],('board-vrm-io-heatsink','board-vrm-top-heatsink','detail-board-m2-heatsink','board-chipset-heatsink'))
                self.assertFalse(meta['cad_verified'])

    def test_six_styles_keep_physical_meshes_and_unverified_fans_static(self):
        from assembly_style import apply_model_styles
        from top_bar_config import HARDWARE_ICON_STYLES
        for identity in (*REFINED,'msi-mpg-b650i-edge-wifi','asus-rog-strix-b650e-i-wifi'):
            anchors,meshes,meta=build(identity)
            before=copy.deepcopy(meta);topology=[(m.name,m.vertices,m.position,m.rotor) for m in meshes]
            for style in HARDWARE_ICON_STYLES:
                styled,_=apply_model_styles(meshes,style,{},(250.,500.,500.),{'front':'open'})
                self.assertEqual([(m.name,m.vertices,m.position,m.rotor) for m in styled],topology)
                self.assertFalse(any(m.rotor for m in styled))
            self.assertEqual(meta,before)
            json.dumps(meta)


if __name__=='__main__':unittest.main()
