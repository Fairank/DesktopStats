"""Primary-observed rear-bay skins/frames; pure helper, no host construction."""
from collections import Counter
import copy
import hashlib
import json
import math
import struct
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,box
from assembly_auxiliary import _segment_triangle,add_auxiliary
from assembly_case_shrouds052 import apply_layout_anchors
from assembly_cooling import add_cooling
from assembly_rear_bay_group_b052 import CASE_IDS,PENDING_IDS,NV7,C8,PANO,VISION,KING,PSU_BASIS,build,layout_reference
from assembly_style import apply_model_styles
from assembly_visibility048 import mesh_visible
from chassis_catalog import get_case

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
TONE=(.12,.14,.16,1.)


def dims(case):return tuple(float(case['dimensions_mm'][k]) for k in ('width','height','depth'))


def triangles(mesh):
    return tuple(tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12))
        for i in range(0,len(mesh.vertices),18))


def bounds(mesh):return tuple(tuple(op(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for op in (min,max))


def hit(mesh,a,b):return any(_segment_triangle(a,b,t) for t in triangles(mesh))


def separated(a,b):return any(a[1][k]<=b[0][k]+1e-8 or b[1][k]<=a[0][k]+1e-8 for k in range(3))


def surfaces_separated(mesh,bb):
    if separated(bounds(mesh),bb):return True
    return all(separated(tuple(tuple(op(p[k] for p in t) for k in range(3)) for op in (min,max)),bb) for t in triangles(mesh))


def canonical(value):
    """Type/F64-preserving value representation; never object identity."""
    if value is None:return ['none']
    if isinstance(value,bool):return ['bool',value]
    if isinstance(value,int):return ['int',str(value)]
    if isinstance(value,float):return ['f64',struct.pack('<d',value).hex()]
    if isinstance(value,str):return ['str',value]
    if isinstance(value,dict):return ['dict',[[canonical(k),canonical(v)] for k,v in sorted(value.items(),key=lambda p:repr(p[0]))]]
    if isinstance(value,(tuple,list)):return [type(value).__name__,[canonical(v) for v in value]]
    raise TypeError(type(value))


class RearBayGroupB052Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('Pure reference construction only')))

    def test_exact_five_primary_bindings_detached_metadata_and_variant_isolation(self):
        self.assertEqual(CASE_IDS,(NV7,C8,PANO,VISION,KING));self.assertEqual(PENDING_IDS,())
        for identity,count in zip(CASE_IDS,(4,2,3,3,3)):
            case=get_case(identity);before=copy.deepcopy(case);meshes,meta=build(case,dims(case),TONE)
            self.assertEqual(case,before);self.assertEqual(len(meshes),count)
            self.assertEqual({m.part_id for m in meshes},{r['id'] for r in meta['parts']})
            self.assertTrue(meta['replaces_rear_chamber_shroud'])
            self.assertFalse(meta['chamber_is_solid']);self.assertFalse(meta['selected_component_geometry_used'])
            self.assertFalse(meta['cad_verified']);self.assertFalse(meta['dimensions_verified'])
            self.assertFalse(meta['positions_verified']);self.assertFalse(meta['thickness_verified'])
            self.assertEqual(meta['installed_storage_assumed'],0)
            for row in meta['parts']:
                self.assertEqual(row['component'],'case');self.assertEqual(row['assembly_state'],'installed')
                self.assertFalse(row['dimensions_verified']);self.assertFalse(row['display_screen'])
                self.assertFalse(row['power_sensor_bound']);self.assertTrue(row['source_url'].startswith('https://'))
            meta['parts'][0]['label']='private mutation'
            self.assertNotEqual(build(case,dims(case),TONE)[1]['parts'][0]['label'],'private mutation')
        for identity in ('phanteks-nv5','lian-li-o11-vision-compact'):
            case=get_case(identity);self.assertEqual(build(case,dims(case),TONE),((),{}))
            self.assertEqual(layout_reference(case,dims(case)),{})
        for identity in ('montech-king-95-pro','montech-king-95-ultra','montech-king-95-3d','montech-king-95-mkii'):
            case=copy.deepcopy(get_case(KING));case['id']=identity
            self.assertEqual(build(case,dims(case),TONE),((),{}))
        for value in (None,(253.,586.),(True,586.,532.),(253.,float('inf'),532.),(0.,586.,532.)):
            self.assertEqual(build(get_case(NV7),value,TONE),((),{}))

    def test_closed_outward_nondegenerate_material_and_no_selected_hardware_carving(self):
        for identity in CASE_IDS:
            case=get_case(identity);meshes,_=build(case,dims(case),TONE)
            altered=copy.deepcopy(case);altered.update(selected_psu_length_mm=999,selected_fan_size_mm=999)
            alternate,_=build(altered,dims(case),TONE)
            self.assertEqual([m.vertices for m in alternate],[m.vertices for m in meshes])
            for mesh in meshes:
                counts=Counter();directions=Counter();volume=0.
                for i,(a,b,c) in enumerate(triangles(mesh)):
                    ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
                    normal=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                    self.assertGreater(math.hypot(*normal),1e-9)
                    stored=mesh.vertices[i*18+3:i*18+6]
                    self.assertAlmostEqual(math.hypot(*stored),1.)
                    self.assertGreater(sum(stored[k]*normal[k] for k in range(3)),0.)
                    volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6.
                    for p,q in zip((a,b,c),(b,c,a)):
                        key=tuple(sorted((p,q)));counts[key]+=1;directions[key]+=1 if p<q else -1
                self.assertEqual(set(counts.values()),{2},(identity,mesh.part_id))
                self.assertEqual(set(directions.values()),{0},(identity,mesh.part_id))
                self.assertGreater(volume,1.);self.assertLess(volume,200000.)

    def test_support_void_empty_cages_and_open_o11v_frame_are_actual_material_not_full_bay(self):
        for identity in CASE_IDS:
            case=get_case(identity);w,h,d=dims(case);meshes,meta=build(case,(w,h,d),TONE)
            support=meshes[0];layout=layout_reference(case,(w,h,d));top=layout['psu_support_top_y_mm']
            x=layout['psu']['boundary_x_mm']-43.;z=-d/2+80.
            self.assertFalse(hit(support,(x,top+20.,z),(x,top+130.,z)))
            material_x=w*.20+2. if identity==KING else x
            self.assertTrue(hit(support,(material_x,top-3.,z),(material_x,top+3.,z)))
            if identity==KING:self.assertFalse(hit(support,(x,top-3.,z),(x,top+3.,z)))
            for cage in (m for m in meshes if m.name=='case-empty-drive-cage'):
                low,high=bounds(cage);center=tuple((low[k]+high[k])/2 for k in range(3))
                for axis in range(3):
                    a=list(center);b=list(center);a[axis]=low[axis]-1.;b[axis]=high[axis]+1.
                    self.assertFalse(hit(cage,tuple(a),tuple(b)),(identity,axis))
            if identity==VISION:
                frame=next(m for m in meshes if m.name=='case-rear-psu-frame');low,high=bounds(frame)
                y=(low[1]+high[1])/2
                self.assertFalse(hit(frame,(x,y,low[2]-1.),(x,y,high[2]+1.)))
                self.assertTrue(hit(frame,(low[0]+1.,y,low[2]-1.),(low[0]+1.,y,high[2]+1.)))
                self.assertTrue(meta['source_psu_bracket_protrusion_verified'])
                self.assertFalse(meta['rear_protrusion_modeled']);self.assertFalse(meta['rear_outer_panel_opening_modeled'])

    def test_fixed_psu_faces_bottom_main_bay_and_nv7_hybrid_contract_preserve_reference_boundaries(self):
        self.assertEqual(PSU_BASIS,((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)))
        for identity in CASE_IDS:
            case=get_case(identity);w,h,d=dims(case);layout=layout_reference(case,(w,h,d))
            self.assertEqual(layout['psu']['basis'],PSU_BASIS)
            self.assertEqual(layout['psu']['rear_z_mm'],-d/2+10.)
            self.assertEqual(layout['psu']['boundary_x_mm'],w/2-9.)
            bottom=layout['mount_planes']['bottom']
            self.assertEqual(bottom['normal'],(0.,-1.,0.));self.assertEqual(bottom['position'][1],-h/2+20.)
            self.assertFalse(bottom['positions_verified']);self.assertFalse(bottom['normal_verified'])
            bx=w*.23 if identity==NV7 else w*.10
            self.assertLess(bottom['position'][0]+bottom['span_mm'][0]/2,bx+4.)
            if identity==NV7:
                self.assertEqual(layout['board_y_mm'],-h*.10)
                self.assertAlmostEqual(layout['rear_divider_top_y_mm'],layout['psu_support_top_y_mm']-1.2)
                self.assertGreater(layout['rear_divider_top_y_mm']-(-h*.10+305./2),4.)
            else:self.assertNotIn('board_y_mm',layout)
            if identity==VISION:self.assertNotIn('top',layout['mount_planes'])

    def test_actual_reference_atx_pcb_sanity_and_six_style_physical_identity(self):
        for identity in CASE_IDS:
            case=get_case(identity);w,h,d=dims(case);meshes,_=build(case,(w,h,d),TONE)
            layout=layout_reference(case,(w,h,d));x=layout.get('board_x_mm',w*.10);y=layout.get('board_y_mm',h*.02)
            pcb=Mesh('atx-reference',box(1.6,305.,244.),TONE,(x,y,-d/2+14.+122.),'board')
            for material in meshes:self.assertTrue(surfaces_separated(material,bounds(pcb)),(identity,material.part_id))
            for style in SIX:
                styled,_=apply_model_styles(meshes,style,{},(w,h,d),case['panels'])
                for before,after in zip(meshes,styled):
                    self.assertIs(before.vertices,after.vertices)
                    self.assertEqual((before.position,before.axis,before.part_id),(after.position,after.axis,after.part_id))
            for mesh in meshes:
                self.assertEqual(mesh_visible(mesh,True,True),mesh.name!='rear-chamber-shroud')

    def test_actual_rm1000x_all_three_lod_children_clear_case_supports_and_original_floor(self):
        for identity in CASE_IDS:
            case=get_case(identity);w,h,d=dims(case);materials,_=build(case,(w,h,d),TONE)
            floor=Mesh('case-bottom',box(w,3.,d),TONE,(0.,-h/2+17.5,0.))
            spec=dict(case=case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=False))
            layout=layout_reference(case,(w,h,d))
            anchors=apply_layout_anchors(dict(case=case,case_dimensions=(w,h,d)),spec,layout)
            for lod in ('eco','balanced','close'):
                meshes,meta=add_auxiliary(spec,anchors,lod)
                self.assertEqual(meta['rejected'],[])
                psu=[m for m in meshes if m.component=='psu']
                self.assertEqual(sum(m.name=='psu-shell' for m in psu),1)
                self.assertTrue(any(m.name=='psu-fan-panel-fasteners' for m in psu))
                self.assertEqual(anchors['psu']['world_dimensions_mm'],(86.,150.,160.))
                for mesh in psu:
                    for material in (*materials,floor):
                        self.assertTrue(surfaces_separated(material,bounds(mesh)),(identity,lod,material.part_id,mesh.name))
                self.assertGreater(min(bounds(m)[0][1] for m in psu)-bounds(floor)[1][1],2.7)

    def test_actual_bottom_banks_three_lods_keep_complete_fans_and_clear_thin_material(self):
        for identity in CASE_IDS:
            case=get_case(identity);w,h,d=dims(case);materials,_=build(case,(w,h,d),TONE)
            floor=Mesh('case-bottom',box(w,3.,d),TONE,(0.,-h/2+17.5,0.))
            layout=layout_reference(case,(w,h,d))
            anchors=dict(case=case,case_dimensions=(w,h,d),case_mount_planes=layout['mount_planes'])
            for size,model in ((120,'arctic-p12-pwm'),(140,'arctic-p14-pwm')):
                count=2 if identity in (PANO,KING) and size==140 else 3
                for lod in ('eco','balanced','close'):
                    spec=dict(case=case,cooling=dict(cpu_cooler='none',case_fans=[dict(model=model,mount='bottom',count=count)]))
                    meshes,meta=add_cooling((*materials,floor),spec,lod,anchors)
                    self.assertEqual(meta['rejected'],[],(identity,size,lod))
                    frames=[m for m in meshes if m.name=='case-fan-frame'];rotors=[m for m in meshes if m.rotor]
                    self.assertEqual(len(frames),count);self.assertEqual(len(rotors),count)
                    self.assertEqual({m.part_id for m in frames},{'fans:bottom:'+str(i) for i in range(count)})
                    for mesh in meshes:
                        if any(word in mesh.name for word in ('lead','wire','connector')):continue
                        for material in (*materials,floor):
                            self.assertTrue(surfaces_separated(material,bounds(mesh)),
                                (identity,size,lod,material.part_id,mesh.name))

    def test_king95_original_lower_psu_and_separate_upper_empty_drive_mount_keep_source_conflicts(self):
        case=get_case(KING);w,h,d=dims(case);meshes,meta=build(case,(w,h,d),TONE)
        layout=layout_reference(case,(w,h,d))
        self.assertEqual(layout['psu']['floor_y_mm'],-h/2+22.2)
        self.assertEqual(layout['psu']['basis'],PSU_BASIS)
        self.assertEqual(meta['source_variant'],'original_non_pro_default_glass')
        self.assertEqual(meta['default_psu_mount'],'lower_rear')
        self.assertTrue(meta['alternate_upper_psu_mount_observed']);self.assertFalse(meta['alternate_upper_psu_modeled'])
        self.assertFalse(meta['full_psu_shelf_added']);self.assertEqual(meta['installed_storage_assumed'],0)
        self.assertIsNone(meta['source_max_psu_length_mm']);self.assertFalse(meta['source_psu_length_limit_verified'])
        self.assertEqual(meta['source_psu_length_conflict_mm'],dict(legacy_manual=190.,current_product=185.))
        self.assertFalse(meta['source_psu_length_conflict_resolved'])
        self.assertEqual(meta['source_side_radiator_conflict_mm'],dict(legacy_manual=280.,current_product=240.))
        self.assertFalse(meta['source_side_radiator_capacity_changed'])
        self.assertIn('https://www.telon.com.tw/en/about.php',meta.values())
        self.assertEqual({m.part_id for m in meshes},{'case:rear-psu-support','case:rear-psu-mount','case:drive-cage'})
        rows={r['id']:r for r in meta['parts']}
        self.assertFalse(rows['case:rear-psu-mount']['factory_removable'])
        self.assertEqual(rows['case:rear-psu-mount']['source_fastener_count'],4)
        self.assertFalse(rows['case:rear-psu-mount']['source_fastener_positions_modeled'])
        self.assertTrue(rows['case:drive-cage']['factory_removable'])
        self.assertTrue(rows['case:drive-cage']['empty_drive_mount'])

    def test_prior_four_case_mesh_fields_float64_metadata_and_layout_remain_exact(self):
        # Captured before this exact KING95 extension from the earlier frozen
        # helper a3adbb3a...e239. No dependency on private QA files is needed.
        expected={NV7:'cfe247d9b2edc2e47f772fa807f80d9d833d1ecdd9a0235c1caef50c4102cc6d',
            C8:'16af7e0aefe8668c06034793e768c39624ce21ef13ed503b78d31c01386909a4',
            PANO:'1987a2393813aa489d85cd44587480339623635f1e4c7aff01d345302fc2379a',
            VISION:'c991ecd743b1b8cd5ea3eb42c49dc8bb9effda72f3dbd40b96bae427750a9f63'}
        for identity,wanted in expected.items():
            case=get_case(identity);meshes,meta=build(case,dims(case),TONE)
            fields=[tuple((name,getattr(m,name)) for name in m.__dataclass_fields__) for m in meshes]
            data=json.dumps(canonical((fields,meta,layout_reference(case,dims(case)))),
                ensure_ascii=True,separators=(',',':')).encode()
            self.assertEqual(hashlib.sha256(data).hexdigest(),wanted,identity)


if __name__=='__main__':unittest.main()
