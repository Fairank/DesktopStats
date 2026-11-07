"""Mechanical/motion contracts for the explicit cooling reference builder."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_cooling import add_cooling
from cooling_catalog import choices_coolers,choices_fans,get_cooler,get_fan


ANCHORS={'cpu':{'position':(-35.,35.,10.),'normal':(-1.,0.,0.),'up':(0.,1.,0.)},
         'case_dimensions':(600.,800.,800.)}


def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _dot(a,b):return sum(a[i]*b[i] for i in range(3))
def _sub(a,b):return tuple(a[i]-b[i] for i in range(3))


def _hit(vertices,origin,direction):
    for i in range(0,len(vertices),18):
        a,b,c=(vertices[i+k:i+k+3] for k in (0,6,12))
        e1,e2=_sub(b,a),_sub(c,a);h=_cross(direction,e2);det=_dot(e1,h)
        if abs(det)<1e-9:continue
        inv=1/det;s=_sub(origin,a);u=inv*_dot(s,h)
        if not 0<=u<=1:continue
        q=_cross(s,e1);v=inv*_dot(direction,q)
        if v<0 or u+v>1:continue
        if inv*_dot(e2,q)>1e-7:return True
    return False


class CoolingCatalogTests(unittest.TestCase):
    def test_sources_and_dimensions_are_explicit(self):
        self.assertEqual(len(choices_coolers()),66)
        self.assertEqual(len(choices_fans()),70)
        self.assertEqual({get_fan(c['id'])['size_mm'] for c in choices_fans()},{80,92,120,135,140,160,180,200})
        for choice in choices_coolers():
            row=get_cooler(choice['id']);self.assertTrue(row['sources']);self.assertEqual(row['reviewed'],'2026-11-07')
            self.assertTrue(row['brand']);self.assertTrue(row['series'])
            self.assertTrue(all(url.startswith('https://') for url in row['sources']))
        self.assertEqual(get_cooler('noctua-nh-d15')['dimensions_mm']['height'],165)
        self.assertEqual(get_cooler('noctua-nh-d15-g2')['dimensions_mm']['height'],168)
        self.assertFalse(get_cooler('amd-wraith-stealth')['dimensions_verified'])
        self.assertTrue(get_cooler('intel-laminar-rm1')['envelope_is_upper_bound'])
        self.assertFalse(get_fan('lian-li-lancool-216-160')['dimensions_verified'])
        self.assertFalse(get_fan('lian-li-lancool-216-160')['outer_ring'])
        self.assertFalse(get_cooler('custom-loop-360-reference')['gpu_block'])

    def test_getters_are_detached_and_invalid_ids_are_empty(self):
        row=get_cooler('noctua-nh-d15');row['sources'].clear();row['dimensions_mm']['height']=1
        self.assertEqual(get_cooler('noctua-nh-d15')['dimensions_mm']['height'],165)
        self.assertTrue(get_cooler('noctua-nh-d15')['sources'])
        self.assertEqual(get_cooler([]),{});self.assertEqual(get_fan('unknown'),{})
        row=get_fan('arctic-p12-pwm');row['sources'].clear();self.assertTrue(get_fan(row['id'])['sources'])


class CoolingGeometryTests(unittest.TestCase):
    def test_default_unknown_never_invents_parts(self):
        for spec in ({},None,{'cooling':{}},{'cooling':{'cpu_cooler':'none'}}):
            meshes,meta=add_cooling((),spec,anchors=ANCHORS)
            self.assertEqual(meshes,());self.assertEqual(meta['parts'],[]);self.assertFalse(meta['cpu_fan_tach_usable'])
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'not-real'}})
        self.assertEqual(meshes,());self.assertEqual(meta['rejected'][0]['reason'],'unknown_model')

    def test_no_io_workers_or_input_mutation(self):
        spec={'cooling':{'cpu_cooler':'arctic-liquid-freezer-iii-360','case_fans':[{'model':'arctic-p12-pwm','mount':'side','count':3}]}}
        original=copy.deepcopy((spec,ANCHORS))
        with patch('subprocess.Popen',side_effect=AssertionError('no process')),patch('threading.Thread.start',side_effect=AssertionError('no thread')),patch('builtins.open',side_effect=AssertionError('no file IO')):
            meshes,meta=add_cooling((),spec,anchors=ANCHORS)
        self.assertTrue(meshes);self.assertEqual((spec,ANCHORS),original);self.assertEqual(meta['new_pollers'],0)

    def test_all_catalog_models_all_levels_are_finite_normalized_bounded(self):
        for level in ('eco','balanced','close'):
            for choice in choices_coolers():
                with self.subTest(level=level,model=choice['id']):
                    meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':choice['id']}},level,ANCHORS)
                    self.assertTrue(meshes);self.assertFalse(meta['rejected']);self.assertLess(meta['triangle_count'],30000)
                    self._validate_meshes(meshes)
            for choice in choices_fans():
                with self.subTest(level=level,fan=choice['id']):
                    meshes,meta=add_cooling((),{'cooling':{'case_fans':[{'model':choice['id'],'mount':'front','count':1}]}},level,ANCHORS)
                    self.assertTrue(meshes);self.assertLess(meta['triangle_count'],6000);self._validate_meshes(meshes)

    def _validate_meshes(self,meshes):
        for mesh in meshes:
            self.assertIn(mesh.component,('cooler','fans'));self.assertTrue(mesh.part_id.startswith(mesh.component+':'))
            self.assertEqual(len(mesh.vertices)%18,0);self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
            for i in range(0,len(mesh.vertices),6):
                self.assertTrue(all(abs(mesh.vertices[i+k])<1500 for k in range(3)))
                self.assertAlmostEqual(sum(mesh.vertices[i+k]**2 for k in (3,4,5)),1,places=5)
            if mesh.rotor:self.assertIn('leaves-hub',mesh.name)

    def test_actual_frames_have_open_central_apertures(self):
        spec={'cooling':{'case_fans':[{'model':'arctic-p12-pwm','mount':'front','count':1}]}}
        meshes,meta=add_cooling((),spec,anchors=ANCHORS)
        fan=meta['fans'][0];center=fan['position'];axis=fan['axis']
        origin=tuple(center[i]+axis[i]*100 for i in range(3));direction=tuple(-v for v in axis)
        frames=[m for m in meshes if m.name=='case-fan-frame']
        self.assertEqual(len(frames),1);self.assertFalse(_hit(frames[0].vertices,origin,direction))
        self.assertTrue(_hit(frames[0].vertices,(center[0]+56,center[1]+45,origin[2]),direction))

    def test_mount_direction_axes_and_stators_remain_separate(self):
        for mount,normal in {'front':(0,0,1),'rear':(0,0,-1),'top':(0,1,0),'bottom':(0,-1,0),'side':(1,0,0)}.items():
            for direction,sign in (('intake',1),('exhaust',-1)):
                meshes,meta=add_cooling((),{'cooling':{'case_fans':[{'model':'arctic-p12-pwm','mount':mount,'count':1,'direction':direction}]}},anchors=ANCHORS)
                rotor=[m for m in meshes if m.rotor];self.assertEqual(len(rotor),1)
                self.assertEqual(rotor[0].axis,tuple(v*sign for v in normal));self.assertEqual(meta['fans'][0]['rpm'],None)
                self.assertTrue(any('stator' in m.name and not m.rotor for m in meshes))
                self.assertTrue(all(not m.rotor for m in meshes if 'frame' in m.name or 'pads' in m.name))

    def test_case_known_mount_limits_and_no_silent_truncation(self):
        anchors=copy.deepcopy(ANCHORS);anchors['case']={'fan_mounts':[{'position':'front','count':2,'size_mm':[120]}]}
        for model,count in (('noctua-nf-a14-pwm',1),('arctic-p12-pwm',3),('arctic-p12-pwm',True),('arctic-p12-pwm',0)):
            meshes,meta=add_cooling((),{'cooling':{'case_fans':[{'model':model,'mount':'front','count':count}]}},anchors=anchors)
            self.assertEqual(meshes,());self.assertTrue(meta['rejected'])
        meshes,meta=add_cooling((),{'cooling':{'case_fans':[{'model':'arctic-p12-pwm','mount':'front','count':2}]}},anchors=anchors)
        self.assertEqual(len(meta['fans']),2);self.assertEqual(len({f['part_id'] for f in meta['fans']}),2)

    def test_reference_preset_counts_no_duplicate_radiator_mount(self):
        spec={'cooling':{'cpu_cooler':'arctic-liquid-freezer-iii-360','radiator_mount':'top','case_fans':[
            {'model':'arctic-p12-pwm','mount':'side','count':3},{'model':'arctic-p12-pwm','mount':'bottom','count':3},
            {'model':'arctic-p12-pwm','mount':'rear','count':1},{'model':'arctic-p12-pwm','mount':'top','count':3}]}}
        meshes,meta=add_cooling((),spec,anchors=ANCHORS)
        self.assertEqual(sum(f['role']=='case' for f in meta['fans']),7)
        self.assertEqual(sum(f['role']=='radiator' for f in meta['fans']),3)
        self.assertEqual(sum(f['role']=='vrm_independent' for f in meta['fans']),1)
        self.assertEqual(meta['rejected'][0]['reason'],'radiator_occupies_mount')
        self.assertLess(meta['triangle_count'],45000)
        self.assertFalse(meta['cpu_fan_tach_usable']);self.assertEqual(meta['real_cpu_rotor_parts'],[])

    def test_sensor_semantics_air_header_not_aio_pump_or_vrm(self):
        for choice in choices_coolers():
            _,meta=add_cooling((),{'cooling':{'cpu_cooler':choice['id']}},anchors=ANCHORS)
            passive=choice['kind']=='passive_tower'
            air=choice['kind'] not in ('aio','custom_loop','passive_tower')
            self.assertEqual(meta['cpu_fan_tach_usable'],air)
            main=[fan for fan in meta['fans'] if fan['role']=='cpu_main']
            reviewed=bool(main) and all(fan.get('blade_geometry_reviewed') for fan in main)
            self.assertEqual(meta['real_cpu_rotor_parts'],['cooler:cpu'] if air and reviewed else [])
            self.assertIn('Passive' if passive else 'representative' if air else 'pump',meta['fan_tach_mapping'])

    def test_posed_cpu_normal_is_used_exactly_once(self):
        anchors=copy.deepcopy(ANCHORS);anchors['cpu']={'position':(50,40,30),'normal':(0,1,0),'up':(0,0,1)}
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'noctua-nh-l9i-17xx'}},anchors=anchors)
        fan=next(m for m in meshes if m.rotor);self.assertEqual(fan.axis,(0.,1.,0.))
        self.assertGreater(fan.position[1],40);self.assertAlmostEqual(fan.position[0],50);self.assertAlmostEqual(fan.position[2],30)

    def test_custom_loop_has_real_categories_and_no_gpu_block(self):
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'custom-loop-360-reference'}},anchors=ANCHORS)
        self.assertEqual({p['kind'] for p in meta['parts']},{'radiator','radiator_fan','pump_reservoir','cpu_waterblock'})
        self.assertTrue(any('liquid-tubes' in m.name for m in meshes));self.assertTrue(any('d5-pump' in m.name for m in meshes))
        self.assertFalse(any(m.component=='gpu' or 'gpu-block' in m.name for m in meshes))

    def test_reservoir_glass_and_fluid_remain_transparent_across_styles(self):
        from assembly_style import apply_model_styles
        from top_bar_config import HARDWARE_ICON_STYLES
        meshes,_=add_cooling((),{'cooling':{'cpu_cooler':'custom-loop-360-reference'}},anchors=ANCHORS)
        expected={'cooler-reservoir-shell':.22,'cooler-reservoir-fluid-core':.55,
                  'cooler-reservoir-caps':1.,'cooler-d5-pump':1.,'cooler-reservoir-clamps':1.}
        for entry in HARDWARE_ICON_STYLES:
            style=entry[0] if isinstance(entry,(tuple,list)) else entry
            styled,_=apply_model_styles(meshes,style,{},ANCHORS['case_dimensions'],{})
            actual={m.name:m.color[3] for m in styled if m.name in expected}
            self.assertEqual(actual,expected,style)

    def test_explicit_gpu_block_replaces_only_on_success_with_two_distinct_radiators(self):
        anchors=copy.deepcopy(ANCHORS);anchors['gpu']={'pcb':dict(position=(-40,-50,20),width_mm=140,length_mm=300,normal=(0,-1,0),up=(1,0,0))}
        spec={'cooling':{'cpu_cooler':'custom-loop-360-reference','gpu_waterblock':True,'case_fans':[dict(model='arctic-p12-pwm',mount='side',count=3)]}}
        meshes,meta=add_cooling((),spec,anchors=anchors)
        self.assertTrue(meta['replace_gpu_cooler']);self.assertEqual(meta['secondary_radiator_mount'],'side')
        self.assertEqual(sum(p['kind']=='radiator' for p in meta['parts']),2)
        block=[m for m in meshes if m.part_id=='gpu:waterblock'];self.assertTrue(block)
        self.assertTrue(all(m.component=='gpu' and not m.rotor for m in block))
        self.assertTrue(any(m.color[3]<1 for m in block));self.assertEqual(meta['rejected'][0]['reason'],'radiator_occupies_mount')
        spec['cooling']['radiator_mount']='side';_,meta=add_cooling((),spec,anchors=anchors)
        self.assertTrue(meta['replace_gpu_cooler']);self.assertEqual(meta['secondary_radiator_mount'],'top')
        _,meta=add_cooling((),spec,anchors=ANCHORS)
        self.assertFalse(meta['replace_gpu_cooler']);self.assertTrue(any('original GPU cooler retained' in w for w in meta['warnings']))

    def test_attached_power_wires_avoid_invented_argb_or_controller(self):
        spec={'cooling':{'cpu_cooler':'noctua-nh-u12a','case_fans':[dict(model='arctic-p12-pwm',mount='front',count=2)]}}
        meshes,meta=add_cooling((),spec,anchors=ANCHORS)
        self.assertEqual(len(meta['wire_anchors']),4)
        self.assertTrue(all(a['kind']=='fan4' and a['header']=='fan' and a['connector_rendered'] for a in meta['wire_anchors']))
        self.assertTrue(all(a['position_verified'] is False for a in meta['wire_anchors']))
        self.assertTrue(all(any(m.part_id==a['owner'] and 'power-connector' in m.name for m in meshes) for a in meta['wire_anchors']))

    def test_lfiii_primary_crown_replaces_generic40mm_axial_reference(self):
        row=get_cooler('arctic-liquid-freezer-iii-360')
        self.assertEqual(row['pump_reference_mm'],dict(width=91,height=68.5,depth=108.5))
        self.assertEqual(row['vrm_fan_diameter_mm'],60)
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':row['id']}},anchors=ANCHORS)
        crown=[m for m in meshes if m.name=='cooler-lfiii-static-radial-crown'];self.assertEqual(len(crown),1)
        self.assertFalse(crown[0].rotor)
        self.assertTrue(any(m.name=='cooler-lfiii-twin-hose-elbows' and not m.rotor for m in meshes))
        self.assertTrue(any(m.name=='cooler-lfiii-undercut-cheeks' for m in meshes))
        vrm=next(f for f in meta['fans'] if f['role']=='vrm_independent')
        self.assertEqual(vrm['diameter_mm'],60);self.assertFalse(vrm['blade_count_verified'])
        self.assertFalse(meta['cpu_fan_tach_usable']);self.assertEqual(meta['real_cpu_rotor_parts'],[])

    def test_rear_fan_lead_can_exit_glass_side_without_moving_verified_fan(self):
        for mount in ('rear','bottom'):
            spec={'cooling':{'case_fans':[dict(model='arctic-p12-pwm',mount=mount,count=1,direction='exhaust')]}}
            meshes,meta=add_cooling((),spec,anchors=ANCHORS)
            self.assertEqual(meta['fans'][0]['position'][0],0)
            anchor=meta['wire_anchors'][0]
            self.assertLess(anchor['position'][0],-60)
            self.assertEqual(anchor['normal'],(-1.,0.,0.))
            self.assertFalse(anchor['position_verified'])
            self.assertTrue(any(m.rotor and m.position==meta['fans'][0]['position'] for m in meshes))

    def test_source_side_mount_uses_outward_face_and_inward_actual_thickness(self):
        anchors=copy.deepcopy(ANCHORS);anchors['case_dimensions']=(320,470,470)
        anchors['case_mount_planes']={'side':dict(position=(108.8,0,108.1),normal=(1,0,0),up=(0,1,0),source='official-manual-reference',method='observed_proportions')}
        meshes,meta=add_cooling((),{'cooling':{'case_fans':[dict(model='arctic-p12-pwm',mount='side',count=3)]}},anchors=anchors)
        frames=[m for m in meshes if m.name=='case-fan-frame'];self.assertEqual(len(frames),3)
        self.assertAlmostEqual(max(v+m.position[0] for m in frames for v in m.vertices[0::6]),108.8)
        self.assertAlmostEqual(min(v+m.position[0] for m in frames for v in m.vertices[0::6]),83.8)
        self.assertFalse(meta['mount_plane_sources']['side']['dimensions_verified'])
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'arctic-liquid-freezer-iii-360','radiator_mount':'side'}},anchors=anchors)
        rails=[m for m in meshes if m.name=='cooler-radiator044-folded-rails']
        self.assertAlmostEqual(max(v+m.position[0] for m in rails for v in m.vertices[0::6]),108.8)
        self.assertTrue(all(f['position'][0]<108.8-38 for f in meta['fans'] if f['role']=='radiator'))

    def test_known_raised_deck_moves_reference_reservoir_without_scaling(self):
        anchors=copy.deepcopy(ANCHORS);anchors['case_dimensions']=(320,470,470)
        anchors['case_floor_deck']=dict(position=(-61.5,-190,0),normal=(0,1,0),thickness_mm=2)
        spec={'cooling':{'cpu_cooler':'custom-loop-360-reference'}}
        meshes,meta=add_cooling((),spec,anchors=anchors)
        pump=[m for m in meshes if m.name=='cooler-d5-pump']
        self.assertEqual(len(pump),1)
        lower=min(pump[0].vertices[1::6])+pump[0].position[1]
        self.assertAlmostEqual(lower,-187.)
        self.assertEqual(meta['cooler']['reservoir_mm']['height'],200)

    def test_new_family_envelopes_and_unknown_bundled_fans_are_not_substituted(self):
        from assembly_cooling import _reference_fan
        self.assertEqual(get_cooler('thermalright-axp90-x47-full')['dimensions_mm'],dict(width=95,height=47,depth=94.5))
        self.assertFalse(get_cooler('thermalright-assassinx120-refined-se')['dimensions_verified'])
        self.assertEqual(get_cooler('idcooling-is55-argb')['dimensions_mm']['height'],55)
        self.assertEqual(get_cooler('coolermaster-ma824-stealth')['fan_sizes'],[120,135])
        self.assertEqual(get_cooler('enermax-aquafusion-adv360')['pump_reference_mm'],dict(width=69.5,height=54.5,depth=68.5))
        x360=get_cooler('gigabyte-aorus-waterforce-x360');fan=_reference_fan(x360)
        self.assertIsNone(x360['fan_model']);self.assertNotEqual(fan['id'],'gigabyte-aorus120-argb')
        self.assertFalse(fan['dimensions_verified']);self.assertFalse(fan['blade_count_verified'])
        self.assertFalse(fan.get('blade_geometry_reviewed',False))
        self.assertGreaterEqual(len({get_cooler(c['id'])['brand'] for c in choices_coolers()}),16)

    def test_new_fan_thickness_is_physical_and_unknown_rpm_is_static(self):
        expected={'thermalright-tl9015r':15,'idcooling-is55-argb-bundled12015':15,
                  'msi-meg-silent-gale-p12':27.5,'phanteks-d30-120-regular':30,
                  'phanteks-t30-120':30,'enermax-squa-rgb-adv120':26}
        for model,depth in expected.items():
            meshes,meta=add_cooling((),{'cooling':{'case_fans':[dict(model=model,mount='front',count=1)]}},anchors=ANCHORS)
            frame=next(m for m in meshes if m.name=='case-fan-frame');axis=meta['fans'][0]['axis']
            coords=[sum(frame.vertices[i+k]*axis[k] for k in range(3)) for i in range(0,len(frame.vertices),6)]
            self.assertAlmostEqual(max(coords)-min(coords),depth,places=6, msg=model)
            self.assertIsNone(meta['fans'][0]['rpm']);self.assertEqual(meta['fans'][0]['rotation_default'],'static')
            self.assertFalse(meta['fans'][0]['rotation_direction_verified'])
            self.assertTrue(all(not m.rotor for m in meshes if 'frame' in m.name or 'stator' in m.name or 'interlock' in m.name))

    def test_mobius_joining_ring_stays_planar_and_rotates_with_leaves(self):
        from assembly_cooling import _leaf_geometry
        from assembly_geometry import ring
        fan=get_fan('coolermaster-mobius120');radius=fan['size_mm']*.465;depth=4.5
        vertices=_leaf_geometry(fan,radius,depth);annulus=ring(radius*.994,radius*.968,depth,40)
        self.assertEqual(vertices[-len(annulus):],annulus)
        self.assertEqual(set(round(z,4) for z in annulus[2::6]),{-depth/2,depth/2})
        meshes,_=add_cooling((),{'cooling':{'case_fans':[dict(model=fan['id'],mount='front',count=1)]}},anchors=ANCHORS)
        self.assertEqual(sum(m.rotor for m in meshes),1)
        self.assertFalse(any('joining-ring' in m.name and not m.rotor for m in meshes))

    def test_cambered_foil_caps_have_continuous_normals_and_hard_side_walls(self):
        from assembly_cooling import _cambered_leaves
        from assembly_geometry import fan_rotor
        model=get_fan('thermalright-tlc12c');raw=fan_rotor(model,55,4)
        foil=_cambered_leaves(raw,model,55);self.assertEqual(len(foil),len(raw))
        shared={};duplicates=0;hard_sides=0
        for i in range(0,len(raw),6):
            self.assertEqual(foil[i:i+2],raw[i:i+2])
            normal=foil[i+3:i+6];self.assertAlmostEqual(sum(v*v for v in normal),1,places=6)
            if abs(raw[i+5])>.9:
                point=foil[i:i+3]
                if point in shared:
                    self.assertEqual(normal,shared[point]);duplicates+=1
                shared[point]=normal
                self.assertGreater(normal[2]*raw[i+5],0)
            elif abs(normal[2])<.1:hard_sides+=1
        self.assertGreater(duplicates,20);self.assertGreater(hard_sides,20)

    def test_mixed_size_tower_preserves_fan_thickness_and_stays_below_documented_height(self):
        anchors={'cpu':dict(position=(0,0,0),normal=(0,1,0),up=(0,0,1)),'case_dimensions':(600,800,800)}
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'coolermaster-ma824-stealth'}},anchors=anchors)
        self.assertEqual([f['diameter_mm'] for f in meta['fans']],[120,135])
        frames=[m for m in meshes if m.name=='cooler-tower-fan-frame'];self.assertEqual(len(frames),1)
        # Both batched physical frames, not two artificially resized copies.
        self.assertLessEqual(max(frames[0].vertices[1::6]),165.6+.001)
        self.assertEqual(meta['real_cpu_rotor_parts'],[])
        self.assertTrue(meta['fans'][0]['blade_geometry_reviewed']);self.assertFalse(meta['fans'][1]['blade_count_verified'])
        self.assertTrue(any('reference geometry' in s for s in meta['warnings']))

    def test_new_pump_architectures_have_observed_caps_and_truthful_internal_fans(self):
        cases={'gigabyte-aorus-waterforce-x360':'cooler-blank-circular-lcd',
               'msi-meg-coreliquid-s360':'cooler-blank-ips-lcd',
               'asus-tuf-lc240-argb':'cooler-faceted-blank-cover',
               'phanteks-glacier-one360d30':'cooler-bridge-fine-stripes',
               'idcooling-frostflow-x240':'cooler-pump-white-light-ring',
               'enermax-aquafusion-adv360':'cooler-square-mirror-outlines'}
        for model,name in cases.items():
            meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':model}},anchors=ANCHORS)
            self.assertTrue(any(m.name==name for m in meshes),model)
            self.assertFalse(meta['cpu_fan_tach_usable']);self.assertEqual(meta['real_cpu_rotor_parts'],[])
            if model=='msi-meg-coreliquid-s360':
                self.assertEqual(meta['known_unplaced_vrm_fans'],1)
                self.assertEqual(get_cooler(model)['vrm_fan_diameter_mm'],60)
                self.assertFalse(any(f['role']=='vrm_independent' for f in meta['fans']))
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'msi-mag-coreliquid240r-v2'}},anchors=ANCHORS)
        self.assertTrue(any(m.name=='cooler-radiator-integrated-pump' and m.part_id=='cooler:radiator' for m in meshes))
        self.assertEqual(next(p['kind'] for p in meta['parts'] if p['id']=='cooler:pump'),'aio_cpu_block')

    def test_rgb12v_is_not_wired_to_argb5v_and_square_frame_stays_static(self):
        meshes,meta=add_cooling((),{'cooling':{'case_fans':[dict(model='coolermaster-sickleflow120-rgb',mount='front',count=1)]}},anchors=ANCHORS)
        self.assertEqual({a['kind'] for a in meta['wire_anchors']},{'fan4'})
        self.assertFalse(any('argb' in m.name for m in meshes))
        meshes,meta=add_cooling((),{'cooling':{'case_fans':[dict(model='phanteks-d30-120-regular',mount='front',count=1)]}},anchors=ANCHORS)
        self.assertEqual({a['kind'] for a in meta['wire_anchors']},{'fan4','argb3'})
        self.assertTrue(any(m.name=='case-fan-square-rgb-rim' and not m.rotor for m in meshes))
        self.assertTrue(any(m.name=='case-fan-interlock-cover' and not m.rotor for m in meshes))

    def test_new_aio_rejects_known_wrong_mount_without_shrinking_or_guessing_fan(self):
        anchors=copy.deepcopy(ANCHORS);anchors['case']={'fan_mounts':[dict(position='top',size_mm=[140],count=2)]}
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'gigabyte-aorus-waterforce-x360'}},anchors=anchors)
        self.assertEqual(meshes,());self.assertEqual(meta['rejected'][0]['reason'],'unsupported_radiator_mount')
        anchors['case_dimensions']=(200,200,200);anchors['case']={}
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'phanteks-glacier-one360d30'}},anchors=anchors)
        self.assertEqual(meshes,());self.assertEqual(meta['rejected'][0]['reason'],'radiator_exceeds_mount_plane')


if __name__=='__main__':unittest.main()
