"""Exact six observed lower structures: actual geometry, not AABB-only fit."""
import copy
from contextlib import ExitStack
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,box,color
from assembly_shroud_other052 import build,layout_reference,CASE_IDS
from chassis_catalog import CASES,get_case

STYLES=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def _sub(a,b):return tuple(x-y for x,y in zip(a,b))
def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _world(mesh):
    return tuple(tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3))
        for j in (0,6,12)) for i in range(0,len(mesh.vertices),18))
def _bounds(tri):return tuple(tuple(f(p[k] for p in tri) for k in range(3)) for f in (min,max))
def _mesh_bounds(mesh):
    return tuple(tuple(f(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for f in (min,max))


def _ray_inside(point,triangles,direction=(1.,.173,.317)):
    hits=[]
    for a,b,c in triangles:
        e1,e2=_sub(b,a),_sub(c,a);h=_cross(direction,e2);det=_dot(e1,h)
        if abs(det)<1e-10:continue
        inv=1/det;s=_sub(point,a);u=inv*_dot(s,h)
        if not -1e-10<=u<=1+1e-10:continue
        q=_cross(s,e1);v=inv*_dot(direction,q)
        if v < -1e-10 or u+v > 1+1e-10:continue
        t=inv*_dot(e2,q)
        if t>1e-8:hits.append(t)
    unique=[]
    for t in sorted(hits):
        if not unique or abs(t-unique[-1])>1e-7:unique.append(t)
    return len(unique)%2==1


def _surface_intersection(a,b):
    """Independent static SAT with coplanar in-plane separators."""
    aa,bb=_bounds(a),_bounds(b)
    if any(aa[1][k]<bb[0][k]-1e-8 or bb[1][k]<aa[0][k]-1e-8 for k in range(3)):return False
    ea=tuple(_sub(a[(i+1)%3],a[i]) for i in range(3));eb=tuple(_sub(b[(i+1)%3],b[i]) for i in range(3))
    na,nb=_cross(ea[0],ea[1]),_cross(eb[0],eb[1])
    axes=[na,nb,*(_cross(x,y) for x in ea for y in eb)]
    if _dot(_cross(na,nb),_cross(na,nb))<1e-14*_dot(na,na)*_dot(nb,nb):
        axes.extend(_cross(na,e) for e in (*ea,*eb))
    for axis in axes:
        length=math.sqrt(_dot(axis,axis))
        if length<1e-10:continue
        pa=[_dot(p,axis) for p in a];pb=[_dot(p,axis) for p in b]
        if max(pa)<min(pb)-1e-8*length or max(pb)<min(pa)-1e-8*length:return False
    return True


def _dim(case):return tuple(case['dimensions_mm'][k] for k in ('width','height','depth'))


class OtherShroud052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure geometry only')))

    def test_exact_six_only_fixed_structure_and_unknown_manufacturing_dimensions(self):
        self.assertEqual(len(CASE_IDS),6);self.assertEqual(len(set(CASE_IDS)),6)
        for case in CASES:
            previous=copy.deepcopy(case);meshes,meta=build(case,_dim(case),color('#25313e'))
            self.assertEqual(case,previous)
            if case['id'] not in CASE_IDS:self.assertEqual((meshes,meta),((),{}));continue
            self.assertTrue(meshes);self.assertFalse(meta['chamber_is_solid'])
            self.assertEqual(meta.get('replaces_case_bottom',False),case['id'] in
                ('cooler-master-haf-700-evo','inwin-dubili','be-quiet-shadow-base-800-fx'))
            for field in ('dimensions_verified','positions_verified','thickness_verified','cad_verified','selected_component_geometry_used'):
                self.assertIs(meta[field],False)
            self.assertTrue(meta['source_urls']);self.assertTrue(all(u.startswith('https://') for u in meta['source_urls']))
            changed=copy.deepcopy(case);changed['selected_fan']=dict(size=1000,count=4);changed['board']={'form':'itx'}
            other,other_meta=build(changed,_dim(case),color('#25313e'))
            self.assertEqual(other,meshes);self.assertEqual(other_meta,meta)
            self.assertEqual({m.part_id for m in meshes},{p['id'] for p in meta['parts']})
            self.assertTrue(all(m.component=='case' and m.part_id.startswith('case:') for m in meshes))
            for bad in ((1,2),(239.,float('nan'),490.),(True,486.,490.),(239.,486.,2000.)):
                self.assertEqual(build(case,bad,color('#25313e')),((),{}))

    def test_finite_non_degenerate_unit_outward_geometry_and_bounded_cost(self):
        for key in CASE_IDS:
            case=get_case(key);meshes,_=build(case,_dim(case),color('#25313e'));total=0
            for mesh in meshes:
                self.assertEqual(len(mesh.vertices)%18,0)
                total+=len(mesh.vertices)//18
                for at,triangle in zip(range(0,len(mesh.vertices),18),_world(mesh)):
                    n=_cross(_sub(triangle[1],triangle[0]),_sub(triangle[2],triangle[0]))
                    self.assertGreater(_dot(n,n),1e-16)
                    for vertex in (0,6,12):
                        normal=mesh.vertices[at+vertex+3:at+vertex+6]
                        self.assertAlmostEqual(_dot(normal,normal),1.,places=8)
                        self.assertGreater(_dot(n,normal),0.)
                    self.assertTrue(all(math.isfinite(v) for p in triangle for v in p))
            self.assertLess(total,1500)

    def test_old_compartment_centre_is_actual_void_and_retained_material_is_not_empty(self):
        for key in CASE_IDS:
            case=get_case(key);w,h,d=_dim(case);meshes,meta=build(case,(w,h,d),color('#25313e'))
            point=(0.,-h*.405,0.)
            for mesh in meshes:
                for direction in ((1.,.173,.317),(.317,1.,.173),(.173,.317,1.)):
                    self.assertFalse(_ray_inside(point,_world(mesh),direction),(key,mesh.name))
            self.assertTrue(any(mesh.vertices for mesh in meshes));self.assertTrue(meta['front_bay_open'])
            if meta['horizontal_psu_cover_present']:
                inside=(meta['side_world_x_mm']+.6,-h*.405,-d*.30)
                if key=='phanteks-eclipse-g500a-drgb':inside=(inside[0],-h*.48,-d*.30)
                self.assertTrue(_ray_inside(inside,_world(meshes[0])),key)

    def test_source_specific_haf_rear_chamber_dubili_open_floor_and_g500_actual_window(self):
        haf=get_case('cooler-master-haf-700-evo');hm,hmeta=build(haf,_dim(haf),color('#25313e'))
        self.assertFalse(hmeta['horizontal_psu_cover_present']);self.assertEqual(hmeta['source_behind_tray_clearance_mm'],(90.,101.))
        self.assertTrue(hmeta['hardware_chamber_pose_requires_reference_review'])
        self.assertTrue(all(m.name!='psu-shroud' for m in hm))
        layout=layout_reference(haf,_dim(haf))
        self.assertEqual(layout['board_x_mm'],35.5);self.assertEqual(layout['tray_x_mm'],43.5)
        self.assertEqual(layout['psu']['boundary_x_mm'],48.5)
        self.assertEqual((layout['psu']['floor_y_mm'],layout['psu']['rear_z_mm']),(-267.,-323.))
        self.assertEqual(layout['psu']['basis'],((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)))
        self.assertFalse(layout['positions_verified']);self.assertFalse(layout['dimensions_verified'])
        tray=next(m for m in hm if m.part_id=='case:motherboard-tray')
        self.assertEqual(len(tray.vertices)//18,92)
        # Official-photo CPU access opening is actual missing tray material;
        # a neighbouring region remains a real thin plate.
        self.assertFalse(_ray_inside((43.5,80.,-180.),_world(tray),(1.,0.,0.)))
        self.assertTrue(_ray_inside((43.5,-100.,-250.),_world(tray),(1.,0.,0.)))
        for other in CASES:
            if other['id'] not in CASE_IDS:self.assertEqual(layout_reference(other,_dim(other)),{})
        dubili=get_case('inwin-dubili');dm,dmeta=build(dubili,_dim(dubili),color('#25313e'))
        self.assertFalse(dmeta['horizontal_psu_cover_present']);self.assertFalse(dmeta['cable_shields_are_psu_cover'])
        self.assertTrue(all(m.name!='psu-shroud' for m in dm))
        case=get_case('phanteks-eclipse-g500a-drgb');meshes,meta=build(case,_dim(case),color('#25313e'))
        hole=meta['side_holes_local_zy'][0];point=(meta['side_world_x_mm']+.6,
            sum(p[1] for p in hole)/len(hole),-sum(p[0] for p in hole)/len(hole))
        self.assertFalse(_ray_inside(point,_world(meshes[0]),(1.,0.,0.)))
        self.assertTrue(meta['psu_observation_window_open'])
        self.assertEqual(meta['roof_reference_vent_samples'],0)
        self.assertEqual(meta['roof_vent_sampling'],'not_inferred_solid_psu_roof')
        frame=get_case('corsair-frame-4000d');_,fmeta=build(frame,_dim(frame),color('#25313e'))
        self.assertTrue(fmeta['stock_front_cutaway']);self.assertIn('STANDARD',fmeta['manual_section'])

    def test_fixed_horizontal_psu_floor_roof_board_and_per_source_orientation(self):
        proportions={'be-quiet-shadow-base-800-fx':.28,'asus-tuf-gt302-argb':.275,
            'phanteks-eclipse-g500a-drgb':.28,'corsair-frame-4000d':.265}
        for key in (*proportions,'inwin-dubili'):
            case=get_case(key);w,h,d=_dim(case);layout=layout_reference(case,(w,h,d))
            self.assertEqual(layout['psu']['floor_y_mm'],-h/2+(21 if key=='inwin-dubili' else 20))
            self.assertEqual(layout['psu']['center_x_mm'],0.)
            self.assertEqual(layout['psu']['basis'],((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)))
            self.assertEqual(layout['psu_fan_face_reference'],'down')
            self.assertEqual(layout['psu_fan_orientation_verified'],key=='corsair-frame-4000d')
            self.assertFalse(layout['positions_verified']);self.assertFalse(layout['dimensions_verified'])
            self.assertTrue(layout['psu_orientation_source'].startswith('https://'))
            covers,meta=build(case,(w,h,d),color('#25313e'))
            if key in proportions:
                self.assertEqual(meta['roof_world_y_mm'],-h*proportions[key])
                self.assertEqual(layout['board_y_mm'],h*.10)
                self.assertGreater(meta['roof_world_y_mm']-1.2-(layout['psu']['floor_y_mm']+86.),0.)
                self.assertGreater(layout['board_y_mm']-305/2-meta['roof_world_y_mm'],0.)
            else:self.assertNotIn('board_y_mm',layout)

    def test_bottom_revision_preserves_other_four_whole_payloads_and_existing_two_materials(self):
        # Captured immediately before the two exact-model bottom references.
        # Protect metadata/layout too: no brand-wide or generic pose changes.
        expected={
            'cooler-master-haf-700-evo':'c41726f0d3ab2dee93ea0d522876810421a7f105ece819d2078056e9d4254e45',
            'asus-tuf-gt302-argb':'3546e036db1450392f09f6544f2f3e68e3a7df4325c571331a3289ea19854590',
            'phanteks-eclipse-g500a-drgb':'c06a0616a0ded6584a68b2492151043610bdcfc7587f5e599fe54373e2d71b4e',
            'corsair-frame-4000d':'42dafc450d3a4d5ee0fcf895cb4401bb8cc8366e325622a538c8d79f5279b6ee'}
        digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        for key,sha in expected.items():
            case=get_case(key);dims=_dim(case);meshes,meta=build(case,dims,color('#25313e'))
            self.assertEqual(digest(dict(meshes=[asdict(m) for m in meshes],meta=meta,
                layout=layout_reference(case,dims))),sha,key)
        originals={
            'inwin-dubili':(1,'ef8697dc9dd44212ee5d92b8e554a99076ff8f4a14449d4c6f9a31ed3ef4d447'),
            'be-quiet-shadow-base-800-fx':(2,'d2810fb93d27d0cebf813af88a4934668089486ce9284750d58c7cac27cf51f6')}
        for key,(count,sha) in originals.items():
            case=get_case(key);meshes,_=build(case,_dim(case),color('#25313e'))
            self.assertEqual(digest([asdict(m) for m in meshes[:count]]),sha,key)

    def test_bottom_reference_fixed_front_floor_capacity_and_conditional_psu_source(self):
        for key in ('inwin-dubili','be-quiet-shadow-base-800-fx'):
            case=get_case(key);w,h,d=_dim(case);layout=layout_reference(case,(w,h,d))
            plane=layout['mount_planes']['bottom'];limit=layout['fan_constraints']['bottom']
            self.assertEqual(plane['case_id'],key);self.assertEqual(limit['case_id'],key)
            self.assertEqual(plane['normal'],(0.,-1.,0.));self.assertEqual(plane['up'],(0.,0.,1.))
            self.assertEqual(plane['position'],(0.,-h/2+(20.6 if key=='inwin-dubili' else 20.),
                d*(.16 if key=='inwin-dubili' else .25)))
            expected={'120':2,'140':1} if key=='inwin-dubili' else {'120':1,'140':1}
            self.assertEqual(limit['max_count_by_size_mm'],expected)
            self.assertEqual(plane['source_capacity_count_by_size_mm'],expected)
            for field in ('positions_verified','dimensions_verified','mounting_hole_positions_verified','span_verified'):
                self.assertIs(plane[field],False)
            self.assertIs(limit['dimensions_verified'],False)
            self.assertEqual(plane['source'],limit['source_url'])
            declared={str(size):max(row['count'] for row in case['fan_mounts']
                if row['position']=='bottom' and size in row['size_mm']) for size in (120,140)}
            self.assertEqual(declared,expected)
            changed=copy.deepcopy(case);changed.update(selected_psu_length=230,selected_fan_size=500,board={'form':'itx'})
            self.assertEqual(layout_reference(changed,(w,h,d)),layout)
            if key=='inwin-dubili':
                self.assertEqual(limit['source_manual_pdf_page'],4)
                self.assertEqual(limit['psu_length_threshold_mm'],180.)
                self.assertEqual(limit['max_count_above_psu_length_threshold'],1)
                self.assertEqual(limit['source_max_psu_length_mm'],230.)
            else:
                self.assertEqual(limit['source_mount_role'],'front_floor_under_psu_cover')
                self.assertFalse(limit['source_original_bytes_verified'])
                meshes,meta=build(case,(w,h,d),color('#25313e'))
                floor=next(m for m in meshes if m.part_id=='case:bottom-intake-floor')
                self.assertTrue(meta['replaces_case_bottom']);self.assertEqual(meta['bottom_floor_vent_samples'],24)
                self.assertEqual(_mesh_bounds(floor)[1][1],-h/2+18.1)
                # Real open slots and neighbouring supporting material, not a
                # black texture over the old complete six-faced solid floor.
                left=-w/2+3.;rear=-d/2+3.
                hole=(left+5.+(w-16.)/6-2.5,-h/2+17.5,rear+4.+(d-14.)/16-2.)
                self.assertFalse(_ray_inside(hole,_world(floor),(0.,1.,0.)))
                self.assertTrue(_ray_inside((left+1.,-h/2+17.5,0.),_world(floor),(0.,1.,0.)))

    def test_actual_bottom_fan_frames_rotors_leads_and_connectors_clear_fixed_material_all_lods(self):
        from assembly_auxiliary import add_auxiliary
        from assembly_case_shrouds052 import apply_layout_anchors
        from assembly_cooling import add_cooling
        rows=0
        for key in ('inwin-dubili','be-quiet-shadow-base-800-fx'):
            case=get_case(key);dims=_dim(case);w,h,d=dims;covers,meta=build(case,dims,color('#25313e'))
            layout=layout_reference(case,dims)
            selections=[(120,'arctic-p12-pwm',2 if key=='inwin-dubili' else 1,'corsair-rm1000x-2024'),
                        (140,'arctic-p14-pwm',1,'corsair-rm1000x-2024')]
            if key=='inwin-dubili':selections.append((120,'arctic-p12-pwm',1,'asus-rog-thor-1000p2'))
            for size,model,count,psu_model in selections:
                spec=dict(case=case,auxiliary=dict(psu=dict(model_id=psu_model),cables_enabled=False),
                    cooling=dict(cpu_cooler='none',case_fans=[dict(model=model,mount='bottom',count=count,direction='intake')]))
                anchors=apply_layout_anchors(dict(case=case,case_dimensions=dims,connectors={}),spec,layout)
                for level in ('eco','balanced','close'):
                    psu,_=add_auxiliary(spec,anchors,level)
                    obstacles=(*covers,*(m for m in psu if m.component=='psu'))
                    fans,cooling=add_cooling(obstacles,spec,level,anchors)
                    self.assertEqual(cooling['rejected'],[],(key,size,level))
                    self.assertEqual(len([p for p in cooling['parts'] if p['kind']=='case_fan']),count)
                    self.assertEqual(len([m for m in fans if m.rotor]),count)
                    self.assertEqual(len([m for m in fans if m.name=='case-fan-power-connector']),count)
                    self.assertTrue(all(f['rpm'] is None for f in cooling['fans']))
                    for fan in fans:
                        # Every actual static/rotating mesh, including the
                        # attached schematic PWM lead, retains its real pose.
                        for other in obstacles:
                            aa,bb=_mesh_bounds(fan),_mesh_bounds(other)
                            if any(aa[1][k]<bb[0][k]-1e-8 or bb[1][k]<aa[0][k]-1e-8 for k in range(3)):continue
                            self.assertFalse(any(_surface_intersection(a,b) for a in _world(fan) for b in _world(other)),
                                (key,size,level,fan.name,other.name))
                    self.assertGreater(min(_mesh_bounds(m)[0][1] for m in fans)-
                        max(_mesh_bounds(m)[1][1] for m in covers if m.name=='case-bottom-cooling-support'),0.)
                    rows+=1
        self.assertEqual(rows,15)

    def test_previous_base10_plane_has_actual_three_ray_shared_material_not_just_bounds(self):
        from assembly_cooling import add_cooling
        # Witnesses of the two pre-fix reference layouts. Recreate the old
        # fixed face, then independently test actual frame and floor faces.
        # These are historical model defects, not retail-case limitations.
        for key,count,point in (
            ('inwin-dubili',2,(59.99858578643763,-251.9014142135624,-79.83046745007093)),
            ('be-quiet-shadow-base-800-fx',1,(38.02836219133768,-242.00141421356238,-59.99858578643763))):
            case=get_case(key);dims=_dim(case);w,h,d=dims;meshes,_=build(case,dims,color('#25313e'))
            floor=next(m for m in meshes if m.name=='case-bottom-cooling-support') if key=='inwin-dubili' else \
                Mesh('historical-case-bottom',box(w,3.,d),color('#25313e'),(0.,-h/2+17.5,0.))
            anchors=dict(case=case,case_dimensions=dims,case_mount_planes={'bottom':dict(
                position=(0.,-h/2+10.,0.),normal=(0.,-1.,0.),up=(0.,0.,1.))})
            spec=dict(case=case,cooling=dict(cpu_cooler='none',case_fans=[dict(model='arctic-p12-pwm',
                mount='bottom',count=count,direction='intake')]))
            fans,cooling=add_cooling((floor,),spec,'eco',anchors)
            self.assertEqual(cooling['rejected'],[])
            frames=[m for m in fans if m.name=='case-fan-frame']
            self.assertEqual(len(frames),count)
            for direction in ((1.,.173,.317),(.317,1.,.173),(.173,.317,1.)):
                self.assertTrue(_ray_inside(point,_world(floor),direction),key)
                self.assertTrue(any(_ray_inside(point,_world(m),direction) for m in frames),key)

    def test_actual_rm1000x_mesh_clears_each_fixed_cover_and_floor_all_lods(self):
        from assembly_auxiliary import add_auxiliary
        from assembly_case_shrouds052 import apply_layout_anchors
        for key in ('be-quiet-shadow-base-800-fx','asus-tuf-gt302-argb',
                    'phanteks-eclipse-g500a-drgb','corsair-frame-4000d','inwin-dubili'):
            case=get_case(key);dims=_dim(case);w,h,d=dims
            covers,meta=build(case,dims,color('#25313e'));layout=layout_reference(case,dims)
            spec=dict(case=case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=False))
            anchors=apply_layout_anchors(dict(case=case,case_dimensions=dims,connectors={}),spec,layout)
            for level in ('eco','balanced','close'):
                meshes,aux=add_auxiliary(spec,anchors,level)
                self.assertEqual(aux['rejected'],[])
                psu=[m for m in meshes if m.component=='psu'];self.assertTrue(psu)
                actual_low=min(min(m.vertices[1::6])+m.position[1] for m in psu)
                floor_top=(-h/2+19.6) if key=='inwin-dubili' else (-h/2+19.)
                self.assertGreater(actual_low-floor_top,0.,(key,level))
                if meta['horizontal_psu_cover_present']:
                    actual_high=max(max(m.vertices[1::6])+m.position[1] for m in psu)
                    self.assertGreater(meta['roof_world_y_mm']-meta['thickness_mm']-actual_high,0.,(key,level))
                for a in psu:
                    aa=_mesh_bounds(a)
                    for b in covers:
                        # L roof+side can share one Mesh: inspect each actual
                        # triangle against the actual PSU bound, not its full
                        # filled compartment box. Any candidate stays strict.
                        for tri in _world(b):
                            bb=_bounds(tri)
                            self.assertTrue(any(aa[1][k]<bb[0][k]-1e-8 or bb[1][k]<aa[0][k]-1e-8
                                for k in range(3)),(key,level,a.name,b.name,tri))
            # Old base+12 actually embeds part of the selected PSU below the
            # fixed floor material; keep the regression rather than merely
            # asserting the new nominal centre moved upwards.
            old=dict(anchors,psu=dict(anchors['psu'],position=(0.,-h/2+12.+43.,-d/2+90.)))
            old_meshes,_=add_auxiliary(spec,old,'eco')
            self.assertLess(min(min(m.vertices[1::6])+m.position[1] for m in old_meshes if m.component=='psu'),floor_top)
            old_shell=next(m for m in old_meshes if m.name=='psu-shell')
            old_point=(74.3,-h/2+(19. if key=='inwin-dubili' else 17.5),-d/2+(25. if key=='inwin-dubili' else 50.))
            floor_material=next(m for m in covers if m.name=='case-bottom-cooling-support') if key=='inwin-dubili' else \
                Mesh('actual-generic-case-bottom',box(w,3.,d),color('#25313e'),(0.,-h/2+17.5,0.))
            for direction in ((1.,.173,.317),(.317,1.,.173),(.173,.317,1.)):
                self.assertTrue(_ray_inside(old_point,_world(old_shell),direction),(key,'old PSU real side sheet'))
                self.assertTrue(_ray_inside(old_point,_world(floor_material),direction),(key,'old shared floor-material interior'))
            if meta['horizontal_psu_cover_present']:
                # Raising only the floor while retaining legacy -.32H roof
                # would still run the real ATX side metal through that roof.
                old_roof=Mesh('legacy-low-roof',box(w-12.,1.2,d-12.),color('#25313e'),(0.,-h*.32-.6,0.))
                proper_shell=next(m for m in meshes if m.name=='psu-shell')
                point=(74.3,-h*.32-.6,-d/2+50.)
                for direction in ((1.,.173,.317),(.317,1.,.173),(.173,.317,1.)):
                    self.assertTrue(_ray_inside(point,_world(proper_shell),direction),(key,'legacy roof real PSU sheet'))
                    self.assertTrue(_ray_inside(point,_world(old_roof),direction),(key,'legacy roof material'))

    def test_actual_declared_front_fans_all_three_lods_have_no_cover_surface_crossing(self):
        from assembly_cooling import add_cooling
        # Production front positions/counts and actual triangulated fan frames,
        # no translated/shrunken test substitutes or omission accepted as fit.
        rows=0;historical_positive=0
        for key in CASE_IDS:
            case=get_case(key);dims=_dim(case);w,h,d=dims;covers,_=build(case,dims,color('#25313e'))
            shroud_triangles=[(t,_bounds(t)) for mesh in covers for t in _world(mesh)]
            for size,model,depth in ((120,'arctic-p12-pwm',25.),(140,'arctic-p14-pwm',27.)):
                matches=[m for m in case['fan_mounts'] if m['position']=='front' and size in m['size_mm']]
                if not matches:continue
                count=min(3,max(m['count'] for m in matches));spec=dict(case=case,cooling=dict(cpu_cooler='none',
                    case_fans=[dict(model=model,mount='front',count=count,direction='intake')]))
                for level in ('eco','balanced','close'):
                    fans,meta=add_cooling(covers,spec,level,dict(case=case,case_dimensions=dims))
                    self.assertEqual(meta['rejected'],[],(key,size,level));parts=[p for p in meta['parts'] if p['kind']=='case_fan']
                    self.assertEqual(len(parts),count);frames=[m for m in fans if m.name=='case-fan-frame']
                    self.assertEqual(len(frames),count)
                    for mesh in frames:
                        for triangle in _world(mesh):
                            bb=_bounds(triangle)
                            candidates=[t for t,tb in shroud_triangles if all(
                                bb[1][k]>=tb[0][k]-1e-8 and tb[1][k]>=bb[0][k]-1e-8 for k in range(3))]
                            self.assertFalse(any(_surface_intersection(triangle,t) for t in candidates),(key,size,level,mesh.part_id))
                    if level=='eco':
                        witness=(0.,-count*size/2+2.,d/2-depth/2-10.)
                        old=Mesh('historical-full-solid',box(w-12,h*.17,d-12),color('#25313e'),(0.,-h*.405,0.))
                        old_inside=_ray_inside(witness,_world(old))
                        actual_frame_inside=any(_ray_inside(witness,_world(frame)) for frame in frames)
                        if old_inside and actual_frame_inside:historical_positive+=1
                    rows+=1
        self.assertEqual(rows,33);self.assertEqual(historical_positive,9)

    def test_six_styles_share_original_vertices_ids_pose_no_extra_renderer_or_worker(self):
        from assembly_style import apply_model_styles
        for key in CASE_IDS:
            case=get_case(key);dims=_dim(case);meshes,_=build(case,dims,color('#25313e'))
            for style in STYLES:
                styled,meta=apply_model_styles(meshes,style,{},dims,case['panels'])
                physical=[m for m in styled if not m.name.startswith('style-')]
                self.assertEqual(len(physical),len(meshes))
                for a,b in zip(physical,meshes):
                    self.assertIs(a.vertices,b.vertices);self.assertEqual(a.position,b.position)
                    self.assertEqual((a.part_id,a.component,a.axis,a.rotor),(b.part_id,b.component,b.axis,b.rotor))
                self.assertEqual(meta['visual_style'],style)


class ActualBottomHost052Tests(unittest.TestCase):
    """Two complete AIR references, not a placeholder CPU blocking the bay."""
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        os.environ.setdefault('QT_QUICK_BACKEND','software')
        from PySide6.QtCore import QCoreApplication,QEvent
        from PySide6.QtGui import QGuiApplication,QOpenGLContext
        from PySide6.QtQml import QQmlEngine
        import hardware_packs
        from hardware_packs import PackStore
        from assembly_geometry import build_scene
        from assembly_parts import reference_preset
        from assembly_profiles import bake_profiles
        from assembly_spec import build_spec
        from stats_config import DEFAULT
        cls.qt=(QCoreApplication,QEvent,QOpenGLContext)
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software/offscreen reference construction only')
        cls.stack=ExitStack();cls.addClassCleanup(cls.stack.close)
        folder=Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.stack.enter_context(patch.object(hardware_packs,'_store',PackStore(folder/'packs')))
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            cls.stack.enter_context(patch(target,create=True,side_effect=AssertionError('No hardware/network/worker')))
        cls.engine=QQmlEngine();cls.warnings=[]
        cls.engine.warnings.connect(lambda rows:cls.warnings.extend(row.toString() for row in rows))
        cls.rows={};cls.geometry={}
        for key in ('inwin-dubili','be-quiet-shadow-base-800-fx'):
            bottom=dict(model='arctic-p12-pwm',count=2) if key=='inwin-dubili' else dict(model='arctic-p14-pwm',count=1)
            config=copy.deepcopy(DEFAULT)
            config['assembly']=dict(reference_preset({},'air'),case_model=key,
                board_model='asus-rog-strix-z790-a-wifi-d4',cpu_model='intel-13700kf',gpu_model='asus-astral-5090',
                memory_models=['gskill-f4-3200c16d-16gtzr']*2,psu_model='corsair-rm1000x-2024',
                cooler_model='noctua-nh-u12a',gpu_waterblock=False,cables_enabled=False,
                appearance_style='miniature',part_styles={},detail_level='balanced',
                case_fans=[dict(model='arctic-p14-pwm',mount='front',count=3,direction='intake'),
                           dict(bottom,mount='bottom',direction='intake')])
            original=copy.deepcopy(config);spec=bake_profiles(build_spec({},config,{},[]),cls.engine)
            scene=build_scene(spec)
            if original!=config:raise AssertionError('Public construction mutated reference selection')
            cls.rows[key]=(spec,scene)

    @classmethod
    def tearDownClass(cls):
        cls.rows.clear();cls.geometry.clear();cls.engine.deleteLater()
        core,event,gl=cls.qt;core.sendPostedEvents(None,event.DeferredDelete)
        if cls.warnings:raise AssertionError(cls.warnings)
        if cls.app.topLevelWindows() or gl.currentContext() is not None:
            raise AssertionError('No visible window or GL context allowed')

    def shape(self,mesh):
        import test_case_layout_hosts052 as material
        if id(mesh) not in self.geometry:self.geometry[id(mesh)]=material._geometry(mesh)
        return self.geometry[id(mesh)]

    def test_public_complete_identities_source_anchors_and_load_bearing_floor_visibility(self):
        from assembly_visibility048 import mesh_visible
        for key,(spec,scene) in self.rows.items():
            with self.subTest(case=key):
                self.assertEqual(spec['case']['id'],key);self.assertEqual(scene.metadata['case_id'],key)
                self.assertTrue(all(row['state']=='within_limit' for row in spec['checks']),spec['checks'])
                self.assertEqual([sum(p['kind']==kind for p in scene.metadata['hardware']['parts'])
                    for kind in ('cpu','gpu','memory')],[1,1,2])
                self.assertEqual(scene.metadata['memory_rendered_count'],2)
                self.assertEqual(scene.metadata['auxiliary']['device_counts']['psu'],1)
                self.assertEqual(scene.metadata['auxiliary']['rejected'],[])
                self.assertEqual(scene.metadata['cooling']['rejected'],[])
                self.assertEqual(scene.metadata['auxiliary']['cable_count'],0)
                for family in ('cpu','gpu','memory'):self.assertFalse(spec[family]['telemetry_bound'])
                plane=scene.metadata['attachment_anchors']['case_mount_planes']['bottom']
                self.assertEqual(plane['case_id'],key);self.assertFalse(plane['positions_verified'])
                self.assertFalse(plane['dimensions_verified'])
                self.assertTrue(scene.metadata['case_shroud']['replaces_case_bottom'])
                self.assertEqual(sum(m.name=='case-bottom' for m in scene.meshes),0)
                floor=next(m for m in scene.meshes if m.name=='case-bottom-cooling-support')
                for cutaway in (False,True):
                    for show in (False,True):self.assertTrue(mesh_visible(floor,cutaway,show_psu=show))
                expected=5 if key=='inwin-dubili' else 4
                parts=[p for p in scene.metadata['cooling']['parts'] if p['kind']=='case_fan']
                self.assertEqual(len(parts),expected)
                for part in parts:
                    meshes=[m for m in scene.meshes if m.part_id==part['id']]
                    self.assertEqual(sum(m.name=='case-fan-frame' for m in meshes),1)
                    self.assertEqual(sum(m.rotor for m in meshes),1)
                    self.assertEqual(sum(m.name=='case-fan-power-connector' for m in meshes),1)

    def test_actual_board_psu_front_and_bottom_fans_have_no_structure_material_witness(self):
        import test_case_layout_hosts052 as material
        for key,(_,scene) in self.rows.items():
            structures=[m for m in scene.meshes if m.component in ('case','panel')]
            targets=[m for m in scene.meshes if m.component in ('cpu','gpu','memory','psu','fans','cooler')
                     or m.name=='motherboard-reference']
            self.assertTrue(targets);self.assertTrue(structures)
            for target in targets:
                for structure in structures:
                    self.assertIsNone(material._positive_overlap(self.shape(target),self.shape(structure)),
                        (key,target.part_id,target.name,structure.part_id,structure.name))


if __name__=='__main__':unittest.main()
